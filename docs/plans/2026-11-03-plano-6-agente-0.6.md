# PcX Control — Plano 6: diagnóstico automático, pacote de suporte e agente estável (agente 0.6.0, app 0.5.0)

> **Para quem executa:** seguir tarefa por tarefa, na ordem. Cada passo usa checkbox (`- [ ]`).
> TDD: o teste vem antes e precisa falhar antes do código.

**Objetivo:** o agente avisa sozinho quando algo dá errado, corrige o que é dele, gera um pacote
de suporte num arquivo só, escolhe a placa de rede pelo tipo e registra travamentos e erros de GPU
à parte. O app explica quando a versão do PC e a do celular não combinam.

**Arquitetura:** a lógica nova fica em funções e classes puras, com relógio e entradas injetáveis:
`diagnostics/monitor.py`, `diagnostics/support.py`, `tray/alerts.py`, `network.choose_lan`,
`d3dkmt.parse_perfdata_caps` e `mobile/src/protocol/compat.ts`. As chamadas do Windows
(`GetAdaptersAddresses`, `CheckInterfaceSupport`, `SHGetKnownFolderPath`) ficam em módulos
próprios em `winsys/` e `sensors/windows/`, testados na CI do Windows.

**Tecnologias:** Python 3.13, FastAPI/Uvicorn, tkinter + pystray, ctypes, pytest; Expo SDK 58,
TypeScript, Jest.

**Spec:** `docs/specs/2026-11-03-agente-0.6-suporte-design.md`. Base: spec e código do agente
0.5.0 (`docs/specs/2026-11-02-diagnostico-design.md`).

## Restrições globais

- Agente `0.6.0`, app `0.5.0`; protocolo `1`, só acréscimos (`temp_warn_c` em cada GPU).
- Logs, relatório e pacote de suporte nunca trazem senha, código ou token (`logs.redact`).
- Textos da bandeja só em `tray/texts.py`; cores só em `tray/theme.py`; janelas com até ~150 linhas.
- Verificações automáticas a cada **5 minutos**; primeira rodada **10 s** depois de iniciar.
- Notificação: uma por `id` que entra no alerta, no máximo **uma a cada 10 minutos** no total.
- Leitura parada: mais de **30 s** sem leitura nova.
- Troca de porta: a partir de `porta + 1`, até **20** tentativas.
- Crash por arquivo: ficam os **10** mais recentes. `gpu.log`: 2 arquivos de **512 KiB**.
- Commits no nome do Alexandre, em português, padrão Conventional Commits, sem coautor.

## Desvio do spec (decidido antes de começar)

**Fechamento inesperado e desligamento do PC.** No desligamento ou reinício do Windows, o
processo pode ser encerrado sem rodar o `atexit`. O `crash.log` ficaria sem "encerrado
normalmente" depois de todo reinício, e o aviso apareceria sempre. Por isso só conta como
fechamento inesperado se a última linha do `agent.log` da execução anterior for **depois do
último boot** (`psutil.boot_time()`). O horário mostrado é o dessa última linha.

**Clique na notificação.** O `pystray` não avisa quando a pessoa clica na notificação do
Windows. No lugar disso, com o alerta aceso, a **ação padrão do ícone** (clique duplo) passa de
"Parear celular" para "Verificar conexão" e volta quando o alerta apaga (Tarefa 8).

## Revisão de riscos (cada um tem teste na tarefa dona)

1. **Callbacks fora da thread do Tk:** o monitor e o evento de sensor rodam na thread do
   diagnóstico ou do coletor; tocar no Tk ou no pystray dali trava a bandeja. Tudo passa pelo
   `ui` injetado (o `Dispatcher`). Teste na Tarefa 8.
2. **`config.json` ilegível ou sem permissão na troca de porta:** a correção devolve `False`, não
   derruba o agente e a porta antiga continua. Teste na Tarefa 3.
3. **Arquivo de log preso ou ilegível ao montar o pacote** (o Windows segura o `agent.log`, ou
   falta permissão): o `.zip` sai mesmo assim e o `relatorio.txt` lista o que ficou de fora.
   Teste na Tarefa 7.
4. **Área de Trabalho sem permissão ou do OneDrive fora do ar:** cai para Documentos e depois para
   `logs`. Teste na Tarefa 7.
5. **Vários problemas ao mesmo tempo na primeira rodada:** uma notificação só; as outras saem nas
   rodadas seguintes, respeitando os 10 minutos. Teste na Tarefa 1.

---

### Tarefa 1: monitor do alerta

**Arquivos:** criar `agent/pcx_agent/diagnostics/monitor.py` e `agent/tests/test_diagnostics_monitor.py`.

