# Teste manual do app (antes de cada versão)

Faça este roteiro no Expo Go e depois de novo no APK instalado.

## Preparar o PC (Windows)

1. Baixe o instalador (`PcXControl-Setup-X.Y.Z.exe`) do artefato `instalador-windows` da CI
   ou da release do agente, e instale. Aceite o pedido de administrador: ele cria a regra de
   firewall só para a rede **Privada**.
2. A rede Wi-Fi de casa precisa estar como **Privada** nas configurações do Windows.
3. O assistente abre sozinho: crie a senha e deixe o QR code na tela.

**Plano B (sem o instalador, rodando pelo código):** libere a porta no PowerShell como
administrador e rode o agente no terminal.

```powershell
New-NetFirewallRule -Name "PcXControl-Agente" -DisplayName "PcX Control - agente" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765 -Profile Private -RemoteAddress LocalSubnet
cd agent
.\.venv\Scripts\python.exe -m pip install -e ".[dev,windows]"
.\.venv\Scripts\python.exe -m pcx_agent --console
```

## Instalador e bandeja

| # | Teste | Esperado |
| --- | --- | --- |
| A1 | Cronometrar do clique no instalador até o primeiro dado no celular | Menos de 2 minutos |
| A2 | Regra no "Firewall do Windows com Segurança Avançada" | "PcX Control - agente", entrada, perfil Privado, rede local |
| A3 | Abrir o PcX Control de novo pelo menu Iniciar | "O PcX Control já está rodando." |
| A4 | Passar o mouse no ícone, com e sem celular conectado | "aguardando celular" / "conectado a <nome>" |
| A5 | Dois cliques no ícone | Abre "Parear celular" com o QR e a contagem regressiva |
| A6 | Parear pelo QR | "Celular <nome> pareado!", a janela fecha em 2 s e chega a notificação |
| A7 | Esperar 5 minutos com o QR aberto | "Código expirado. Gere outro." e o botão gera outro |
| A8 | Celulares pareados → Desconectar o celular ativo | O app mostra "Este celular foi desconectado no PC." |
| A9 | Trocar senha → "Sim, desconectar" | A senha nova funciona no pareamento manual; todos os celulares saem |
| A10 | Desmarcar e marcar "Iniciar com o Windows" e reiniciar o PC | Abre sozinho só quando marcado |
| A11 | Abrir pasta de logs | Abre `logs`; o `agent.log` não contém senha, código nem token |
| A12 | CPU do agente ocioso no Gerenciador de Tarefas por 5 min | Média abaixo de 1% |
| A13 | Instalar de novo com o agente aberto | O instalador pede para fechar o PcX Control |
| A14 | Desinstalar | A regra de firewall some; `%LOCALAPPDATA%\PcXControl` continua |
| A15 | Marcar a rede do PC como Pública e abrir "Parear celular" | Faixa "A rede deste PC está como Pública…" com o botão que abre as configurações de rede; o QR, o endereço e os botões continuam visíveis |
| A16 | PC com VPN (Radmin, Hamachi) ligada | O endereço da janela é o IP do Wi-Fi ou Ethernet, não o da VPN |
| A17 | Parear com senha errada e depois certa; conectar e sair do app | `agent.log` tem uma linha por tentativa (IP, método, resultado) e as linhas de conexão e desconexão, sem a senha |
| A18 | Bandeja → Verificar conexão, com a rede Privada e a regra criada | "Nenhum problema encontrado" (ou só pontos de atenção); placas de vídeo listadas com fabricante e VRAM |
| A19 | Marcar a rede como Pública e verificar de novo | "Tipo de rede no Windows: Problema" com "Abrir configurações de rede"; ao mudar para Privada e voltar à janela, verifica de novo sozinho |
| A20 | Apagar a regra "PcX Control - agente" e verificar | "Regra do firewall: Problema"; "Criar regra do firewall" pede administrador e, ao voltar, fica OK |
| A21 | Com a Radmin VPN ligada, verificar | "VPN: Atenção" com o nome da Radmin |
| A22 | Salvar pacote de suporte (agente 0.6.0; antes era "Copiar relatório") e abrir o `.zip` | Relatório com versões, resultados, placas de rede e de vídeo, e os logs; sem senha, código ou token |
| A23 | PC com placa AMD (RX 7600): comparar com o Gerenciador de Tarefas por 2 min, com e sem jogo | Uso da GPU a até 5 pontos e temperatura a até 2 °C do Gerenciador |
| A24 | Conferir a pasta `logs` depois de abrir o agente | `crash.log` com o cabeçalho da versão; `agent.log` com as linhas "Placa de video:" e a de início com as versões |
| A25 | Marcar a rede como Pública e apagar a regra do firewall, sem abrir a janela | Em até 5 minutos o ícone da bandeja muda e chega **uma** notificação; o clique duplo no ícone abre o Verificar conexão. Corrigir os dois apaga o alerta e o clique duplo volta a abrir "Parear celular" |
| A26 | Verificar conexão → Reiniciar sensores | Os sensores voltam em poucos segundos e o app continua recebendo leituras |
| A27 | Abrir outro programa na porta 8765 (por exemplo `python -m http.server 8765`), fechar o agente e abri-lo de novo | O agente avisa que a porta está ocupada; **Trocar porta** escolhe a próxima livre, o QR passa a usar a nova e o celular pareia de novo |
| A28 | Verificar conexão → Copiar caminho | O caminho da pasta de logs vai para a área de transferência (colar no Explorer abre a pasta) |
| A29 | Salvar pacote de suporte e abrir o `.zip` | Tem relatório, `agent.log`, `crash.log` e `gpu.log`; **não** tem arquivo `.db`; procurar o nome do seu usuário do Windows em todos os arquivos não acha nada |
| A30 | Renomear a placa da Radmin VPN (ou outra VPN) para "casa" e verificar | "VPN: Atenção" com o nome novo, e o QR continua com o IP do Wi-Fi ou Ethernet |
| A31 | Encerrar o PcXControl.exe pelo Gerenciador de Tarefas e abrir de novo | Aparece "O agente fechou inesperadamente" com o horário da última atividade |
| A32 | Reiniciar o PC (com e sem "Iniciar com o Windows") | **Sem** o aviso de fechamento inesperado |

