# PcX Control — Plano 1: backend do agente

**Objetivo:** entregar o agente (Python/FastAPI/SQLite) que lê sensores, pareia celulares, mantém uma sessão ativa única, transmite leituras por WebSocket e guarda 24 h de histórico, rodando em modo `--demo` no Linux.

**Arquitetura:** `SensorProvider` (interface) alimenta um `Sampler` único. A API consulta `Sampler.latest`, `HistoryStore`, `PairingService` e `SessionManager`. Nada na API conhece o Windows. A bandeja e o instalador (Plano 3) e o app (Plano 2) ficam fora deste plano.

**Stack:** Python 3.13, FastAPI, Uvicorn, Pydantic 2, psutil, sqlite3 (biblioteca padrão), hashlib.scrypt. Testes: pytest, pytest-asyncio, pytest-cov, httpx. Lint: ruff. Somente Windows: pywin32, nvidia-ml-py.

**Spec:** `docs/specs/2026-10-30-pcx-control-v1-design.md`

## Restrições globais

- Python 3.13; código em `agent/pcx_agent/`; testes em `agent/tests/`.
- Porta padrão 8765; versão do app `1.0.0`; `protocol: 1`; API sob `/v1`.
- Senha: mínimo 8 caracteres, hash scrypt com salt. Token: 256 bits (`secrets.token_urlsafe(32)`), guardado como `sha256`. Código de pareamento: 128 bits, uso único, validade de 300 s.
- Token expira 30 dias após o último uso. Limite: 5 falhas por minuto por IP bloqueiam por 60 s.
- Coleta: 5 s sem sessão ativa, 1 s com sessão. Histórico: média e máximo a cada 5 s, retenção de 24 h.
- Fechamentos do WebSocket: `4401` token inválido, `4408` sem auth em 5 s, `4409` sessão assumida, `4423` sessão ocupada sem `takeover`.
- Sem uso por núcleo de CPU. Senha, código e token nunca aparecem em logs.
- Commits em português, no padrão Conventional Commits, sem trailers de coautoria.
- Cobertura mínima de 80% fora de `sensors/windows` e `tray`.

## Revisão de riscos (entradas que o spec não detalha)

1. Dois pedidos de `pair` com o mesmo código ao mesmo tempo: só um pode vencer.
2. `device_name` vazio, muito longo (>64) ou com caracteres de controle: rejeitar com 422, nunca 500.
3. Primeira mensagem do WebSocket que não é JSON, não é `auth` ou é gigante: fechar sem derrubar o agente.
4. `history` com métrica ou intervalo desconhecidos: 422 com mensagem, nunca 500.
5. `provider.read()` lançando exceção (GPU some, driver reinicia): o `Sampler` registra, mantém a última leitura e continua.

## Estrutura de arquivos

```
agent/
├─ pyproject.toml
├─ pcx_agent/
│  ├─ __init__.py              # __version__, PROTOCOL
│  ├─ config.py                # Settings, load_settings
│  ├─ main.py                  # CLI: --demo, --data-dir, --port
│  ├─ session.py               # SessionManager
│  ├─ sampler.py               # Sampler
│  ├─ sensors/base.py          # modelos + SensorProvider
│  ├─ sensors/fake.py          # FakeSensorProvider
│  ├─ sensors/windows/         # gpu.py, provider.py
│  ├─ storage/db.py            # Database
│  ├─ storage/history.py       # HistoryStore
│  ├─ auth/passwords.py        # hash e PasswordService
│  ├─ auth/ratelimit.py        # RateLimiter
│  ├─ auth/pairing.py          # PairingService
│  └─ api/app.py, api/stream.py
└─ tests/
.github/workflows/agent.yml
```

---

### Tarefa 1: Projeto, modelos de leitura e sensor simulado

**Arquivos:** criar `agent/pyproject.toml`, `pcx_agent/__init__.py`, `sensors/base.py`, `sensors/fake.py`, `tests/test_fake_sensors.py`, `.github/workflows/agent.yml`.

