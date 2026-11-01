# Decisões técnicas e pendências

Registro de como o agente v0.1.0 foi construído: o que mudou em relação ao plano, o que a
revisão independente encontrou e o que ficou para depois. Os documentos de origem são o
[spec](specs/2026-10-30-pcx-control-v1-design.md) e o [plano](plans/2026-10-30-plano-1-agente.md).

## Como o trabalho foi feito

- 12 tarefas, cada uma começando pelo teste (que falha primeiro) e terminando num commit.
- Integração contínua a cada push, no Ubuntu e no Windows. O passo do Windows **falha se algum
  teste específico de Windows for pulado**.
- Revisão final independente da branch inteira, seguida de uma rodada de correções, cada uma com
  um teste que falhava antes.
- Teste manual com servidor real (Uvicorn + cliente WebSocket) e no PC com Windows (RTX 3070).

## Decisões que divergem ou completam o plano

| Decisão | Por quê |
| --- | --- |
| `release()` aceita `session=` e só libera se for a mesma sessão | Evita que a conexão antiga do mesmo celular derrube a nova ao fechar. |
| O coletor apaga o histórico com mais de 24 h a cada hora | O spec exige a limpeza e o plano a tinha esquecido. |
| Mensagem inicial inválida, binária ou grande fecha com `4401` | O spec não define código para lixo. Veja a pendência sobre `4400`/`1008`. |
| Sessão expirada ou substituída pelo mesmo aparelho fecha com `1001` | O app deve tratar como queda de rede e reconectar. |
| `Sampler.nudge()` acorda o laço quando a sessão começa | Sem isso, o primeiro dado levaria até 5 s. |
| Código nativo do Windows separado do parser puro de GPU | O pacote importa e é testado no Linux. |
| `websockets` é dependência obrigatória | O Uvicorn sem ela não serve WebSocket; os testes em memória não pegavam isso. |
| Sem `--demo` e sem senha, o terminal pede a senha | Provisório até a bandeja existir (Plano 3). |
| `--demo` usa pasta temporária | Não grava a senha de demonstração no banco real. |
| O celular não precisa enviar nada depois do `auth` | O agente envia pings do protocolo WebSocket (5 s) e cada envio bem-sucedido renova a sessão. |
| Agente na versão `0.1.0` | O `1.0.0` fica para a release com app e instalador. |

## Achados da revisão independente (corrigidos)

1. **Limite de tentativas furável** por pedidos simultâneos, que ainda alocavam ~32 MiB por
   tentativa de senha. Agora a tentativa é reservada de forma atômica e o scrypt roda no máximo
   2 vezes em paralelo.
2. **Celular que só escuta era derrubado após 15 s.** Agora vale o envio bem-sucedido e o ping do
   protocolo. Verificado com servidor real.
3. **Revogar um aparelho não encerrava a transmissão dele.** Agora a sessão cai na hora com `4401`.
4. **SQLite bloqueava o laço de eventos.** Gravações em outra thread, numa única transação, com
   `synchronous=NORMAL`.
5. **Falha no NVML apagava a GPU inteira.** A temperatura é isolada e o sensor tenta voltar a cada
   60 s, assim como os contadores de GPU.

## Pendências (menores, sem urgência)

- Um `code` ou token com caractere inválido (surrogate) gera erro 500 em vez de 401.
- O motivo do fechamento `4423` pode ser cortado quando o nome do aparelho tem mais de 123 bytes.
- O teste de corrida do código de pareamento não falha sem o lock; precisa forçar a intercalação.
- Considerar `4400`/`1008` para mensagem inicial malformada, para não apagar um token válido no app.
- O prazo de 30 dias do token não renova durante uma transmissão longa (só na conexão).
- Nomes de aparelho com emoji composto (ZWJ) são recusados.
- Uma leitura de sensor travada deixa o dado antigo sem aviso e pode atrasar o desligamento.
- Pendrives (unidades removíveis) podem aparecer na lista de discos.
- Duas placas iguais recebem a mesma temperatura (a ligação é pelo nome).
- O `config.json` do spec (§7) não existe; há apenas `--port`.
- Endurecer o Uvicorn (`ws_max_size`, `limit_concurrency`) e criar um teto global de tentativas.

## Validação em hardware real

- Windows 11, Ryzen 5 5600, 32 GB de RAM, NVIDIA GeForce RTX 3070.
- Os 4 testes específicos de Windows passam. O `snapshot` trouxe CPU, RAM, 3 discos, rede e a GPU
  com VRAM e temperatura.
- AMD, Intel e várias GPUs físicas **ainda não foram testadas**.
