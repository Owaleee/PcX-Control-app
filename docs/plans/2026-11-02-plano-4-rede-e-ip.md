# PcX Control — Plano 4: rede, IP e log (app 0.3.0 e agente 0.4.0)

**Objetivo:** tornar o pareamento mais fácil e o "PC não encontrado" mais fácil de entender: pontos automáticos no campo de IP, dica de rede Privada no app, log de pareamento e conexão, IP certo no QR (sem VPNs) e aviso quando a rede do PC está como Pública.

**Origem:** primeiro teste em outro PC (Windows 10, Ethernet + Radmin VPN). O agente estava aberto e a regra de firewall existia, mas o celular não chegava ao PC. O log não mostrava se o celular tinha tentado, e nada avisava que uma das redes estava como Pública.

**Arquitetura:** a lógica nova fica em funções puras e testáveis no Linux (`mobile/src/protocol/ip.ts`, `agent/pcx_agent/network.py`, `AgentController`). Só a chamada que lê o tipo de rede do Windows depende do sistema e é testada na CI do Windows.

**Spec:** `docs/specs/2026-10-30-pcx-control-v1-design.md` (§3 pareamento, §6 mensagens de erro, §7 agente no Windows).

## Restrições globais

- Versões: app `0.3.0` (junto com o cartão da GPU), agente `0.4.0`. Protocolo continua `1`.
- Logs nunca trazem senha, código ou token (o `RedactFilter` continua valendo).
- Textos da bandeja só em `tray/texts.py`; cores só em `tray/theme.py`.
- Commits em português, no padrão Conventional Commits.

## Revisão de riscos

1. PC só com placas virtuais (ou só VPN): o QR usa o IP da rota padrão, como antes, em vez de `127.0.0.1`.
2. `Get-NetConnectionProfile` lento, ausente ou com saída inesperada: a janela abre na hora e simplesmente não mostra o aviso.
3. Colar um IP com espaços, vírgulas ou zeros à esquerda no campo: vira um IP válido, sem pontos duplicados.
4. Apagar no campo de IP: o ponto automático não volta sozinho e trava a edição.
5. Nome do aparelho com caracteres estranhos no log: uma linha só, sem quebrar o JSON.

---

### Tarefa 1: app — pontos automáticos no IP e dica de rede Privada

**Arquivos:** `mobile/src/protocol/ip.ts`, `mobile/app/add.tsx`, `mobile/src/api/http.ts`, testes em `mobile/__tests__/protocol/` e `mobile/__tests__/screens/add.test.tsx`.

- `formatIpInput(text: string, deleting: boolean): string`: troca `,` e espaço por `.`, descarta o resto, no máximo 4 blocos. Ao digitar, o ponto entra sozinho quando o bloco não aceita mais dígitos (3 dígitos, um `0`, ou valor × 10 > 255). Um separador fecha um bloco curto; separador repetido é ignorado. Apagando, não insere ponto.
- O campo "IP do PC" usa `keyboardType="decimal-pad"` e passa pelo `formatIpInput`.
- A mensagem de PC não encontrado ganha: "e se a rede do PC está como Privada no Windows".
- Testes: `192168` → `192.168.`; `192.168.18` + `.` + `22` → `192.168.18.22`; `26` → `26.`; `0` → `0.`; colar ` 192,168,018,22 ` → `192.168.18.22`; separador duplo; quinto bloco ignorado; apagar `192.` → `192` sem voltar o ponto.

### Tarefa 2: agente — log de pareamento e de conexão

**Arquivos:** `agent/pcx_agent/api/app.py`, `agent/pcx_agent/api/stream.py`, `agent/tests/test_activity_log.py`.

- `POST /v1/pair`: uma linha `INFO` em `pcx_agent.pairing` com `ip`, `metodo` (`qr` ou `senha`), `resultado` (`pareado`, `senha_errada`, `codigo_invalido`, `bloqueado`, `nome_invalido`) e o nome do aparelho entre aspas (`repr`).
- WebSocket: linhas em `pcx_agent.stream` para conectado, ocupado (`4423`), assumido (`4409`), token inválido (`4401`, com o IP), desconectado no PC e desconexão.
- Testes com `caplog`: cada resultado do pareamento gera uma linha com o IP e o método e sem a senha nem o código; a conexão e a desconexão de um celular geram linhas.

### Tarefa 3: agente — IP certo no QR

**Arquivos:** criar `agent/pcx_agent/network.py`, `agent/tests/test_network.py`; modificar `controller.py` e `main.py`.

- `NetInterface(name, ipv4, up)`; `is_virtual(name, ipv4) -> bool` (nomes com Radmin, Hamachi, ZeroTier, Tailscale, WireGuard, OpenVPN, TAP, VPN, vEthernet, Hyper-V, VirtualBox, VMware, WSL, Loopback, Teredo, Bluetooth; faixas 26/8, 25/8, 100.64/10, 169.254/16, 127/8).
- `choose_lan(interfaces, preferred) -> NetInterface | None`: placas ativas, reais e com IP privado; a da rota padrão (`preferred`) vence; depois `192.168` > `10` > `172.16-31`.
- `lan_address() -> tuple[str, str | None]` (IP e nome da placa) com `psutil`; sem candidata, usa a rota padrão como antes.
- `AgentController` usa `lan_address` por padrão; `PairingInfo` ganha `interface: str | None`. O modo `--console` também.
- Testes: Ethernet + Radmin com a rota padrão na Radmin → Ethernet; Hamachi, Tailscale, vEthernet e placa desligada ignorados; preferência entre faixas; só VPN → `None`.

### Tarefa 4: agente — aviso de rede Pública

**Arquivos:** `network.py`, `controller.py`, `tray/pairing.py`, `tray/texts.py`, testes.

- `parse_profiles(json_text) -> dict[str, str]` (nome da placa → `public`, `private`, `domain`), aceitando objeto ou lista e a categoria como número (PowerShell 5.1) ou texto.
- `network_category(interface) -> str | None`: no Windows, `powershell -NoProfile -NonInteractive` com `Get-NetConnectionProfile | ConvertTo-Json`, sem janela, prazo de 5 s; qualquer falha → `None`.
- `AgentController.public_network_warning(info) -> str | None`: o texto do aviso quando a placa do QR está numa rede Pública.
- Janela de pareamento: a checagem roda numa thread (`concurrent.futures`) e a janela consulta o resultado com `after`; com aviso, mostra a faixa e o botão "Abrir configurações de rede" (`ms-settings:network-status`), sem esconder o QR.
- Testes: `parse_profiles` com as três formas de saída; controlador com categoria falsa; janela (Xvfb e CI do Windows) mostra e esconde a faixa; a chamada real roda na CI do Windows.

### Tarefa 5: versões, documentação e lançamento

- App `0.3.0`, agente `0.4.0`; `CHANGELOG.md` (`[app 0.3.0]` completo e `[agente 0.4.0]`).
- `README.md`: download direto do instalador, tabela de compatibilidade, "Solução de problemas" com o diagnóstico de rede em um comando do cmd.
- `docs/teste-manual-app.md` e `docs/decisoes-e-pendencias.md`.
- Revisão independente da branch, correções com teste, CI verde, PR atualizado. As tags `agente-v0.4.0` e `app-v0.3.0` são criadas por você.
