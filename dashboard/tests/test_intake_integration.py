"""Integration tests for the Mazda document-intake pipeline.

These exercise the REAL rol_finances scripts that the dashboard hands Mazda after
a scan — they are the end-to-end guard for the 2026-06-28 intake regression where
the categorizer command died with `ModuleNotFoundError: No module named 'tools'`
because it was invoked as bare `python3` instead of the venv interpreter with
PYTHONPATH set.

Unlike test_server.py (pure string/logic checks), these actually run the scripts,
so they are skipped when the rol_finances repo/venv is not on the box. The single
network/LLM-dependent check (classify_scan.py → Gemini vision) is further gated
behind MAZDA_RUN_CLASSIFY_INTEGRATION=1 so the default run stays offline + free.
"""
import json
import os
import subprocess
import urllib.error
import urllib.request

import pytest
import server

ROL_FINANCES_DIR = '/home/adamsl/rol_finances'
CATEGORIZER = os.path.join(ROL_FINANCES_DIR, 'tools', 'categorizer', 'categorizer_main.py')

EXECUTOR_URL = os.environ.get('EXECUTOR_URL', 'http://localhost:8787').rstrip('/')
EXECUTOR_TOKEN = os.environ.get('EXECUTOR_TOKEN', '')

# Skip the whole module if the finance repo + venv aren't present (e.g. CI box).
_repo_ready = (
    os.path.isdir(ROL_FINANCES_DIR)
    and os.path.isfile(server.MAZDA_RF_VENV_PY)
    and os.path.isfile(CATEGORIZER)
)
pytestmark = pytest.mark.skipif(
    not _repo_ready,
    reason='rol_finances repo/venv not available on this box',
)


def _run_categorizer(input_payload, *, with_pythonpath, tmp_path):
    """Invoke the real categorizer CLI exactly the way the scan message does."""
    inp_file = tmp_path / 'mazda_cat_input.json'
    inp_file.write_text(json.dumps(input_payload))
    env = dict(os.environ)
    if with_pythonpath:
        env['PYTHONPATH'] = ROL_FINANCES_DIR
    else:
        env.pop('PYTHONPATH', None)
    return subprocess.run(
        [server.MAZDA_RF_VENV_PY if with_pythonpath else 'python3',
         CATEGORIZER, '-i', str(inp_file), '--provider=gemini'],
        cwd=ROL_FINANCES_DIR, env=env,
        capture_output=True, text=True, timeout=90,
    )


def test_categorizer_resolves_known_vendor_without_llm(tmp_path):
    """The command form the scan message hands Mazda must run cleanly and return
    a real category for a vendor_key already in vendor_category.yaml — no LLM,
    no network, no ModuleNotFoundError. (goodwill_cascade -> category_id 3.)"""
    proc = _run_categorizer(
        {'id_light': '', 'description': 'Goodwill Cascade Grand Rapids MI',
         'vendor_key': 'goodwill_cascade'},
        with_pythonpath=True, tmp_path=tmp_path,
    )
    assert proc.returncode == 0, f'stderr: {proc.stderr}'
    assert 'ModuleNotFoundError' not in proc.stderr
    out = json.loads(proc.stdout[proc.stdout.find('{'):])
    assert out['vendor_key'] == 'goodwill_cascade'
    assert out['category_id'] == 3


def test_categorizer_resolves_goodwill_grand_rapids_without_llm(tmp_path):
    """2026-06-29 Blocker B: the first scanned receipt parsed merchant
    "Goodwill of Greater Grand Rapids" -> vendor_key goodwill_of_greater_grand_rapids,
    which was NOT in vendor_category.yaml (only goodwill_cascade existed), so the
    categorizer fell through to the (Node-18-crashing) LLM research path and
    returned null. The added yaml entry must resolve it to category_id 3 with NO
    LLM — same Goodwill thrift category as goodwill_cascade."""
    proc = _run_categorizer(
        {'id_light': '', 'description': 'Goodwill of Greater Grand Rapids',
         'vendor_key': 'goodwill_of_greater_grand_rapids'},
        with_pythonpath=True, tmp_path=tmp_path,
    )
    assert proc.returncode == 0, f'stderr: {proc.stderr}'
    assert 'Invalid regular expression flags' not in proc.stderr  # the Node-18 crash
    out = json.loads(proc.stdout[proc.stdout.find('{'):])
    assert out['vendor_key'] == 'goodwill_of_greater_grand_rapids'
    assert out['category_id'] == 3


