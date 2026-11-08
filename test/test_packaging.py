"""Library-readiness checks: what a consumer sees after `pip install`."""
import ast
import importlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "metaprobe"
# distribution name -> import name, where they differ
IMPORT_NAMES = {"beautifulsoup4": "bs4"}


def test_package_imports_cleanly():
    assert importlib.import_module("metaprobe")


def test_declared_dependencies_match_actual_imports():
    tomllib = pytest.importorskip("tomllib")  # stdlib on 3.11+
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"][
        "dependencies"
    ]
    declared = {
        IMPORT_NAMES.get(n, n)
        for n in (re.split(r"[<>=!~\[ ;]", d, maxsplit=1)[0].lower() for d in deps)
    }
    imported = set()
    for path in SRC.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])
    assert declared - imported == set(), "declared but never imported"
    assert {"httpx", "bs4"} <= declared, "imported but not declared"


@pytest.mark.xfail(strict=True, reason="README.md is empty")
def test_readme_is_not_empty():
    assert (ROOT / "README.md").stat().st_size > 200


@pytest.mark.xfail(strict=True, reason="LICENSE is empty")
def test_license_is_not_empty():
    assert (ROOT / "LICENSE").stat().st_size > 200


@pytest.mark.xfail(strict=True, reason="__init__.py exports nothing")
def test_public_api_importable_from_top_level():
    mod = importlib.import_module("metaprobe")
    assert hasattr(mod, "MetadataExtractor")


@pytest.mark.xfail(strict=True, reason="no __version__")
def test_version_exposed():
    assert hasattr(importlib.import_module("metaprobe"), "__version__")


@pytest.mark.xfail(strict=True, reason="no py.typed marker; mypy users get Any")
def test_py_typed_marker_present():
    assert (SRC / "py.typed").is_file()
