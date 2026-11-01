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

Anote o modelo do celular, a versão do Android e a versão do Windows junto com o resultado.

## Resultados

| Data | Aparelho | Sistema | Como | Resultado |
| --- | --- | --- | --- | --- |
| 01/11/2026 | Poco X7 Pro | Android 16, HyperOS 3.0.302 | Expo Go + agente no Windows (RTX 3070) | Itens 1 a 16 aprovados, sem erros. Pedido: percentuais inteiros por padrão e RAM livre (itens 18 e 19, adicionados depois) |
| 01/11/2026 | Poco X7 Pro | Android 16, HyperOS 3.0.302 | Expo Go + agente no Windows (RTX 3070) | Itens 18 e 19 aprovados (números precisos e RAM livre) |