## Roteiro

| # | Teste | Esperado |
| --- | --- | --- |
| 1 | Adicionar PC pelo QR code | Abre o painel do PC e mostra "Conectado" |
| 2 | Ler um QR de outra coisa (link, Wi-Fi) | "Este QR code não é do PcX Control." e a câmera continua |
| 3 | Pareamento manual com senha errada | "Senha incorreta. Restam N tentativas." |
| 4 | Pareamento manual certo (IP com vírgula) | Abre o painel |
| 5 | Painel | CPU, RAM, GPU (VRAM e temperatura), rede e discos com valores plausíveis |
| 6 | Tocar no cartão da CPU | Gráfico com 15 min, 1 h e 24 h; média e máximo |
| 7 | Modo painel | Gira para paisagem, a tela não apaga, toque mostra Sair/Tema/Escurecer por 3 s |
| 8 | Sair do modo painel pelo gesto de voltar | Volta para retrato; a tela volta a apagar normalmente |
| 9 | Temas Escuro, Claro e AMOLED | Tudo legível; AMOLED com fundo preto |
| 10 | Desligar o Wi-Fi do celular por 20 s e religar | "Reconectando…", valores esmaecidos, volta sozinho |
| 11 | Segundo celular pareado tenta conectar | Pergunta "Assumir a sessão?"; ao assumir, o primeiro mostra "Sessão assumida por outro aparelho" |
| 12 | Mandar o app para segundo plano por 1 min | Ao voltar, reconecta sozinho |
| 13 | Esquecer o PC nos ajustes | Some da lista; no PC, o token deixa de valer |
| 14 | Modo painel por 1 h | Sem travar nem desconectar |
| 15 | Suspender o PC com o painel aberto e acordar | Em até ~10 s mostra "Reconectando…" com valores esmaecidos; volta sozinho quando o PC acorda |
| 16 | Trocar o IP do PC (ou reiniciar o roteador) e corrigir em Ajustes do PC → "Salvar endereço" | Volta a conectar sem parear de novo; o apelido continua |
| 17 | Ler um QR code expirado (mais de 5 minutos) | Mostra "Código expirado. Gere outro no PC." uma vez, sem bloquear o celular por excesso de tentativas |

