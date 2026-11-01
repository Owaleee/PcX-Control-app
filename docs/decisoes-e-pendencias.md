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

---

# App Android v0.2.0 (Plano 2)

Documentos de origem: o [spec](specs/2026-10-30-pcx-control-v1-design.md) (§4 a §6) e o
[plano 2](plans/2026-11-01-plano-2-app.md).

## Decisões que divergem ou completam o plano

| Decisão | Por quê |
| --- | --- |
| **Uma conexão por PC**, num `PcProvider` compartilhado pelas telas | Se cada tela abrisse a sua, o mesmo celular abriria várias sessões e uma derrubaria a outra em ciclo. |
| Avisos de "PC em uso" e "desconectado no PC" ficam no `PcProvider` | Valem em qualquer tela do PC, inclusive no modo painel. |
| Contrato do protocolo em `docs/protocol/fixtures`, gerado pelo agente | Se um lado mudar o formato, os testes do outro lado falham. |
| QR code impresso no terminal do agente | Permite testar o app antes da bandeja do Windows (Plano 3). |
| O mesmo QR lido várias vezes gera um único pareamento | A câmera dispara o mesmo código várias vezes por segundo. |
| Espera de reconexão com teto de 15 s depois da variação de ±20% | O spec diz "até 15 s". |
| Ao voltar do segundo plano, só reconecta se foi o app que pausou | Não reabre sessões revogadas, assumidas ou ocupadas. |
| Contraste mínimo 4,5:1 também no texto secundário dos temas | Legibilidade, principalmente no AMOLED. |
| Cartão sem ação é uma `View`, e a barra de progresso é acessível | O leitor de tela (TalkBack) não enxergava a barra. |
| Instalação das dependências com a tabela local do SDK (`EXPO_OFFLINE`) | O ambiente de build não alcança o servidor de compatibilidade do Expo. |
| `react-dom` fixado na versão do React do SDK | Conflito de versões puxado pelo expo-router. |
| Removidos do template os arquivos que não fazem parte do app | `App.tsx`, `index.ts`, favicon, licença duplicada e arquivos de configuração de ferramentas. |
| Perfil `development` do EAS não criado | Exigiria o `expo-dev-client`; o Expo Go cobre o desenvolvimento. |

## Achados da revisão independente (corrigidos)

1. **Conexão meio-aberta ficava em "Conectado" com valores congelados** (PC suspenso, roteador
   reiniciado): agora um vigia reconecta após 8 s sem nenhuma mensagem do agente.
2. **QR expirado diante da câmera virava uma sequência de tentativas** até bloquear o IP: o QR que
   falhou não é tentado de novo.
3. **Histórico não era buscado de novo** depois de assumir a sessão ou reconectar: cada sessão nova
   refaz a busca.
4. **"Desconectar" duplicava a tela inicial** na pilha de navegação: as saídas voltam à tela
   inicial existente.
5. **Trocar o IP do PC exigia parear de novo**: agora o endereço pode ser corrigido nos ajustes
   (o app confere que é o mesmo PC) e um novo pareamento preserva o apelido.
6. **Gráficos distorciam o tempo** (o eixo seguia a ordem dos pontos): agora o eixo é o horário.
7. **Modo painel não esmaecia valores antigos** e o aviso de estado ficava fixo (risco de
   burn-in): agora esmaece e o aviso anda junto com o painel.
8. **Modo painel ignorava as áreas seguras** (recorte da câmera e barra de navegação).
9. **"Esquecer este PC" mostrava um alerta de erro**: a conexão é encerrada antes.

Durante as correções, um teste também pegou um defeito novo: depois de parar a conexão de
propósito, voltar do segundo plano a reabria.

## Pendências (menores)

- Texto do aviso de sessão assumida pode ficar mais claro ("Outro aparelho assumiu a sessão deste PC").
- Um QR de outro PC já pareia naquele PC antes de o app recusar (aparelho órfão no outro agente).
- Voltar da tela de pareamento com um pedido em andamento ainda pode abrir o painel depois.
- Câmera negada em definitivo: oferecer o atalho para as configurações do Android.
- Uma GPU ou disco com dado inválido descarta a leitura inteira em vez de só o item.
- O `hello` não confere se o PC no endereço é o mesmo salvo.
- Cartões de disco sem gráfico; taxas de leitura e escrita dos discos não aparecem.
- Gráfico de 24 h sem redução de pontos (até ~17 mil pontos redesenhados).
- O tema salvo aparece um instante depois da abertura (começa no escuro).
- Estado "ocupado" sem botão "Tentar de novo".
- Agente: aviso quando não encontra o IP da rede e o QR sai com `127.0.0.1`.
- Testes de navegação real (`renderRouter`) e do `AppState` integrado ao `PcProvider`.
- Rodar `npx expo install --check` numa máquina com acesso ao servidor do Expo antes do build.

## Validação

- 228 testes no app (Jest) e 189 no agente (pytest); typecheck, lint e CI verdes.
- Falta o teste manual no celular e no PC: [roteiro](teste-manual-app.md).