**Interfaces:**
- Produz `GpuReading(id, name, usage_percent, vram_used_bytes|None, vram_total_bytes|None, temp_c|None)`, `DiskVolume(mount, percent, used_bytes, total_bytes)`, `Snapshot(t: datetime, cpu_total, ram_percent, ram_used_bytes, ram_total_bytes, disks, disk_read_bps, disk_write_bps, net_down_bps, net_up_bps, gpus, host_name, uptime_s)` (todos Pydantic; percentuais entre 0 e 100).
- Produz `Snapshot.metrics() -> dict[str, float]` com as chaves de histórico: `cpu.total`, `ram.percent`, `net.down_bps`, `net.up_bps`, `disk.read_bps`, `disk.write_bps`, `gpu.usage`, `gpu.temp`, `gpu.vram_percent` (as `gpu.*` usam a primeira GPU e somem se não houver dado).
- Produz `SensorProvider` (Protocol): `capabilities() -> set[str]`, `read() -> Snapshot`, `close() -> None`. Capacidades possíveis: `cpu ram disk net gpu gpu.temp`.
- Produz `FakeSensorProvider(seed: int = 0)`, determinístico.

- [ ] **Passo 1: escrever os testes** (`test_fake_sensors.py`): `test_snapshot_rejects_percent_over_100` (`Snapshot` com `cpu_total=101` levanta `ValidationError`); `test_fake_is_deterministic_per_seed` (dois providers com a mesma seed geram o mesmo `cpu_total` na 1ª leitura); `test_fake_declares_capabilities` (contém `{"cpu","ram","disk","net","gpu","gpu.temp"}`); `test_metrics_keys` (`metrics()` contém todas as chaves da lista acima); `test_metrics_omits_gpu_when_no_gpu` (sem GPU, não há chaves `gpu.*`).
- [ ] **Passo 2:** rodar `cd agent && pytest tests/test_fake_sensors.py -v`. Esperado: FAIL (módulos inexistentes).
- [ ] **Passo 3:** criar `pyproject.toml` (extras `dev` com pytest, pytest-asyncio, pytest-cov, httpx, ruff; extra `windows` com pywin32 e nvidia-ml-py; marcador `windows`; `asyncio_mode = "auto"`; ruff com `line-length = 100`) e implementar os modelos e o `FakeSensorProvider`. Os valores simulados oscilam de forma suave (seno + ruído da seed).
- [ ] **Passo 4:** criar `.github/workflows/agent.yml`: matriz Ubuntu e Windows, Python 3.13, `pip install -e agent[dev]`, `ruff check`, `pytest --cov=pcx_agent --cov-fail-under=80` no Ubuntu e `pytest -m windows` no Windows.
- [ ] **Passo 5:** rodar os testes. Esperado: PASS.
- [ ] **Passo 6:** commit `feat(agent): adiciona modelos de leitura e sensor simulado`.

---

### Tarefa 2: Configuração e banco de dados

**Arquivos:** criar `config.py`, `storage/db.py`, `tests/test_db.py`.

**Interfaces:**
- Produz `Settings(data_dir: Path, port: int = 8765, version: str)` e `load_settings(data_dir: Path | None = None, port: int | None = None) -> Settings` (padrão: `%LOCALAPPDATA%\PcXControl` no Windows, `~/.local/share/pcx-control` nos demais; cria a pasta).
- Produz `Database(path: Path | str)` com `get_setting(key) -> str | None`, `set_setting(key, value)`, `execute(sql, params=())`, `query(sql, params=()) -> list[sqlite3.Row]`, `close()`, `agent_id` (UUID v4 gerado uma vez e guardado em `settings`) e `agent_name`.
- Esquema: `settings(key PK, value)`, `devices(id PK, name, token_hash UNIQUE, created_at, last_used_at)`, `history(ts, metric, avg, max, PK(ts, metric))`. Conexão com `check_same_thread=False` e um `threading.Lock` em todas as operações.

