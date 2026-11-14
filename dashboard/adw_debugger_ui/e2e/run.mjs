// Browser acceptance run for the ADW debugger, in Chrome, against real pilot runs.
//
//   E2E_BASE=http://127.0.0.1:8795/ E2E_STALL_TIMEOUT=4 node e2e/run.mjs [scenario ...]
//
// Every scenario starts the real adw_debug_pilot.py, which writes to the real
// sssf.db; the page under test reads it back through the feed. Nothing is mocked.
import { spawn, execFileSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import puppeteer from 'puppeteer-core'

const BASE = process.env.E2E_BASE ?? 'http://127.0.0.1:8795/'
const AGENT_BLOCKS = process.env.E2E_AGENT_BLOCKS ?? `${process.env.HOME}/agent_blocks`
const PYTHON = process.env.E2E_PYTHON ?? `${AGENT_BLOCKS}/lancedb_memory/.venv/bin/python`
const CHROME = process.env.E2E_CHROME ?? '/usr/bin/google-chrome'
const DB = process.env.E2E_DB ?? `${AGENT_BLOCKS}/adws/adw_data/sssf.db`
const STALL = Number(process.env.E2E_STALL_TIMEOUT ?? 4)
const SHOTS = process.env.E2E_SHOTS ?? '/tmp/adw-debugger-e2e'
const TAB = process.env.E2E_TERMINAL_TAB ?? ''          // selector to click first, on the real dashboard

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
const results = []
const pageErrors = []
const history = []            // what the page showed, each time it changed; printed when a scenario fails
let page

function pilot(id, ...args) {
  const child = spawn(PYTHON, ['adws/adw_debug_pilot.py', '--adw-id', id, ...args], { cwd: AGENT_BLOCKS, stdio: 'ignore' })
  return new Promise(resolve => child.on('exit', code => resolve(code)))
}

function rowCount(runId) {
  const sql = `import sqlite3;print(sqlite3.connect('file:${DB}?mode=ro',uri=True).execute("select count(*) from events where adw_id=?",('${runId}',)).fetchone()[0])`
  return Number(execFileSync('python3', ['-c', sql]).toString().trim())
}

const snapshot = () => page.evaluate(() => {
  const text = selector => document.querySelector(selector)?.textContent?.trim() ?? ''
  const boxes = edge => [...document.querySelectorAll(`#adw-debugger-root .sd-box[data-edge="${edge}"]`)].map(box => ({
    instance: box.dataset.instance, status: box.dataset.status, selected: box.classList.contains('sd-selected'),
    background: getComputedStyle(box).backgroundColor, text: box.textContent.replace(/\s+/g, ' ').trim() }))
  return {
    run: text('[data-field="run"]').replace('run ', ''), status: text('[data-field="status"]'), mode: text('[data-field="mode"]'),
    top: boxes('top'), bottom: boxes('bottom'),
    labels: [...document.querySelectorAll('#adw-debugger-root .sd-label')].map(label => label.textContent),
    lines: [...document.querySelectorAll('#adw-debugger-root .adwdbg-log-line')].map(line => ({ run: line.dataset.run, kind: line.dataset.kind, text: line.textContent })),
    logLabel: text('.adwdbg-log-label'), timing: text('[data-field="timing"]'),
    warning: document.querySelector('[data-warning]')?.dataset.warning ?? '',
    clearLabel: text('[data-action="clear-run"]'),
    legacyVisible: getComputedStyle(document.getElementById('terminal-stream')).display !== 'none',
    pwned: window.pwned !== undefined, scripts: document.querySelectorAll('#adw-debugger-root script').length,
  }
})

async function until(description, predicate, timeoutMs = 30000) {
  const start = Date.now()
  let last
  while (Date.now() - start < timeoutMs) {
    last = await snapshot()
    const seen = `${last.run} ${last.status} ${last.mode} [${last.top.map(entry => `${entry.instance.split(':')[1] ?? entry.instance}=${entry.status}`).join(' ')}] ${last.warning}`
    if (seen !== history.at(-1)?.seen) history.push({ at: new Date().toISOString().slice(11, 23), seen })
    if (predicate(last)) return last
    await sleep(100)
  }
  throw new Error(`timed out waiting for: ${description}\n${JSON.stringify({ ...last, lines: last?.lines.length, labels: last?.labels.length })}`)
}

function check(condition, message) {
  if (!condition) throw new Error(`check failed: ${message}`)
}

const click = action => page.click(`[data-action="${action}"]`)
const box = (state, key) => state.top.find(entry => entry.instance.endsWith(`:${key}`))
const id = prefix => `${prefix}${Date.now().toString(36).slice(-6)}`
const COLOURS = { waiting: 'rgb(158, 158, 158)', running: 'rgb(255, 213, 79)', stalled: 'rgb(255, 152, 0)', fail: 'rgb(211, 47, 47)', pass: 'rgb(46, 125, 50)' }

const scenarios = {
  async placement() {
    const above = await page.evaluate(() => {
      const root = document.getElementById('adw-debugger-root')
      const stream = document.getElementById('terminal-stream')
      return !!root && !!(root.compareDocumentPosition(stream) & Node.DOCUMENT_POSITION_FOLLOWING)
        && root.getBoundingClientRect().top < stream.getBoundingClientRect().top
    })
    check(above, 'the debugger is mounted above the existing terminal stream')
    return 'mounted above #terminal-stream'
  },

  async success() {
    const run = id('ok')
    const done = pilot(run, '--pace', '1.5', '--torture')
    let state = await until('the new run is followed live with waiting columns', s => s.run === run && s.mode === 'Live' && s.top.length >= 4)
    check(state.top.some(entry => entry.status === 'waiting' && entry.background === COLOURS.waiting), 'a real waiting instance is gray')
    state = await until('lookup-2 is running', s => box(s, 'lookup-2')?.status === 'running')
    check(box(state, 'lookup-2').background === COLOURS.running, 'running is yellow')
    check(JSON.stringify(state.top.map(e => [e.instance, e.status, e.background])) === JSON.stringify(state.bottom.map(e => [e.instance, e.status, e.background])), 'upper and lower boxes match')
    check(!box(state, 'prepare'), 'a completed column was replaced by the next active set')
    check(state.top.filter(entry => entry.text.startsWith('lookup')).length >= 1 && box(state, 'lookup-2').instance !== `${run}:lookup-1`, 'same-named phases keep separate identities')
    await page.click(`.sd-box[data-edge="bottom"][data-instance="${run}:lookup-2"]`)
    state = await until('the terminal is filtered to lookup-2', s => !s.legacyVisible && s.logLabel.includes(`${run}:lookup-2`))
    check(box(state, 'lookup-2').selected && state.bottom.find(e => e.instance === `${run}:lookup-2`).selected, 'both boxes show the selection outline')
    check(state.lines.length > 0 && state.lines.every(line => line.run === run), 'only the selected run in the filtered terminal')
    const before = state.lines.length
    state = await until('incoming logs for the selected phase arrive, with the whole tool result', s => s.lines.length > before && s.lines.some(l => l.kind === 'tool_result'))
    const result = state.lines.find(line => line.kind === 'tool_result').text
    check(result.includes('<script>alert("x")</script>') && result.includes('\nend\n') && result.endsWith('tail') && result.includes('long '.repeat(60)), 'tool result text is complete in the terminal')
    check(!state.pwned && state.scripts === 0, 'recorded text was not interpreted as markup')
    check(state.lines.every(line => !['progress', 'waiting'].includes(line.kind)), 'no other phase leaked into the filter')
    await page.screenshot({ path: `${SHOTS}/success-filtered.png`, fullPage: true })
    await click('all-events')
    state = await until('All events restores the existing stream', s => s.legacyVisible && s.logLabel.endsWith('All events'))
    check((await done) === 0, 'the pilot exited 0')
    state = await until('the run completed and its last diagram stayed', s => s.status === 'success' && s.mode === 'Completed' && s.top.length > 0)
    check(box(state, 'report')?.status === 'pass' && box(state, 'report').background === COLOURS.pass, 'final snapshot shows pass in green')
    await page.screenshot({ path: `${SHOTS}/success-final.png`, fullPage: true })
    return `run ${run}; ${state.timing}`
  },

  async clear() {
    const first = id('clra'); const second = id('clrb')
    check((await pilot(first, '--pace', '0.2')) === 0, 'first run ok')
    await until('first run shown', s => s.run === first && s.status === 'success')
    check((await pilot(second, '--pace', '0.2')) === 0, 'second run ok')
    let state = await until('second run shown', s => s.run === second && s.status === 'success')
    const rows = rowCount(second)
    check(state.clearLabel === `Clear displayed logs for ${second}`, 'Clear names its run')
    check(state.lines.some(l => l.run === second) && state.lines.some(l => l.run === first), 'both runs in All events before Clear')
    await click('clear-run')
    state = await until('selected run cleared from the display', s => !s.lines.some(l => l.run === second))
    check(state.lines.some(l => l.run === first), 'the other run is still displayed')
    check(rowCount(second) === rows && rows > 0, `database rows untouched (${rows})`)
    check(state.top.length > 0, 'the diagram survived Clear')
    await page.click(`.sd-box[data-edge="top"][data-instance="${second}:report"]`)
    state = await until('phase filter on', s => !s.legacyVisible)
    check(state.lines.length === 0, 'filtering does not resurrect cleared lines')
    await page.reload({ waitUntil: 'domcontentloaded' }); await openTab()
    state = await until('reattached after reload', s => s.run === second && s.lines.length > 0)
    check(!state.lines.some(l => l.run === second), 'reconnecting does not resurrect cleared lines')
    return `runs ${first}, ${second}; ${rows} rows preserved`
  },

  async failure() {
    const bad = id('bad'); const next = id('nxt')
    check((await pilot(bad, '--pace', '0.4', '--fail-at', 'lookup-2')) === 1, 'the failing pilot exited 1')
    let state = await until('failed run pinned with a red phase', s => s.run === bad && s.mode === 'Pinned after failure' && box(s, 'lookup-2')?.status === 'fail')
    check(box(state, 'lookup-2').background === COLOURS.fail && state.bottom.find(e => e.instance === `${bad}:lookup-2`).background === COLOURS.fail, 'both boxes red')
    check(state.lines.some(l => l.run === bad && l.kind === 'cleanup' && l.text.includes(`${bad}_03_lookup`) === false && l.text.includes('cleanup ok')), 'cleanup evidence recorded despite the exception')
    check(state.lines.filter(l => l.run === bad && l.text.includes('never executed')).length === 2, 'the two phases that never ran say so')
    const done = pilot(next, '--pace', '2')
    await until('the later run is being received', s => s.lines.some(l => l.run === next))
    state = await snapshot()
    check(state.run === bad && state.mode === 'Pinned after failure' && box(state, 'lookup-2').status === 'fail', 'a later run did not replace the pinned failure')
    await page.screenshot({ path: `${SHOTS}/failure-pinned.png`, fullPage: true })
    await click('all-events')
    check((await snapshot()).run === bad, 'All events does not release the pin')
    await click('follow-live')
    state = await until('Follow live released the pin', s => s.run === next && s.mode === 'Live')
    await done
    return `failed run ${bad}; later run ${next}`
  },

  async concurrent() {
    const first = id('cona'); const second = id('conb')
    const a = pilot(first, '--pace', '1.2')
    await until('first run live', s => s.run === first && s.mode === 'Live')
    const b = pilot(second, '--pace', '1.2')
    await until('second run is being received', s => s.lines.some(l => l.run === second))
    for (let i = 0; i < 20; i += 1) {
      const state = await snapshot()
      if (state.status !== 'running') break
      check(state.run === first, 'the active selection was not stolen')
      check(state.top.every(entry => entry.instance.startsWith(`${first}:`) || entry.instance.startsWith(`${first}_`)), 'no column from the other run')
      await sleep(200)
    }
    await a
    const state = await until('view moved to the still-running second run', s => s.run === second)
    check(state.top.every(entry => entry.instance.startsWith(second)), 'identities did not mix after the switch')
    await b
    return `runs ${first} then ${second}`
  },

  async stall() {
    const run = id('stl')
    const done = pilot(run, '--pace', '0.5', '--stall-at', 'wait', '--stall-seconds', String(STALL + 5))
    const startWait = await until('wait phase running', s => s.run === run && box(s, 'wait')?.status === 'running', 20000)
    const t0 = Date.now()
    check(box(startWait, 'wait').background === COLOURS.running, 'yellow before the threshold')
    let state = await until('wait phase stalled', s => box(s, 'wait')?.status === 'stalled', (STALL + 4) * 1000)
    const took = (Date.now() - t0) / 1000
    check(took >= STALL - 1.2, `not stalled before the ${STALL}s threshold (took ${took.toFixed(1)}s)`)
    check(box(state, 'wait').background === COLOURS.stalled && /no progress for \d+s \(timeout \d+s\)/.test(box(state, 'wait').text), 'orange with elapsed time and reason')
    check(state.status === 'running' && state.mode === 'Live', 'a stall is a warning, not a failure')
    await page.screenshot({ path: `${SHOTS}/stalled.png`, fullPage: true })
    state = await until('progress recovers the phase', s => ['running', 'waiting', 'pass'].includes(box(s, 'wait')?.status ?? ''), 12000)
    check((await done) === 0, 'the stalled pilot still exited 0')
    await until('run passed', s => s.run === run && s.status === 'success')
    return `run ${run}; orange after ${took.toFixed(1)}s with a ${STALL}s timeout`
  },

  async kill() {
    const run = id('kil')
    check((await pilot(run, '--pace', '0.3', '--kill-at', 'lookup-1')) === 137, 'the pilot was killed mid-phase')
    const state = await until('interrupted run shown as uncertain', s => s.run === run && s.status === 'interrupted')
    const phase = box(state, 'lookup-1')
    check(phase.status === 'stalled' && phase.text.includes('no cleanup recorded'), 'the open phase is orange and says no cleanup was recorded')
    check(!state.lines.some(l => l.run === run && l.kind === 'cleanup' && l.text.includes('[' + run + ' lookup cleanup]')), 'no cleanup event was invented')
    check(!state.top.some(entry => entry.status === 'pass' && entry.instance.endsWith('lookup-1')), 'no success was invented')
    await page.screenshot({ path: `${SHOTS}/killed.png`, fullPage: true })
    return `run ${run}`
  },

  async latency() {
    const run = id('lat')
    const done = pilot(run, '--pace', '1')
    const delays = new Set()
    await until('run live', s => s.run === run && s.mode === 'Live')
    for (let finished = false; !finished;) {
      const state = await snapshot()
      const match = state.timing.match(/shown\s+(\d+) ms/)
      if (match) delays.add(Number(match[1]))
      finished = state.status !== 'running'
      await sleep(50)
    }
    await done
    const sorted = [...delays].sort((a, b) => a - b)
    check(sorted.length > 3, 'enough delay samples')
    return `run ${run}; record-to-screen delay over ${sorted.length} deliveries: min ${sorted[0]} ms, median ${sorted[Math.floor(sorted.length / 2)]} ms, max ${sorted.at(-1)} ms`
  },

  async regression() {
    if (!TAB) return 'skipped: only meaningful on the real dashboard'
    const before = pageErrors.length
    // The existing Clear is shared by every viewer (POST /api/terminal-clear), so it is
    // checked for presence and a live feed, not pressed.
    await page.waitForFunction(() => document.getElementById('terminal-status')?.textContent.startsWith('Connected'), { timeout: 30000 })
    check(await page.$eval('#terminal-clear', node => !node.disabled), 'the existing Clear button is present and enabled')
    check(await page.$eval('#terminal-stream', node => getComputedStyle(node).display !== 'none'), 'the existing stream is shown in All events')
    const visited = []
    for (const target of ['notes', 'all-monitors', 'status', 'terminal']) {
      // Some views swap the main nav for their own; step back out first when that happened.
      const back = await page.evaluateHandle(() => [...document.querySelectorAll('.back-tab')].find(node => node.offsetParent !== null) ?? null)
      if (back.asElement()) { await back.asElement().click(); await sleep(400) }
      await page.click(`[data-nav="main"][data-target="${target}"]`)
      await sleep(700)
      check(await page.$eval(`#${target}`, node => node.classList.contains('active')).catch(() => true), `the ${target} view opened`)
      visited.push(target)
    }
    check(await page.$eval('#terminal', node => node.classList.contains('active')), 'back on the Terminal view')
    const run = id('arw')
    const done = pilot(run, '--pace', '2')
    await until('a tool call arrow is on screen', s => s.run === run && s.labels.some(label => label.includes('catalog.get')), 20000)
    await page.screenshot({ path: `${SHOTS}/live-arrows.png` })
    await done
    check(pageErrors.length === before, `no page errors (${pageErrors.slice(before).join(' | ')})`)
    return `existing terminal feed connected; visited ${visited.join(', ')}; no page errors; arrows run ${run}`
  },

  async disconnect() {
    const run = id('net')
    const done = pilot(run, '--pace', '1.5')
    await until('run live', s => s.run === run && s.mode === 'Live')
    await page.setOfflineMode(true)
    let state = await until('connection warning shown', s => s.warning === 'connection', 15000)
    check(state.status === 'running' && state.mode === 'Live' && !state.top.some(entry => entry.status === 'fail'), 'a lost feed is not reported as an ADW failure')
    await page.screenshot({ path: `${SHOTS}/disconnected.png`, fullPage: true })
    await done
    await page.setOfflineMode(false)
    state = await until('reconnected and caught up', s => s.warning === '' && s.status === 'success', 20000)
    const kinds = state.lines.filter(l => l.run === run)
    check(kinds.length === rowCount(run), `no gap and no duplicate after reconnect (${kinds.length} lines, ${rowCount(run)} rows)`)
    return `run ${run}; ${kinds.length} events, none lost or repeated`
  },
}

async function openTab() {
  if (TAB) {
    await page.waitForFunction(() => !document.body.classList.contains('startup-loading'), { timeout: 60000 })
    await page.click(TAB)
  }
  await page.waitForSelector('#adw-debugger-root .adwdbg', { timeout: 20000 })
  await click('follow-live')
}

mkdirSync(SHOTS, { recursive: true })
const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox', '--window-size=1500,1300'], defaultViewport: { width: 1500, height: 1300 } })
page = await browser.newPage()
page.on('pageerror', error => { pageErrors.push(error.message); console.log('PAGE ERROR', error.message) })
await page.goto(BASE, { waitUntil: 'domcontentloaded' })      // the dashboard polls forever; it is never network-idle
await openTab()
const wanted = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(scenarios)
for (const name of wanted) {
  try {
    await click('follow-live'); await click('all-events').catch(() => {})
    const detail = await scenarios[name]()
    results.push([name, 'PASS', detail]); console.log(`PASS ${name} -- ${detail}`)
  } catch (error) {
    results.push([name, 'FAIL', error.message]); console.log(`FAIL ${name} -- ${error.message}`)
    console.log(history.slice(-14).map(entry => `   ${entry.at} ${entry.seen}`).join('\n'))
    await page.screenshot({ path: `${SHOTS}/FAIL-${name}.png`, fullPage: true }).catch(() => {})
  }
}
await browser.close()
console.log(`browser: ${CHROME}; base: ${BASE}; ${results.filter(r => r[1] === 'PASS').length}/${results.length} passed`)
process.exit(results.every(r => r[1] === 'PASS') ? 0 : 1)
