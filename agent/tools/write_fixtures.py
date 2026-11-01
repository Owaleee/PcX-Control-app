"""Gera docs/protocol/fixtures/*.json a partir do codigo do agente.

Uso (dentro de agent/):  python tools/write_fixtures.py
"""

import json

from pcx_agent.contract import FIXTURES_DIR, build_fixtures

FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
for name, value in build_fixtures().items():
    path = FIXTURES_DIR / f"{name}.json"
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"escrito {path}")