**Interfaces:**
- Produz:
  - `ALERT_STATUSES = frozenset({"problema", "atencao"})`
  - `ALERT_EXCLUDED = frozenset({"rede.vpn"})`
  - `DiagnosticsMonitor(on_alert_change: Callable[[frozenset[str]], None], on_notify: Callable[[CheckResult], None], clock: Callable[[], float] = time.monotonic, notify_gap_s: float = 600.0)`
  - `update(results: list[CheckResult], ran: set[str]) -> None`. `ran` são os `id`s que rodaram nesta vez; só eles são substituídos, os outros ficam como estavam.
  - `alert_ids: frozenset[str]` (propriedade).

- [ ] **Passo 1: testes que falham**
  - `test_problem_enters_alert_and_notifies_once`: `rede.tipo` em `problema` em duas rodadas → `on_alert_change` uma vez com `{"rede.tipo"}`; `on_notify` uma vez.
  - `test_info_and_vpn_never_alert`: `info` em `sensores.gpu` e `atencao` em `rede.vpn` → `alert_ids == frozenset()`.
  - `test_cleared_then_back_notifies_again` (após mais de 600 s no relógio falso).
  - `test_partial_run_keeps_other_ids`: firewall em `problema` numa rodada completa; rodada com `ran={"rede.tipo"}` não apaga `rede.firewall`.
  - `test_many_problems_one_notification_then_rest_after_gap` (risco 5): três `id`s em `problema` → uma notificação; com o relógio em +599 s, nenhuma; em +600 s, a segunda.
  - `test_multiple_results_same_id_uses_worst` (`antivirus.terceiros` vem um por produto).
- [ ] **Passo 2:** `cd agent && pytest tests/test_diagnostics_monitor.py -v` → FAIL (módulo não existe).
- [ ] **Passo 3:** implementar. Quem ainda não foi notificado fica pendente e sai na próxima `update` depois do intervalo, se continuar no alerta.
- [ ] **Passo 4:** os mesmos testes → PASS.
- [ ] **Passo 5:** `git commit -m "feat(agent): monitor do alerta do diagnostico"`

### Tarefa 2: leitura parada, estado do servidor e verificações parciais

**Arquivos:** `sampler.py`, `server.py`, `diagnostics/checks.py`, `diagnostics/runner.py`, `diagnostics/model.py`, `main.py`; testes em `test_sampler.py`, `test_server.py`, `test_diagnostics_checks.py`, `test_diagnostics_runner.py`, `test_run_tray.py`.

**Interfaces:**
- Produz:
  - `Sampler.latest_at: float | None`: relógio do `Sampler` na última leitura boa.
  - `AgentServer.start_error: Literal["port_in_use", "other"] | None`, `AgentServer.port: int` e `AgentServer.restart(port: int | None = None) -> None`. `restart` chama `stop` e `start` e grava `start_error` em vez de lançar exceção.
  - `Fix` ganha `"reiniciar_sensores" | "reiniciar_servidor" | "trocar_porta" | "copiar_caminho" | "salvar_pacote"`.
  - `check_reading(snapshot, error, age_s: float | None = None, stale_after_s: float = 30.0)`: com `age_s > 30` dá `problema` ("Os sensores pararam de responder há N s."); com `problema`, `fix="reiniciar_sensores"`.
  - `check_agent(probe, address, server_error: str | None = None, server_running: bool = True)`:
    - `port_in_use` → `fix="trocar_porta"`;
    - servidor parado → `fix="reiniciar_servidor"`;
    - outro programa respondendo → `fix="trocar_porta"`.
  - `check_antivirus`: cada produto de terceiros ganha `fix="copiar_caminho"` e o detalhe "Libere este programa no {nome}."
  - `Sources` ganha `reading_age: Callable[[], float | None] = lambda: None` e `server_state: Callable[[], tuple[str | None, bool]] = lambda: (None, True)`, com padrão para os testes atuais seguirem.
  - `run_all(sources, only: set[str] | None = None) -> list[CheckResult]`: com `only`, roda só aqueles `id`s.
  - `QUICK_CHECKS = frozenset({"rede.ip", "rede.tipo", "sensores.leitura"})` em `runner.py`.
  - `run_tray`: com `PortInUseError`, **não sai mais**; segue para a bandeja com `server.start_error == "port_in_use"` (o alerta da Tarefa 8 avisa). O `texts.PORT_IN_USE` sai da caixa de erro.

- [ ] **Passo 1: testes que falham**
  - `test_latest_at_updates_on_good_read_only`
  - `test_restart_records_port_in_use` (porta ocupada por um socket do teste)
  - `test_reading_stale_after_30s[29→ok, 31→problema]`
  - `test_agent_port_in_use_offers_trocar_porta`
  - `test_agent_stopped_offers_restart`
  - `test_antivirus_offers_copy_path`
  - `test_run_all_only_runs_selected`
  - `test_run_tray_continues_when_port_in_use` (bandeja falsa recebe o servidor com `start_error`)
