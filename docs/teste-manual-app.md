# Teste manual do app (antes de cada versão)

Faça este roteiro no Expo Go e depois de novo no APK instalado.

## Preparar o PC (Windows)

1. Atualize o código e as dependências do agente (a 0.2.0 tem dependência nova, o `qrcode`):

```powershell
cd $HOME\Documents\PcX-Control-app
git pull
cd agent
.\.venv\Scripts\python.exe -m pip install -e ".[dev,windows]"
```

2. Libere a porta 8765 **só na rede privada** (PowerShell como administrador, uma vez):

```powershell
New-NetFirewallRule -Name "PcXControl-Agente" -DisplayName "PcX Control - agente" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765 -Profile Private -RemoteAddress LocalSubnet
```

A rede Wi-Fi de casa precisa estar como **Privada** nas configurações do Windows.

3. Rode o agente aberto para a rede (PowerShell normal):

```powershell
.\.venv\Scripts\python.exe -m pcx_agent
```

O terminal mostra o código de pareamento, o endereço `pcx://pair?...` e o QR code.

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
