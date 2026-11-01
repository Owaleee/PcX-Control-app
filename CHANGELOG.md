# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.
O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto usa
[Versionamento Semântico](https://semver.org/lang/pt-BR/). Os commits seguem o padrão
[Conventional Commits](https://www.conventionalcommits.org/pt-br/).

A versão do **protocolo** é independente da versão do app (hoje: `protocol: 1`).

## [Não lançado]

### Planejado
- App Android: pareamento por QR code, painel em retrato, modo painel em paisagem, temas
  Escuro, Claro e AMOLED (Plano 2).
- Agente no Windows: ícone na bandeja, assistente da primeira execução, instalador e regra de
  firewall (Plano 3).
- Versão `1.0.0`: instalador do agente + APK + notas de lançamento.

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

[Não lançado]: https://github.com/Owaleee/PcX-Control-app/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Owaleee/PcX-Control-app/releases/tag/v0.1.0
