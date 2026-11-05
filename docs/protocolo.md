# Protocolo do PcX Control (versão 1)

Como o app conversa com o agente. Todos os exemplos estão em
[`docs/protocol/fixtures/`](protocol/fixtures/): eles são gerados pelo código do agente e os
testes dos dois lados (agente e app) leem os mesmos arquivos.

- Base: `http://<ip-do-pc>:<porta>` (porta padrão **8765**). WebSocket: `ws://<ip>:<porta>/v1/stream`.
- Rotas protegidas usam `Authorization: Bearer <token>`.
- Erros HTTP têm sempre o corpo `{"code": "...", "message": "..."}`, às vezes com campos extras.

## QR code de pareamento

```
pcx://pair?v=1&id=<agent_id>&h=<ipv4>&p=<porta>&c=<código>
```

O código vale 5 minutos e só pode ser usado uma vez. Gerar outro invalida o anterior.

## Rotas HTTP

| Rota | Autenticação | Resposta | Exemplo |
| --- | --- | --- | --- |
| `GET /v1/info` | não | id, nome, versão, protocolo e se há sessão ativa | [`info.json`](protocol/fixtures/info.json) |
| `POST /v1/pair` | código **ou** senha | `device_id`, `token` e dados do agente | [`pair.json`](protocol/fixtures/pair.json) |
| `GET /v1/snapshot` | token + sessão livre ou própria | uma leitura (`data` de `snapshot_message`) | [`snapshot_message.json`](protocol/fixtures/snapshot_message.json) |
| `GET /v1/history?metric=&range=` | token + sessão livre ou própria | pontos `{t, avg, max}`; `range` = `15m`, `1h` ou `24h` | [`history.json`](protocol/fixtures/history.json) |
| `DELETE /v1/devices/me` | token | `204`; o aparelho é desconectado | |

Corpo do `POST /v1/pair`: `{"device_name": "Moto G", "code": "..."}` ou `{"device_name": "Moto G", "password": "..."}`.

| Status | `code` | Campos extras |
| --- | --- | --- |
| 401 | `bad_credentials` | `attempts_left` ([exemplo](protocol/fixtures/error_bad_credentials.json)) |
| 401 | `invalid_token` | |
| 409 | `session_busy` | `active_device` ([exemplo](protocol/fixtures/error_session_busy.json)) |
| 410 | `code_invalid_or_expired` | |
| 422 | `invalid_name`, `invalid_metric`, `invalid_range`, `invalid_request` | |
| 429 | `rate_limited` | `retry_after` (e cabeçalho `Retry-After`) |
| 503 | `starting` | |

## Métricas do histórico

Nomes e regra de cálculo em [`metrics.json`](protocol/fixtures/metrics.json): `cpu.total`,
`ram.percent`, `net.down_bps`, `net.up_bps`, `disk.read_bps`, `disk.write_bps`, `gpu.usage`,
`gpu.temp` e `gpu.vram_percent`. As métricas `gpu.*` usam a primeira GPU e só existem quando há dado.

## WebSocket `/v1/stream`

1. O celular abre a conexão e, em até 5 s, envia `{"type": "auth", "token": "...", "takeover": false}`.
2. O agente responde com [`hello`](protocol/fixtures/hello.json) e depois envia
   [`snapshot`](protocol/fixtures/snapshot_message.json) a cada leitura (1 por segundo).
3. O celular **não precisa enviar mais nada**. O agente envia pings do protocolo WebSocket e fecha
   conexões mortas. Mensagens extras do celular são aceitas e ignoradas.
4. Um celular lento recebe sempre a leitura mais nova (`seq` pode pular).

| Fechamento | Significado | O que o app faz |
| --- | --- | --- |
| `4401` | token inválido, expirado ou revogado (ou mensagem inicial malformada) | apaga o PC salvo e volta ao pareamento |
| `4408` | autenticação não chegou em 5 s | reconecta |
| `4409` | sessão assumida por outro aparelho | avisa e não reconecta sozinho |
| `4423` | sessão ocupada; o motivo traz o nome do aparelho ativo (até 123 bytes) | pergunta se quer assumir (`takeover: true`) |
| `1001` | sessão encerrada (por exemplo, o mesmo celular reconectou) | reconecta |
| outros | queda de rede | reconecta com espera de 1, 2, 4, 8 s, até 15 s |

## Como o protocolo evolui

O agente deve ficar **estável**: depois de instalado, só precisa de atualização para corrigir
algo sério. As funções novas entram pelo **app**. Para isso, o protocolo segue estas regras:

1. **Só acréscimos na versão 1.** Campos, métricas, rotas e capacidades novas podem entrar;
   nada existente muda de nome, tipo ou significado, e nada é removido.
2. **O app tolera o que não conhece.** Campos extras no JSON são ignorados, e o app usa a
   lista `capabilities` do `hello` para mostrar só o que o agente oferece.
3. **Função nova no agente vira capacidade nova.** Por exemplo, um agente que passe a ler a
   temperatura da CPU anuncia `cpu.temp`; o app esconde o cartão em agentes que não anunciam.
4. **Quebra de compatibilidade só com protocolo 2**, e o agente continua aceitando o 1 por pelo
   menos uma versão. Desde o app 0.5.0, o app que não reconhece o protocolo anunciado (no `hello`
   ou em `/v1/info`) mostra "Atualize o app" com o link das releases em vez de só falhar; se o PC
   anuncia um protocolo mais antigo, pede para atualizar o programa no PC.

### Acréscimos já feitos na versão 1

| Agente | Acréscimo | Como o app trata |
| --- | --- | --- |
| 0.5.0 | `vendor` em cada item de `gpus` (`"nvidia"`, `"amd"`, `"intel"` ou `"outra"`, a partir do `VendorId` da placa) | opcional; ausente ou inválido vira `null`. Usado em relatório e log, não aparece na tela |
| 0.5.0 | `gpus` ordenadas pela VRAM dedicada, da maior para a menor | o app continua mostrando `gpus[0]` no painel, que agora é a placa dedicada |
| 0.6.0 | `temp_warn_c` em cada item de `gpus` (temperatura de alerta da placa, em °C, informada pelo driver) | opcional; `null` quando o driver não informa. Ausente ou inválido vira `null` |
