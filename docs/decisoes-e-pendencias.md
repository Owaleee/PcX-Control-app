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
| Sem `--demo` e sem senha, o terminal pede a senha | Continua no modo `--console`; na bandeja, o assistente cria a senha (agente 0.3.0). |
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
- Testes de navegação real (`renderRouter`) e do `AppState` integrado ao `PcProvider`.
- Rodar `npx expo install --check` numa máquina com acesso ao servidor do Expo antes do build.

## Depois do primeiro teste no celular

- Teste manual no Poco X7 Pro (Android 16): itens 1 a 16 aprovados.
- Pedidos do teste: **percentuais inteiros por padrão**, com a opção "Números precisos" (desligada)
  nas Configurações, e **RAM livre** ao lado da usada. Tamanhos (GiB) e velocidades continuam com
  uma casa decimal, para não esconder valores pequenos como "0,4 KB/s".
- O botão "Aparência" virou "Configurações", com as seções Aparência e Números.

## Validação

- 243 testes no app (Jest) e 189 no agente (pytest); typecheck, lint e CI verdes.
- Falta o teste manual no celular e no PC: [roteiro](teste-manual-app.md).

---

# Agente 0.3.0 no Windows (Plano 3)

Documentos de origem: o [spec](specs/2026-10-30-pcx-control-v1-design.md) (§3, §7 e §9) e o
[plano 3](plans/2026-11-01-plano-3-windows.md). O visual das janelas segue o mockup aprovado em
01/11/2026, com as cores do tema escuro do app.

## Decisões que divergem ou completam o plano

| Decisão | Por quê |
| --- | --- |
| **Versões separadas** para agente e app, com tags `agente-v*` e `app-v*` | Os dois mudam em ritmos diferentes; não faz sentido subir a versão do app quando só o agente mudou. A compatibilidade é dada pelo `protocol`. |
| Regra de firewall **pelo programa**, sem porta fixa | Mudar a porta no `config.json` continua funcionando sem refazer a regra. Continua só no perfil Privado e só na rede local. |
| `AppMutex` do instalador igual ao mutex do agente | O instalador pede para fechar o agente antes de atualizar. |
| Desinstalar mantém `%LOCALAPPDATA%\PcXControl` | Reinstalar não exige parear os celulares de novo. |
| Teto global: 30 senhas erradas por minuto somando todos os IPs | Impede varrer senhas trocando de IP. Vale só para senha: os códigos do QR têm 128 bits, então o dono continua pareando pelo QR mesmo se alguém na rede travar o pareamento por senha por 60 s. Só falhas reais contam, e o teto é conferido antes do limite do IP. |
| Logs escondem qualquer palavra base64url de 22+ caracteres | Pega tokens e códigos sem depender de quem escreve o log. Também esconde o `agent_id` e nomes longos em tracebacks. |
| `setup_logging` assume os loggers do Uvicorn | A configuração padrão do Uvicorn corta a propagação, e os erros dele sumiriam do arquivo. |
| Checagem de porta com `SO_EXCLUSIVEADDRUSE` no Windows | Com `SO_REUSEADDR`, o Windows deixaria dois programas na mesma porta. |
| Ícone recortado em volta do monitor | O ícone do app tem a margem do ícone adaptativo do Android e ficaria minúsculo a 16 px. |
| Interface: cores e tamanhos em `tray/theme.py`, textos em `tray/texts.py`, regras no `AgentController` | Manutenção: mudar uma cor ou frase é mexer num arquivo só; janelas novas herdam de `BaseWindow`. |
| `--self-test` no executável | A CI prova que o `.exe` congelado tem todos os módulos (PyInstaller costuma esquecer importações dinâmicas). |

## Achados da revisão independente (corrigidos)

1. **Uma ação do menu que falhasse travava a bandeja inteira**, inclusive o Sair, sem nada no
   log: agora cada ação é isolada e os erros da interface vão para o `agent.log`.
2. **Erro inesperado ao iniciar** aparecia como o traceback cru do PyInstaller: agora vai para o
   log e vira uma mensagem.
3. **O autoteste não carregava a bandeja**: agora carrega o pystray, o tkinter e o QR no
   executável, e o teste de fumaça exige isso.