- [ ] **Passo 2:** `pytest tests/test_sampler.py tests/test_server.py tests/test_diagnostics_checks.py tests/test_diagnostics_runner.py tests/test_run_tray.py -v` → os novos FAIL.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** `pytest -q` → tudo PASS.
- [ ] **Passo 5:** `git commit -m "feat(agent): leitura parada, estado do servidor e verificacoes parciais"`

### Tarefa 3: correções novas

**Arquivos:** `diagnostics/fixes.py`, `config.py`, `controller.py`, `sensors/windows/provider.py`, `sensors/fake.py`, `tray/diagnostics_rows.py`, `tray/diagnostics_window.py`, `tray/texts.py`; testes em `test_diagnostics_fixes.py` (novo), `test_config_file.py`, `test_controller_diagnostics.py`, `test_windows_provider_logic.py`, `test_tray_windows.py`.

**Interfaces:**
- Consome: `AgentServer.restart`, `AgentServer.port` e `Fix` (Tarefa 2).
- Produz:
  - `fixes.find_free_port(start: int, attempts: int = 20, is_free: Callable[[int], bool] = port_is_free) -> int | None`. `port_is_free` usa o mesmo `bind` de `server._ensure_port_free`.
  - `config.save_port(path: Path, port: int) -> bool`: preserva as outras chaves; JSON ilegível ou `OSError` → `False`, sem reescrever o arquivo.
  - `reset_sensors() -> None` no `WindowsSensorProvider` (fecha e reabre PDH, NVML e D3DKMT na hora) e no `FakeSensorProvider` (não faz nada).
  - `AgentController.__init__` ganha `server=None`; `AgentController.port` passa a ler `server.port`. O QR e a sonda usam a porta atual.
  - `AgentController.program_path() -> str` (`sys.executable`).
  - `AgentController.last_fix_message: str | None`: texto da troca de porta para a janela mostrar.
  - `apply_fix` aceita `reiniciar_sensores`, `reiniciar_servidor` e `trocar_porta`. `copiar_caminho` é tratado na janela (área de transferência do Tk) com `program_path()`.
- Textos:
  - `DIAG_FIX_SENSORS = "Reiniciar sensores"`
  - `DIAG_FIX_RESTART = "Reiniciar o agente na rede"`
  - `DIAG_FIX_PORT = "Trocar a porta"`
  - `DIAG_FIX_COPY_PATH = "Copiar caminho do programa"`
  - `DIAG_PATH_COPIED = "Caminho copiado. Cole na lista de programas liberados do antivírus."`
  - `DIAG_PORT_CHANGED = "Porta trocada para {porta}. Nos celulares já pareados, ajuste a porta em Ajustes do PC."`

- [ ] **Passo 1: testes que falham**
  - `test_find_free_port_skips_busy` (8766 ocupada → 8767)
  - `test_find_free_port_gives_up_after_20`
  - `test_save_port_keeps_other_keys`
  - `test_save_port_unreadable_returns_false` (risco 2: arquivo com lixo e pasta somente leitura → `False` e conteúdo intacto)
  - `test_trocar_porta_restarts_on_new_port_and_sets_message`
  - `test_trocar_porta_keeps_old_port_when_save_fails`
  - `test_reset_sensors_reopens_now` (fábricas falsas contadas)
  - `test_rows_show_new_fix_buttons`
  - `test_copy_path_puts_exe_in_clipboard` (Xvfb)
- [ ] **Passo 2:** os testes acima → FAIL.
- [ ] **Passo 3:** implementar. Depois de qualquer correção, a janela roda o diagnóstico de novo, como no `_after_fix` atual.
- [ ] **Passo 4:** `pytest -q` → PASS.
- [ ] **Passo 5:** `git commit -m "feat(agent): correcoes de sensores, porta e antivirus no diagnostico"`

### Tarefa 4: crash por arquivo e fechamento inesperado

**Arquivos:** `crashlog.py`, `main.py`, `diagnostics/checks.py`, `diagnostics/runner.py`, `controller.py`; testes em `test_crashlog.py`, `test_diagnostics_checks.py`, `test_controller_diagnostics.py`.

