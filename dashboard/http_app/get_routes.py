"""do_GET: the dashboard read-side route ladder.

References into `server` go through the module object (`srv.name`) rather than
`from server import name`, so late rebinds and test monkeypatches on `server`
are still seen here — the ladder is a view onto server's live state, not a
snapshot of it.
"""
import os
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote, urlparse

from . import services as srv
from .static_files import resolve_static_asset


class GetRoutesMixin:
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        agent_id = query.get('agent', [''])[0]

        if path == '/api/terminal':
            return self.handle_terminal_ws(query)

        if path == '/api/code-status':
            return self.json_response(srv.get_code_status())
        if path == '/api/agents':
            return self.json_response(srv.build_agent_list(force_refresh=query.get('refresh', ['0'])[0] == '1'))

        if path == '/api/agent-model':
            lid = srv.letta_id_for(agent_id)
            if not lid:
                return self.json_response({'ok': False, 'error': 'not a Letta agent', 'options': []})
            return self.json_response(srv.agent_model_payload(lid))

        if path == '/api/agent-oauth-account':
            lid = srv.letta_id_for(agent_id)
            if not lid:
                return self.json_response({'ok': False, 'error': 'not a Letta agent', 'current': '', 'options': []})
            return self.json_response(
                srv.agent_oauth_account_payload(lid, pending_model=query.get('model', [''])[0]))

        if path == '/api/model-stats-agents':
            return self.json_response(
                srv.model_stats_agents_payload(force_refresh=query.get('refresh', ['0'])[0] == '1'))

        if path == '/api/claude-sdk-account':
            return self.json_response(srv.claude_sdk_account_payload())

        if path == '/api/router-agent':
            from router.classify import build_router_strategy
            strategy = build_router_strategy()
            if not strategy.agent_id:
                return self.json_response({'ok': False, 'error': 'router agent not found'})
            return self.json_response({'ok': True, 'agent_id': strategy.agent_id})

        if path == '/api/receptionist-agent':
            cfg = next((a for a in srv.LETTA_AGENTS if a['name'] == 'Toyota'), None)
            rid = srv.get_letta_id(cfg) if cfg else None
            if not rid:
                return self.json_response({'ok': False, 'error': 'receptionist agent not found'})
            return self.json_response({'ok': True, 'agent_id': rid, 'name': 'Toyota'})

        if path == '/api/agent-voice':
            return self.json_response(srv.agent_voice_payload(agent_id))

        if path == '/api/agent-activity':
            return self.json_response(srv.agent_activity_status())

        if path == '/api/agent-health':
            return self.json_response(srv.agent_health_status())

        if path == '/api/vendor-keys':
            return self.json_response(srv.list_vendor_keys())

        if path == '/api/rol-finance-categories':
            return self.json_response(
                {'ok': True,
                 'categories': [c['name'] for c in srv._rol_finance_categories()]})

        if path == '/api/pending-vendor-review':
            return self.json_response(srv.list_pending_vendor_review())

        if path == '/api/model-stats-sources':
            return self.json_response([
                {'key': k, 'label': v.label, 'kind': v.kind}
                for k, v in srv.MODEL_STAT_SOURCES.items()
            ])

        if path == '/api/model-stats':
            src = query.get('source', [''])[0]
            return self.json_response(srv.apply_mute_overlay(srv.model_stats(src), src))

        if path == '/api/mazda-mode':
            return self.json_response(srv._MAZDA_MODE_SERVICE.current().to_http())

        if path == '/api/codex-sync-status':
            return self.json_response(srv.codex_sync_status().model_dump(mode='json'))

        if path == '/api/chatgpt-provider-account-status':
            return self.json_response(srv.get_chatgpt_provider_account_status().model_dump(mode='json'))

        if path == '/api/pc-monitors':
            return self.json_response([
                {'key': k, 'label': v.label, 'note': v.note}
                for k, v in srv.PC_MONITORS.items()
            ])

        if path == '/api/pc-metrics':
            return self.json_response(srv.pc_metrics(query.get('pc', [''])[0]))

        if path == '/api/agent-card':
            agent = next((a for a in srv.build_agent_list()
                          if a['id'] == agent_id or a['name'] == agent_id), None)
            if not agent:
                return self.json_response({'error': 'agent not found'})
            return self.json_response(srv.build_agent_card(agent['name'], agent['id']))

        if path == '/api/thoughts':
            if agent_id == 'agent-claude':
                return self.json_response([])   # Claude Code doesn't have thoughts
            lid = srv.letta_id_for(agent_id)
            if lid:
                scanner_key = query.get('scanner', [''])[0]
                intake = srv.get_scanner_intake(scanner_key) if scanner_key else None
                conversation_id = str(
                    (intake or {}).get('conversation_id') or '').strip()
                return self.json_response(srv.cached_thoughts(lid, conversation_id))
            return self.json_response([])

        if path == '/api/messages':
            if agent_id == 'agent-claude':
                now = datetime.now(timezone.utc)
                rows = srv._load_json(srv.CLAUDE_LOG_FILE)
                rows = [r for r in rows if srv._within_max_age(r, now)]
                return self.json_response(rows)
            lid = srv.letta_id_for(agent_id)
            if lid:
                return self.json_response(srv.letta_convo(lid))
            return self.json_response([])

        if path == '/api/toolcalls':
            if agent_id == 'agent-claude':
                return self.json_response(srv._load_json(srv.CLAUDE_TOOL_LOG_FILE))
            lid = srv.letta_id_for(agent_id)
            if lid:
                return self.json_response(srv.letta_toolcalls(lid))
            return self.json_response([])

        if path == '/api/servers':
            return self.json_response([
                {
                    'key': s['key'],
                    'name': s['name'],
                    'note': s.get('note', ''),
                    'url': s.get('health_url'),
                    'health_url': s.get('health_url'),
                    'skills': s.get('skills', []),
                }
                for s in srv.SERVERS
            ])

        if path == '/api/server-logs':
            key = query.get('server', [''])[0]
            q = query.get('q', [''])[0]
            cfg = srv.get_server(key)
            if not cfg:
                return self.json_response({'status': {'ok': False, 'text': 'unknown server'}, 'rows': []})
            return self.json_response(srv.server_log_rows(cfg, q))

        if path == '/api/server-health':
            # Overall health: returns per-server status + aggregate status.
            # A server is "down" if it has a health_url and it doesn't respond OK.
            # A server is "starting" if marked as such by a recent start action.
            # Log-only servers (no health_url) have no endpoint to ping — their
            # status is derived from whether they're still writing to their log
            # (see log_activity_health): recent writes → up, stale/missing → down.
            result = {
                'servers': [],
                'all_up': True,
                'any_down': False,
                'any_concern': False,
                'any_stale': False,
            }
            status_by_key = {}
            container_states = [None]  # lazily probed once per build if needed
            for cfg in srv.SERVERS:
                has_active_check = cfg.get('health_url') or cfg.get('tcp_check') or cfg.get('check')
                key = cfg['key']
                restartable = key in srv.RESTARTABLE_KEYS
                health = None
                if has_active_check:
                    health = srv.cached_server_health(cfg)
                elif cfg.get('log_file'):
                    health = srv.log_activity_health(cfg)

                if health is not None and health.get('ok'):
                    # A real "up" always wins — flip out of the starting window.
                    srv.clear_server_starting(key)
                # Same classifier the detail panel uses (server_status_kind) so the
                # tab and the opened page never disagree.
                status = srv.server_status_kind(cfg, health)
                if status is None:
                    continue
                status_by_key[key] = status

                # Root-cause grouping: if this server depends on a node that's not
                # healthy, mark it blocked_by so it reads as a symptom, not its own
                # failure (the node is restartable, so it reads 'concern' not 'down').
                dep = cfg.get('depends_on')
                blocked_by = dep if (dep and status_by_key.get(dep) not in (None, 'up')) else None

                down_for, stale = srv.track_down_duration(key, status)
                _fc = srv.classify_failure((health or {}).get('text', '')) if status != 'up' else None
                entry = {
                    'key': key,
                    'name': cfg['name'],
                    'status': status,
                    'restartable': restartable,
                    'down_for_seconds': down_for,
                    'stale': stale,
                }
                if blocked_by:
                    entry['blocked_by'] = blocked_by
                if _fc:
                    entry['failure_class'] = _fc[0]
                # Indicator #2: attach the Docker container status (exit code /
                # restart count) for Win10-hosted servers when they're not up.
                if key in srv.WIN10_CONTAINERS and status != 'up':
                    if container_states[0] is None:
                        container_states[0] = srv.win10_container_states()
                    cs = srv.container_status_for(key, container_states[0])
                    if cs:
                        entry['container_status'] = cs
                result['servers'].append(entry)
                if status == 'down':
                    result['any_down'] = True
                    result['all_up'] = False
                elif status in ('concern', 'starting'):
                    result['any_concern'] = True
                if stale:
                    result['any_stale'] = True
            return self.json_response(result)

        if path == '/api/rol-finance-reports':
            month_key = query.get('month', [srv.ROL_FINANCES_REPORTS_DEFAULT_MONTH])[0]
            if month_key not in srv.ROL_FINANCES_REPORTS_MONTHS:
                month_key = srv.ROL_FINANCES_REPORTS_DEFAULT_MONTH
            base_dir = srv._rol_reports_base_dir(month_key)
            result = []
            for r in srv._rol_finance_reports_for_month(month_key):
                report_file = os.path.join(base_dir, r['dir'], 'report.html')
                exists = os.path.isfile(report_file)
                status = srv._classify_report_status(report_file) if exists else 'missing'
                entry = {
                    'key': r['key'],
                    'label': r['label'],
                    'exists': exists,
                    'status': status,
                    'url': f'{srv.ROL_FINANCES_REPORTS_URL_PREFIX}/{month_key}/{r["dir"]}/report.html' if exists else None,
                }
                # Red and yellow reports carry the human-facing reason and
                # recommended action pulled from the report itself, since the
                # iframe hides everything but Verified Transactions.
                if status in ('fail', 'review'):
                    detail = srv._extract_report_attention_detail(report_file)
                    if not detail:
                        detail = {
                            'badge': 'REVIEW NEEDED' if status == 'review' else 'FAILED',
                            'summary': 'This report needs attention but does not include a structured explanation.',
                            'recommended_action': 'Open the full report, identify the unresolved verification item, and update or reprocess the document.',
                        }
                    entry['attention_detail'] = detail
                    if detail:
                        # Preserve the existing API field for older red-row
                        # clients while they migrate to attention_detail.
                        if status == 'fail':
                            entry['failure_detail'] = detail
                result.append(entry)
            # Synthetic "Receipt Only" tab: receipts with no bank-statement
            # transaction. Include the exact resolved-file count so completed
            # receipt work is visible in the month overview even while every
            # statement/document placeholder is still red.
            receipt_count = len(srv._fetch_receipt_only_rows(month_key))
            result.append({
                'key': 'receipt-only',
                'label': 'Receipt Only',
                'exists': True,
                'status': None,
                'receipt_count': receipt_count,
                'url': f'{srv.RECEIPT_ONLY_REPORT_PATH}?month={month_key}',
            })
            return self.json_response(result)

        if path == '/api/rol-finance-recent-reports':
            try:
                limit = int(query.get('limit', ['5'])[0])
            except (ValueError, TypeError):
                limit = 5
            return self.json_response(srv._rol_finance_recent_reports(limit))

        if path == '/api/expense-stored-events':
            try:
                since_ts = float(query.get('since', ['0'])[0])
            except (ValueError, TypeError):
                since_ts = 0.0
            return self.json_response(srv.get_stored_expense_events(since_ts))

        # Fail-loud intake-halt state — IntakeHaltAlert polls this and raises a
        # full-screen "cannot continue" modal while a halt is active.
        if path == '/api/intake-halt':
            return self.json_response(srv.read_intake_halt())

        # Statements quarantined in bank_statements/_needs_review/ — the Scanner
        # screen polls this and pops a dialog for each one.
        if path == '/api/statement-reviews':
            return self.json_response({
                'ok': True,
                'reviews': srv.statement_review.list_reviews(),
            })

        if path == '/api/statement-review-document':
            fp = srv.statement_review.review_document_path(
                query.get('id', [''])[0])
            if fp:
                ext = os.path.splitext(fp)[1].lower()
                ctype = {
                    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                    '.png': 'image/png', '.gif': 'image/gif',
                    '.webp': 'image/webp', '.pdf': 'application/pdf',
                }.get(ext, 'application/octet-stream')
                return self.serve_file(fp, ctype)
            self.send_error(404)
            return

        if path == '/api/rol-finance-recent-scans':
            try:
                limit = int(query.get('limit', ['5'])[0])
            except (TypeError, ValueError):
                limit = 5
            month = (query.get('month', [''])[0] or '').strip() or None
            try:
                return self.json_response(srv._fetch_recent_scans(limit, month))
            except Exception as e:
                return self.json_response(
                    {'rows': [], 'queue_total': 0, 'limit': 5, 'error': str(e)})

        if path == '/api/rol-finance-month-status':
            try:
                return self.json_response({'months': srv._fetch_month_status()})
            except Exception as e:
                return self.json_response({'months': [], 'error': str(e)})

        if path == '/api/rol-finance-categories':
            return self.json_response({'categories': srv._rol_finance_categories()})

        if path == '/api/ssh-connections':
            return self.json_response([
                {'key': c['key'], 'name': c['name'], 'note': c.get('note', '')}
                for c in srv.SSH_CONNECTIONS
            ])

        if path == '/api/ssh-connection-health':
            # Overall SSH health: a real `ssh ... echo CONNECTED` round trip per
            # connection. "down" means SSH itself is broken to that host.
            result = {'connections': [], 'all_up': True, 'any_down': False}
            for cfg in srv.SSH_CONNECTIONS:
                h = srv.cached_ssh_health(cfg)
                status = 'up' if h.get('ok') else 'down'
                result['connections'].append({'key': cfg['key'], 'name': cfg['name'], 'status': status})
                if status == 'down':
                    result['any_down'] = True
                    result['all_up'] = False
            return self.json_response(result)

        if path == '/api/ssh-connection-logs':
            key = query.get('conn', [''])[0]
            cfg = srv.get_ssh_connection(key)
            if not cfg:
                return self.json_response({'status': {'ok': False, 'text': 'unknown connection'}, 'rows': []})
            with srv._ssh_log_lock:
                rows = list(srv._ssh_log_cache.get(key, []))
            return self.json_response({'status': srv.cached_ssh_health(cfg), 'rows': rows})

        if path == '/api/ssh-connection-test':
            key = query.get('conn', [''])[0]
            cfg = srv.get_ssh_connection(key)
            if not cfg:
                return self.json_response({'ok': False, 'text': 'unknown connection'})
            h = srv.connection_test(cfg)
            with srv._ssh_health_lock:
                srv._ssh_health_cache[key] = {'fails': 0 if h.get('ok') else 1, 'result': h}
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            srv._record_ssh_log(key, f"[{ts}] {'OK' if h['ok'] else 'FAIL'} — {h['text']} (manual test)")
            return self.json_response(h)

        if path == '/' or path == '':
            return self.serve_file(os.path.join(srv.HERE, 'dashboard.html'), 'text/html')

        if path == srv.ROL_FINANCES_PLAN_PATH:
            return self.serve_file(srv.ROL_FINANCES_PLAN_FILE, 'text/html')

        if path == srv.RECEIPT_ONLY_REPORT_PATH:
            try:
                month_key = query.get('month', [srv.ROL_FINANCES_REPORTS_DEFAULT_MONTH])[0]
                if month_key not in srv.ROL_FINANCES_REPORTS_MONTHS:
                    month_key = srv.ROL_FINANCES_REPORTS_DEFAULT_MONTH
                body = srv.build_receipt_only_report_html(month_key)
            except Exception as e:
                from html import escape as _esc
                import traceback as tb
                body = ('<!doctype html><meta charset="utf-8"><body><pre>'
                        'DEBUG: Receipt Only endpoint is being executed\n'
                        + _esc(tb.format_exc()) + '</pre></body></html>')
            data = body.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path == srv.RECENT_REPORT_PATH:
            try:
                body = srv.build_recent_report_html()
            except Exception as e:
                from html import escape as _esc
                body = ('<!doctype html><meta charset="utf-8"><body>'
                        '<pre>Recent Report build error: %s</pre>' % _esc(str(e)))
            data = body.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            # Always re-resolved — a cached copy would pin an older document.
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)
            return

        if path == srv.SCANNER_REPORT_PATH:
            try:
                body = srv.build_scanner_report_html(query.get('scanner', [''])[0])
            except Exception as e:
                from html import escape as _esc
                body = ('<!doctype html><meta charset="utf-8"><body>'
                        '<pre>Scanner Report build error: %s</pre>' % _esc(str(e)))
            data = body.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            # Always re-resolved — a cached copy would pin an older scan.
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)
            return

        if path.startswith(srv.ROL_FINANCES_REPORTS_URL_PREFIX + '/'):
            fp = srv._report_file_for_url(path)
            if fp:
                data = srv._report_html_with_current_picker(fp).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_error(404)
            return

        if path == '/api/scanner-status':
            return self.json_response(srv.scanner_status(query.get('scanner', [''])[0]))

        if path == '/api/scanner-diagnostics':
            return self.json_response(
                srv.scanner_diagnostics(query.get('scanner', [''])[0]))

        if path == '/api/scanner-intake-status':
            key = query.get('scanner', [''])[0]
            intake = srv.get_scanner_intake(key)
            if intake:
                status = str(intake.get('status') or 'processing').lower()
                return self.json_response({'ok': True, 'status': status})
            return self.json_response({'ok': True, 'status': 'idle'})

        if path == srv.SCANNER_IMAGE_URL_PREFIX:
            key = query.get('scanner', [''])[0]
            cfg = srv.SCANNERS.get(key)
            if cfg:
                fp = os.path.join(srv.SCAN_TOOLS_DIR, cfg['output'])
                if os.path.isfile(fp):
                    ctype = 'image/jpeg' if fp.endswith(('.jpg', '.jpeg')) else 'image/png'
                    return self.serve_file(fp, ctype)
            self.send_error(404)
            return

        if path == srv.INTAKE_DOCUMENT_URL_PREFIX:
            fp = srv.scanner_intake_document_path(query.get('scanner', [''])[0])
            if fp:
                ext = os.path.splitext(fp)[1].lower()
                ctype = {
                    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                    '.png': 'image/png', '.webp': 'image/webp',
                }.get(ext, 'application/octet-stream')
                return self.serve_file(fp, ctype)
            self.send_error(404)
            return

        for _prefix, _serve_base, _subtree in srv.RECEIPT_MOUNTS:
            if path.startswith(_prefix + '/'):
                rel = unquote(path[len(_prefix) + 1:])
                base = os.path.abspath(_serve_base)
                fp = os.path.abspath(os.path.join(base, rel))
                if os.path.commonpath([fp, base]) == base and os.path.isfile(fp):
                    ext = fp.rsplit('.', 1)[-1].lower()
                    ctype = {
                        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
                        'gif': 'image/gif', 'webp': 'image/webp', 'pdf': 'application/pdf',
                    }.get(ext, 'application/octet-stream')
                    return self.serve_file(fp, ctype)
                self.send_error(404)
                return

        if path == '/report-source-document':
            try:
                document_path = srv._report_source_document_view(
                    query.get('report_path', [''])[0])
            except Exception as exc:
                print(f'[report-source-document] Render failed: {exc}')
                self.send_error(500, 'Could not render source document')
                return
            if document_path:
                ext = os.path.splitext(document_path)[1].lower()
                ctype = {
                    '.html': 'text/html; charset=utf-8',
                    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                    '.png': 'image/png', '.gif': 'image/gif',
                    '.webp': 'image/webp', '.pdf': 'application/pdf',
                }.get(ext, 'application/octet-stream')
                return self.serve_file(document_path, ctype)
            self.send_error(404)
            return

        if path.startswith(srv.SUPPORTING_DOCUMENT_URL_PREFIX + '/'):
            parts = path[len(srv.SUPPORTING_DOCUMENT_URL_PREFIX) + 1:].split('/')
            document_path = (
                srv._supporting_document_view_for_expense(
                    parts[0],
                    parts[1],
                    # raw — see /api/supporting-documents
                    query.get('report_path', [''])[0],
                )
                if len(parts) == 2
                else None
            )
            if document_path:
                ext = os.path.splitext(document_path)[1].lower()
                if ext in {'.xlsx', '.xlsm'}:
                    browser_path = os.path.join(
                        srv.SUPPORTING_DOCUMENT_ANNOTATION_CACHE,
                        os.path.basename(document_path) + '.html',
                    )
                    try:
                        document_path = srv.render_excel_for_browser(
                            document_path, browser_path)
                        ext = '.html'
                    except Exception as exc:
                        print(f'[supporting-document] Excel render failed: {exc}')
                        self.send_error(500, 'Could not render spreadsheet')
                        return
                ctype = {
                    '.html': 'text/html; charset=utf-8',
                    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                    '.gif': 'image/gif', '.webp': 'image/webp',
                    '.pdf': 'application/pdf',
                    '.xlsx': (
                        'application/vnd.openxmlformats-officedocument.'
                        'spreadsheetml.sheet'
                    ),
                    '.xlsm': 'application/vnd.ms-excel.sheet.macroEnabled.12',
                }.get(ext, 'application/octet-stream')
                return self.serve_file(document_path, ctype)
            self.send_error(404)
            return

        if path.startswith('/'):
            asset = resolve_static_asset(path, (srv.HERE, srv.REPO_ROOT))
            if asset:
                return self.serve_file(asset)

        self.send_error(404)