- [ ] **Passo 1: testes** (`test_db.py`): `test_agent_id_is_stable_across_reopen` (mesmo UUID ao reabrir o arquivo); `test_set_get_setting`; `test_schema_has_tables` (as três tabelas existem); `test_concurrent_writes_from_threads` (8 threads gravando 50 linhas cada em `history`, 400 linhas no fim, sem exceção); `test_load_settings_creates_dir` (usando `tmp_path`).
- [ ] **Passo 2:** rodar. Esperado: FAIL.
- [ ] **Passo 3:** implementar `config.py` e `Database` (WAL ligado, `row_factory = sqlite3.Row`).
- [ ] **Passo 4:** rodar. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(agent): adiciona configuracao e banco SQLite`.

---

### Tarefa 3: Senha com scrypt

**Arquivos:** criar `auth/passwords.py`, `tests/test_passwords.py`.

**Interfaces:**
- Consome `Database.get_setting/set_setting`.
- Produz `hash_password(password: str) -> str` (formato `scrypt$n$r$p$salt_b64$hash_b64`, com `n=2**15, r=8, p=1`), `verify_password(password: str, stored: str) -> bool` (usa `hmac.compare_digest`), `PasswordService(db)` com `is_set() -> bool`, `set_password(password: str) -> None` (levanta `ValueError` se `len < 8`) e `verify(password: str) -> bool` (`False` se não houver senha).

- [ ] **Passo 1: testes:** `test_hash_is_not_plaintext_and_salted` (duas chamadas geram hashes diferentes e nenhum contém a senha); `test_verify_accepts_right_and_rejects_wrong`; `test_verify_rejects_malformed_stored_value` (retorna `False`, não levanta); `test_set_password_rejects_short` (7 caracteres → `ValueError`); `test_service_without_password_never_verifies`; `test_password_stored_only_as_hash` (nenhuma linha de `settings` contém a senha).
- [ ] **Passo 2:** rodar. Esperado: FAIL.
- [ ] **Passo 3:** implementar com `hashlib.scrypt` e `secrets.token_bytes(16)`; a chave `password_hash` fica em `settings`.
- [ ] **Passo 4:** rodar. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(agent): adiciona senha com hash scrypt`.

---

### Tarefa 4: Limite de tentativas

**Arquivos:** criar `auth/ratelimit.py`, `tests/test_ratelimit.py`.

**Interfaces:**
- Produz `RateLimiter(max_failures=5, window_s=60.0, block_s=60.0, clock=time.monotonic)` com `blocked_for(key: str) -> float | None` (segundos restantes), `record_failure(key: str) -> int` (devolve tentativas restantes antes do bloqueio) e `reset(key: str) -> None`.

- [ ] **Passo 1: testes** (clock falso): `test_blocks_after_five_failures` (a 5ª falha bloqueia; `blocked_for` ≈ 60); `test_remaining_attempts_counts_down` (4, 3, 2, 1, 0); `test_block_expires` (após 61 s, `blocked_for` é `None`); `test_failures_outside_window_are_forgotten`; `test_keys_are_independent`; `test_reset_clears_failures`.
- [ ] **Passo 2:** rodar. Esperado: FAIL.
- [ ] **Passo 3:** implementar com `deque` de instantes por chave e dicionário de bloqueios.
- [ ] **Passo 4:** rodar. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(agent): adiciona limite de tentativas`.

---

### Tarefa 5: Pareamento e tokens de aparelho

**Arquivos:** criar `auth/pairing.py`, `tests/test_pairing.py`.

**Interfaces:**
- Consome `Database`, `PasswordService.verify`, `RateLimiter`.
- Produz `Device(id: str, name: str, created_at: float, last_used_at: float)`, `PairResult(device_id: str, token: str)` e `PairError(Exception)` com atributos `kind: Literal["rate_limited", "bad_credentials", "code_invalid_or_expired", "invalid_name"]`, `retry_after: float | None`, `attempts_left: int | None`.
- Produz `PairingService(db, passwords, limiter, code_ttl_s=300.0, token_ttl_s=30*86400.0, clock=time.monotonic, now=time.time)` com `new_code() -> str` (substitui o anterior), `pair(device_name: str, *, code: str | None = None, password: str | None = None, client_ip: str) -> PairResult`, `authenticate(token: str) -> Device | None` (renova `last_used_at`; `None` se expirado), `revoke(device_id: str) -> bool`, `revoke_all() -> None`, `list_devices() -> list[Device]`.
- Regras: nome com 1 a 64 caracteres visíveis, sem caracteres de controle; o código é consumido de forma atômica (protegido por `threading.Lock`); erro de senha chama `limiter.record_failure(client_ip)`; sucesso chama `reset`.

- [ ] **Passo 1: testes:** `test_pair_with_password_returns_token_and_stores_only_hash` (o token não aparece em nenhuma coluna de `devices`); `test_pair_with_code_is_single_use` (2º uso → `code_invalid_or_expired`); `test_new_code_invalidates_previous`; `test_code_expires_after_300s` (clock falso); `test_wrong_password_reports_attempts_left` (4, depois 3); `test_sixth_attempt_is_rate_limited_with_retry_after`; `test_authenticate_valid_and_unknown_token`; `test_token_expires_30_days_after_last_use` e `test_use_renews_expiry` (`now` falso); `test_revoke_makes_token_invalid`; `test_revoke_all`; `test_concurrent_pair_same_code_only_one_wins` (10 threads, exatamente 1 sucesso); `test_device_name_validation` (vazio, 65 caracteres e `"a\x00b"` → `invalid_name`).
- [ ] **Passo 2:** rodar. Esperado: FAIL.
- [ ] **Passo 3:** implementar. O código vem de `secrets.token_urlsafe(16)`; a comparação usa `hmac.compare_digest`.
- [ ] **Passo 4:** rodar. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(agent): adiciona pareamento, tokens e revogacao`.

