# PcX Control v1 — Especificação de design

- **Data:** 30/10/2026
- **Autor:** Alexandre Queiroz (Owaleee)
- **Status:** aguardando revisão
- **Substitui:** repositório `Owaleee/PcX_Control` (v0.1.0, que será tornado privado)

## 1. Objetivo

Aplicativo Android de código aberto (licença MIT) que transforma o celular em um **painel de sensores do PC Windows** na rede local, com conexão em segundos por **QR code** ou **IP + senha**.

O projeto também serve de portfólio de backend: autenticação com sessões, protocolo em tempo real, persistência, arquitetura testável e CI.

### Critérios de sucesso da v1

1. Uma pessoa sem conhecimento técnico instala o agente por um `.exe`, cria uma senha, escaneia o QR code e vê os dados do PC em menos de 2 minutos.
2. O modo painel em paisagem roda por horas com a tela ligada, atualizando a cada 1 s, sem travar ou desconectar em Wi-Fi doméstico estável.
3. Sem celular conectado, o agente consome menos de 1% de CPU em média.
4. A suíte de testes do agente roda em Linux (sem Windows) e cobre pelo menos 80% do código não específico do Windows.
5. A release `v1.0.0` no GitHub contém o instalador do agente, o APK, as notas e um README com GIF do modo painel.

### Diferenciais escolhidos

- **Modo painel ("sensor panel")** em paisagem, sempre ligado, com temas Escuro, Claro e AMOLED.
- **Pareamento por QR code**, com alternativa manual de IP + senha.

### Fora da v1 (a arquitetura deve permitir a entrada depois)

Deck com ações no PC, perfis automáticos por programa em foco, Wake-on-LAN, desligar e suspender, temperatura da CPU, FPS, descoberta automática do PC na rede, HTTPS, iPhone, histórico por núcleo de CPU.

## 2. Arquitetura

```
pcx-control/
├─ agent/                    # PC Windows: Python 3.13 + FastAPI + SQLite
│  ├─ pcx_agent/
│  │  ├─ main.py             # entrada: python -m pcx_agent [--demo]
│  │  ├─ config.py           # pastas, porta, versão, opções
│  │  ├─ sensors/
│  │  │  ├─ base.py          # SensorProvider (interface) e modelos Snapshot
│  │  │  ├─ windows/         # psutil, GPU via PDH/DXGI, temperatura via NVML
│  │  │  └─ fake.py          # dados simulados: testes, Linux, Docker, demo
│  │  ├─ sampler.py          # laço único de coleta
│  │  ├─ session.py          # regra de sessão ativa única
│  │  ├─ auth/               # senha, pareamento, tokens, limite de tentativas
│  │  ├─ storage/            # SQLite: configurações, aparelhos, histórico
│  │  ├─ api/                # HTTP /v1 e WebSocket /v1/stream
│  │  └─ tray/               # bandeja (pystray) e janelas (tkinter)
│  ├─ tests/
│  └─ pyproject.toml
├─ mobile/                   # Android: Expo + TypeScript + expo-router
├─ docs/
└─ .github/workflows/
```

### Princípios

- **Uma coleta só.** O `Sampler` lê os sensores num laço em segundo plano. A API nunca dispara coleta.
- **Sensores atrás de interface.** `SensorProvider` expõe `capabilities()` e `read() -> Snapshot`. A API, o histórico e os testes não conhecem o Windows.
- **Consulta PDH persistente.** A consulta de contadores de GPU fica aberta e é lida a cada volta do laço. Não existe `sleep` dentro da leitura.
- **API versionada** em `/v1`. A versão do protocolo é independente da versão do app.
- **Uma sessão ativa por vez** (seção 4).

### Fluxo de dados

```
SensorProvider ──► Sampler ──► última leitura (memória)
                     ├──► sessão ativa via WebSocket (1 s)
                     └──► SQLite: média e máximo a cada 5 s, retenção de 24 h
```

| Estado do agente | Intervalo de coleta | WebSocket |
|---|---|---|
| Ocioso (sem sessão ativa) | 5 s | nenhum |
| Ativo (uma sessão) | 1 s | envia para o único celular ativo |

