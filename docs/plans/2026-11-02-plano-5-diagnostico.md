# PcX Control — Plano 5: diagnóstico, logs de falhas e GPU (agente 0.5.0, app 0.4.0)

**Objetivo:** o agente aponta sozinho por que o celular não conecta (menu "Verificar conexão"), guarda na pasta `logs` tudo o que for preciso para tratar travamentos e problemas de placa de vídeo, e mostra uso e temperatura da GPU coerentes com o Gerenciador de Tarefas em NVIDIA, AMD e Intel.

**Arquitetura:** verificações como funções puras com entradas injetáveis (`diagnostics/checks.py`); leituras do Windows isoladas em `diagnostics/windows.py` e `sensors/windows/d3dkmt.py`, testadas com saídas gravadas; a janela só monta a tela.

**Spec:** `docs/specs/2026-11-02-diagnostico-design.md`.

## Restrições globais

- Agente `0.5.0`; protocolo `1`, só acréscimos (`vendor` em cada GPU).
- Logs nunca trazem senha, código ou token. Textos em `tray/texts.py`, cores em `tray/theme.py`.
- Arquivos de janela com até ~150 linhas.
- Commits no nome do Alexandre, em português, padrão Conventional Commits.

## Desvio do spec (decidido antes de começar)

O uso da GPU continua vindo dos contadores PDH, sem os motores de vídeo: isso já faz o número
bater com o Gerenciador de Tarefas (a amostra real da RX 7600 dá 1,90%). O D3DKMT entra só para a
temperatura (`KMTQAITYPE_ADAPTERPERFDATA`), uma estrutura pequena e testável sem a placa. Ler o
uso pelo D3DKMT (`D3DKMTQueryStatistics`, estrutura grande) fica para quando outra placa mostrar
números estranhos.

## Revisão de riscos

1. Driver sem `ADAPTERPERFDATA` (WDDM antigo) ou temperatura 0: sem temperatura, sem erro.
2. PowerShell ausente, lento ou com saída inesperada no diagnóstico: o item vira `info` ("não deu para verificar"), nunca trava a janela.
3. Pessoa recusa o pedido de administrador ao criar a regra: o diagnóstico roda de novo e mostra o mesmo problema, sem caixa de erro.
4. Duas placas com o mesmo nome: a temperatura é associada pelo LUID, não pelo nome.
5. Exceção dentro de uma verificação: só aquele item vira `info` com o erro; os outros aparecem.

---

### Tarefa 1: uso da GPU sem os motores de vídeo

**Arquivos:** `sensors/windows/gpu.py`, `tests/test_windows_gpu_parser.py`, `tests/data/pdh_rx7600_instant_replay.json`.

- `parse_gpu_usage` ignora instâncias cujo `engtype_` comece com `video` (`video codec`, `video decode`, `video encode`, `video processing`).
- A amostra gravada traz as duas instâncias reais da RX 7600 (vídeo 70,4794…, compute 1,8990…).
- Testes: `test_rx7600_instant_replay_uses_compute_not_video` (1,90%); `test_video_engines_are_ignored[...]` para os quatro nomes; `test_unknown_engine_type_still_counts`.

### Tarefa 2: fabricante, ordem das placas e log de GPU

**Arquivos:** `sensors/base.py`, `sensors/windows/gpu.py`, `sensors/windows/native.py`, `sensors/windows/provider.py`, `docs/protocol/fixtures` (regerar), testes.

- `AdapterInfo` ganha `vendor_id: int`; `vendor_name(vendor_id) -> str` (`0x10DE` nvidia, `0x1002` amd, `0x8086` intel, senão `outra`).
- `GpuReading.vendor: str | None = None`; `parse_gpu_usage` preenche e devolve as placas ordenadas por `vram_total_bytes` decrescente.
- `describe_adapters(adapters) -> list[str]`: uma linha por placa (nome, fabricante, `VendorId` em hexa, VRAM em GiB, LUID). O provider registra essas linhas ao abrir e quando a lista de placas muda.
- `RateLimitedLog(logger, interval_s=60)`: `warning(key, msg, *args)` registra no máximo uma vez por minuto por `key`; usado nas falhas de PDH, DXGI, NVML e D3DKMT.
- Testes: ordem por VRAM (integrada de 512 MiB depois da dedicada de 8 GiB); `vendor` de cada `VendorId`; linhas de `describe_adapters`; `RateLimitedLog` com relógio falso; fixtures do protocolo regeradas com `vendor` e o teste de contrato verde.

### Tarefa 3: temperatura pelo D3DKMT

**Arquivos:** criar `sensors/windows/d3dkmt.py`, `tests/test_d3dkmt.py`; modificar `provider.py`.

- `parse_perfdata(raw: bytes) -> float | None`: estrutura `D3DKMT_ADAPTER_PERFDATA` de 64 bytes; `Temperature` (ULONG, décimos de °C) no deslocamento 56; 0 ou acima de 1500 → `None`.
- `D3dkmtTemperatures(luids: list[str])`: `read() -> dict[str, float]` (LUID → °C) via `gdi32` `D3DKMTOpenAdapterFromLuid`, `D3DKMTQueryAdapterInfo` (`Type = 62`, `KMTQAITYPE_ADAPTERPERFDATA`, `PhysicalAdapterIndex = 0`) e `D3DKMTCloseAdapter`.
- No provider: temperatura pelo D3DKMT por LUID; para a placa sem valor, NVML pelo nome (como hoje). `gpu.temp` aparece quando qualquer fonte devolver valor.
- Testes: `parse_perfdata` com bytes montados (52,0 °C; 0 → `None`; curto demais → `None`); provider com fontes falsas (D3DKMT vence, NVML completa, nenhuma → sem `gpu.temp`); `@windows`: `D3dkmtTemperatures` com os LUIDs reais do runner roda sem exceção.

