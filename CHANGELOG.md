# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.
O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto usa
[Versionamento Semântico](https://semver.org/lang/pt-BR/). Os commits seguem o padrão
[Conventional Commits](https://www.conventionalcommits.org/pt-br/).

Até a `0.2.0`, agente e app tinham a mesma versão. Daqui em diante cada um tem a sua: as
seções são `[agente X.Y.Z]` e `[app X.Y.Z]`, com as tags `agente-vX.Y.Z` e `app-vX.Y.Z`. Os dois
conversam pelo **protocolo**, versionado à parte (hoje: `protocol: 1`).

## [Não lançado]

### Planejado
- Versão `1.0.0` (agente e app): lançamento público, com README e GIF do modo painel.

## [app 0.3.0] - 2026-11-02

Compatível com o agente 0.2.0 ou mais novo (protocolo 1).

### Adicionado
- Modo painel: **um cartão só para a GPU**, com o uso, a VRAM (usada / total e percentual) e a
  temperatura. Antes a temperatura tinha um cartão próprio e a VRAM não aparecia.
- Tocar no cartão da GPU (no modo painel ou no painel em retrato) abre o **histórico da GPU**:
  uso, VRAM e temperatura no mesmo intervalo (15 min, 1 h ou 24 h), com média e máximo de cada.

## [agente 0.3.0] - 2026-11-02

Primeira versão do agente para **qualquer pessoa no Windows**: instalador, ícone na bandeja e
janelas. Compatível com o app 0.2.0 (protocolo 1).

### Adicionado
- Instalador (`PcXControl-Setup-0.3.0.exe`) para o usuário atual, com a opção "Iniciar com o
  Windows" e a regra de firewall só para a rede **Privada** e a rede local (um único pedido de
  administrador). O desinstalador remove a regra e mantém os dados.
- Ícone na bandeja com Parear celular, Celulares pareados, Trocar senha, Iniciar com o Windows,
  Abrir pasta de logs e Sair. A dica do ícone mostra se há celular conectado.
- Assistente da primeira execução: cria a senha e mostra o QR code, o endereço do PC (para
  parear por IP e senha) e o botão Concluir.
- Janela de pareamento com contagem regressiva, "Gerar outro código", aviso de PC sem rede e
  "Celular pareado!", seguida de notificação do Windows.
- Janela de celulares pareados, com quem está conectado agora e a opção de desconectar.
- Trocar a senha sem a antiga, com a pergunta se desconecta todos os celulares.
- `config.json` na pasta de dados para mudar a porta; arquivo quebrado não impede o agente de
  abrir.
- Logs em `logs\agent.log` (JSON por linha, 5 arquivos de 1 MiB), sem senha, código ou token.
- Instância única: abrir de novo mostra "O PcX Control já está rodando."
- Modos `--console` (terminal) e `--self-test` (autoteste usado pela CI no executável).

### Segurança
- Teto global de 30 tentativas de pareamento erradas por minuto, somando todos os IPs.
- Limites no servidor: mensagens de WebSocket de até 16 KiB e até 64 conexões simultâneas.

### Corrigido
- A porta ocupada por outro programa agora gera uma mensagem clara em vez de o agente fechar.

## [0.2.0] - 2026-11-01

Primeira versão do **app Android**.

### Adicionado
- App em Expo SDK 58 com as telas Meus PCs, Adicionar PC, Aparência, Painel, Detalhe da métrica,
  Ajustes do PC e Modo painel.
- Pareamento lendo o QR code do agente ou por IP + senha, com mensagens de erro em português.
- Conexão em tempo real com reconexão automática (1, 2, 4, 8 s, até 15 s), sessão única com opção
  de assumir e tratamento de celular revogado no PC.
- Painel com CPU, RAM, GPU (uso, VRAM e temperatura), rede e discos, com gráficos dos últimos
  15 minutos e detalhe de 15 min, 1 h e 24 h.
- Modo painel em paisagem: tela sempre ligada, controles por toque, escurecer e deslocamento de
  pixels contra burn-in.
- Temas Escuro, Claro e AMOLED (fundo preto puro), com contraste de leitura testado.
- Percentuais inteiros por padrão (51%) e opção "Números precisos" nas Configurações (50,5%).
- Memória RAM livre ao lado da usada, no painel e no modo painel.
- Token guardado no armazenamento seguro do Android; a senha nunca é salva no celular.
- Ícone próprio e build do APK pelo EAS.
- Agente: QR code de pareamento no terminal e contrato do protocolo em
  [`docs/protocol/fixtures`](docs/protocol/fixtures), testado pelo agente e pelo app.

### Corrigido
- Agente: o aviso de sessão ocupada (`4423`) não chegava quando o nome do aparelho ativo passava
  de 123 bytes.

### Documentação
- [Protocolo](docs/protocolo.md) e [teste manual do app](docs/teste-manual-app.md).

## [0.1.0] - 2026-11-01

Primeira versão do **agente** (backend). Ainda não há app nem instalador: o agente roda pelo
terminal, no Windows (sensores reais) ou em qualquer sistema com `--demo` (sensores simulados).

### Adicionado
- Leitura de sensores atrás de uma interface (`SensorProvider`): CPU, RAM, discos, rede e GPU,
  com implementação para Windows (psutil, contadores PDH, DXGI e NVML) e uma simulada.
- Laço único de coleta: 1 s com um celular conectado, 5 s sem ninguém.
- Senha do PC guardada como hash scrypt com salt.
- Pareamento por código de uso único (válido por 5 minutos) ou por senha, com limite de 5
  tentativas por minuto por IP.
- Tokens de aparelho de 256 bits, guardados como hash, que expiram 30 dias após o último uso e
  podem ser revogados.
- Sessão ativa única: um celular por vez, com opção de assumir a sessão de outro.
- API HTTP em `/v1` (`info`, `pair`, `snapshot`, `history`, `devices/me`) e transmissão em
  tempo real por WebSocket em `/v1/stream`.
- Histórico de 24 h em SQLite (média e máximo a cada 5 s) com limpeza automática por hora.
- Linha de comando `python -m pcx_agent` com modo `--demo`.
- Integração contínua no Ubuntu e no Windows, com cobertura mínima de 80%.

### Segurança
- Comunicação em HTTP sem criptografia: para uso em rede doméstica confiável. HTTPS é
  pré-requisito para qualquer função que execute ações no PC.
- Sem documentação interativa (`/docs`) exposta; segredos nunca são gravados em log.

### Validação
- Testado no Windows real (RTX 3070): sensores, GPU com VRAM e temperatura, discos e rede.
- Amostras reais dos contadores de GPU guardadas como teste de regressão.

### Pendências conhecidas
Veja [docs/decisoes-e-pendencias.md](docs/decisoes-e-pendencias.md).

[Não lançado]: https://github.com/Owaleee/PcX-Control-app/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Owaleee/PcX-Control-app/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Owaleee/PcX-Control-app/releases/tag/v0.1.0
