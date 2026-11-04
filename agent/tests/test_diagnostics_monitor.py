"""Testes do monitor do alerta do diagnostico."""

from pcx_agent.diagnostics.model import CheckResult
from pcx_agent.diagnostics.monitor import (
    ALERT_EXCLUDED,
    ALERT_STATUSES,
    DiagnosticsMonitor,
)


def res(id_: str, status: str, detail: str = "") -> CheckResult:
    return CheckResult(id_, "Grupo", id_, status, detail)  # type: ignore[arg-type]


class Harness:
    def __init__(self) -> None:
        self.now = 1000.0
        self.changes: list[frozenset[str]] = []
        self.notified: list[CheckResult] = []
        self.monitor = DiagnosticsMonitor(
            self.changes.append, self.notified.append, clock=lambda: self.now
        )

    def update(self, results: list[CheckResult], ran: set[str] | None = None) -> None:
        self.monitor.update(results, ran if ran is not None else {r.id for r in results})


def test_constants() -> None:
    assert ALERT_STATUSES == frozenset({"problema", "atencao"})
    assert ALERT_EXCLUDED == frozenset({"rede.vpn"})


def test_problem_enters_alert_and_notifies_once() -> None:
    h = Harness()
    h.update([res("rede.tipo", "problema")])
    h.update([res("rede.tipo", "problema")])
    assert h.changes == [frozenset({"rede.tipo"})]
    assert [r.id for r in h.notified] == ["rede.tipo"]
    assert h.monitor.alert_ids == frozenset({"rede.tipo"})


def test_info_and_vpn_never_alert() -> None:
    h = Harness()
    h.update([res("sensores.gpu", "info"), res("rede.vpn", "atencao")])
    assert h.monitor.alert_ids == frozenset()
    assert h.changes == []
    assert h.notified == []


def test_cleared_then_back_notifies_again() -> None:
    h = Harness()
    h.update([res("rede.tipo", "problema")])
    h.now += 601
    h.update([res("rede.tipo", "ok")])
    assert h.monitor.alert_ids == frozenset()
    h.now += 601
    h.update([res("rede.tipo", "problema")])
    assert len(h.notified) == 2
    assert h.changes == [frozenset({"rede.tipo"}), frozenset(), frozenset({"rede.tipo"})]


def test_partial_run_keeps_other_ids() -> None:
    h = Harness()
    h.update([res("rede.firewall", "problema"), res("rede.tipo", "ok")])
    h.update([res("rede.tipo", "ok")], ran={"rede.tipo"})
    assert h.monitor.alert_ids == frozenset({"rede.firewall"})


def test_ran_id_without_result_is_cleared() -> None:
    h = Harness()
    h.update([res("rede.firewall", "problema")])
    h.update([], ran={"rede.firewall"})
    assert h.monitor.alert_ids == frozenset()


def test_many_problems_one_notification_then_rest_after_gap() -> None:
    h = Harness()
    h.update([res("a", "problema"), res("b", "problema"), res("c", "problema")])
    assert len(h.notified) == 1
    h.now += 599
    h.update([res("a", "problema"), res("b", "problema"), res("c", "problema")])
    assert len(h.notified) == 1
    h.now += 1
    h.update([res("a", "problema"), res("b", "problema"), res("c", "problema")])
    assert len(h.notified) == 2
    h.now += 600
    h.update([res("a", "problema"), res("b", "problema"), res("c", "problema")])
    assert sorted(r.id for r in h.notified) == ["a", "b", "c"]
    assert len(h.changes) == 1


def test_pending_dropped_if_cleared_before_gap() -> None:
    h = Harness()
    h.update([res("a", "problema"), res("b", "problema")])
    h.now += 700
    h.update([res("b", "ok")])
    h.now += 700
    h.update([res("b", "ok")])
    assert len(h.notified) == 1


def test_multiple_results_same_id_uses_worst() -> None:
    h = Harness()
    h.update(
        [
            res("antivirus.terceiros", "ok"),
            res("antivirus.terceiros", "problema", "pior"),
            res("antivirus.terceiros", "atencao"),
        ]
    )
    assert h.monitor.alert_ids == frozenset({"antivirus.terceiros"})
    assert h.notified[0].status == "problema"
    assert h.notified[0].detail == "pior"
