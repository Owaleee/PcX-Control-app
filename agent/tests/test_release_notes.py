"""tools/release_notes.py: tag do componente, notas do CHANGELOG e versoes conferidas."""

import importlib.util
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "release_notes.py"
spec = importlib.util.spec_from_file_location("release_notes", TOOL)
release_notes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_notes)

CHANGELOG = """# Changelog

## [Não lançado]

## [agente 0.3.0] - 2026-11-02

Bandeja do Windows.

### Adicionado
- Instalador.

## [app 0.2.1] - 2026-11-02

- Correção no app.

## [0.2.0] - 2026-11-01

Primeira versão do app.
"""


@pytest.mark.parametrize(
    ("tag", "expected"),
    [("agente-v0.3.0", ("agente", "0.3.0")), ("app-v0.2.1", ("app", "0.2.1"))],
)
def test_parse_tag_accepts_agent_and_app(tag, expected):
    assert release_notes.parse_tag(tag) == expected


@pytest.mark.parametrize("tag", ["v0.3.0", "agente-0.3.0", "cli-v1.0.0", "agente-v1.0", ""])
def test_parse_tag_rejects_old_and_unknown_formats(tag):
    with pytest.raises(ValueError):
        release_notes.parse_tag(tag)


def test_extracts_only_requested_section():
    body = release_notes.changelog_section(CHANGELOG, "agente", "0.3.0")
    assert body.startswith("Bandeja do Windows.")
    assert "- Instalador." in body
    assert "app 0.2.1" not in body
    assert "## [" not in body


def test_missing_section_raises():
    with pytest.raises(ValueError, match="agente 9.9.9"):
        release_notes.changelog_section(CHANGELOG, "agente", "9.9.9")


def test_versions_must_match_tag():
    release_notes.check_versions(
        "agente", "0.3.0", {"agent/pcx_agent/__init__.py": "0.3.0", "agent/pyproject.toml": "0.3.0"}
    )
    with pytest.raises(ValueError, match=r"agent/pyproject\.toml.*0\.2\.0"):
        release_notes.check_versions(
            "agente",
            "0.3.0",
            {"agent/pcx_agent/__init__.py": "0.3.0", "agent/pyproject.toml": "0.2.0"},
        )


def test_reads_real_version_files():
    found = release_notes.read_versions("agente")
    assert set(found) == {"agent/pcx_agent/__init__.py", "agent/pyproject.toml"}
    assert len(set(found.values())) == 1
    assert set(release_notes.read_versions("app")) == {"mobile/app.json"}
