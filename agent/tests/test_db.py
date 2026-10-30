import threading
import uuid

from pcx_agent.config import load_settings
from pcx_agent.storage.db import Database


def test_agent_id_is_stable_across_reopen(tmp_path):
    path = tmp_path / "pcx.db"
    first = Database(path)
    first_id = first.agent_id
    first.close()
    second = Database(path)
    assert second.agent_id == first_id
    assert str(uuid.UUID(first_id)) == first_id
    second.close()


def test_set_get_setting(tmp_path):
    db = Database(tmp_path / "pcx.db")
    assert db.get_setting("chave") is None
    db.set_setting("chave", "valor")
    db.set_setting("chave", "novo")
    assert db.get_setting("chave") == "novo"
    db.close()


def test_schema_has_tables(tmp_path):
    db = Database(tmp_path / "pcx.db")
    names = {row["name"] for row in db.query("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"settings", "devices", "history"} <= names
    db.close()


def test_concurrent_writes_from_threads(tmp_path):
    db = Database(tmp_path / "pcx.db")
    errors: list[Exception] = []

    def work(worker: int) -> None:
        try:
            for i in range(50):
                db.execute(
                    "INSERT INTO history (ts, metric, avg, max) VALUES (?, ?, 1, 1)",
                    (float(i), f"m{worker}"),
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert db.query("SELECT COUNT(*) AS n FROM history")[0]["n"] == 400
    db.close()


def test_load_settings_creates_dir(tmp_path):
    target = tmp_path / "dados" / "pcx"
    settings = load_settings(data_dir=target, port=9000)
    assert target.is_dir()
    assert settings.port == 9000
    assert settings.data_dir == target


def test_load_settings_default_port(tmp_path):
    assert load_settings(data_dir=tmp_path).port == 8765


def test_wal_with_normal_synchronous(tmp_path):
    db = Database(tmp_path / "pcx.db")
    assert db.query("PRAGMA journal_mode")[0][0] == "wal"
    assert db.query("PRAGMA synchronous")[0][0] == 1  # NORMAL
    db.close()
