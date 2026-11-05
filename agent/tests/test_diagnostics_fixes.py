"""Correcoes do diagnostico que nao dependem do Windows: busca de porta livre."""

import socket

from pcx_agent.diagnostics import fixes


def test_find_free_port_skips_busy():
    busy = {8766}
    assert fixes.find_free_port(8766, is_free=lambda p: p not in busy) == 8767


def test_find_free_port_gives_up_after_20():
    tried = []

    def never(port: int) -> bool:
        tried.append(port)
        return False

    assert fixes.find_free_port(9000, is_free=never) is None
    assert tried == list(range(9000, 9020))


def test_find_free_port_stops_at_the_last_valid_port():
    assert fixes.find_free_port(65535, is_free=lambda p: False) is None


def test_port_is_free_sees_a_listening_socket():
    with socket.socket() as taken:
        taken.bind(("0.0.0.0", 0))
        taken.listen()
        assert fixes.port_is_free(taken.getsockname()[1]) is False
