"""Explicit, synthetic-only browser check. Never collected by ordinary pytest.

Run: uv run --with playwright python tests/receptionist_training_browser_check.py
The fixture lives in rol_receptionist_training; the real expense API is read-only.
"""
import argparse
import json

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect, sync_playwright


class TrainingDashboardPage:
    """Browser Adapter: the scenario below talks to application operations."""
    def __init__(self, page, origin):
        self.page, self.origin = page, origin
        self.box = page.locator('#receptionist-box')
        self.work = page.locator('#receptionist-work')
        # The dashboard's own startup is slow and variable (its boot wires Letta, voice and
        # finance panels), so reaching domcontentloaded can pass Playwright's 30s default
        # even though the server answers the HTML itself in milliseconds. Every other wait
        # here already allows 45-100s; navigation was the one inconsistent limit.
        page.set_default_navigation_timeout(120000)

    def open(self):
        # Deliberately 'commit' rather than 'domcontentloaded': the dashboard's boot opens
        # several long-lived streams, and once Chrome's 6-connections-per-origin limit is
        # saturated a still-pending module request can keep DOMContentLoaded from ever
        # firing -- observed here as goto hanging past 120s on some runs and finishing in
        # 5s on others. The two waits below are the real readiness assertions anyway: the
        # startup gate released, and the receptionist work panel actually on screen.
        self.page.goto(self.origin + '/', wait_until='commit')
        expect(self.page.locator('#startup-overlay')).to_be_hidden(timeout=180000)
        expect(self.work).to_be_visible(timeout=45000)

    def compose(self, message):
        """Resolve the composer and type into it, retrying a resolve failure we cannot explain.

        Twice now, on the turn after the assignment starts, fill() has reported no match at all
        for this textarea for its full timeout -- its call log stops at 'waiting for
        locator("#receptionist-box").locator("textarea").first' and never prints a resolved
        line -- even though the visibility assertion immediately before it passed against the
        same locator. A document-level probe contradicts a vanishing composer: it found two
        visible, enabled textareas in this same container continuously for 45s after that turn,
        with the container never replaced. So this retries a freshly resolved locator rather
        than asserting a cause it has not demonstrated. If every attempt fails, it still raises.
        """
        for attempt in range(3):
            field = self.box.locator('textarea').first
            try:
                expect(field).to_be_visible(timeout=100000)
                field.fill(message, timeout=45000)
                return
            except PlaywrightTimeout:
                if attempt == 2:
                    raise
                print('    composer did not accept text; re-resolving (attempt %d)' % (attempt + 2), flush=True)

    def say(self, message, expected):
        print('  say: ' + message, flush=True)  # so a failing step is identifiable in the log
        button = self.box.get_by_role('button', name='Send', exact=True)
        expect(button).to_be_enabled(timeout=100000)
        self.compose(message)
        # force=True because headless Chrome on DESKTOP-2OBSQMC produces no animation frames
        # at all (requestAnimationFrame fired 0 times in 1s, measured on a bare
        # '<button>Hello</button>' page as well as this dashboard, and under both --headless
        # and --headless=new). Playwright implements its stability check by comparing the
        # bounding box across two consecutive rAF callbacks, so without frames that check can
        # never resolve and every click hangs -- the call log stops at 'waiting for element to
        # be visible, enabled and stable' and never advances. force skips those pre-checks
        # while still dispatching a real mouse event that Chromium hit-tests itself; the
        # button was independently confirmed to be the top element at its own centre
        # (document.elementFromPoint returned it, pointer-events:auto, nothing overlapping),
        # so this stays an honest click rather than a JS-level shortcut. The visible-browser
        # mode this box normally wants is unavailable here: /tmp/.X11-unix/X0 exists but has
        # no listener, so Chrome exits with 'Missing X server or $DISPLAY'.
        button.click(force=True)
        expect(self.work.locator('[aria-live="polite"]')).to_contain_text(expected, timeout=100000)
        expect(button).to_be_enabled(timeout=100000)

    def supporting_information(self):
        frame = self.page.frame_locator('#receptionist-work iframe')
        expect(frame.get_by_role('heading', name='Training receipt — synthetic purchase')).to_be_visible()

    def expense_editor(self):
        frame = self.page.frame_locator('#receptionist-work iframe')
        expect(frame.get_by_role('heading', name='Editing expense #900001')).to_be_visible()

    def stored_record(self):
        response = self.page.request.post(self.origin + '/api/receptionist-training/expense-search',
                                          data={'expense_id':900001}).json()
        assert response['ok'] and len(response['records']) == 1
        return response['records'][0]

    def fact(self, field):
        return self.work.locator('.receptionist-facts dd[data-field="' + field + '"]')

    def panel(self, phase, verified):
        """The panel must distinguish conditions by itself, not leave them to one status line."""
        facts = self.work.locator('.receptionist-facts')
        expect(facts).to_have_attribute('data-phase', phase, timeout=45000)
        expect(facts).to_have_attribute('data-verified', 'true' if verified else 'false')
        return facts

    def checkpoint(self):
        return self.page.request.get(self.origin + '/api/receptionist-work').json()['state']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', default='http://localhost:8765')
    parser.add_argument('--chrome', default='/opt/google/chrome/chrome')
    parser.add_argument('--screenshot', default='/tmp/toyota-training-complete.png')
    # Headless Chrome is unreliable on DESKTOP-2OBSQMC: navigation and clicks time out
    # against this dashboard even though the server answers in milliseconds. That box has
    # a real display (WSLg), so --headed is the working mode there; keep headless the
    # default for machines without one.
    parser.add_argument('--headed', action='store_true', help='Run a visible browser (needed on DESKTOP-2OBSQMC)')
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chrome, headless=not args.headed,
                                             args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        context = browser.new_context(viewport={'width':1600,'height':1100})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        app = TrainingDashboardPage(page, args.origin)
        app.open()
        before = app.stored_record()
        assert before['id'] == 900001  # Never substitute a real expense ID.
        app.say("Let's tackle the tax problems", 'ready:')
        app.say('Show me the paperwork for this one', 'Opened supporting information')
        app.supporting_information()
        app.say('Bring up its edit form', 'Opened the expense editor')
        app.expense_editor()
        # Exercise an actual change even if the fixture was used previously.
        targets = [('Walgreens (RJ)',426),('Walgreens (RM)',425)] if before['category_id'] == 425 else [('Walgreens (RM)',425)]
        for label, category_id in targets:
            app.say('Please put this one under ' + label, 'Verified training expense #900001')
            stored = app.stored_record()
            assert stored['category_id'] == category_id
            for field in ('description','transaction_date','total_amount','distance_miles','map_link','notes'):
                assert stored[field] == before[field], (field, before[field], stored[field])
        state = app.checkpoint()
        assert state['status'] == 'verified' and state['command'] is None
        # A completed save must read as completed in the panel, name the record it changed, and
        # attribute itself to a run -- and it must not simultaneously show a problem or a question.
        app.panel('verified', True)
        expect(app.fact('record')).to_contain_text('900001')
        expect(app.fact('verified-evidence')).to_contain_text(state['category'])
        expect(app.fact('operation-and-run')).to_contain_text(state['run_ids'][-1])
        expect(app.fact('assignment')).to_contain_text('Tax issues')
        expect(app.fact('problem')).to_have_count(0)
        expect(app.fact('waiting-for-you')).to_have_count(0)
        page.screenshot(path=args.screenshot, full_page=True)
        page.reload(wait_until='commit')  # see open(): DOMContentLoaded is unreliable here.
        expect(page.locator('#receptionist-work [aria-live="polite"]')).to_contain_text('Verified training expense #900001', timeout=45000)
        assert not errors, errors
        print(json.dumps({'stored_category':425, 'expense_id':900001, 'untouched_fields':'preserved',
                          'checkpoint':'restored after reload', 'run_ids':state['run_ids'], 'browser_errors':errors}))
        browser.close()


if __name__ == '__main__':
    main()
