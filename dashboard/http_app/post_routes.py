"""do_POST: the dashboard write-side route ladder.

Same late-binding rule as get_routes: reach into `server` through the module
object so monkeypatches and runtime rebinds stay visible.
"""
import json
import os
import subprocess
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import urlparse

from . import services as srv


class PostRoutesMixin:
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length)

        # /api/voice carries a binary audio blob — handle before decoding as text.
        if path == '/api/voice':
            return self._handle_voice(raw)

        body = raw.decode('utf-8', errors='replace')

        if path == '/api/claude-log':
            try:
                data = json.loads(body)
                srv._append_json(srv.CLAUDE_LOG_FILE, srv._claude_log_lock, {
                    'date': data.get('date', datetime.now().isoformat()),
                    'type': data.get('type', 'assistant_message'),
                    'text': data.get('text', ''),
                })
                return self.json_response({'ok': True})
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)

        if path == '/api/claude-toollog':
            try:
                data = json.loads(body)
                srv._append_json(srv.CLAUDE_TOOL_LOG_FILE, srv._claude_tool_log_lock, {
                    'date': data.get('date', datetime.now().isoformat()),
                    'type': data.get('type', 'tool_call'),
                    'text': data.get('text', ''),
                }, maxlen=200)
                return self.json_response({'ok': True})
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)

        if path == '/api/codex-sync-now':
            try:
                req = srv.CodexSyncRequest.model_validate(json.loads(body) if body.strip() else {})
            except (json.JSONDecodeError, srv.ValidationError) as exc:
                return self.error_response(f'invalid request: {exc}', 400)
            return self.json_response(srv.run_codex_sync_now(req.source).model_dump(mode='json'))

        if path == '/api/codex-sync-toggle':
            try:
                req = srv.CodexSyncToggleRequest.model_validate(json.loads(body) if body.strip() else {})
            except (json.JSONDecodeError, srv.ValidationError) as exc:
                return self.error_response(f'invalid request: {exc}', 400)
            return self.json_response(srv.toggle_codex_sync(req.enabled).model_dump(mode='json'))

        if path == '/api/chatgpt-provider-account':
            try:
                req = srv.ChatGptProviderSwapRequest.model_validate(json.loads(body) if body.strip() else {})
            except (json.JSONDecodeError, srv.ValidationError) as exc:
                return self.error_response(f'invalid request: {exc}', 400)
            return self.json_response(srv.set_chatgpt_provider_account(req.source).model_dump(mode='json'))

        if path == '/api/mazda-mode':
            # A preference, not a command: this decides who reads the NEXT
            # scanned document. Nothing in flight is re-dispatched or recalled.
            try:
                data = json.loads(body) if body.strip() else {}
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv._MAZDA_MODE_SERVICE.set_from_http(data))

        if path == '/api/model-stats-mute':
            try:
                req = srv.ModelStatsMuteRequest.model_validate(json.loads(body) if body.strip() else {})
            except (json.JSONDecodeError, srv.ValidationError) as exc:
                return self.error_response(f'invalid request: {exc}', 400)
            srv.set_muted(req.source, req.muted)
            return self.json_response(srv.apply_mute_overlay(srv.model_stats(req.source), req.source))

        if path == '/api/server-action':
            try:
                data = json.loads(body)
                server = data.get('server', '')
                action = data.get('action', '')

                if action == 'start' and server == 'executor':
                    result = srv.start_executor_server()
                    return self.json_response(result)

                if action == 'start' and server == 'logger-api':
                    result = srv.start_logger_api()
                    return self.json_response(result)

                if action == 'start' and server == 'frita-executor':
                    result = srv.start_frita_executor()
                    return self.json_response(result)

                if action == 'deploy' and server == 'dashboard':
                    # Keyboard-free deploy: pull the current branch + self-restart.
                    result = srv.deploy_dashboard()
                    return self.json_response(result)

                if action in ('start', 'restart') and server == 'dashboard':
                    result = srv.restart_dashboard_server()
                    return self.json_response(result)

                # Generic restart — every Server Management entry is restartable
                # from the UI so the user never needs the command line.
                if action == 'restart':
                    return self.json_response(srv.restart_server(server))

                return self.json_response({'ok': False, 'text': f'Unknown action: {action} for {server}'})
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)

        if path == '/api/tts':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            result = srv.synthesize_speech(data.get('text', ''),
                                       voice=data.get('voice'))
            if not result.get('ok'):
                return self.json_response(result)
            return self.serve_file(result['path'], content_type='audio/mpeg')

        if path == '/api/scanner-scan':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.run_scanner(data.get('scanner', '')))

        if path == '/api/scanner-clear-verification':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            result = srv.clear_scanner_verification_lock(data.get('scanner', ''))
            return self.json_response(result)

        if path == '/api/scanner-archive-path':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            scanner_key = data.get('scanner', '')
            intake = srv.get_scanner_intake(scanner_key)
            if not intake:
                return self.json_response({'ok': False, 'error': 'No intake found'})
            rows = srv._fetch_expenses_by_ids(intake.get('expense_ids') or [])
            archive_file = srv.scanner_intake_archive_path(intake, rows)
            # The result above is the specific filed document (a file, not a
            # directory) - the archive-verification terminal needs to `cd`
            # into its containing folder to `ls -a` the sibling documents/
            # receipts, not the file itself.
            archive_path = os.path.dirname(archive_file) if archive_file else ''
            if archive_path and os.path.isdir(archive_path):
                return self.json_response({
                    'ok': True,
                    'archive_path': archive_path,
                    'archive_name': os.path.basename(archive_file),
                })
            return self.json_response({'ok': False, 'error': 'Archive path not found'})

        if path == '/api/fix-printer':
            return self.json_response(srv.fix_deskjet_printer())

        if path == '/api/process-document':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.process_scanned_document(
                data.get('scanner', ''),
                org_id=data.get('org_id', 1),
                engine=data.get('engine', 'gemini'),
                statement_metadata=data.get('statement_metadata'),
                doc_kind_override=data.get('doc_kind_override'),
            ))

        if path == '/api/process-pdf':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.process_pdf_document(
                data.get('file_path', ''),
                label=data.get('label'),
                org_id=data.get('org_id', 1),
                engine=data.get('engine', 'gemini'),
            ))

        if path == '/api/reprocess-report':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.reprocess_report(
                srv._resolve_report_path_alias(data.get('report_url', ''))))

        if path == '/api/expense-stored':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.record_stored_expense(data))

        # The dialog's OK / Save button: re-run the store for one quarantined
        # statement, with any human-supplied amounts filled in. A failure keeps
        # the item queued so the dialog reappears.
        if path == '/api/statement-review-resolve':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            review_id = data.get('id')
            if not review_id:
                return self.error_response('Missing review id', 400)
            ok, payload = srv.statement_review.resolve_review(
                review_id, amounts=data.get('amounts'))
            if ok:
                srv.merge_statement_review_result(payload)
            return self.json_response({'ok': ok, **payload})

        if path == '/api/manual-receipt-entry':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.submit_manual_receipt_entry(data))

        # The Edit Expense button's two calls: find an already-stored row, then
        # correct it. Save All only ever inserts, so these are the write path
        # for everything that was typed wrong the first time.
        if path == '/api/expense-search':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.search_stored_expenses(data))

        if path == '/api/expense-edit':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.edit_stored_expense(data))

        if path == '/api/manual-receipt-entry-preview':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            image_path = str(data.get('image_path') or '').strip()
            if not image_path:
                return self.error_response('Missing image_path', 400)
            engine = str(data.get('engine') or 'local').strip()
            if engine not in srv.manual_entry.PREVIEW_ENGINES:
                return self.error_response(f'Unsupported engine: {engine}', 400)
            # The category namer translates the vendor's leaf category
            # ("Housing Gas Bill") into the reporting-bucket label the form's
            # dropdown is built from ("Housing Payment & Upkeep"). Without it
            # the dropdown silently ignored a correctly-resolved category.
            ok, payload = srv.manual_entry.preview_receipt_parse(
                image_path, engine=engine,
                category_namer=srv.taxonomy_category_namer())
            return self.json_response({'ok': ok, **payload})

        # The statement pair, alongside the receipt endpoints above: the same
        # form serves both document kinds, and which pair it calls is decided
        # by what the document IS, not by how many rows are on screen.
        # "Mazda Fill": one button, one cheap model, both document kinds.
        # Replaced the form's five reading buttons on 2026-08-19 -- see
        # finance/mazda_fill.py for why picking the reader by eye was the bug.
        if path == '/api/mazda-fill':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.mazda_fill_document(data))

        if path == '/api/manual-statement-breakup':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.break_up_statement_document(data))

        if path == '/api/manual-statement-entry':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.submit_manual_statement_entry(data))

        if path == '/api/manual-receipt-entry-archive-preview':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.preview_manual_entry_archive_path(data))

        if path == '/api/intake-status':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            result = srv.record_intake_status(data)
            return self.json_response(result)

        if path == '/api/intake-halt':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.record_intake_halt(data))

        if path == '/api/intake-halt-ack':
            return self.json_response(srv.acknowledge_intake_halt())

        if path == '/api/route-detect':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            from router.classify import build_router_strategy
            result = build_router_strategy().classify(data.get('text', ''))
            return self.json_response({'ok': True, **result})

        if path == '/api/receptionist-intent':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            transcript = data.get('text', '')
            if not isinstance(transcript, str):
                return self.error_response('text must be a string', 400)
            return self.json_response(srv.build_receptionist_strategy().evaluate(transcript))

        # ── Note-command channel (Toyota's command box) ──────────────────────
        # Two stages, deliberately separate endpoints: the browser asks "is the
        # instruction finished?" on every finalized speech fragment, then asks
        # to apply it exactly once. See voice/note_service.py.
        if path == '/api/note-command-complete':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            text = data.get('text', '')
            if not isinstance(text, str):
                return self.error_response('text must be a string', 400)
            decision = srv.note_command_service().assess(srv.PartialVoiceCommand(text=text))
            return self.json_response({'ok': True, **decision.model_dump()})

        if path == '/api/note-command-apply':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            note = data.get('note', '')
            command = data.get('command', '')
            if not isinstance(note, str) or not isinstance(command, str):
                return self.error_response('note and command must be strings', 400)
            try:
                request = srv.NoteEditRequest(note=note, command=command)
            except srv.ValidationError:
                return self.error_response('command must not be blank', 400)
            outcome = srv.note_command_service().apply(request)
            return self.json_response({'ok': True, **outcome.model_dump()})

        if path == '/api/agent-model':
            try:
                data = json.loads(body)
                lid = srv.letta_id_for(data.get('agent', ''))
                model = data.get('model', '')
                if not lid:
                    return self.json_response({'ok': False, 'error': 'not a Letta agent'})
                cur = srv.letta_get(f'/v1/agents/{lid}', timeout=15) or {}
                cur_handle = (cur.get('llm_config') or {}).get('handle') or ''
                if model not in srv.agent_model_options(cur_handle):
                    return self.json_response({'ok': False, 'error': f'model {model!r} is not in the allowed list'})
                # Preserve the agent's currently-assigned OAuth account across a
                # model swap. AGENT_MODEL_OPTIONS always names the default
                # (mom's) provider row per family, so without this a plain
                # model change would silently move an eg-assigned agent back
                # onto the shared token.
                cur_provider = (cur.get('llm_config') or {}).get('provider_name') or ''
                cur_account = (srv.OAUTH_PROVIDER_ACCOUNTS.get(cur_provider) or {}).get('account')
                if cur_account:
                    req_provider, _, req_model_id = model.partition('/')
                    req_family = (srv.OAUTH_PROVIDER_ACCOUNTS.get(req_provider) or {}).get('family')
                    target_provider = srv.OAUTH_ACCOUNT_PROVIDER.get((req_family, cur_account))
                    if target_provider:
                        model = f'{target_provider}/{req_model_id}'
                req = urllib.request.Request(
                    f'{srv.LETTA_BASE_URL}/v1/agents/{lid}',
                    data=json.dumps({'model': model}).encode(),
                    headers={'Content-Type': 'application/json'},
                    method='PATCH',
                )
                with urllib.request.urlopen(req, timeout=30) as r:
                    resp = json.loads(r.read().decode())
                new_handle = (resp.get('llm_config') or {}).get('handle') or model
                return self.json_response({'ok': True, 'model': new_handle})
            except urllib.error.HTTPError as e:
                return self.json_response({'ok': False, 'error': f'letta {e.code}: {e.read().decode()[:200]}'})
            except Exception as e:
                return self.json_response({'ok': False, 'error': str(e)})

        if path == '/api/agent-oauth-account':
            try:
                data = json.loads(body)
                return self.json_response(
                    srv.patch_agent_oauth_account(data.get('agent', ''), data.get('account', '')))
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            except urllib.error.HTTPError as e:
                return self.json_response({'ok': False, 'error': f'letta {e.code}: {e.read().decode()[:200]}'})
            except Exception as e:
                return self.json_response({'ok': False, 'error': str(e)})

        if path == '/api/claude-sdk-account':
            try:
                data = json.loads(body)
                return self.json_response(
                    srv.set_claude_sdk_account(data.get('account', '')))
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            except Exception as e:
                return self.json_response({'ok': False, 'error': str(e)})

        if path == '/api/agent-voice':
            try:
                data = json.loads(body)
                return self.json_response(
                    srv.patch_agent_voice(data.get('agent', ''), data.get('voice', '')))
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            except urllib.error.HTTPError as e:
                return self.json_response(
                    {'ok': False, 'error': f'letta {e.code}: {e.read().decode()[:200]}'})
            except Exception as e:
                return self.json_response({'ok': False, 'error': str(e)})

        if path == '/api/test':
            try:
                data = json.loads(body)
                agent_id = data.get('agent', '')
                text = data.get('text', '')

                if agent_id == 'agent-claude':
                    srv._clear_json(srv.CLAUDE_LOG_FILE, srv._claude_log_lock)
                    srv._clear_json(srv.CLAUDE_TOOL_LOG_FILE, srv._claude_tool_log_lock)
                    return self.json_response({'replies': [{'type': 'assistant_message', 'text': f'[stub] {agent_id} got: {text}'}]})

                lid = srv.letta_id_for(agent_id)
                if lid:
                    reset_req = urllib.request.Request(
                        f'{srv.LETTA_BASE_URL}/v1/agents/{lid}/reset-messages',
                        data=json.dumps({'add_default_initial_messages': False}).encode(),
                        headers={'Content-Type': 'application/json'},
                        method='PATCH',
                    )
                    try:
                        with urllib.request.urlopen(reset_req, timeout=10):
                            pass
                    except Exception:
                        pass

                    # Send a real message to the Letta agent
                    payload = json.dumps({
                        'messages': [{'role': 'user', 'content': text}],
                        'stream': False,
                    }).encode()
                    req = urllib.request.Request(
                        f'{srv.LETTA_BASE_URL}/v1/agents/{lid}/messages',
                        data=payload,
                        headers={'Content-Type': 'application/json'},
                        method='POST',
                    )
                    try:
                        # Jeri may delegate to a Mazda minion via send_letta_message,
                        # which blocks on run_claude_code_sdk (up to a 300s subprocess
                        # timeout). Give the round trip enough headroom that a slow
                        # delegation doesn't look like a dashboard timeout.
                        with urllib.request.urlopen(req, timeout=330) as r:
                            resp = json.loads(r.read().decode())
                        replies = []
                        for m in resp.get('messages', []):
                            if m.get('message_type') == 'assistant_message':
                                replies.append({'type': 'assistant_message', 'text': srv._msg_text(m)})
                        if not replies:
                            # The agent ended its turn without a final assistant_message
                            # (e.g. it ran a tool and stopped). Fall back to showing
                            # the last tool call/return so the user sees what happened
                            # instead of a bare "(no reply)".
                            for m in resp.get('messages', []):
                                mtype = m.get('message_type')
                                if mtype in ('tool_call_message', 'tool_return_message', 'reasoning_message'):
                                    replies.append({'type': mtype, 'text': srv._msg_text(m)})
                        srv.clear_agent_send_error(lid)
                        return self.json_response({'replies': replies or [{'type': 'assistant_message', 'text': '(no reply)'}]})
                    except Exception as e:
                        err_text = str(e)
                        srv.record_agent_send_error(lid, err_text)
                        return self.json_response({'replies': [{'type': 'error', 'text': err_text}]})
                return self.json_response({'replies': [{'type': 'assistant_message', 'text': f'[stub] {agent_id} got: {text}'}]})
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)

        if path == '/api/letta-code-message':
            try:
                data = json.loads(body)
                return self.json_response(srv.run_letta_code_message(
                    data.get('agent', ''), data.get('text', ''),
                    conversation_id=data.get('conversation_id') or None))
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            except ValueError as e:
                return self.error_response(str(e), 400)
            except subprocess.TimeoutExpired:
                return self.error_response('Mazda took too long to answer', 504)
            except Exception as e:
                return self.error_response(str(e), 502)
        if path == '/api/headless-prompt':
            # Headless mode: run letta -p with JSON output (no terminal UI noise)
            # Used by "Ask Mazda" to get clean, readable output without ANSI codes
            try:
                data = json.loads(body)
                agent_id = data.get('agent', '')
                prompt_text = data.get('prompt', '')
                if not prompt_text.strip():
                    return self.json_response({'ok': False, 'error': 'prompt is required'})
                return self.json_response(srv.run_letta_headless(agent_id, prompt_text))
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)

        if path == '/api/recategorize-expense':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.recategorize_expense(
                data.get('date', ''),
                data.get('signed_amount', ''),
                data.get('vendor_key', ''),
                data.get('reporting_category', ''),
                data.get('description', ''),
                srv._resolve_report_path_alias(data.get('report_path', '')),
                data.get('expense_id'),
            ))

        if path == '/api/undo-recategorize-expense':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(
                srv.undo_recategorize_expense(data.get('undo_token', '')))

        if path == '/api/set-receipt-vendor':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.set_receipt_vendor(
                data.get('expense_id'), data.get('vendor_key', '')))

        if path == '/api/receipt-lookup':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.lookup_receipt(
                data.get('date', ''),
                data.get('signed_amount', ''),
                data.get('vendor_key', ''),
                data.get('description', ''),
                srv._resolve_report_path_alias(data.get('report_path', '')),
                data.get('expense_id'),
            ))

        if path == '/api/supporting-documents':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.lookup_supporting_documents(
                data.get('date', ''),
                data.get('signed_amount', ''),
                data.get('vendor_key', ''),
                data.get('description', ''),
                # Raw, NOT alias-resolved: the alias collapses a scanner /
                # intake-mode page to '' (correct for row recolor, which has no
                # file to rewrite), and that erased the only clue to which
                # scanned document the row's page was built from.
                data.get('report_path', ''),
                data.get('expense_id'),
            ))

        if path == '/api/open-supporting-document':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.open_supporting_document(
                data.get('date', ''),
                data.get('signed_amount', ''),
                data.get('vendor_key', ''),
                data.get('document_type', ''),
                data.get('description', ''),
                data.get('expense_id'),
                data.get('report_path', ''),  # raw — see /api/supporting-documents
                bool(data.get('wait_for_highlight', False)),
            ))

        if path == '/api/receipts-present':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.receipts_present(data.get('rows', [])))

        if path == '/api/scanned-statements-present':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(
                srv.scanned_statements_present(data.get('rows', [])))

        if path == '/api/save-expense-notes':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(srv.save_expense_notes(
                data.get('date', ''),
                data.get('signed_amount', ''),
                data.get('vendor_key', ''),
                data.get('description', ''),
                data.get('notes', ''),
                data.get('expense_id'),
            ))

        self.send_error(404)

    def _handle_voice(self, audio_bytes):
        filename = self.headers.get('X-Filename', 'audio.webm')
        result = srv.handle_voice_upload(srv.build_pipeline(), audio_bytes, filename)
        if result.get('ok'):
            srv._append_json(srv.VOICE_LOG_FILE, srv._voice_log_lock, {
                'date': datetime.now().isoformat(),
                'raw': result.get('raw_transcript', ''),
                'cleaned': result.get('cleaned_text', ''),
            })
        return self.json_response(result)
