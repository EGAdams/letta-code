"""Project Plans navigation and living-plan document contracts."""

from pathlib import Path
import re


DASHBOARD_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DASHBOARD_DIR.parent
DASHBOARD_HTML = DASHBOARD_DIR / "dashboard.html"
SERVER_REWRITE_PLAN = REPO_ROOT / "notes_plans_handoffs" / "codebase_rewrite.html"
VOICE_COMMUNICATION_PLAN = (
    REPO_ROOT.parent / "talking_agent_parts" / "voice_communication_plan.html"
)
VOICE_COMMUNICATION_DASHBOARD_LINK = (
    DASHBOARD_DIR / "voice_communication_plan.html"
)
# The original single-document plan, preserved verbatim when the tab became an
# interface workspace. Linked from the workspace's Overview and Design Protocol.
VOICE_COMMUNICATION_PLAN_V1 = (
    REPO_ROOT.parent / "talking_agent_parts" / "voice_communication_plan_v1.html"
)
VOICE_COMMUNICATION_V1_DASHBOARD_LINK = (
    DASHBOARD_DIR / "voice_communication_plan_v1.html"
)
VOICE_WORKSPACE_DIR = DASHBOARD_DIR / "js" / "plans" / "voice-communication"
PLAN_MODULES_DIR = DASHBOARD_DIR / "js" / "plans"


def _voice_workspace_source() -> str:
    """Every spec module's text, concatenated — the workspace's content."""
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(VOICE_WORKSPACE_DIR.rglob("*.js"))
    )


def test_voice_communication_tab_targets_the_external_plan_source():
    dashboard = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert (
        'data-nav="plans" data-target="plans-voice-communication">Voice Communication'
        in dashboard
    )
    section = re.search(
        r'<section id="plans-voice-communication" class="view">(.*?)</section>',
        dashboard,
        re.DOTALL,
    )
    assert section is not None
    assert 'id="voice-communication-plan-frame"' in section.group(1)
    assert 'class="plan-frame"' in section.group(1)
    assert 'src="/voice_communication_plan.html"' in section.group(1)
    assert VOICE_COMMUNICATION_DASHBOARD_LINK.is_symlink()
    assert (
        VOICE_COMMUNICATION_DASHBOARD_LINK.resolve()
        == VOICE_COMMUNICATION_PLAN.resolve()
    )


def test_voice_communication_page_is_an_spa_shell_not_a_document():
    """The tab is a workspace shell; its content lives in reusable modules."""
    plan = VOICE_COMMUNICATION_PLAN.read_text(encoding="utf-8")

    assert 'id="workspace-nav"' in plan
    assert 'id="workspace-content"' in plan
    assert '/js/plans/voice-communication/boot.js' in plan
    assert '/css/plan-workspace.css' in plan
    # Mermaid + pan/zoom must both be present, or diagrams cannot be inspected.
    assert "mermaid@10" in plan
    assert "svg-pan-zoom" in plan
    # The shell must stay a shell: no per-interface markup hard-coded into it.
    assert "Responsibility" not in plan
    assert len(plan.splitlines()) < 60


def test_the_original_plan_document_is_preserved_and_reachable():
    assert VOICE_COMMUNICATION_PLAN_V1.is_file()
    assert VOICE_COMMUNICATION_V1_DASHBOARD_LINK.is_symlink()
    assert (
        VOICE_COMMUNICATION_V1_DASHBOARD_LINK.resolve()
        == VOICE_COMMUNICATION_PLAN_V1.resolve()
    )
    v1 = VOICE_COMMUNICATION_PLAN_V1.read_text(encoding="utf-8")
    assert "SOLID Change Protocol" in v1
    assert "Gang of Four First" in v1
    # ...and the workspace links to it rather than orphaning it.
    assert "/voice_communication_plan_v1.html" in _voice_workspace_source()


def test_voice_communication_workspace_keeps_the_design_protocol():
    source = _voice_workspace_source()

    assert "SOLID Change Protocol" in source
    assert "Gang of Four First" in source
    assert "Single Responsibility" in source
    assert "Open/Closed" in source
    assert "Liskov Substitution" in source
    assert "Interface Segregation" in source
    assert "Dependency Inversion" in source
    assert "Pipecat" in source
    assert "voice_agent" in source


def test_voice_communication_workspace_covers_every_planned_interface():
    source = _voice_workspace_source()

    for name in (
        "VoiceSession",
        "ConversationCoordinator",
        "IConversationAgent",
        "LettaAgentAdapter",
        "DetectionInterface",
        "LanguageProcessor",
        "PipelineFactory",
    ):
        assert name in source, f"{name} has no coverage in the workspace"