**Interfaces:**
- Produz:
  - `CRASH_PREFIX = "crash-"` e `MAX_CRASH_FILES = 10`.
  - `write_exception_file(log_dir: Path, thread_name: str, text: str, now: datetime) -> Path`: nome `crash-AAAAMMDD-HHMMSS.log`; numa colisão no mesmo segundo, sufixo `-2`, `-3`…; texto passa pelo `redact`; apaga os mais antigos além de 10. `_excepthook` e `_thread_excepthook` chamam essa função depois do `logger.critical`.
  - `PreviousSession(crashed: bool, last_seen: datetime | None)` e `previous_session(log_dir: Path, boot_time: float) -> PreviousSession`. Lê o `crash.log` **antes** de abrir a sessão nova. A última sessão (do último cabeçalho `=== PcX Control … iniciado em … ===` até o fim) sem `ENDED_NORMALLY` **e** com o último `ts` do `agent.log` depois de `boot_time` → `crashed=True`.
  - `maintenance(log_dir: Path) -> None`: corta o `crash.log` acima de 1 MiB durante a execução (reabre o handle do `faulthandler`).
  - `check_shutdown(previous: PreviousSession | None) -> list[CheckResult]`. Com queda: `id` `agente.encerramento`, grupo `GROUP_AGENT`, `problema`, "O PcX Control fechou inesperadamente em DD/MM às HH:MM." (horário local), `fix="salvar_pacote"`. Sem queda, não devolve nada.
  - `Sources.previous_session: Callable[[], PreviousSession | None] = lambda: None`.
  - `AgentController.clear_crash_notice() -> None`.
  - `main.run_tray` calcula `previous_session` antes de `setup_logging` e entrega ao controlador.

- [ ] **Passo 1: testes que falham**
  - `test_exception_file_written_redacted_and_rotated` (12 arquivos → ficam 10)
  - `test_same_second_gets_suffix`
  - `test_previous_session_crashed_after_boot`
  - `test_previous_session_before_boot_is_shutdown` (desvio do spec)
  - `test_previous_session_ended_normally`
  - `test_previous_session_empty_or_old_format` (arquivo vazio, sem cabeçalho → `crashed=False`)
  - `test_maintenance_trims_while_running`
  - `test_check_shutdown_message_and_fix`
  - `test_clear_crash_notice_hides_check`
- [ ] **Passo 2:** `pytest tests/test_crashlog.py tests/test_diagnostics_checks.py tests/test_controller_diagnostics.py -v` → os novos FAIL.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** `pytest -q` → PASS.
- [ ] **Passo 5:** `git commit -m "feat(agent): arquivo por travamento e aviso de fechamento inesperado"`

### Tarefa 5: temperatura de alerta da GPU (`temp_warn_c`)

**Arquivos:** `sensors/windows/d3dkmt.py`, `sensors/base.py`, `sensors/windows/provider.py`, `docs/protocol/fixtures/` (regerar), `docs/protocolo.md`; testes em `test_d3dkmt.py`, `test_windows_provider_logic.py`, `test_contract_fixtures.py`.

**Interfaces:**
- Produz:
  - `KMTQAITYPE_ADAPTERPERFDATA_CAPS = 63` e `PERFDATACAPS_SIZE = 40`.
  - `D3DKMT_ADAPTER_PERFDATACAPS`: `UINT32 PhysicalAdapterIndex`, 4 bytes de alinhamento, `ULONGLONG MaxMemoryBandwidth` (8), `ULONGLONG MaxPCIEBandwidth` (16), `ULONG MaxFanRPM` (24), `ULONG TemperatureMax` (28), `ULONG TemperatureWarning` (32).
  - `parse_perfdata_caps(raw: bytes) -> float | None`: lê `TemperatureWarning` no deslocamento 32, em décimos de °C; 0 ou acima de 1500 → `None`.
  - `D3dkmtTemperatures.read_warnings(luids: list[str]) -> dict[str, float]`.
  - `GpuReading.temp_warn_c: float | None = None`. O provider lê os avisos **uma vez por lista de placas** (junto com `_refresh_adapters`) e preenche por LUID.

- [ ] **Passo 1: testes que falham**
  - `test_parse_perfdata_caps[830→83.0, 0→None, 1600→None, curto→None]`
  - `test_provider_fills_temp_warn_by_luid` (fonte falsa)
  - `test_warnings_read_once_per_adapter_list`
  - `@windows test_read_warnings_real_adapters_no_exception`
  - fixtures do protocolo com `temp_warn_c`
- [ ] **Passo 2:** `pytest tests/test_d3dkmt.py tests/test_windows_provider_logic.py tests/test_contract_fixtures.py -v` → FAIL.
- [ ] **Passo 3:** implementar; regerar as fixtures com o script atual do contrato; em `protocolo.md`, documentar `temp_warn_c` (opcional, °C, `null` sem dado).
- [ ] **Passo 4:** `pytest -q` → PASS (no Linux; o teste `@windows` roda na CI do Windows).
- [ ] **Passo 5:** `git commit -m "feat(agent): temperatura de alerta da GPU pelo driver"`

### Tarefa 6: `gpu.log`, versão do driver e fonte da temperatura