### Tarefa 4: logs de travamento

**Arquivos:** criar `crashlog.py`, `tests/test_crashlog.py`; modificar `main.py`, `server.py`.

- `install_crash_logging(log_dir: Path) -> None`: `sys.excepthook` e `threading.excepthook` registram `CRITICAL` com o nome da thread; `faulthandler.enable(file=logs/crash.log)` (arquivo cortado para os últimos 1 MiB ao iniciar); cabeçalho com data e versão a cada início.
- `asyncio`: o servidor instala `loop.set_exception_handler` que registra `ERROR` com o traceback.
- Log de início (`INFO`): versão do agente, versão do Windows (`platform.version()`), Python, se é o `.exe`.
- Chamado em `run_tray` e `run_console`, logo depois de `setup_logging`.
- Testes: exceção numa thread vira linha `CRITICAL` com a thread; `sys.excepthook` idem; `crash.log` criado, cortado quando grande e com cabeçalho; exceção no laço do asyncio registrada.

### Tarefa 5: diagnóstico (lógica)

**Arquivos:** criar `diagnostics/__init__.py`, `model.py`, `checks.py`, `windows.py`, `runner.py`, `report.py` e testes.

- `Status = Literal["ok", "atencao", "problema", "info"]`; `Fix = Literal["abrir_rede", "criar_firewall"]`; `CheckResult(id, group, title, status, detail, fix: Fix | None = None)`.
- `checks.py`, uma função por item do spec (`rede.ip`, `rede.tipo`, `rede.firewall`, `rede.vpn`, `agente.local`, `antivirus.terceiros`, `sensores.gpu`, `sensores.leitura`), todas recebendo os dados prontos.
- `windows.py`: `firewall_rules_script`/`parse_firewall_rules(json)` (nome, ativa, direção, ação, perfis, programa); `security_products_script`/`parse_security_products(json)` (nome, tipo antivírus ou firewall, se é do Windows); todos com `encoding="utf-8-sig"`, `stdin=DEVNULL`, sem janela e prazo de 15 s.
- `runner.py`: `run_all(context) -> list[CheckResult]` com cada verificação protegida (exceção → `info` com o erro) e uma linha de log por resultado.
- `report.py`: `build_report(results, facts) -> str` (versões, resultados, placas de rede e de vídeo, instâncias PDH); passa pelo `redact` do log.
- Testes: cada verificação em cada situação do spec; parsers com saídas gravadas (objeto, lista, vazio, lixo, BOM); `run_all` com uma verificação que levanta; relatório sem senha, código nem token.

### Tarefa 6: diagnóstico (janela, menu e correções)

**Arquivos:** criar `tray/diagnostics_window.py`, `tray/diagnostics_rows.py`; modificar `tray/icon.py`, `tray/app.py`, `tray/texts.py`, `tray/theme.py`, `packaging/firewall.cmd` (sem mudança de comportamento), testes.

- Menu: "Verificar conexão" entre "Celulares pareados" e "Trocar senha".
- `DiagnosticsWindow(BaseWindow)` 560×640: "Verificando…", lista com rolagem agrupada, ícone de situação com as cores novas `ok` e `atencao` no tema (contraste ≥ 4,5 sobre o fundo), botão de correção por item; rodapé "Copiar relatório", "Verificar de novo", "Fechar". A execução roda numa thread e a janela consulta com `after`.
- Correções: `abrir_rede` → `ms-settings:network-status`; `criar_firewall` → `ShellExecute` com `runas` em `cmd /c ""<app>\firewall.cmd" add "<exe>""` (só no `.exe` instalado); ao voltar o foco para a janela, roda de novo.
- Testes (Xvfb e CI do Windows): a janela abre, mostra os resultados de um runner falso, cada correção chama a ação injetada, "Copiar relatório" põe o texto na área de transferência, nada fica cortado; tema com as novas cores e contraste.

### Tarefa 7: cores de alerta no app

**Arquivos:** `mobile/src/alerts/levels.ts` (novo), `mobile/src/storage/alertLimits.ts` (novo), `mobile/src/components/Gauge.tsx`, `mobile/src/components/MetricCard.tsx`, `mobile/app/pc/[id]/panel.tsx`, `mobile/app/pc/[id]/index.tsx`, `mobile/app/settings.tsx`, testes.

- `alertLevel(value, limits)` → `normal | alto | critico`, funções puras; limites padrão (uso 80/95%, temperatura 75/85 °C) e leitura/gravação no aparelho com validação (alto < crítico, faixas da spec) e "Restaurar padrão".
- `Gauge` e `MetricCard` recebem os selos (`badges`) e o nível da borda; a GPU tem dois selos empilhados (uso e temperatura) ao lado do título e do nome; o cálculo do nome desconta a largura dos selos.
- Temperatura e VRAM mudam de cor sem selo; a rede fica sem alerta.
- Seção "Alertas" em Configurações.
- Testes da spec, seção 7 (limites exatos, selos independentes, borda, configurações, tela do PC, cartão de 160 px).

### Tarefa 8: versão, documentação e revisão

- Agente `0.5.0` e app `0.4.0`; `CHANGELOG.md` `[agente 0.5.0]` e `[app 0.4.0]`; tabela de compatibilidade do README; README (diagnóstico e temperatura em AMD e Intel); `docs/teste-manual-app.md` (itens do diagnóstico e comparação com o Gerenciador de Tarefas na RX 7600); `docs/decisoes-e-pendencias.md`.
- Revisão independente da branch, correções com teste, CI verde, PR.
