"""Log de falhas repetidas sem encher o arquivo: no maximo uma linha por minuto por tipo."""

import logging
import time
from collections.abc import Callable


class RateLimitedLog:
    """`report(key, ...)` vai para o log como aviso no maximo uma vez a cada `interval_s` por `key`.

    As repeticoes dentro do intervalo descem para DEBUG: nao aparecem no log normal, mas nao
    somem de vez para quem liga o nivel de depuracao.
    """

    def __init__(
        self,
        logger: logging.Logger,
        interval_s: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._logger = logger
        self._interval = interval_s
        self._clock = clock
        self._last: dict[str, float] = {}

    def report(self, key: str, msg: str, *args: object, exc_info: bool = False) -> None:
        now = self._clock()
        last = self._last.get(key)
        if last is None or now - last >= self._interval:
            self._last[key] = now
            self._logger.warning(msg, *args, exc_info=exc_info)
        else:
            self._logger.debug(msg, *args, exc_info=exc_info)
