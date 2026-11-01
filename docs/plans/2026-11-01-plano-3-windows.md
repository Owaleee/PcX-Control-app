# PcX Control — Plano 3: agente no Windows e release 1.0.0

**Objetivo:** transformar o agente num programa de Windows para qualquer pessoa: ícone na bandeja, assistente da primeira execução, janelas de pareamento e de aparelhos, instância única, início com o Windows, logs em arquivo, executável PyInstaller, instalador Inno Setup com regra de firewall e release `v1.0.0` montada pela CI.

**Arquitetura:** a lógica nova fica em módulos puros e testáveis no Linux (`config.py`, `logs.py`, `server.py`, `controller.py`, `winsys/`). A interface (`tray/`) só chama o `AgentController` e não tem regra própria. O servidor Uvicorn roda numa thread (`AgentServer`); a thread principal roda o `tkinter`; o `pystray` roda destacado (`run_detached`) e entrega os cliques ao `tkinter` por uma fila. O instalador e a release são verificados na CI do Windows por um teste de fumaça que instala, roda `--self-test` e desinstala.

**Stack:** Python 3.13, pystray, Pillow, qrcode, tkinter (biblioteca padrão), pywin32, winreg, PyInstaller 6 (`onedir`), Inno Setup 6, GitHub Actions (`windows-latest`).

**Spec:** `docs/specs/2026-10-30-pcx-control-v1-design.md` (§1 critérios, §3 senha e pareamento, §7 agente no Windows, §8 testes, §9 CI e lançamento). Agente v0.1.0 e app v0.2.0 já prontos.

## Restrições globais

- Código em `agent/pcx_agent/`; testes em `agent/tests/`; empacotamento em `agent/packaging/`.
- Dados em `%LOCALAPPDATA%\PcXControl\`: `pcx.db`, `config.json`, `logs\`. Porta padrão 8765, configurável em `config.json`.
- Senha: mínimo 8 caracteres. "Trocar senha" não pede a senha atual (o acesso físico ao PC é a prova de dono) e pergunta se deve desconectar todos os aparelhos.
- Bandeja, nesta ordem: Parear celular (padrão, duplo clique), Celulares pareados, Trocar senha, Iniciar com o Windows (marcável), Abrir pasta de logs, Sair.
- Início com o Windows: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, valor `PcXControl`, conteúdo `"<caminho>\PcXControl.exe"` (com aspas). O instalador e o agente escrevem exatamente o mesmo valor.
- Instância única: mutex `Local\PcXControl.Agent`; mensagem "O PcX Control já está rodando." O instalador usa o mesmo nome em `AppMutex`.
- Logs em JSON por linha, rotação de 5 arquivos × 1 MiB (`maxBytes=1_048_576`, `backupCount=4`). Senha, código e token nunca são registrados.
- Firewall: só perfil **Privado**, só `LocalSubnet`, TCP, regra `PcX Control - agente`. O instalador pede administrador uma vez; o desinstalador remove a regra.
- Instalador: usuário atual (`PrivilegesRequired=lowest`), pasta `{localappdata}\Programs\PcX Control`, saída `PcXControl-Setup-X.Y.Z.exe`, idioma português do Brasil. Desinstalar mantém os dados do usuário.
- Versão `1.0.0` igual em `pcx_agent/__init__.py`, `agent/pyproject.toml` e `mobile/app.json`; a tag `vX.Y.Z` precisa bater com elas.
- Textos da interface em português do Brasil. Commits em português, no padrão Conventional Commits.
- Cobertura mínima de 80% fora de `sensors/windows`, `tray` e `winsys` (os dois últimos entram no `omit`).

## Revisão de riscos (entradas que o spec não detalha)

1. **Porta 8765 já ocupada** por outro programa: janela com "A porta 8765 já está em uso por outro programa. Feche-o ou mude a porta em `<config.json>`." e saída com código 1, nunca um ícone na bandeja sem servidor. (Tarefa 2)
2. **PC sem rede** ao abrir o pareamento (o IP sai `127.0.0.1`): a janela mostra o aviso em vez de um QR que nunca vai funcionar. (Tarefa 4)
3. **`config.json` quebrado ou com porta inválida** (texto, `0`, `70000`, `true`, `80.5`, JSON malformado): usa 8765, registra aviso no log, não sobrescreve o arquivo do usuário e não trava. (Tarefa 1)
4. **Sair pela bandeja com um celular conectado:** o celular recebe o fechamento, o processo termina em até 5 s e a porta fica livre para abrir o agente de novo na hora. (Tarefa 2)
5. **Abrir o programa duas vezes** (atalho + início com o Windows) ou **atualizar com o agente aberto:** a segunda cópia avisa e sai; o instalador pede para fechar o agente antes de copiar os arquivos. (Tarefas 3 e 8)

## Estrutura de arquivos

```
agent/
├─ pyproject.toml                # pystray, Pillow; extra build (pyinstaller); package-data
├─ pcx_agent/
│  ├─ config.py                  # + config.json, config_path, log_dir
│  ├─ logs.py                    # setup_logging, JsonFormatter, RedactFilter
│  ├─ server.py                  # AgentServer (Uvicorn em thread), PortInUseError
│  ├─ controller.py              # AgentController, PairingInfo, DeviceRow, format_last_used
│  ├─ selftest.py                # run_self_test
│  ├─ main.py                    # modos: bandeja (padrão), --console, --demo, --self-test
│  ├─ auth/pairing.py            # + teto global de tentativas, on_pair
│  ├─ assets/icon.ico, tray.png  # gerados de mobile/assets/icon.png
│  ├─ winsys/instance.py         # instância única (mutex no Windows, flock fora)
│  ├─ winsys/autostart.py        # AutoStart, RunStore, launch_command
│  ├─ winsys/dialogs.py          # show_message (MessageBoxW / stderr)
│  └─ tray/
│     ├─ dispatcher.py           # fila thread-safe para o tkinter
│     ├─ qr.py                   # QR como imagem Tk
│     ├─ first_run.py, pairing.py, devices.py, password.py   # janelas
│     ├─ icon.py                 # menu do pystray
│     └─ app.py                  # TrayApp: junta servidor, controlador e janelas
├─ packaging/
│  ├─ entry.py, PcXControl.spec  # PyInstaller onedir, sem console
│  ├─ installer.iss, firewall.cmd
│  └─ smoke-test.ps1
├─ tools/make_icons.py, tools/release_notes.py
└─ tests/  test_config_file.py, test_logs.py, test_server.py, test_controller.py,
           test_instance.py, test_autostart.py, test_selftest.py, test_release_notes.py,
           test_assets.py, test_tray_windows.py
