"""Pacote de suporte: um zip com relatorio, logs e configuracao, sem banco e sem segredos."""

import os
import re
import zipfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from pcx_agent.logs import redact

SUPPORT_NAME = "PcXControl-suporte-{:%Y%m%d-%H%M}.zip"
LOG_PATTERNS = ("agent.log*", "gpu.log*", "crash-*.log", "crash.log")
HOME_MARK = "%USERPROFILE%"
MIN_USER_LENGTH = 3  # nomes menores estragariam o texto ("ab" dentro de "tabela")
LEFT_OUT = "[Arquivos que ficaram de fora]"
_WORD = r"A-Za-z0-9_"


def scrub(text: str, home: str, user: str) -> str:
    """`redact`, depois a pasta do usuario e o nome dele viram %USERPROFILE%."""
    text = redact(text)
    parts = [p for p in re.split(r"[\\/]+", home.strip()) if p]
    if parts:
        sep = r"[\\/]+"
        # `home` com barra no inicio (/home/ana) ou unidade (C:): mantem o que veio antes dos nomes.
        prefix = "" if re.match(r"^[A-Za-z]:", home) else (sep if home[:1] in "\\/" else "")
        pattern = prefix + sep.join(re.escape(p) for p in parts)
        text = re.sub(pattern + rf"(?![{_WORD}])", lambda _m: HOME_MARK, text, flags=re.IGNORECASE)
    user = user.strip()
    if len(user) >= MIN_USER_LENGTH:
        pattern = rf"(?<![{_WORD}]){re.escape(user)}(?![{_WORD}])"
        text = re.sub(pattern, lambda _m: HOME_MARK, text, flags=re.IGNORECASE)
    return text


def choose_dest(candidates: list[Path], can_write: Callable[[Path], bool]) -> Path:
    """A primeira pasta onde da para gravar; sem nenhuma, a ultima (a pasta `logs`)."""
    for candidate in candidates:
        if can_write(candidate):
            return candidate
    return candidates[-1]


def _log_files(log_dir: Path) -> list[Path]:
    found: dict[str, Path] = {}
    try:
        for pattern in LOG_PATTERNS:
            for path in log_dir.glob(pattern):
                if path.is_file() and ".db" not in path.name:
                    found[path.name] = path
    except OSError:
        pass
    return [found[name] for name in sorted(found)]


def build_support_zip(
    dest_dir: Path,
    report: str,
    log_dir: Path,
    config_path: Path,
    now: datetime,
    home: str,
    user: str,
) -> Path:
    """Monta o zip em `dest_dir`. Arquivo que nao abre vai para a lista de fora, no relatorio."""
    contents: dict[str, str] = {}
    left_out: list[str] = []
    entries = [(f"logs/{p.name}", p) for p in _log_files(log_dir)] + [(config_path.name, config_path)]
    for entry, path in entries:
        if path.suffix == ".db" or path.name.endswith(("-wal", "-shm")):
            continue
        try:
            contents[entry] = path.read_bytes().decode("utf-8", errors="replace")
        except OSError as exc:
            left_out.append(f"- {entry}: {exc.strerror or exc}")
    text = report.rstrip() + "\n"
    if left_out:
        text += f"\n{LEFT_OUT}\n" + "\n".join(left_out) + "\n"
    target = dest_dir / SUPPORT_NAME.format(now)
    temp = target.with_name(target.name + ".part")
    try:  # nome temporario: falha no meio nao deixa um .zip truncado
        with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("relatorio.txt", scrub(text, home, user))
            for name, body in contents.items():
                archive.writestr(name, scrub(body, home, user))
        os.replace(temp, target)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    return target