def test_goodwill_grand_rapids_is_a_recognized_vendor():
    """check_vendor_key reports recognized:true only for vendor_keys present in
    vendor_category.yaml's entries: section (exact match via VendorCategoryLookup).
    Guards that the Goodwill-GR entry stays recognized so intake judges PASS, not
    NEEDS_REVIEW. Runs under the rol_finances venv (which has PyYAML), reading the
    same YAML the live check_vendor_key tool reads on this box."""
    script = (
        'from tools.categorizer.python_libary.vendor_category_lookup '
        'import VendorCategoryLookup; '
        'm = VendorCategoryLookup().vendor_map; '
        'import json; print(json.dumps({'
        '"gr": m.get("goodwill_of_greater_grand_rapids"), '
        '"cascade": m.get("goodwill_cascade")}))'
    )
    proc = subprocess.run(
        [server.MAZDA_RF_VENV_PY, '-c', script],
        cwd=ROL_FINANCES_DIR, env=dict(os.environ, PYTHONPATH=ROL_FINANCES_DIR),
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, f'stderr: {proc.stderr}'
    vmap = json.loads(proc.stdout[proc.stdout.find('{'):])
    assert vmap['gr'] == 3
    assert vmap['cascade'] == 3  # the original entry is untouched


def test_bare_python3_invocation_reproduces_the_regression(tmp_path):
    """Negative control: the OLD bare-`python3` invocation (no venv, no
    PYTHONPATH) still fails with the exact ModuleNotFoundError. This is what the
    venv+PYTHONPATH fix in build_mazda_scan_message prevents — if this ever
    stops failing, the guard above is no longer meaningful and should be revisited."""
    proc = _run_categorizer(
        {'id_light': '', 'description': 'Goodwill', 'vendor_key': 'goodwill_cascade'},
        with_pythonpath=False, tmp_path=tmp_path,
    )
    assert proc.returncode != 0
    assert "No module named 'tools'" in proc.stderr


def test_scan_message_categorizer_command_is_actually_runnable(tmp_path):
    """Tie the unit-tested message to reality: the venv interpreter + the
    categorizer path that build_mazda_scan_message embeds must both exist and
    execute. Guards against the message drifting to a stale path."""
    msg = server.build_mazda_scan_message('/scans/x.jpg', 'Scanner', None)
    assert server.MAZDA_RF_VENV_PY in msg
    assert 'tools/categorizer/categorizer_main.py' in msg
    # The interpreter named in the message can run the categorizer's --help.
    proc = subprocess.run(
        [server.MAZDA_RF_VENV_PY, CATEGORIZER, '--help'],
        cwd=ROL_FINANCES_DIR, env=dict(os.environ, PYTHONPATH=ROL_FINANCES_DIR),
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0
    assert '--category' in proc.stdout or 'usage' in proc.stdout.lower()


def _executor_reachable():
    try:
        urllib.request.urlopen(EXECUTOR_URL + '/', timeout=3)
    except urllib.error.HTTPError:
        return True  # any HTTP status means the server is up
    except Exception:
        return False
    return True


def _executor_run(command, cwd='.', env=None, timeout=30):
    """Call the live executor /run endpoint, returning (http_status, body)."""
    payload = json.dumps(
        {'command': command, 'cwd': cwd, 'timeout_sec': timeout, 'env': env}
    ).encode()
    req = urllib.request.Request(
        EXECUTOR_URL + '/run', data=payload, method='POST',
        headers={'Authorization': f'Bearer {EXECUTOR_TOKEN}',
                 'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout + 10) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


@pytest.mark.skipif(
    not EXECUTOR_TOKEN or not _executor_reachable(),
    reason='set EXECUTOR_TOKEN and run the executor on :8787 for this check',
)
def test_executor_rejects_inline_pythonpath_prefix_but_accepts_env_arg():
    """2026-06-29 regression (live trace 53): a BARE command whose first token is
    an inline ``PYTHONPATH=...`` assignment is rejected by the executor allowlist
    ("Command not in allowlist: PYTHONPATH=...") because the env-prefix is only
    stripped on the shell path (commands containing &&/|/>). The fix is to pass
    PYTHONPATH through executor_run's ``env`` argument. Both halves are asserted so
    build_mazda_scan_message can never silently regress to the broken form."""
    venv = server.MAZDA_RF_VENV_PY
    # The categorizer is a *script* invocation (`python3 tools/.../x.py`), so the
    # real failure was ModuleNotFoundError without PYTHONPATH; here we only need a
    # command whose first token triggers the allowlist, so a bare interpreter line
    # is enough to exercise the prefix-rejection path.
    probe = f'{venv} -c "print(\'PROBE_OK\')"'

    # OLD broken form — inline prefix makes `PYTHONPATH=...` the first token, which
    # the allowlist rejects before the command ever runs (the 2026-06-29 failure).
    code, body = _executor_run(
        f'PYTHONPATH={ROL_FINANCES_DIR} {probe}', cwd=ROL_FINANCES_DIR,
    )
    assert code == 400, f'expected allowlist rejection, got {code}: {body}'
    assert 'not in allowlist' in str(body)

    # NEW form — full venv path as the executable + PYTHONPATH via the env arg.
    # Allowlist accepts the venv python; the env reaches the child process.
    code, out = _executor_run(
        probe, cwd=ROL_FINANCES_DIR, env={'PYTHONPATH': ROL_FINANCES_DIR},
    )
    assert code == 200, f'env-arg form should be accepted: {out}'
    assert out['returncode'] == 0, f'stderr: {out.get("stderr")}'
    assert 'PROBE_OK' in out['stdout']

    # And PYTHONPATH genuinely arrives in the child via the env arg (not inlined).
    code, out = _executor_run(
        f'{venv} -c "import os; print(os.environ.get(\'PYTHONPATH\',\'MISSING\'))"',
        cwd=ROL_FINANCES_DIR, env={'PYTHONPATH': ROL_FINANCES_DIR},
    )
    assert code == 200 and ROL_FINANCES_DIR in out['stdout']


@pytest.mark.skipif(
    os.environ.get('MAZDA_RUN_CLASSIFY_INTEGRATION') != '1',
    reason='set MAZDA_RUN_CLASSIFY_INTEGRATION=1 to run the Gemini vision check (network + key)',
)
def test_classify_scan_identifies_a_receipt_image():
    """classify_scan.py (Gemini vision) is the fallback the scan message routes
    Mazda to when the text-extraction facade returns doc_kind=unknown for a JPEG.
    It must correctly identify a real scanned receipt. Network + Gemini key."""
    image = '/home/adamsl/planner/nonprofit_finance_db/receipt_scanning_tools/scan_freezer.jpg'
    if not os.path.isfile(image):
        pytest.skip(f'test image not present: {image}')
    proc = subprocess.run(
        [server.MAZDA_RF_VENV_PY, 'tools/classify_scan.py', image],
        cwd=ROL_FINANCES_DIR, env=dict(os.environ, PYTHONPATH=ROL_FINANCES_DIR),
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, f'stderr: {proc.stderr}'
    result = json.loads(proc.stdout[proc.stdout.find('{'):])
    assert result['doc_type'] in ('receipt', 'statement')
    assert result['confidence'] > 0
