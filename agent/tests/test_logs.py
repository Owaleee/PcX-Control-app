"""Logs em JSON por linha, com rotacao, sem senha, codigo ou token."""

import json
import logging
import secrets

import pytest

from pcx_agent.logs import setup_logging


@pytest.fixture(autouse=True)
def restore_root_logger():
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    for handler in root.handlers[:]:
        if handler not in handlers:
            root.removeHandler(handler)
            handler.close()
    root.setLevel(level)


def _flush():
    for handler in logging.getLogger().handlers:
        handler.flush()


def _lines(log_dir):
    _flush()
    return (log_dir / "agent.log").read_text(encoding="utf-8").splitlines()


def test_writes_one_json_object_per_line(tmp_path):
    setup_logging(tmp_path)
    logging.getLogger("pcx_agent.teste").info("primeira")
    try:
        raise ValueError("falhou")
    except ValueError:
        logging.getLogger("pcx_agent.teste").exception("segunda")
    records = [json.loads(line) for line in _lines(tmp_path)]
    assert [r["msg"] for r in records] == ["primeira", "segunda"]
    assert records[0]["level"] == "INFO"
    assert records[0]["logger"] == "pcx_agent.teste"
    assert records[0]["ts"].endswith("Z")
    assert "exc" not in records[0]
    assert "ValueError: falhou" in records[1]["exc"]


def test_rotation_keeps_five_files_of_1mib(tmp_path):
    setup_logging(tmp_path)
    logger = logging.getLogger("pcx_agent.teste")
    chunk = "linha de log " * 77  # ~1000 caracteres, sem cara de token
    for _ in range(6500):  # ~6,5 MiB
        logger.info(chunk)
    _flush()
    files = sorted(tmp_path.glob("agent.log*"))
    assert len(files) == 5
    assert all(f.stat().st_size <= 1_048_576 + 2048 for f in files)


def test_redacts_tokens_and_pairing_code(tmp_path):
    setup_logging(tmp_path)
    token = secrets.token_urlsafe(32)
    code = "Ab3_x"  # curto: so o c= da URI denuncia que e um codigo
    logging.getLogger("pcx_agent.teste").warning(
        "token %s e uri pcx://pair?v=1&id=abc&h=1.2.3.4&p=8765&c=%s fim", token, code
    )
    text = "\n".join(_lines(tmp_path))
    assert token not in text
    assert f"c={code}" not in text
    assert "[oculto]" in text
    assert "fim" in text


def test_uvicorn_errors_reach_the_file(tmp_path):
    setup_logging(tmp_path)
    logging.getLogger("uvicorn.error").error("porta ocupada")
    assert any(json.loads(line)["msg"] == "porta ocupada" for line in _lines(tmp_path))


def test_setup_twice_does_not_duplicate_lines(tmp_path):
    setup_logging(tmp_path)
    setup_logging(tmp_path)
    logging.getLogger("pcx_agent.teste").info("uma vez")
    assert len(_lines(tmp_path)) == 1


def test_console_handler_is_optional(tmp_path):
    setup_logging(tmp_path, console=True)
    kinds = {type(h).__name__ for h in logging.getLogger().handlers}
    assert "StreamHandler" in kinds
    assert "RotatingFileHandler" in kinds