---

### Tarefa 6: Sessão ativa única

**Arquivos:** criar `session.py`, `tests/test_session.py`.

**Interfaces:**
- Produz `ActiveSession(device_id: str, device_name: str, evict: Callable[[], None])` e `AcquireResult(status: Literal["granted", "busy"], active_device_name: str | None)`.
- Produz `SessionManager(timeout_s=15.0, clock=time.monotonic)` com `acquire(session: ActiveSession, takeover: bool) -> AcquireResult`, `release(device_id: str) -> None`, `touch(device_id: str) -> None`, `active() -> ActiveSession | None` (expira sessões sem `touch` há mais de `timeout_s`) e `has_active() -> bool`.

- [ ] **Passo 1: testes:** `test_first_acquire_is_granted`; `test_second_acquire_is_busy_and_names_the_active_device`; `test_takeover_evicts_previous_and_grants` (o `evict` antigo é chamado exatamente 1 vez); `test_same_device_reacquire_does_not_evict_itself`; `test_release_frees_session`; `test_release_of_non_active_device_is_noop`; `test_stale_session_expires_after_15s_without_touch`; `test_touch_keeps_session_alive`.
- [ ] **Passo 2:** rodar. Esperado: FAIL.
- [ ] **Passo 3:** implementar com `threading.Lock`; `evict` é chamado fora do lock.
- [ ] **Passo 4:** rodar. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(agent): adiciona sessao ativa unica`.

---

### Tarefa 7: Histórico

**Arquivos:** criar `storage/history.py`, `tests/test_history.py`.

**Interfaces:**
- Consome `Database`.
- Produz `HistoryStore(db)` com `record(ts: float, metric: str, avg: float, max_: float) -> None`, `query(metric: str, range_: Literal["15m", "1h", "24h"], now: float) -> list[HistoryPoint]` (`HistoryPoint(t: float, avg: float, max: float)`, ordenado por `t`) e `prune(now: float, keep_s: float = 86400.0) -> int`. Constante `VALID_RANGES`.

- [ ] **Passo 1: testes:** `test_query_returns_only_requested_range` (pontos antigos de 20 min ficam fora de `15m` e dentro de `1h`); `test_points_are_ordered`; `test_prune_removes_older_than_24h_and_returns_count`; `test_query_unknown_metric_returns_empty`; `test_query_invalid_range_raises_value_error`; `test_record_same_ts_metric_overwrites` (chave primária).
- [ ] **Passo 2:** rodar. Esperado: FAIL.
- [ ] **Passo 3:** implementar com `INSERT OR REPLACE`.
- [ ] **Passo 4:** rodar. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(agent): adiciona historico de metricas`.

