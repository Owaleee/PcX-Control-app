"""Instancia unica: abrir o agente duas vezes nao sobe dois servidores."""

import sys

import pytest

from pcx_agent.winsys.instance import MUTEX_NAME, acquire_single_instance


def test_mutex_name_matches_installer():
    assert MUTEX_NAME == "Local\\PcXControl.Agent"


@pytest.mark.skipif(sys.platform == "win32", reason="no Windows vale o mutex")
def test_second_lock_is_refused(tmp_path):
    first = acquire_single_instance(tmp_path)
    assert first is not None
    try:
        assert acquire_single_instance(tmp_path) is None
    finally:
        first.release()


@pytest.mark.skipif(sys.platform == "win32", reason="no Windows vale o mutex")
def test_lock_is_free_after_release(tmp_path):
    acquire_single_instance(tmp_path).release()
    again = acquire_single_instance(tmp_path)
    assert again is not None
    again.release()


@pytest.mark.windows
@pytest.mark.skipif(sys.platform != "win32", reason="mutex nomeado do Windows")
def test_windows_mutex_refuses_second(tmp_path):
    first = acquire_single_instance(tmp_path)
    assert first is not None
    try:
        assert acquire_single_instance(tmp_path) is None
    finally:
        first.release()
    again = acquire_single_instance(tmp_path)
    assert again is not None
    again.release()