## 3. Pareamento e autenticação

### Senha do PC

- Criada na primeira execução pelo assistente da bandeja. Mínimo de 8 caracteres.
- Armazenada como hash `scrypt` (biblioteca padrão), com salt aleatório e parâmetros guardados junto ao hash. A senha em texto nunca é gravada.
- Esqueceu? A bandeja oferece "Trocar senha". O acesso físico ao PC é a prova de dono.
- Ao trocar a senha, o agente pergunta se deve revogar todos os aparelhos.

### Identidade do PC

Na primeira execução, o agente gera um `agent_id` (UUID v4) e o salva. Os tokens ficam ligados ao `agent_id`, não ao IP, então mudar de IP não exige parear de novo.

### Pareamento por QR code (caminho principal)

1. Na bandeja, "Parear celular" abre a janela com o QR code.
2. O QR contém `pcx://pair?v=1&id=<agent_id>&h=<ipv4>&p=<porta>&c=<código>`.
3. O código tem 128 bits aleatórios, é de uso único e vale 5 minutos. Abrir a janela de novo gera outro código e invalida o anterior.
4. O app chama `POST /v1/pair` com `{ "code": "...", "device_name": "Moto G de Alexandre" }`.

### Pareamento manual

O app chama `POST /v1/pair` com `{ "password": "...", "device_name": "..." }`.

### Resposta do pareamento

```json
{ "device_id": "uuid", "token": "<256 bits em base64url>", "agent": { "id": "...", "name": "...", "version": "1.0.0", "protocol": 1 } }
```

- O celular guarda o token com `expo-secure-store`. A senha nunca é guardada no celular.
- O agente guarda apenas `sha256(token)`, junto com o nome do aparelho, a data de criação e a data do último uso.

### Validade e revogação

- O token expira **30 dias após o último uso**. Cada uso renova o prazo.
- A bandeja lista os aparelhos pareados, marca o ativo e permite revogar cada um.
- `DELETE /v1/devices/me` permite ao celular se desconectar e esquecer o PC.

### Proteções

- **Limite de tentativas:** 5 falhas de `pair` por minuto por IP bloqueiam esse IP por 60 s. A resposta é `429`, com `retry_after`.
- Comparações de código e de hash em tempo constante.
- No WebSocket, o token vai na primeira mensagem, nunca na URL.
- O instalador cria a regra de firewall apenas para o perfil **Privado**.

### Limitação assumida

A v1 usa HTTP sem criptografia. O README informa que o uso é para redes domésticas confiáveis. O campo `v` do QR permite incluir, na v1.1, a impressão digital de um certificado autoassinado para HTTPS. **HTTPS é pré-requisito para o Deck executar ações no PC.**

## 4. Sessão ativa única

- Vários celulares podem estar pareados com o mesmo PC, mas apenas **um tem sessão ativa**.
- Enquanto há sessão ativa, outros aparelhos recebem `409` nas rotas protegidas (`snapshot`, `history`) e no WebSocket, com `{ "code": "session_busy", "active_device": "Moto G de Alexandre" }`.
- **Assumir a sessão:** o app pergunta "PC em uso por *X*. Assumir?". Se o usuário confirmar, envia `takeover: true` na autenticação. O aparelho antigo recebe o fechamento `4409` ("Sessão assumida por outro aparelho").
- A sessão termina quando o WebSocket fecha, quando o aparelho fica 15 s sem responder ao ping ou quando é revogado.
- Ao terminar, o agente volta ao modo ocioso.

## 5. Dados e protocolo

### Métricas da v1

| Grupo | Campos | Fonte |
|---|---|---|
| CPU | `cpu.total` (%) | psutil |
| RAM | `ram.percent`, `ram.used_bytes`, `ram.total_bytes` | psutil |
| Discos | por unidade fixa: `mount`, `percent`, `used_bytes`, `total_bytes`; global: `read_bps`, `write_bps` | psutil |
| Rede | `net.down_bps`, `net.up_bps` | psutil |
| GPU | por placa: `id`, `name`, `usage_percent`, `vram_used_bytes`, `vram_total_bytes`, `temp_c` (`null` se indisponível) | PDH, DXGI e NVML |
| Sistema | `host_name`, `uptime_s` | psutil |