---

### Tarefa 8: Sampler

**Arquivos:** criar `sampler.py`, `tests/test_sampler.py`.

**Interfaces:**
- Consome `SensorProvider`, `HistoryStore`, `Snapshot.metrics()`.
- Produz `Sampler(provider, history, has_active_session: Callable[[], bool], on_snapshot: Callable[[Snapshot], None] | None = None, idle_interval=5.0, active_interval=1.0, flush_interval=5.0, clock=time.monotonic, wall=time.time)` com `latest: Snapshot | None`, `async tick() -> None` (lê o provider em `asyncio.to_thread`, atualiza `latest`, acumula, chama `on_snapshot` só se há sessão ativa, grava média e máximo a cada `flush_interval`), `current_interval() -> float`, `async run() -> None` (laço até `stop()`) e `stop() -> None`.

- [ ] **Passo 1: testes:** `test_tick_updates_latest`; `test_interval_is_5s_idle_and_1s_active`; `test_on_snapshot_called_only_with_active_session`; `test_flush_writes_avg_and_max_after_5s` (3 leituras com `cpu_total` 10, 20, 60 → média 30, máximo 60 em `cpu.total`); `test_no_flush_before_5s`; `test_provider_error_keeps_last_snapshot_and_loop_continues` (provider que levanta na 2ª chamada; `latest` permanece; a 3ª chamada funciona); `test_run_stops_on_stop`.
- [ ] **Passo 2:** rodar. Esperado: FAIL.
- [ ] **Passo 3:** implementar; erros do provider vão para `logging.getLogger("pcx_agent.sampler").exception`.
- [ ] **Passo 4:** rodar. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(agent): adiciona laco unico de coleta`.

---

### Tarefa 9: API HTTP

**Arquivos:** criar `api/app.py`, `tests/conftest.py`, `tests/test_api_http.py`.

**Interfaces:**
- Consome todas as classes das tarefas 1 a 8.
- Produz `AppContext(settings, db, passwords, limiter, pairing, sessions, history, sampler, provider)`, `build_context(settings: Settings, provider: SensorProvider) -> AppContext` e `create_app(ctx: AppContext) -> FastAPI` (sem `/docs`, `/redoc` nem `/openapi.json`).
- Rotas: `GET /v1/info` → `{agent_id, name, version, protocol, busy: bool}`; `POST /v1/pair` com `{device_name, code?, password?}` → `{device_id, token, agent}`; `GET /v1/snapshot`; `GET /v1/history?metric=&range=` → `{metric, range, points}`; `DELETE /v1/devices/me` → 204. Rotas protegidas usam `Authorization: Bearer <token>`.
- Erros (corpo `{code, message, ...}`): 401 `invalid_token`; 401 `bad_credentials` + `attempts_left`; 410 `code_invalid_or_expired`; 422 para nome, métrica ou intervalo inválidos; 429 `rate_limited` + `retry_after` (cabeçalho `Retry-After` também); 409 `session_busy` + `active_device`; 503 `starting` se ainda não há leitura.
- `conftest.py` fornece a fixture `ctx` (banco em `tmp_path`, `FakeSensorProvider`, clock falso) e `client` (`httpx.AsyncClient` com `ASGITransport`) e a função `pair_device(client, ctx, name) -> str` (devolve o token).

- [ ] **Passo 1: testes:** `test_info_is_public_and_has_protocol_1`; `test_docs_routes_are_off` (`/docs` e `/openapi.json` → 404); `test_pair_with_password_ok`; `test_pair_wrong_password_401_with_attempts_left`; `test_pair_rate_limited_429_with_retry_after`; `test_pair_code_single_use_410`; `test_pair_invalid_name_422` (vazio, 65 caracteres, controle); `test_snapshot_requires_token_401`; `test_snapshot_with_token_ok`; `test_snapshot_503_before_first_reading`; `test_history_ok`; `test_history_unknown_metric_422` e `test_history_invalid_range_422`; `test_delete_me_revokes_and_token_stops_working`; `test_snapshot_busy_409_names_active_device` (outro aparelho com sessão ativa); `test_no_secret_in_logs` (`caplog` após parear não contém senha, código nem token).
- [ ] **Passo 2:** rodar. Esperado: FAIL.
- [ ] **Passo 3:** implementar com um `exception_handler` para `PairError` e uma dependência `current_device` que valida o token e checa a sessão. IP do cliente: `request.client.host`.
- [ ] **Passo 4:** rodar. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(agent): adiciona API HTTP /v1`.