4. **Desinstalar podia deixar o início com o Windows apontando para um .exe apagado**, e uma
   atualização religava o início desligado na bandeja: agora o desinstalador sempre remove o
   valor e a atualização não mexe nele.
5. **Reabrir logo depois de Sair** com celular conectado podia dar "porta em uso" no Windows:
   restos em `TIME_WAIT` não contam mais, e Sair termina em poucos segundos.
6. `config.json` salvo com BOM (Bloco de Notas) era ignorado.
7. O teto global bloqueava também o pareamento por QR.
8. Recusar o pedido de administrador mostrava uma caixa de erro no instalador.

## Validação

- Testes no Linux (pytest, cobertura acima de 80%) e na CI do Windows, inclusive as janelas
  (tkinter) e o registro.
- Teste de fumaça na CI do Windows: instala em silêncio, confere a regra de firewall e o início
  com o Windows, roda o `--self-test` no executável e desinstala.
- Falta o roteiro manual "Instalador e bandeja" no PC: [teste manual](teste-manual-app.md).

---

# Agente 0.4.0 e app 0.3.0 (Plano 4)

Documento de origem: o [plano 4](plans/2026-11-02-plano-4-rede-e-ip.md). Motivo: no primeiro
teste em outro PC (Windows 10 com Ethernet e Radmin VPN), o agente estava aberto e a regra de
firewall existia, mas o celular não chegava ao PC, e nem o log nem a janela ajudavam a entender.

## Decisões

| Decisão | Por quê |
| --- | --- |
| O IP do QR vem da placa da rede local, não da rota padrão | Uma VPN pode virar a rota padrão; o celular nunca alcança esse IP. Sem placa local, o agente volta a usar a rota padrão, como antes. |
| VPNs e placas virtuais reconhecidas por nome e por faixa de IP | Radmin usa `26.x`, Hamachi `25.x`, Tailscale `100.64/10`; os nomes cobrem as que usam faixas privadas (ZeroTier, Hyper-V, WSL, VirtualBox). |
| Tipo da rede lido pelo `Get-NetConnectionProfile`, numa thread | É a fonte oficial do Windows, mas leva cerca de 1 s; a janela abre na hora e o aviso aparece depois. Qualquer falha esconde o aviso em vez de travar. |
| A faixa de aviso encolhe o QR | Mantém o endereço do PC e os botões visíveis sem aumentar a janela (que já tem 720 px no assistente). |
| Uma linha de log por tentativa de pareamento e por evento de conexão | Responde na hora "o celular chegou ao PC?". O nome do aparelho vai com `repr`, então nunca quebra a linha. |
| Mensagem de "PC não encontrado" estendida | O spec fixava o texto; a nova versão acrescenta a dica de rede Privada, a causa mais comum no Windows. |
| Pontos automáticos no IP, com separador para blocos curtos | Um IP só com dígitos é ambíguo (`1921681822`); o ponto automático entra quando o bloco não aceita mais dígitos, e `.`, `,` ou espaço fecham blocos curtos. |

## Achados da revisão independente

Corrigidos, cada um com um teste que falhava antes:
1. Editar um bloco no meio do IP juntava ou embaralhava os blocos; agora, com os 4 blocos na tela,
   a edição não redistribui os dígitos.
2. Colar um IP mais curto por cima do atual virava um IP inválido.
3. Um bloco do IP podia passar de 255 enquanto se digitava.
4. Nomes de placa com acento (`Conexão Local`) não batiam com a saída do PowerShell em pt-BR, e o
   aviso de rede Pública nunca aparecia: a leitura agora é em UTF-8.
5. Vários cliques em "Gerar outro código" enfileiravam checagens de rede e faziam a faixa piscar.
6. Um nome de aparelho gigante ia inteiro para o log em cada tentativa.

## Pendências (Plano 4)

- VPN com nome que o agente não reconhece (um WireGuard chamado "casa", um adaptador TAP
  "Ethernet 3") ainda pode ir para o QR. O caminho robusto é ler o tipo e a descrição da placa no
  Windows (`GetAdaptersAddresses` ou `Get-NetAdapter`).
- No modo painel, um toque no cartão da GPU abre o histórico mesmo quando a ideia era só mostrar
  os controles; avaliar toque longo se incomodar no uso.
- `tray/pairing.py` (163 linhas) e `panel.tsx` (177) passaram um pouco das ~150 linhas.
