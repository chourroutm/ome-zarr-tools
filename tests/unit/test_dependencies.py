"""Static checks on which third-party packages this codebase's own modules
import -- not behavior, but a real, easily-regressed architectural boundary
(FR-005/FR-006): ``bioio_ome_zarr`` must be gone entirely, and ``ngff_zarr``
must be confined to ``migrate.py``.
"""

import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "ome_zarr_tools"


def _imported_top_level_modules(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(), filename=str(py_file))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def test_bioio_ome_zarr_is_imported_nowhere():
    offenders = [
        py_file
        for py_file in SRC_ROOT.rglob("*.py")
        if "bioio_ome_zarr" in _imported_top_level_modules(py_file)
    ]
    assert offenders == []


def test_ngff_zarr_is_imported_only_by_migrate():
    offenders = [
        py_file
        for py_file in SRC_ROOT.rglob("*.py")
        if "ngff_zarr" in _imported_top_level_modules(py_file) and py_file.name != "migrate.py"
    ]
    assert offenders == []
    assert "ngff_zarr" in _imported_top_level_modules(SRC_ROOT / "commands" / "migrate.py")