**Arquivos:** `logs.py`, `sensors/windows/gpu.py`, `sensors/windows/native.py`, `sensors/windows/provider.py`; testes em `test_logs.py`, `test_gpu_adapters.py`, `test_windows_provider_logic.py`, `test_windows_provider.py`.

**Interfaces:**
- Produz:
  - `GPU_LOG_FILE = "gpu.log"`, `GPU_MAX_BYTES = 524_288` e `GPU_BACKUP_COUNT = 1`. `setup_logging` adiciona um `RotatingFileHandler` com `RedactFilter` e `JsonFormatter` só para o logger `pcx_agent.sensors`, que continua propagando para o `agent.log`.
  - `AdapterInfo` ganha `device_id: int = 0` e `driver_version: str | None = None`.
  - `format_umd_version(value: int) -> str`: os quatro blocos de 16 bits, do mais alto ao mais baixo (`0x001F_0000_000F_1B5A` → `"31.0.15.7002"`).
  - Em `native.list_adapters`: `IDXGIAdapter::CheckInterfaceSupport` (vtable 9), com `IID_IDXGIDevice` `54ec77fa-1377-44e6-8c32-88fd5f44c84c`; falha → `None`.
  - `describe_adapters` inclui `DeviceId` e `driver X`.
  - `temperature_sources(readings, by_luid, by_name) -> dict[str, str]`, com o LUID como chave e `"driver"`, `"nvml"` ou `"nenhuma"` como valor. O provider registra "Temperatura de {placa}: {fonte}" na primeira leitura e quando muda.
  - Falhas registradas pelo `RateLimitedLog` ganham a placa e a fonte na mensagem.
  - `WindowsSensorProvider.temperature_source: dict[str, str]` (para o relatório da Tarefa 7).

- [ ] **Passo 1: testes que falham**
  - `test_sensor_logs_go_to_gpu_log_and_agent_log`
  - `test_gpu_log_redacts`
  - `test_format_umd_version`
  - `test_describe_adapters_has_driver_and_device`
  - `test_temperature_sources_logged_once_and_on_change`
  - `@windows test_list_adapters_has_driver_version`
- [ ] **Passo 2:** os testes acima → FAIL.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** `pytest -q` → PASS.
- [ ] **Passo 5:** `git commit -m "feat(agent): gpu.log com versao do driver e fonte da temperatura"`

### Tarefa 7: pacote de suporte

**Arquivos:** criar `diagnostics/support.py`, `winsys/folders.py`, `tests/test_support.py`; modificar `diagnostics/report.py`, `controller.py`, `tray/diagnostics_window.py`, `tray/texts.py`, `test_tray_windows.py`.

**Interfaces:**
- Consome:
  - `temperature_source` e `driver_version` (Tarefa 6);
  - `clear_crash_notice` e o `Fix` `salvar_pacote` (Tarefa 4).