As capacidades disponíveis (por exemplo `gpu.temp`) são informadas no `hello`. O app esconde o que não for suportado.

### Rotas HTTP

| Método e rota | Autenticação | Função |
|---|---|---|
| `GET /v1/info` | não | `agent_id`, nome, versão, protocolo, se a sessão está ocupada |
| `POST /v1/pair` | código ou senha | pareamento |
| `GET /v1/snapshot` | token e sessão ativa | uma leitura |
| `GET /v1/history?metric=&range=15m\|1h\|24h` | token e sessão ativa | pontos `{t, avg, max}` |
| `DELETE /v1/devices/me` | token | desparear o próprio aparelho |

### WebSocket `/v1/stream`

```jsonc
// celular → agente, em até 5 s após abrir
{ "type": "auth", "token": "...", "takeover": false }

// agente → celular
{ "type": "hello", "protocol": 1, "agent": { "id": "...", "name": "...", "version": "1.0.0" },
  "capabilities": ["cpu", "ram", "disk", "net", "gpu", "gpu.temp"] }
{ "type": "snapshot", "seq": 42, "t": "2026-10-30T21:00:00Z", "data": { /* métricas */ } }
```

| Código de fechamento | Significado | Ação do app |
|---|---|---|
| `4401` | token inválido, expirado ou revogado | apagar o token e voltar ao pareamento |
| `4408` | autenticação não enviada em 5 s | reconectar |
| `4409` | sessão assumida por outro aparelho | mostrar aviso e não reconectar sozinho |
| `4423` | sessão ocupada e `takeover` falso | perguntar se deve assumir |

O envio usa uma fila de 1 item, em que a leitura mais nova substitui a anterior. Um celular lento nunca bloqueia o `Sampler`.

### Histórico

- A cada 5 s, o agente grava uma linha por métrica: `(ts, metric, avg, max)`.
- Uma limpeza por hora remove dados com mais de 24 h.
- Ao abrir o painel, o app busca 15 min de histórico e depois acrescenta as leituras ao vivo.

## 6. Aplicativo Android

### Telas (expo-router)

1. **Meus PCs:** um cartão por PC pareado, com nome, IP, indicador online/offline (via `/v1/info`), indicação de ocupado e botão **Adicionar PC**.
2. **Adicionar PC:** câmera para o QR code (`expo-camera`) e link "Digitar IP e senha". O campo de IP aceita vírgula como ponto e remove zeros à esquerda.
3. **Painel (retrato):** cartões de CPU, RAM, GPU (uso, VRAM, temperatura), Rede e Discos, cada um com gráfico dos últimos 15 min. Tocar no cartão abre o detalhe com 15 min, 1 h e 24 h.
4. **Modo painel (paisagem):** tela cheia, `expo-keep-awake`, indicadores grandes em grade e controles que aparecem por 3 s ao tocar. Opção de escurecer a tela. **Deslocamento de pixels** a cada 3 minutos contra burn-in.
5. **Ajustes do PC:** renomear, desconectar, esquecer o PC.

### Temas

Escuro, Claro e AMOLED (fundo `#000000`). A escolha vale para o app inteiro e fica salva.

### Mensagens de erro (exemplos obrigatórios)

- "Senha incorreta. Restam 3 tentativas."
- "Muitas tentativas. Tente de novo em 60 s."
- "Código expirado. Gere outro no PC."
- "PC não encontrado. Confira se o celular e o PC estão na mesma rede Wi-Fi e se o PcX Control está aberto."
- "Sessão assumida por outro aparelho."
- "Este celular foi desconectado no PC. Pareie de novo."

### Organização do código

- `ConnectionManager`: classe TypeScript sem React, responsável por WebSocket, autenticação, reconexão (1, 2, 4, 8 s, até 15 s), sessão e histórico. Emite eventos de estado.
- Hooks (`usePcConnection`, `useMetric`) conectam a classe às telas.
- Gráficos próprios com `react-native-svg`, sem biblioteca de gráficos.
- Em segundo plano, o app fecha o WebSocket. Ao voltar, reconecta.
- Validação do JSON recebido em `src/protocol/` (reaproveita a ideia de `isStats` da v0.1).

