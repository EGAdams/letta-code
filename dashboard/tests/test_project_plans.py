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


def test_voice_communication_plan_defines_the_new_design_protocol():
    plan = VOICE_COMMUNICATION_PLAN.read_text(encoding="utf-8")

    assert "SOLID Change Protocol" in plan
    assert "Gang of Four First" in plan
    assert "Single Responsibility Principle" in plan
    assert "Open/Closed Principle" in plan
    assert "Liskov Substitution Principle" in plan
    assert "Interface Segregation Principle" in plan
    assert "Dependency Inversion Principle" in plan
    assert "voice_agent" in plan
    assert "Pipecat" in plan
    assert "VoiceSession" in plan
    assert "ConversationCoordinator" in plan
    assert "PipelineFactory" in plan
    assert "LettaAgentAdapter" in plan


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