- Produz:
  - `SUPPORT_NAME = "PcXControl-suporte-{:%Y%m%d-%H%M}.zip"`.
  - `LOG_PATTERNS = ("agent.log*", "gpu.log*", "crash-*.log", "crash.log")`.
  - `scrub(text: str, home: str, user: str) -> str`: `redact`, depois o caminho `home` (maiúsculas ou minúsculas, `\` ou `/`) vira `%USERPROFILE%`, e depois o nome `user` sozinho, como palavra inteira, também vira `%USERPROFILE%`.
  - `build_support_zip(dest_dir: Path, report: str, log_dir: Path, config_path: Path, now: datetime, home: str, user: str) -> Path`:
    - nunca inclui `*.db`, `*.db-wal` nem `*.db-shm`;
    - arquivo que não abre entra na seção `[Arquivos que ficaram de fora]` do `relatorio.txt`, com o motivo;
    - todos os arquivos dentro do `.zip` passam pelo `scrub`.
  - `choose_dest(candidates: list[Path], can_write: Callable[[Path], bool]) -> Path` (o último candidato é a pasta `logs`).
  - `folders.desktop_dir() -> Path | None` e `folders.documents_dir() -> Path | None`, por `SHGetKnownFolderPath` (`FOLDERID_Desktop`, `FOLDERID_Documents`); `None` fora do Windows ou em falha.
  - `folders.reveal(path: Path) -> None`: `explorer /select,"<path>"`.
  - `ReportFacts.extra: list[str] = []`, impresso em `[PC e agente]` antes das verificações. O controlador preenche:
    - CPU;
    - driver e fonte da temperatura de cada placa;
    - porta;
    - início com o Windows;
    - quantidade de celulares pareados e se há um conectado agora (sem nomes).
  - `AgentController.save_support_package(results: list[CheckResult]) -> Path`: chama `clear_crash_notice()`.
  - Janela: "Copiar relatório" sai; `DIAG_SAVE_PACKAGE = "Salvar pacote de suporte"`; depois de salvar, `DIAG_PACKAGE_SAVED = "Pacote salvo: {nome}. Mande este arquivo para quem está ajudando."` e `reveal`. O `Fix` `salvar_pacote` faz o mesmo.

- [ ] **Passo 1: testes que falham**
  - `test_zip_has_report_logs_config_and_no_db`
  - `test_zip_contents_scrubbed`: token de 22+ caracteres vira `[oculto]`; `C:\Users\Alexandre\AppData` e `c:/users/alexandre` viram `%USERPROFILE%`; o nome solto também.
  - `test_unreadable_log_listed_and_zip_still_created` (risco 3)
  - `test_choose_dest_falls_back_to_documents_then_logs` (risco 4)
  - `test_report_extra_has_no_device_names`
  - `test_save_package_clears_crash_notice`
  - `test_window_save_button_replaces_copy` (Xvfb)
  - `@windows test_desktop_dir_exists`
- [ ] **Passo 2:** `pytest tests/test_support.py tests/test_controller_diagnostics.py tests/test_tray_windows.py -v` → FAIL.
- [ ] **Passo 3:** implementar. Montar o pacote numa thread com `in_background`; a janela mostra "Salvando…" enquanto isso.
- [ ] **Passo 4:** `pytest -q` → PASS.
- [ ] **Passo 5:** `git commit -m "feat(agent): pacote de suporte em zip no lugar do relatorio copiado"`

### Tarefa 8: diagnóstico automático e alerta na bandeja

**Arquivos:** criar `tray/alerts.py`, `tests/test_tray_alerts.py`; modificar `tray/app.py`, `tray/icon.py`, `tray/texts.py`, `tools/make_icons.py`, `pcx_agent/assets/` (novo `tray-alert.png`), `sensors/windows/provider.py`, `controller.py`, `test_assets.py`.

**Interfaces:**
- Consome:
  - `DiagnosticsMonitor` (Tarefa 1);
  - `run_all(..., only=)` e `QUICK_CHECKS` (Tarefa 2);
  - `crashlog.maintenance` (Tarefa 4).
- Produz:
  - `AlertScheduler(run: Callable[[set[str] | None], list[CheckResult]], monitor: DiagnosticsMonitor, schedule: Callable[[int, Callable[[], None]], None], background: Callable[[Callable[[], object]], Future], ui: Callable[[Callable[[], None]], None], first_delay_ms: int = 10_000, interval_ms: int = 300_000)`. O parâmetro `run` recebe os `id`s, ou `None` para todos.
    - `start()`: primeira rodada completa depois de 10 s, depois `QUICK_CHECKS` a cada 5 min.
    - `trigger(ids: set[str])`: rodada daquele evento. Sem fila: com uma rodada em andamento, guarda só o pedido mais recente.
    - Cada rodada também chama `crashlog.maintenance`.
    - Os callbacks do monitor sempre passam por `ui`.
  - `AgentController.run_checks(ids: set[str] | None) -> list[CheckResult]`.
  - `WindowsSensorProvider.on_sensor_failure: Callable[[], None] | None`, chamado na mesma hora do `RateLimitedLog.report`; a bandeja liga isso a `trigger({"sensores.leitura", "sensores.gpu"})`.
  - `TrayApp`:
    - `set_alert(ids: frozenset[str])` troca a imagem (`tray.png` ↔ `tray-alert.png`), a dica (`TOOLTIP_ALERT = "PcX Control: atenção, abra Verificar conexão"`) e o texto do item (`MENU_DIAGNOSTICS_ALERT = "⚠ Verificar conexão"`, com `pystray.MenuItem` recebendo uma função de texto);
    - `notify(result)` usa `icon.notify(result.title, texts.APP_NAME)`.
  - Com servidor em `port_in_use` ao iniciar, `trigger({"agente.local"})` logo na abertura.
  - O resultado da janela "Verificar conexão" também alimenta o monitor (`ran` = todos).
  - `make_icons.py` gera `tray-alert.png`: o `tray.png` com um círculo `COLORS["danger"]` de 30% do lado no canto inferior direito, com contorno de 2 px da cor de fundo.

- [ ] **Passo 1: testes que falham** (relógio, `schedule` e `background` falsos e síncronos)
  - `test_first_full_run_after_10s_then_quick_every_5min`
  - `test_trigger_while_running_keeps_only_latest`
  - `test_callbacks_go_through_ui_only` (risco 1: `ui` falso registra; `on_alert_change` e `on_notify` nunca são chamados fora dele)
  - `test_window_results_feed_monitor`
  - `test_port_in_use_triggers_agent_check_on_start`
  - `test_alert_icon_asset_exists_and_same_size`
  - `test_set_alert_swaps_icon_tooltip_and_menu` (pystray falso)
  - `test_default_action_is_diagnostics_while_alert` (desvio do spec: clique duplo no ícone)
- [ ] **Passo 2:** `pytest tests/test_tray_alerts.py tests/test_assets.py -v` → FAIL.
- [ ] **Passo 3:** implementar; rodar `python tools/make_icons.py` e commitar o PNG gerado.
- [ ] **Passo 4:** `pytest -q` → PASS; na CI do Windows, `--self-test` continua verde.
- [ ] **Passo 5:** `git commit -m "feat(agent): diagnostico automatico com alerta na bandeja"`

### Tarefa 9: placa de rede pelo tipo

**Arquivos:** criar `winsys/adapters.py`, `tests/test_winsys_adapters.py`, `tests/data/adapters_*.json` (placas gravadas); modificar `network.py`, `diagnostics/checks.py`, `diagnostics/report.py`, `test_network.py`.

**Interfaces:**
- Produz:
  - `NetInterface` ganha `description: str = ""`, `kind: Literal["ethernet", "wifi", "outra", "desconhecido"] = "desconhecido"` e `has_gateway: bool = False`.
  - `classify_if_type(if_type: int) -> str`: 6 `ethernet`, 71 `wifi`, senão `outra`.
  - `adapters.read_adapters() -> list[NetInterface]`, via `GetAdaptersAddresses(AF_INET, GAA_FLAG_INCLUDE_GATEWAYS)` em `iphlpapi.dll`. Campos: `FriendlyName`, `Description`, `IfType`, `OperStatus == 1`, primeiro IPv4 unicast e `FirstGatewayAddress != NULL`. Lança `OSError` em falha.
  - `is_virtual(name, ipv4, description: str = "")`: as palavras de `VIRTUAL_NAMES` também são procuradas na descrição.
  - `choose_lan`: aceita `kind` em `{"ethernet", "wifi", "desconhecido"}`. Entre as válidas, nesta ordem: com gateway, a da rota, depois `_lan_rank`.
  - `list_interfaces()`: no Windows tenta `read_adapters()`; `OSError` → lista do `psutil` (como hoje).
  - `check_vpn` e o relatório mostram `nome (descrição)` quando há descrição.

- [ ] **Passo 1: testes que falham** (placas gravadas em JSON)
  - `test_renamed_radmin_is_ignored_by_description` ("Ethernet 3", descrição "Famatech Radmin VPN Ethernet Adapter", 26.x)
  - `test_hyperv_and_wsl_ignored`
  - `test_gateway_beats_route_hint`
  - `test_tunnel_kind_excluded`
  - `test_psutil_fallback_kind_unknown_still_works` (os testes atuais de `choose_lan` sem mudança)
  - `test_classify_if_type`
  - `@windows test_read_adapters_real_has_one_up`
- [ ] **Passo 2:** `pytest tests/test_network.py tests/test_winsys_adapters.py -v` → FAIL.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** `pytest -q` → PASS.
- [ ] **Passo 5:** `git commit -m "feat(agent): placa de rede escolhida pelo tipo e pela descricao do driver"`

### Tarefa 10: app 0.5.0, compatibilidade de versões

**Arquivos:** criar `mobile/src/protocol/compat.ts`, `mobile/src/components/OutdatedNotice.tsx`, `mobile/src/components/NeedsAgentUpdate.tsx`, `mobile/__tests__/protocol/compat.test.ts`; modificar `src/protocol/types.ts`, `src/protocol/validate.ts`, `src/connection/ConnectionManager.ts`, `src/hooks/PcContext.tsx`, `app/add.tsx`, `app/pc/[id]/index.tsx`, `app/pc/[id]/panel.tsx`; testes em `__tests__/connection/ConnectionManager.test.ts`, `__tests__/protocol/validate.test.ts`, `__tests__/screens/add.test.tsx`, `__tests__/screens/pc.test.tsx`, `__tests__/screens/panel.test.tsx`, `__tests__/components/components.test.tsx`.

**Interfaces:**
- Produz:
  - `SUPPORTED_PROTOCOL = 1`.
  - `RELEASES_URL = 'https://github.com/Owaleee/PcX-Control-app/releases'`.
  - `checkProtocol(protocol: number): 'ok' | 'app' | 'agent'`: maior que o suportado → `'app'`; menor → `'agent'`.
  - `hasCapability(hello: Hello | null, cap: string): boolean`.
  - `helloProtocol(raw: unknown): number | null`: lê só `type` e `protocol`, para o caso em que o `parseHello` recusa a mensagem.
  - `ConnState` ganha `{ kind: 'outdated'; who: 'app' | 'agent'; agentVersion: string }`. Ao receber um `hello` com protocolo diferente, o `ConnectionManager` entra nesse estado, fecha o socket e **não reconecta**.
  - `GpuSnapshot.temp_warn_c?: number | null`, aceito pelo `validate` (ausente, `null` ou número).
  - `add.tsx`: antes do `pair`, `getInfo`. Com `checkProtocol(info.protocol) !== 'ok'`, mostra o `OutdatedNotice` e não pareia.
  - `OutdatedNotice({ who, agentVersion })`:
    - para `app`: "Este PC usa uma versão mais nova do PcX Control. Atualize o app.", com o botão "Baixar a versão nova" (`Linking.openURL(RELEASES_URL)`);
    - para `agent`: "Este PC usa uma versão antiga do PcX Control. Atualize o programa no PC."
  - `NeedsAgentUpdate({ agentVersion })`: "Atualize o PcX Control no PC para usar isto." e "Versão no PC: {agentVersion}".
  - A tela do PC e o modo painel mostram o `OutdatedNotice` no estado `outdated`.
  - Versão `0.5.0` em `package.json`, `package-lock.json` e `app.json`.

- [ ] **Passo 1: testes que falham**
  - `checkProtocol[1→ok, 2→app, 0→agent]`
  - `hasCapability`
  - `hello protocol 2 → outdated(app), sem nova tentativa depois de 60 s no relógio falso`
  - `temp_warn_c ausente/null/número aceito; string recusada`
  - `add: info com protocol 2 mostra aviso e não chama pair`
  - `pc e panel mostram OutdatedNotice`
  - `botão abre RELEASES_URL`
  - `NeedsAgentUpdate mostra a versão`
- [ ] **Passo 2:** `cd mobile && npx jest compat ConnectionManager validate add pc panel components` → FAIL.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** `npx jest && npm run typecheck && npm run lint` → tudo verde.
- [ ] **Passo 5:** `git commit -m "feat(app): aviso de versao do protocolo e componente de atualizar o agente"`

### Tarefa 11: versões, documentação e roteiro manual

**Arquivos:** `agent/pyproject.toml`, `agent/pcx_agent/__init__.py`, `CHANGELOG.md`, `README.md`, `docs/protocolo.md`, `docs/teste-manual-app.md`, `docs/decisoes-e-pendencias.md`, `agent/tests/test_release_notes.py` (se o formato exigir).

- [ ] **Passo 1:** agente `0.6.0`. Rodar `pytest tests/test_release_notes.py` com as seções novas.
- [ ] **Passo 2:** CHANGELOG com `[agente 0.6.0] - AAAA-MM-DD` e `[app 0.5.0] - AAAA-MM-DD`, como nas anteriores:
  - Adicionado / Mudado / Corrigido;
  - a compatibilidade ("Compatível com o app 0.2.0 ou mais novo (protocolo 1)").
- [ ] **Passo 3:** `protocolo.md`: a regra 4 descreve o comportamento do app 0.5.0 (não é mais pendência) e `temp_warn_c` entra na tabela da GPU.
- [ ] **Passo 4:** README, em "Solução de problemas": o pacote de suporte e o alerta na bandeja. Tirar o "Copiar relatório".
- [ ] **Passo 5:** `teste-manual-app.md`, itens novos:
  - rede Pública e regra do firewall apagada → alerta em até 5 min e uma notificação;
  - reiniciar sensores;
  - porta ocupada por outro programa ao abrir o agente → trocar porta;
  - copiar caminho;
  - pacote de suporte aberto e conferido (sem `.db`, sem o nome do usuário);
  - Radmin renomeada;
  - fechar o agente pelo Gerenciador de Tarefas → aviso de fechamento inesperado na próxima abertura;
  - reiniciar o PC → **sem** aviso;
  - app com agente de teste anunciando `protocol: 2` (`--demo` com uma variável só de teste, documentada no roteiro).
- [ ] **Passo 6:** `decisoes-e-pendencias.md`: seção "Plano 6" com o desvio do spec, as decisões tomadas na execução e as pendências que fecharam (corte do `crash.log`, fonte da temperatura no log, VPN com nome desconhecido, compatibilidade de protocolo).
- [ ] **Passo 7:** `cd agent && pytest -q && ruff check .` e `cd mobile && npx jest && npm run typecheck && npm run lint` → tudo verde.
- [ ] **Passo 8:** `git commit -m "chore: agente 0.6.0 e app 0.5.0"`

### Fechamento

- [ ] Revisão independente da branch inteira contra o spec e este plano; cada achado corrigido com um teste que falhava antes, registrado em `decisoes-e-pendencias.md`.
- [ ] CI verde no Ubuntu e no Windows (agente, pacote do Windows, app e APK).
- [ ] PR `feat/agente-0.6-suporte` → `main`, com merge commit. Tags e releases (`agente-v0.6.0`, `app-v0.5.0`) só depois do roteiro manual no PC do Alexandre e no PC do amigo (AMD), como pede o critério 6 do spec.
