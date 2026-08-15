import ast
from pathlib import Path


DASHBOARD_DIR = Path(__file__).resolve().parents[1]


def _imports(module_name):
    tree = ast.parse((DASHBOARD_DIR / module_name).read_text())
    return {
        node.names[0].name.split(".")[0]
        if isinstance(node, ast.Import)
        else (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    }


def test_annotation_contracts_remain_independent_of_io_adapters():
    imports = _imports("document_annotation_contracts.py")

    assert imports.isdisjoint(
        {
            "codex_image_region_fallback",
            "document_annotation",
            "json",
            "os",
            "pathlib",
            "shutil",
            "subprocess",
        }
    )


def test_codex_adapter_depends_on_contracts_not_annotation_implementation():
    imports = _imports("codex_image_region_fallback.py")

    assert "document_annotation_contracts" in imports
    assert "document_annotation" not in imports
