import importlib.util
import sys
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(FIXTURES_DIR))

import make_fixtures  # noqa: E402

HAS_DOCLING = importlib.util.find_spec("docling") is not None


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if HAS_DOCLING:
        return
    skip = pytest.mark.skip(reason="extra 'docling' não instalado")
    for item in items:
        if "docling" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def pdfs() -> dict[str, Path]:
    """PDFs sintéticos (gerados uma vez em tests/fixtures/, ignorados pelo git)."""
    return make_fixtures.build(FIXTURES_DIR)
