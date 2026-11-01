"""Notas da release a partir do CHANGELOG, conferindo a versao nos arquivos.

Uso: python tools/release_notes.py agente-v0.3.0 --out notes.md
Tags: agente-vX.Y.Z (instalador do Windows) e app-vX.Y.Z (APK).
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TAG_RE = re.compile(r"^(agente|app)-v(\d+\.\d+\.\d+)$")
VERSION_FILES = {
    "agente": ["agent/pcx_agent/__init__.py", "agent/pyproject.toml"],
    "app": ["mobile/app.json"],
}


def parse_tag(tag: str) -> tuple[str, str]:
    match = TAG_RE.match(tag)
    if match is None:
        raise ValueError(f"Tag inválida: {tag!r}. Use agente-vX.Y.Z ou app-vX.Y.Z.")
    return match.group(1), match.group(2)


def changelog_section(text: str, component: str, version: str) -> str:
    title = f"## [{component} {version}]"
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(title):
            body = []
            for following in lines[index + 1 :]:
                if following.startswith("## ["):
                    break
                body.append(following)
            return "\n".join(body).strip() + "\n"
    raise ValueError(f"Seção '{component} {version}' não encontrada no CHANGELOG.")


def _version_in(relative: str) -> str:
    text = (ROOT / relative).read_text(encoding="utf-8")
    if relative.endswith(".json"):
        return json.loads(text)["expo"]["version"]
    pattern = r'^__version__ = "([^"]+)"' if relative.endswith(".py") else r'^version = "([^"]+)"'
    match = re.search(pattern, text, re.MULTILINE)
    if match is None:
        raise ValueError(f"Versão não encontrada em {relative}.")
    return match.group(1)


def read_versions(component: str) -> dict[str, str]:
    return {path: _version_in(path) for path in VERSION_FILES[component]}


def check_versions(component: str, version: str, found: dict[str, str]) -> None:
    wrong = {path: v for path, v in found.items() if v != version}
    if wrong:
        details = ", ".join(f"{path} = {v}" for path, v in wrong.items())
        raise ValueError(f"A tag pede {component} {version}, mas: {details}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        component, version = parse_tag(args.tag)
        check_versions(component, version, read_versions(component))
        notes = changelog_section(
            (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), component, version
        )
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    args.out.write_text(notes, encoding="utf-8")
    print(f"Notas de {component} {version} gravadas em {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