def test_voice_communication_workspace_documents_the_shipped_seams():
    """The tabs must reflect the code that exists, not only the plan's names."""
    source = _voice_workspace_source()

    for port in (
        "ContinuousListener",
        "VoiceRecorder",
        "TranscriptionStrategy",
        "RouteStrategy",
        "CommandCompletenessStrategy",
        "NoteCommandInterpreter",
        "NoteRepository",
        "NoteDocument",
        "SpeechSynthesizer",
    ):
        assert port in source, f"shipped port {port} is undocumented"


def test_each_interface_tab_is_its_own_spec_file():
    """One file per tab, so adding an interface never edits a shared blob."""
    spec_files = sorted(p.stem for p in (VOICE_WORKSPACE_DIR / "specs").glob("*.js"))
    assert len(spec_files) >= 13
    index = (VOICE_WORKSPACE_DIR / "index.js").read_text(encoding="utf-8")
    for stem in spec_files:
        assert f'./specs/{stem}.js' in index, f"{stem} is not wired into the nav"
    # No spec file may grow into a second one's territory.
    for path in (VOICE_WORKSPACE_DIR / "specs").glob("*.js"):
        assert path.read_text(encoding="utf-8").count("export const ") == 1


def test_workspace_modules_are_reusable_and_project_agnostic():
    """The shell/renderer/mermaid modules must not know about voice work."""
    for module in ("interface-spec.js", "interface-page.js", "interface-workspace.js",
                   "mermaid-view.js"):
        text = (PLAN_MODULES_DIR / module).read_text(encoding="utf-8")
        lowered = text.lower()
        for leaked in ("voicesession", "letta", "toyota", "whisper"):
            assert leaked not in lowered, f"{module} leaks {leaked}"


def test_server_rewrite_tab_targets_the_plan_iframe():
    dashboard = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert (
        'data-nav="plans" data-target="plans-codebase-rewrite">Codebase Rewrite'
        in dashboard
    )
    section = re.search(
        r'<section id="plans-codebase-rewrite" class="view">(.*?)</section>',
        dashboard,
        re.DOTALL,
    )
    assert section is not None
    assert 'id="codebase-rewrite-plan-frame"' in section.group(1)
    assert 'class="plan-frame"' in section.group(1)
    assert 'src="/notes_plans_handoffs/codebase_rewrite.html"' in section.group(1)


def test_server_rewrite_plan_is_a_source_controlled_shrinking_ledger():
    plan = SERVER_REWRITE_PLAN.read_text(encoding="utf-8")

    baseline_match = re.search(r'data-baseline-total="(\d+)"', plan)
    assert baseline_match is not None
    baseline_total = int(baseline_match.group(1))
    active_rows = len(re.findall(r"<tr data-work-item\b", plan))

    assert baseline_total == active_rows
    assert active_rows >= 40
    assert "Program to the Interface" in plan
    assert "Completed work rows are deleted" in plan
    assert "Git is the completion history" in plan


def test_server_rewrite_requires_strict_typed_contracts():
    plan = SERVER_REWRITE_PLAN.read_text(encoding="utf-8")

    assert "Pydantic v2 is mandatory" in plan
    assert "ConfigDict(strict=True, extra=&quot;forbid&quot;, frozen=True)" in plan
    assert "dict[str, Any]" in plan
    assert "All new frontend code is TypeScript" in plan
    assert "tsc --noEmit" in plan
    assert "pyright --project dashboard/pyrightconfig.json" in plan
    assert "typeCheckingMode = &quot;strict&quot;" in plan
    assert "No blind type assertions" in plan


def test_server_rewrite_requires_test_first_red_green_refactor():
    plan = SERVER_REWRITE_PLAN.read_text(encoding="utf-8")

    assert "Red &rarr; Green &rarr; Refactor" in plan
    assert "No production Interface or Object is written before its failing test" in plan
    assert "Characterization tests" in plan
    assert "Shared contract tests" in plan
    assert "Negative validation tests" in plan
    assert "100% branch coverage" in plan
    assert "Observed RED:" in plan


def test_every_server_rewrite_row_names_a_port_object_and_exit_test():
    plan = SERVER_REWRITE_PLAN.read_text(encoding="utf-8")
    rows = re.findall(r"<tr data-work-item(?P<attrs>[^>]*)>(?P<body>.*?)</tr>", plan)

    assert rows
    for attrs, body in rows:
        assert 'data-port="' in attrs
        assert 'data-object="' in attrs
        assert 'class="port"' in body
        assert 'class="object"' in body
        cells = re.findall(r"<td(?: [^>]*)?>(.*?)</td>", body, re.DOTALL)
        assert len(cells) == 5
        assert re.sub(r"<[^>]+>", "", cells[-1]).strip()