---

### Tarefa 10: WebSocket de transmissão

**Arquivos:** criar `api/stream.py`; modificar `api/app.py` (registrar a rota); criar `tests/test_api_stream.py`.

**Interfaces:**
- Consome `AppContext`, `PairingService.authenticate`, `SessionManager.acquire/release/touch`, `Sampler.on_snapshot`.
- Produz a rota `WS /v1/stream`. Fluxo: aceitar; esperar a 1ª mensagem por até 5 s; exigir `{"type":"auth","token":str,"takeover":bool=false}` com no máximo 4 KiB; autenticar; adquirir a sessão; enviar `{"type":"hello","protocol":1,"agent":{id,name,version},"capabilities":[...]}`; depois `{"type":"snapshot","seq":int,"t":iso8601,"data":Snapshot}` a cada leitura nova, usando um slot de 1 item em que a leitura nova substitui a antiga; qualquer mensagem do cliente (por exemplo `{"type":"ping"}`) chama `sessions.touch`; ao terminar, `sessions.release`.
- Fechamentos conforme as restrições globais; uma sessão expulsa recebe `4409`.

- [ ] **Passo 1: testes** (`TestClient` do Starlette): `test_auth_then_hello_then_snapshot`; `test_invalid_token_closes_4401`; `test_no_auth_in_5s_closes_4408` (timeout reduzido por parâmetro de `create_app`); `test_busy_without_takeover_closes_4423`; `test_takeover_closes_old_with_4409_and_new_receives_snapshots`; `test_garbage_first_message_closes_without_crashing` (texto que não é JSON, JSON sem `type`, `type` diferente de `auth`, mensagem de 10 KiB: o servidor continua respondendo `/v1/info` depois); `test_slow_client_gets_latest_not_backlog` (várias leituras sem consumir; a próxima mensagem tem `seq` maior que 1); `test_disconnect_releases_session` (depois da desconexão, `/v1/info` mostra `busy: false`); `test_revoked_token_cannot_connect`.
- [ ] **Passo 2:** rodar. Esperado: FAIL.
- [ ] **Passo 3:** implementar. A ponte entre a thread do `Sampler` e o laço asyncio usa `loop.call_soon_threadsafe` para preencher o slot.
- [ ] **Passo 4:** rodar. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(agent): adiciona WebSocket /v1/stream`.

---

### Tarefa 11: Sensores do Windows

**Arquivos:** criar `sensors/windows/__init__.py`, `gpu.py`, `provider.py`, `tests/test_windows_gpu_parser.py`, `tests/test_windows_provider.py`, `tests/data/pdh_samples.json`.

**Interfaces:**
- Produz (puro, testável no Linux) `parse_gpu_usage(samples: list[dict], adapters: dict[str, AdapterInfo]) -> list[GpuReading]`, em que `AdapterInfo(name: str, vram_total_bytes: int)` e a chave é o LUID `0x…_0x…`. Reaproveita a lógica de `resumir_uso_gpu` do repositório antigo: filtra por LUID DXGI não-software, soma por motor, devolve o maior motor, limita a 100, ignora `nan` e negativos.
- Produz `WindowsGpuReader` (consulta PDH persistente de `\GPU Engine(*)\Utilization Percentage` e `\GPU Adapter Memory(*)\Dedicated Usage`; DXGI por ctypes, com cache de 60 s; temperatura via NVML ligada à placa pelo nome, `None` se não houver) e `WindowsSensorProvider` (CPU com `psutil.cpu_percent(interval=None)` iniciado no construtor; discos fixos; rede e I/O de disco calculados pelo delta entre leituras).
- Suposição a validar no seu PC: a primeira leitura PDH ainda não tem dados, então `gpus` vem vazio nela; o provider não deve lançar nesse caso.

- [ ] **Passo 1: testes do parser** (dados gravados em `pdh_samples.json`, com as instâncias do seu PC e com LUID de software): `test_sums_per_engine_and_takes_busiest`; `test_ignores_software_adapter_luid`; `test_ignores_nan_negative_and_malformed_names`; `test_caps_at_100`; `test_empty_samples_returns_empty_list`; `test_two_physical_gpus_listed_separately`; `test_vram_total_comes_from_adapter_info`.
- [ ] **Passo 2:** testes do provider, marcados `@pytest.mark.windows` e ignorados fora do Windows: `test_read_returns_valid_snapshot_even_without_gpu` (valida com `Snapshot`); `test_two_reads_do_not_raise_and_second_has_net_rates`; `test_capabilities_include_gpu_temp_only_when_nvml_loads`.
- [ ] **Passo 3:** rodar os testes do parser no Linux. Esperado: FAIL, depois PASS após implementar.
- [ ] **Passo 4:** implementar `parse_gpu_usage`, `WindowsGpuReader` e `WindowsSensorProvider`, copiando de `agente/gpu.py` e `agente/adaptadores_gpu.py` do repositório antigo apenas o necessário, em módulos renomeados e sem `if __name__ == "__main__"`.
- [ ] **Passo 5:** commit `feat(agent): adiciona sensores do Windows`. Rodar `pytest -m windows` no seu PC (ou no CI do Windows) e anotar o resultado no commit seguinte, se ajustar algo.

---

### Tarefa 12: CLI, modo demo e teste de ponta a ponta

**Arquivos:** criar `main.py`, `__main__.py`, `agent/README.md`, `tests/test_e2e_demo.py`.

**Interfaces:**
- Consome `build_context`, `create_app`, `FakeSensorProvider`, `WindowsSensorProvider`.
- Produz `main(argv: list[str] | None = None) -> int` com `--demo` (provider simulado, sem bandeja, senha `demo-password` se ainda não houver, imprime o código de pareamento no terminal), `--data-dir`, `--port` e `--host` (padrão `0.0.0.0`); `python -m pcx_agent` chama `main()`. Sem `--demo` em sistema não Windows, sai com código 2 e mensagem clara.

- [ ] **Passo 1: teste** (`test_e2e_demo.py`): `test_full_flow_with_fake_provider` sobe o app em memória, pareia por código, abre o WebSocket, recebe `hello` e 2 snapshots, consulta `history` depois de avançar o clock em 5 s, desconecta e confere que o agente voltou ao intervalo de 5 s. `test_cli_demo_prints_pairing_code` (captura de saída de `main(["--demo", "--data-dir", tmp, "--port", "0", "--dry-run"])`, em que `--dry-run` monta tudo e sai sem abrir o servidor). `test_cli_without_demo_on_linux_exits_2`.
- [ ] **Passo 2:** rodar. Esperado: FAIL.
- [ ] **Passo 3:** implementar o CLI e o `README` do agente (como rodar em `--demo`, como rodar os testes).
- [ ] **Passo 4:** rodar a suíte inteira: `cd agent && pytest --cov=pcx_agent --cov-fail-under=80 && ruff check .`. Esperado: tudo verde.
- [ ] **Passo 5:** fazer um teste manual: `python -m pcx_agent --demo --port 8765`, e em outro terminal `curl localhost:8765/v1/info`. Esperado: JSON com `protocol: 1`.
- [ ] **Passo 6:** commit `feat(agent): adiciona CLI e modo demo`; push da branch e conferência do CI no GitHub.

---

## Próximos planos

- **Plano 2:** app Android (expo-router, `ConnectionManager`, QR code, painel, modo painel, temas).
- **Plano 3:** bandeja do Windows, assistente da primeira execução, PyInstaller, Inno Setup, release e README final.