| 18 | Configurações → "Números precisos" desligado (padrão) e ligado | Percentuais inteiros (51%) e, ligado, com uma casa (50,5%), no painel, no detalhe e no modo painel |
| 19 | Cartão de memória | Mostra usado / total e quanto está livre ("· 17,9 GiB livres") |
| 20 | Modo painel: cartão da GPU | Um cartão só com uso, "VRAM x / y GiB · z%" e "Temperatura" (sem cartão de temperatura separado) |
| 21 | Tocar no cartão da GPU (modo painel e retrato) | Abre o histórico com Uso da GPU, VRAM e Temperatura; as abas 15 min, 1 h e 24 h mudam os três |
| 22 | Digitar o IP no pareamento manual: `192168`, depois `.18.22` | O campo mostra `192.168.18.22`, com os pontos colocados sozinho |
| 23 | Modo painel com a GPU acima de 80% de uso e acima de 75 °C (jogo pesado) | Selos "Uso alto" e "Temperatura alta" empilhados no canto do cartão da GPU, número e borda em amarelo; o nome da placa continua inteiro |
| 24 | Configurações → Alertas: mudar "Temperatura alta" para 60 | Com a GPU acima de 60 °C, o selo aparece sem reiniciar o app; número fora da faixa mostra o erro e não salva |
| 25 | Desligar "Cores de alerta" | Modo painel e tela do PC sem cores, selos nem bordas; ao religar, os limites escolhidos voltam |
| 26 | Celular deitado na tela do PC e no pareamento | Cartões em duas colunas; o quadro da câmera cabe na tela |
| 27 | App com um agente de teste que anuncia `protocol: 2` (veja abaixo) | No pareamento e na tela do PC aparece "Este PC usa uma versão mais nova do PcX Control. Atualize o app." com o botão de baixar; o modo painel mostra o mesmo aviso; nada fica carregando para sempre |

**Agente de teste com `protocol: 2` (item 27).** Em qualquer computador com o código do agente,
rode `PCX_TEST_PROTOCOL=2 python -m pcx_agent --demo` (no Windows, `set PCX_TEST_PROTOCOL=2` antes).
A variável só vale com `--demo`: sem ele, ou com o valor vazio, menor que 1 ou que não seja
número, o agente anuncia o protocolo real (1). Pareie o app pelo QR ou pelo IP com a senha
`demo-password`. Não use isto no agente instalado.

Anote o modelo do celular, a versão do Android e a versão do Windows junto com o resultado.

## Resultados

| Data | Aparelho | Sistema | Como | Resultado |
| --- | --- | --- | --- | --- |
| 01/11/2026 | Poco X7 Pro | Android 16, HyperOS 3.0.302 | Expo Go + agente no Windows (RTX 3070) | Itens 1 a 16 aprovados, sem erros. Pedido: percentuais inteiros por padrão e RAM livre (itens 18 e 19, adicionados depois) |
| 01/11/2026 | Poco X7 Pro | Android 16, HyperOS 3.0.302 | Expo Go + agente no Windows (RTX 3070) | Itens 18 e 19 aprovados (números precisos e RAM livre) |