.github/workflows/windows-package.yml, release.yml
```

---

### Tarefa 1: `config.json` e logs em arquivo

**Arquivos:** modificar `pcx_agent/config.py`, `pyproject.toml` (`omit` com `pcx_agent/winsys/*`); criar `pcx_agent/logs.py`, `tests/test_config_file.py`, `tests/test_logs.py`.

**Interfaces:**
- `Settings` ganha as propriedades `config_path -> Path` (`data_dir / "config.json"`) e `log_dir -> Path` (`data_dir / "logs"`).
- `load_settings(data_dir=None, port=None)` lê `config.json` (`{"port": 8765}`). Se o arquivo não existir, cria com o padrão. Porta válida: `int` (não `bool`) entre 1 e 65535. Inválida ou JSON quebrado: usa 8765, registra `WARNING` em `pcx_agent.config` e não reescreve o arquivo. `port` da linha de comando vence o arquivo.
- `setup_logging(log_dir: Path, *, console: bool = False, level: int = logging.INFO) -> None`: cria a pasta, põe no logger raiz um `RotatingFileHandler(log_dir / "agent.log", maxBytes=1_048_576, backupCount=4, encoding="utf-8")` com `JsonFormatter` e `RedactFilter`; com `console=True`, também um `StreamHandler` em texto. Chamar duas vezes não duplica handlers.
- `JsonFormatter`: uma linha por registro com `ts` (ISO 8601 UTC), `level`, `logger`, `msg` e `exc` (só se houver exceção).
- `RedactFilter`: troca por `[oculto]` qualquer sequência `[A-Za-z0-9_-]{22,}` (tokens e códigos de `token_urlsafe`) e o valor de `c=` numa URI `pcx://`.

- [ ] **Passo 1: testes.** `test_config_file.py`: `test_creates_default_config_file` (arquivo criado com `{"port": 8765}`); `test_config_json_sets_port` (`{"port": 9000}` → 9000); `test_invalid_port_falls_back[valor]` com `"abc"`, `0`, `70000`, `True`, `80.5` → 8765 e aviso no `caplog`; `test_malformed_json_falls_back_and_is_kept` (arquivo com `{port:` continua igual depois); `test_cli_port_overrides_config`. `test_logs.py`: `test_writes_one_json_object_per_line`; `test_rotation_keeps_five_files_of_1mib` (gravar ~6 MiB → no máximo 5 arquivos, cada um ≤ 1 MiB + 1 linha); `test_redacts_tokens_and_pairing_code` (registrar `secrets.token_urlsafe(32)` e uma URI `pcx://pair?...&c=<código>` → nenhum dos dois no arquivo, `[oculto]` presente); `test_uvicorn_errors_reach_the_file` (`logging.getLogger("uvicorn.error").error("x")` aparece no arquivo); `test_setup_twice_does_not_duplicate_lines`.
- [ ] **Passo 2:** `cd agent && .venv/bin/pytest tests/test_config_file.py tests/test_logs.py -q`. Esperado: FAIL.
- [ ] **Passo 3:** implementar. O `JsonFormatter` usa `json.dumps(..., ensure_ascii=False)`.
- [ ] **Passo 4:** `pytest -q && ruff check .`. Esperado: verde, inclusive os testes antigos de `load_settings`.
- [ ] **Passo 5:** commit `feat(agent): adiciona config.json e logs em JSON com rotacao`.

---

### Tarefa 2: servidor em thread, limites do Uvicorn e teto global de tentativas

**Arquivos:** criar `pcx_agent/server.py`, `tests/test_server.py`; modificar `pcx_agent/auth/pairing.py`, `pcx_agent/api/app.py` (`build_context`), `tests/test_pairing.py`.

**Interfaces:**
- Consome `AppContext` e `create_app(ctx)` (Plano 1).
- Produz `PortInUseError(port: int)` e `StartupError`.
- Produz `AgentServer(ctx: AppContext, host: str, port: int)` com `start(timeout: float = 10.0) -> None`, `bound_port -> int`, `stop(timeout: float = 5.0) -> None` e `running -> bool`. `start` primeiro testa a porta com um `socket.bind` sem `SO_REUSEADDR` (ocupada → `PortInUseError`), depois roda `uvicorn.Server.run()` numa thread `daemon` e espera `server.started` (não iniciou no prazo → `StartupError`). Com `port=0`, `bound_port` lê a porta real do socket. `stop` faz `should_exit = True` e espera a thread.
- Configuração do Uvicorn, num lugar só: `access_log=False`, `log_config=None`, `ws_ping_interval=5.0`, `ws_ping_timeout=10.0`, `ws_max_size=16_384`, `limit_concurrency=64`, `timeout_keep_alive=5`.
- `PairingService` ganha `global_limiter: RateLimiter` (padrão `RateLimiter(max_failures=30, window_s=60.0, block_s=60.0)`, chave `"*"`), verificado junto com o limite por IP; sucesso zera só o limite do IP. E ganha `on_pair: Callable[[Device], None] | None`, chamado depois de gravar o aparelho novo, e a propriedade `code_ttl_s -> float` (hoje `_code_ttl`).

- [ ] **Passo 1: testes.** `test_server.py` (servidor real com `FakeSensorProvider` e `tmp_path`): `test_start_serves_info_on_ephemeral_port` (`urllib` em `/v1/info` → 200); `test_port_in_use_raises` (socket escutando numa porta → `PortInUseError` com essa porta); `test_stop_frees_port_quickly` (com um WebSocket autenticado aberto, `stop()` retorna em menos de 5 s, o cliente recebe o fechamento e um `AgentServer` novo sobe na mesma porta); `test_rejects_oversized_websocket_message` (primeira mensagem de 32 KiB → conexão fechada, servidor continua respondendo `/v1/info`). `test_pairing.py`: `test_global_cap_blocks_after_30_failures_from_many_ips` (30 IPs diferentes erram a senha → o 31º recebe `rate_limited`); `test_success_does_not_reset_global_cap`; `test_on_pair_receives_new_device` (nome e id iguais ao `PairResult`).
- [ ] **Passo 2:** `pytest tests/test_server.py tests/test_pairing.py -q`. Esperado: FAIL.
- [ ] **Passo 3:** implementar `AgentServer` e as mudanças no `PairingService`.
- [ ] **Passo 4:** `pytest -q && ruff check .`. Esperado: verde.
- [ ] **Passo 5:** commit `feat(agent): roda o servidor em thread com limites e teto global de tentativas`.

---

### Tarefa 3: instância única, início com o Windows e mensagens nativas

**Arquivos:** criar `pcx_agent/winsys/__init__.py`, `winsys/instance.py`, `winsys/autostart.py`, `winsys/dialogs.py`, `tests/test_instance.py`, `tests/test_autostart.py`.

**Interfaces:**
- `MUTEX_NAME = "Local\\PcXControl.Agent"`. `acquire_single_instance(data_dir: Path) -> InstanceLock | None`: no Windows, `win32event.CreateMutex(None, False, MUTEX_NAME)` e `GetLastError() == ERROR_ALREADY_EXISTS` → `None`; fora do Windows, `fcntl.flock(LOCK_EX | LOCK_NB)` em `data_dir / "agent.lock"`. `InstanceLock.release() -> None`.
- `RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"`, `VALUE_NAME = "PcXControl"`. `RunStore` (Protocol): `get(name) -> str | None`, `set(name, value) -> None`, `delete(name) -> None`. `WinRegistryRunStore` usa `winreg` em `HKEY_CURRENT_USER`.
- `launch_command(executable: str = sys.executable, frozen: bool = getattr(sys, "frozen", False)) -> str`: congelado → `"<executable>"`; senão `"<pythonw.exe ao lado do executable>" -m pcx_agent`.
- `AutoStart(store: RunStore, command: str)`: `is_enabled() -> bool` (o valor existe e é igual a `command`), `enable() -> None`, `disable() -> None` (sem erro se não existir).
- `show_message(title: str, text: str, *, error: bool = False) -> None`: `ctypes.windll.user32.MessageBoxW` no Windows; `stderr` nos demais.

- [ ] **Passo 1: testes.** `test_instance.py`: `test_second_lock_is_refused` (duas chamadas na mesma pasta → a segunda devolve `None`); `test_lock_is_free_after_release`; `test_windows_mutex_refuses_second` (`@pytest.mark.windows`). `test_autostart.py` (store de dicionário): `test_enable_writes_quoted_exe_when_frozen` (`"C:\\Apps\\PcX Control\\PcXControl.exe"` entre aspas); `test_dev_command_uses_pythonw`; `test_enabled_only_when_value_matches` (valor de outra pasta → `False`; `enable()` corrige); `test_disable_is_idempotent`; `test_registry_roundtrip` (`@pytest.mark.windows`, usa um nome de valor de teste e apaga no fim).
- [ ] **Passo 2:** rodar. Esperado: FAIL.
- [ ] **Passo 3:** implementar; `pywin32` só é importado dentro dos ramos do Windows.
- [ ] **Passo 4:** `pytest -q && ruff check .`. Esperado: verde. Atualizar o mínimo do passo "Testes de Windows" em `agent.yml` de 4 para 6.
- [ ] **Passo 5:** commit `feat(agent): adiciona instancia unica e inicio com o Windows`.

---

### Tarefa 4: `AgentController` (a lógica da bandeja)

**Arquivos:** criar `pcx_agent/controller.py`, `tests/test_controller.py`.

**Interfaces:**
- Consome `AppContext`, `pairing_uri`, `local_ipv4`, `PairingService.on_pair`.
- `PairingInfo(code: str, uri: str, host: str, port: int, expires_at: float, warning: str | None)` (frozen). `expires_at` em `time.time()`.
- `DeviceRow(id: str, name: str, last_used: str, active: bool)` (frozen); `last_used` já formatado.
- `PasswordInputError(message: str)`.
- `AgentController(ctx: AppContext, port: int, *, host_lookup: Callable[[], str] = local_ipv4, now: Callable[[], float] = time.time)`:
  - `needs_first_run() -> bool` (sem senha).
  - `set_password(new: str, confirm: str) -> None`: diferentes → `PasswordInputError("As senhas não são iguais.")`; curta → `PasswordInputError("A senha precisa ter pelo menos 8 caracteres.")`.
  - `start_pairing() -> PairingInfo`: novo código (invalida o anterior). Se `host_lookup()` devolver `127.0.0.1`, `warning = "Não encontrei a rede deste PC. Conecte-o ao Wi-Fi ou ao cabo e gere outro código."`.
  - `devices() -> list[DeviceRow]` (ativo primeiro, depois último uso mais recente), `revoke(device_id: str) -> None`, `revoke_all() -> None`.
  - `status_text() -> str`: `"PcX Control: aguardando celular"` ou `"PcX Control: conectado a <nome>"`.
  - `on_paired: Callable[[str], None] | None` (recebe o nome do aparelho), ligado a `PairingService.on_pair`.
- `format_last_used(ts: float, now: float) -> str`: `< 60 s` → `"agora"`; `< 60 min` → `"há N min"`; mesmo dia → `"hoje às HH:MM"`; dia anterior → `"ontem às HH:MM"`; senão `"DD/MM/AAAA"` (hora local).

- [ ] **Passo 1: testes.** `test_set_password_rejects_mismatch`; `test_set_password_rejects_short`; `test_first_run_flag_clears_after_password`; `test_start_pairing_builds_uri_with_lan_host` (`host_lookup` → `192.168.0.10`; URI com `h=192.168.0.10`, `p` = porta, `warning is None`, `expires_at = now + pairing.code_ttl_s`, ou seja, 300); `test_start_pairing_warns_without_network` (`127.0.0.1` → aviso exato acima); `test_new_pairing_invalidates_previous_code` (parear com o primeiro código → `code_invalid_or_expired`); `test_devices_lists_active_first`; `test_revoke_closes_active_session` (usa `SessionManager` com `on_revoke` falso e confere a chamada); `test_status_text_reflects_session`; `test_on_paired_called_with_device_name`; `test_format_last_used[...]` com os cinco casos.
- [ ] **Passo 2:** rodar. Esperado: FAIL.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** `pytest --cov=pcx_agent --cov-fail-under=80 && ruff check .`. Esperado: verde.
- [ ] **Passo 5:** commit `feat(agent): adiciona controlador da bandeja`.

---

### Tarefa 5: ícones do agente

**Arquivos:** criar `tools/make_icons.py`, `pcx_agent/assets/icon.ico`, `pcx_agent/assets/tray.png`, `tests/test_assets.py`; modificar `pyproject.toml` (`[tool.setuptools.package-data] pcx_agent = ["assets/*"]`; `Pillow>=10` nos extras `dev` e `windows`; `pystray>=0.19` no extra `windows`; `qrcode[pil]>=7` no lugar de `qrcode>=7`).

**Interfaces:**
- Produz `pcx_agent.assets_path(name: str) -> Path` em `pcx_agent/__init__.py` (funciona instalado e dentro do PyInstaller via `importlib.resources`).
- `tools/make_icons.py` lê `mobile/assets/icon.png` (1024 px, o mesmo desenho do app) e grava o `.ico` com 16, 24, 32, 48, 64, 128 e 256 px e o `tray.png` com 64 px.

- [ ] **Passo 1: teste** `test_assets.py`: `test_ico_has_all_sizes` (Pillow abre o `.ico` e `info["sizes"]` contém os 7 tamanhos); `test_tray_png_is_64_rgba`; `test_assets_path_points_to_existing_files`.
- [ ] **Passo 2:** FAIL → `python tools/make_icons.py` → PASS.
- [ ] **Passo 3:** commit `chore(agent): adiciona icones do agente`.

---

### Tarefa 6: janelas (tkinter)

**Arquivos:** criar `tray/__init__.py`, `tray/dispatcher.py`, `tray/qr.py`, `tray/first_run.py`, `tray/pairing.py`, `tray/devices.py`, `tray/password.py`, `tests/test_tray_windows.py`.

**Interfaces:**
- Consome `AgentController`, `PairingInfo`, `DeviceRow`, `PasswordInputError` (Tarefa 4).
- `Dispatcher(root: tk.Tk)`: `call(fn: Callable[[], None]) -> None` pode ser chamado de qualquer thread; uma `queue.SimpleQueue` é esvaziada por `root.after(50, ...)`.
- `qr_photo(uri: str, size: int = 320) -> ImageTk.PhotoImage` (`qrcode` com Pillow, borda 2).
- `PairingFrame(parent, controller)`: QR, código em texto, `IP:porta`, contagem regressiva `m:ss` e botão "Gerar outro código". Ao expirar, o QR some e aparece "Código expirado. Gere outro." Com `warning`, mostra o aviso no lugar do QR. `show_paired(name: str)` mostra "Celular <nome> pareado!".
- `open_pairing_window(root, controller) -> PairingWindow` (uma por vez: chamar de novo traz a existente para a frente e gera outro código). Fecha sozinha 2 s depois de `show_paired`.
- `open_first_run(root, controller, on_done: Callable[[], None])`: passo 1 "Crie a senha deste PC" (senha, confirmação, botão "Continuar", erro de `PasswordInputError` em vermelho embaixo); passo 2 o `PairingFrame` e o botão "Concluir".
- `open_devices_window(root, controller)`: `ttk.Treeview` com Nome, Último uso e Status ("Conectado agora"); botões "Desconectar" (do selecionado) e "Desconectar todos" (com `messagebox.askyesno`); atualiza a cada 2 s.
- `open_password_window(root, controller)`: nova senha e confirmação; depois de salvar, `askyesno("Desconectar também todos os celulares pareados?")`.
- Todas as janelas usam o `icon.ico`, não redimensionam e respondem a Esc (fechar) e Enter (ação principal).

- [ ] **Passo 1: teste** `test_tray_windows.py` (`@pytest.mark.windows`, `tk.Tk()` escondido, controlador com `FakeSensorProvider` e `tmp_path`): `test_windows_open_and_close` (cada `open_*` cria a janela, `root.update()` e destrói sem exceção); `test_first_run_shows_mismatch_error` (preenche campos diferentes, aciona "Continuar", o rótulo de erro mostra "As senhas não são iguais."); `test_dispatcher_runs_calls_from_other_thread` (uma thread chama `call`, `root.update()` em laço por até 1 s executa a função).
- [ ] **Passo 2:** no Windows, `pytest -m windows tests/test_tray_windows.py`. Esperado: FAIL.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** PASS no Windows; `ruff check .` verde. Atualizar o mínimo em `agent.yml` de 6 para 9.
- [ ] **Passo 5:** commit `feat(agent): adiciona janelas de pareamento, aparelhos e senha`.

---

### Tarefa 7: bandeja, novos modos de execução e autoteste

**Arquivos:** criar `tray/icon.py`, `tray/app.py`, `pcx_agent/selftest.py`, `tests/test_selftest.py`; modificar `pcx_agent/main.py`, `tests/test_e2e_demo.py`, `agent/README.md`.

**Interfaces:**
- Consome `AgentServer`, `PortInUseError` (Tarefa 2), `acquire_single_instance`, `AutoStart`, `show_message` (Tarefa 3), `AgentController` (Tarefa 4), janelas (Tarefa 6), `setup_logging` (Tarefa 1).
- `build_tray_icon(controller, actions: TrayActions) -> pystray.Icon`; `TrayActions` com `pair`, `devices`, `password`, `toggle_autostart`, `autostart_checked: Callable[[], bool]`, `open_logs`, `quit`. Itens e ordem das Restrições globais; "Parear celular" é `default=True`.
- `TrayApp(settings, ctx, server, controller, autostart)`, `run() -> int`: cria o `tk.Tk()` escondido e o `Dispatcher`, inicia o ícone com `run_detached()`, abre o assistente se `needs_first_run()`, atualiza o `title` do ícone com `status_text()` a cada 2 s, avisa por `icon.notify` quando `on_paired` dispara e roda `root.mainloop()`. "Parear celular" sem senha abre o assistente. "Abrir pasta de logs" usa `os.startfile(settings.log_dir)`. "Sair": `server.stop()`, `icon.stop()`, `root.quit()`.
- `main`: Windows sem flags → bandeja; `--console` → terminal no Windows (comportamento atual, com `AgentServer` no lugar de `uvicorn.run`); `--demo` → terminal com sensores simulados em qualquer sistema; `--self-test SAÍDA` → `run_self_test`. Ordem na bandeja: `setup_logging(log_dir)` → `acquire_single_instance` (`None` → `show_message("PcX Control", "O PcX Control já está rodando.")`, sai com 0) → contexto → `server.start()` (`PortInUseError` → `show_message` com o texto do risco 1, sai com 1) → `TrayApp.run()`. No terminal, o aviso de rede da Tarefa 4 também é impresso.
- `run_self_test(out: Path, *, demo: bool) -> int`: pasta temporária, provedor real (ou o simulado com `demo`), `AgentServer` na porta 0, `GET /v1/info`, um `provider.read()`, e grava `{"ok": true, "version": ..., "capabilities": [...], "port": ...}` em `out`. Qualquer exceção grava `{"ok": false, "error": "<tipo>: <mensagem>"}` e devolve 1. Serve para provar que o executável congelado tem todos os módulos.

- [ ] **Passo 1: testes.** `test_selftest.py`: `test_self_test_demo_writes_ok` (`main(["--demo", "--self-test", str(out)])` → 0 e `ok` verdadeiro com `cpu` nas capacidades); `test_self_test_reports_failure` (provedor que levanta → 1 e `ok` falso com a mensagem). `test_e2e_demo.py`: `test_demo_console_uses_agent_server` (o `--dry-run` continua imprimindo a URI e o QR); `test_non_windows_without_demo_still_refuses`.
- [ ] **Passo 2:** rodar. Esperado: FAIL.
- [ ] **Passo 3:** implementar `selftest.py`, `main.py`, `tray/icon.py` e `tray/app.py`.
- [ ] **Passo 4:** `pytest --cov=pcx_agent --cov-fail-under=80 && ruff check .`. Esperado: verde.
- [ ] **Passo 5 (manual, no seu PC):** `pythonw -m pcx_agent` com uma pasta de dados nova: assistente aparece, senha criada, QR pareia o celular, a janela fecha sozinha e chega a notificação; os seis itens da bandeja funcionam; abrir de novo mostra "O PcX Control já está rodando."; "Sair" encerra e o app no celular mostra a queda.
- [ ] **Passo 6:** atualizar `agent/README.md` (modos de execução e pasta de dados). Commit `feat(agent): adiciona icone na bandeja e assistente da primeira execucao`.

---

### Tarefa 8: executável, instalador, firewall e teste de fumaça na CI

**Arquivos:** criar `packaging/entry.py`, `packaging/PcXControl.spec`, `packaging/installer.iss`, `packaging/firewall.cmd`, `packaging/smoke-test.ps1`, `.github/workflows/windows-package.yml`; modificar `pyproject.toml` (extra `build = ["pyinstaller>=6.10"]`), `.gitignore` (`agent/build/`, `agent/dist/`, `agent/packaging/Output/`).

**Interfaces:**
- `entry.py`: `from pcx_agent.main import main; raise SystemExit(main())`.
- `PcXControl.spec`: `onedir`, `name="PcXControl"`, `console=False`, `icon` = `pcx_agent/assets/icon.ico`, `datas` com `pcx_agent/assets`, `hiddenimports` com `uvicorn.loops.asyncio`, `uvicorn.protocols.http.h11_impl`, `uvicorn.protocols.websockets.websockets_impl`, `uvicorn.lifespan.on` e `pystray._win32`. Saída `dist/PcXControl/PcXControl.exe`.
- `firewall.cmd add "<exe>"`: apaga a regra `PcX Control - agente` (se houver) e cria com `netsh advfirewall firewall add rule name="PcX Control - agente" dir=in action=allow protocol=TCP profile=private remoteip=localsubnet program="<exe>"`. `firewall.cmd remove`: apaga. A regra é pelo programa, sem porta fixa, então mudar a porta no `config.json` continua funcionando.
- `installer.iss` recebe `/DAppVersion=X.Y.Z`. `AppId` fixo (GUID gerado uma vez e nunca mais trocado), `AppName=PcX Control`, `AppPublisher=Alexandre Queiroz`, `PrivilegesRequired=lowest`, `DefaultDirName={localappdata}\Programs\PcX Control`, `AppMutex=Local\PcXControl.Agent`, `OutputBaseFilename=PcXControl-Setup-{#AppVersion}`, `SetupIconFile`, `UninstallDisplayIcon`, idioma `BrazilianPortuguese.isl`, `[Tasks]` `autostart` ("Iniciar com o Windows", marcada) e `desktopicon` (desmarcada). `[Registry]` grava o valor de início das Restrições globais com `Flags: uninsdeletevalue`, só com a tarefa `autostart`. `[Run]`: `firewall.cmd add` com `Verb: runas; Flags: shellexec runhidden waituntilterminated` (um único pedido de administrador; se a pessoa negar, a instalação termina normalmente) e "Abrir o PcX Control" (`postinstall nowait`). `[UninstallRun]`: `firewall.cmd remove` com `runas` e `RunOnceId: "RemoveFirewall"`. Os dados em `%LOCALAPPDATA%\PcXControl` ficam.
- `smoke-test.ps1 -Installer <exe>`: instala com `/VERYSILENT /SUPPRESSMSGBOXES /TASKS="autostart" /DIR=<temp>`; confere o `.exe`, a regra (`Get-NetFirewallRule -DisplayName "PcX Control - agente"`, perfil Private) e o valor `PcXControl` no `Run`; roda `PcXControl.exe --self-test <json>` (espera até 60 s) e exige `ok`; desinstala com `unins000.exe /VERYSILENT`; confere que a regra e o valor sumiram. Qualquer falha → `exit 1`.
- `windows-package.yml`: `on: pull_request` (caminhos `agent/**` e o próprio arquivo), `workflow_dispatch` e `workflow_call` (saída: nome do instalador). Passos: Python 3.13, `pip install -e "agent[windows,build]"`, `pyinstaller packaging/PcXControl.spec`, ISCC (instala com `choco install innosetup -y --no-progress` se `iscc` não existir) com a versão lida de `pcx_agent.__version__`, `smoke-test.ps1`, `actions/upload-artifact` do instalador.

- [ ] **Passo 1:** escrever `smoke-test.ps1` primeiro e rodar o workflow com um `installer.iss` vazio. Esperado: FAIL (instalador inexistente).
- [ ] **Passo 2:** escrever o `.spec`, o `entry.py`, o `firewall.cmd` e o `installer.iss`.
- [ ] **Passo 3:** workflow verde, com o `--self-test` do executável congelado devolvendo `ok`.
- [ ] **Passo 4 (manual, no seu PC):** baixar o artefato, instalar (aceitar o pedido de administrador), conferir a regra no "Firewall do Windows com Segurança Avançada", parear pelo QR, reinstalar com o agente aberto (o instalador pede para fechar), desinstalar e conferir que a regra sumiu e que `%LOCALAPPDATA%\PcXControl` ficou.
- [ ] **Passo 5:** commit `build(agent): adiciona executavel, instalador e teste de fumaca no Windows`.

---

### Tarefa 9: release automática na tag

**Arquivos:** criar `tools/release_notes.py`, `tests/test_release_notes.py`, `.github/workflows/release.yml`.

**Interfaces:**
- `changelog_section(text: str, version: str) -> str`: devolve o corpo da seção `## [X.Y.Z] - AAAA-MM-DD` até a próxima `## [`, sem o título; versão ausente → `ValueError`.
- `check_versions(tag: str, agent: str, pyproject: str, app: str) -> None`: `tag` sem o `v` precisa ser igual às três; senão `ValueError` com as versões encontradas.
- CLI: `python tools/release_notes.py <tag> --out notes.md` lê `CHANGELOG.md`, `pcx_agent/__init__.py`, `pyproject.toml` e `mobile/app.json`, valida e grava as notas.
- Os testes carregam o arquivo com `importlib.util.spec_from_file_location` (fica fora do pacote instalado).
- `release.yml`: `on: push: tags: ["v*"]`, `permissions: contents: write`. Job `notes` (Ubuntu): roda a CLI e envia `notes.md` como artefato. Job `package`: `uses: ./.github/workflows/windows-package.yml`. Job `release` (precisa dos dois): baixa os artefatos e roda `gh release create "$TAG" --draft --title "PcX Control $VERSION" --notes-file notes.md PcXControl-Setup-$VERSION.exe`. A release nasce como rascunho para você anexar o APK e publicar.

- [ ] **Passo 1: testes:** `test_extracts_only_requested_section` (com o `CHANGELOG.md` real e a `0.2.0`: começa em "Primeira versão do **app Android**" e não contém "## [0.1.0]"); `test_missing_version_raises`; `test_versions_must_match_tag` (uma diferente → `ValueError` com o nome do arquivo); `test_tag_without_v_prefix_is_rejected`.
- [ ] **Passo 2:** FAIL → implementar → PASS; `ruff check .` verde.
- [ ] **Passo 3:** commit `ci: gera rascunho da release com o instalador na tag`.

---

### Tarefa 10: versão 1.0.0 e documentação de lançamento

**Arquivos:** modificar `pcx_agent/__init__.py`, `agent/pyproject.toml`, `mobile/app.json` e `mobile/package.json` (versão `1.0.0`), `mobile/eas.json` (perfil `production-apk`: `android.buildType = "apk"`), `CHANGELOG.md` (`[1.0.0]`), `README.md`, `docs/teste-manual-app.md`, `docs/decisoes-e-pendencias.md`; criar `docs/media/` (GIF do modo painel, gravado por você).

- [ ] **Passo 1:** versões em `1.0.0`; `python tools/release_notes.py v1.0.0 --out /tmp/notes.md` passa.
- [ ] **Passo 2:** `CHANGELOG.md`: seção `[1.0.0]` com o que entrou nas Tarefas 1 a 9 (bandeja, assistente, instalador, firewall, início com o Windows, logs, `config.json`, limites e teto global).
- [ ] **Passo 3:** `README.md`: resumo em inglês no topo; GIF do modo painel; "Como instalar" em 4 passos (baixar o instalador da release, instalar, criar a senha, escanear o QR com o APK); diagrama de arquitetura em Mermaid (celular ↔ WebSocket ↔ agente ↔ sensores e SQLite); aviso de HTTP em rede doméstica confiável; aviso sobre antivírus e PyInstaller; link para o Plano 3; status `1.0.0`.
- [ ] **Passo 4:** `docs/teste-manual-app.md`: seção "Instalador" no lugar da preparação manual (o comando `New-NetFirewallRule` vira plano B) e os itens do spec §8 que faltavam: revogar na bandeja, modo painel por 1 h, troca de IP do PC, CPU média do agente ocioso abaixo de 1% (Gerenciador de Tarefas, 5 min) e instalação até o primeiro dado em menos de 2 minutos.
- [ ] **Passo 5:** `docs/decisoes-e-pendencias.md`: seção "Agente no Windows v1.0.0 (Plano 3)" com as decisões (regra de firewall por programa e sem porta fixa; `AppMutex` igual ao mutex do agente; dados mantidos ao desinstalar; teto global de 30 falhas por minuto e o risco de alguém na rede travar o pareamento por 60 s) e retirar das pendências o que foi resolvido (`config.json`, limites do Uvicorn, teto global, aviso de `127.0.0.1`).
- [ ] **Passo 6:** suíte inteira dos dois lados e CI verdes. Commit `chore: prepara a versao 1.0.0`.
- [ ] **Passo 7 (manual):** roteiro completo de `docs/teste-manual-app.md` com o instalador do artefato da CI e o APK `eas build -p android --profile production-apk`; gravar o GIF do modo painel.
- [ ] **Passo 8 (manual):** PR com merge commit; `git tag -a v1.0.0 -m "PcX Control 1.0.0"` e `git push origin v1.0.0`; esperar o rascunho da release, anexar o APK e publicar.

---

## Depois deste plano

- Tornar o repositório antigo (`PcX_Control`) privado e atualizar os links do portfólio e do LinkedIn.
- v1.1: HTTPS com certificado autoassinado (impressão digital no QR, campo `v`), pré-requisito do Deck.
- Pendências menores que continuam em `docs/decisoes-e-pendencias.md`.