## 7. Agente no Windows

- **Bandeja (`pystray`):** Parear celular, Celulares pareados, Trocar senha, Iniciar com o Windows (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`), Abrir pasta de logs, Sair.
- **Janelas (`tkinter`):** assistente da primeira execução (criar senha, mostrar QR), janela de pareamento, lista de aparelhos.
- **Porta padrão** 8765, configurável em `config.json`.
- **Instância única:** um mutex nomeado do Windows impede um segundo agente e mostra "O PcX Control já está rodando".
- **Dados** em `%LOCALAPPDATA%\PcXControl\`: `pcx.db`, `config.json`, `logs\`.
- **Logs** em JSON por linha, com rotação de 5 × 1 MB. Senha, código e token nunca são registrados.
- **Modo demo:** `python -m pcx_agent --demo` usa `FakeSensorProvider`, não abre bandeja e roda em Linux e Docker. Imprime um código de pareamento no terminal.

### Código reaproveitado da v0.1

- `gpu.py` (leitura PDH e agregação por LUID) e `adaptadores_gpu.py` (DXGI), adaptados para consulta PDH persistente e cache dos nomes por 60 s.
- Mensagens de erro e a validação de JSON do app.

## 8. Testes

### Agente (pytest)

- **Unitários:** hash e verificação de senha; geração, expiração e uso único do código; limite de tentativas; regras de sessão (ocupada, assumir, timeout); agregação e retenção do histórico; parser da GPU com amostras gravadas.
- **Integração:** HTTP e WebSocket com `FakeSensorProvider` e banco temporário, incluindo os códigos 4401, 4408, 4409 e 4423.
- **Cobertura:** mínimo de 80% nos módulos fora de `sensors/windows` e `tray/`.
- **Teste rápido no Windows (CI):** o provedor real devolve um `Snapshot` válido, mesmo sem GPU.

### App (Jest)

- `ConnectionManager` com WebSocket simulado: autenticação, reconexão, códigos de fechamento e assumir sessão.
- Validação do protocolo, normalização de IP e formatação de números.
- `typecheck` e `lint`.

### Manual (checklist no aparelho, antes de cada release)

QR code, pareamento manual, assumir sessão entre dois celulares, revogar na bandeja, modo painel por 1 h, três temas, perda e retorno do Wi-Fi, troca de IP do PC.

## 9. CI e lançamento

- **GitHub Actions a cada push:** agente (pytest em Ubuntu e Windows, ruff) e app (lint, typecheck, Jest).
- **Na tag `vX.Y.Z`:** workflow no Windows gera o PyInstaller (`onedir`) e o instalador Inno Setup (`PcXControl-Setup-X.Y.Z.exe`) e anexa à GitHub Release.
- **APK:** `eas build -p android --profile production-apk` e anexo manual à mesma release na v1.
- **Instalador:** instala para o usuário atual e pede administrador uma vez para criar a regra de firewall (perfil Privado, porta configurada). O desinstalador remove a regra.
- **Versionamento:** SemVer, `CHANGELOG.md` no formato Keep a Changelog, commits no padrão Conventional Commits. Protocolo versionado à parte (`protocol: 1`).
- **Documentação:** README em português com resumo em inglês, GIF do modo painel, diagrama de arquitetura, guia de instalação, `docs/protocolo.md` e licença MIT.
- **Repositório antigo:** tornado privado. Links do portfólio e do LinkedIn apontarão para o novo.

## 10. Riscos

| Risco | Mitigação |
|---|---|
| Antivírus marcar o `.exe` do PyInstaller | modo `onedir`, build pública na CI, instruções no README |
| Contadores PDH diferentes em AMD/Intel | parser tolerante, campos `null`, teste em outro PC antes da release |
| NVML ausente em placas não NVIDIA | capacidade `gpu.temp` só aparece quando o NVML carregar |
| Token visível em Wi-Fi compartilhado | aviso no README; HTTPS na v1.1 antes do Deck |
| Burn-in em telas OLED no modo painel | deslocamento de pixels e opção de escurecer |
