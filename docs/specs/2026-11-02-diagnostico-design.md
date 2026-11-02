# PcX Control — Diagnóstico, logs de falhas e preparo para AMD e Intel

- **Data:** 02/11/2026
- **Autor:** Alexandre Queiroz (Owaleee)
- **Status:** aguardando revisão
- **Versões:** agente `0.5.0` e app `0.4.0` (depois do agente 0.4.0 e do app 0.3.0)

## 1. Objetivo

Fazer o agente explicar sozinho por que o celular não conecta, deixar na pasta `logs` tudo o que
for preciso para tratar travamentos e problemas de placa de vídeo, e preparar agente e app para
placas AMD e Intel.

Motivo: no primeiro teste em outro PC (Windows 10, placa AMD, Ethernet e Radmin VPN), o agente
estava aberto e a regra de firewall existia, mas o celular não chegava ao PC. Foi preciso rodar
comandos à mão para achar a causa, e o log não ajudava.

Alinhado à estratégia de agente estável (`decisoes-e-pendencias.md`): um agente que se
diagnostica precisa de menos atualizações.

### Critérios de sucesso

1. Em um PC com a rede como Pública, sem a regra de firewall ou com VPN ligada, "Verificar
   conexão" aponta a causa em menos de 10 segundos, em português, com o que fazer.
2. As correções oferecidas (rede e firewall) resolvem o problema sem a pessoa abrir o terminal.
3. Qualquer travamento do agente, inclusive dentro de uma DLL de driver, deixa um registro na
   pasta `logs`.
4. Num PC com placa integrada e dedicada, o app mostra a dedicada no modo painel.
5. O relatório copiado de um PC com placa AMD traz o necessário para implementar a temperatura
   AMD sem precisar da placa em mãos.

## 2. Diagnóstico

### Onde

Item novo no menu da bandeja, **Verificar conexão**, entre "Celulares pareados" e "Trocar
senha". Abre a janela de diagnóstico, que roda as verificações em segundo plano (mostra
"Verificando…") e lista os resultados. Não roda sozinho em outros momentos.

### Verificações

Cada verificação devolve um resultado com: `id`, grupo, título, situação (`ok`, `atencao`,
`problema` ou `info`), explicação em português e, quando houver, uma correção.

| Grupo | `id` | Situação | Correção |
| --- | --- | --- | --- |
| Rede e firewall | `rede.ip` | `ok` com IP da rede local; `problema` sem rede, só com VPN ou com `169.254.x.x` (o roteador não entregou IP) | — |
| | `rede.tipo` | `ok` em Privada ou Domínio; `problema` em Pública; `info` se não der para ler | Abrir configurações de rede |
| | `rede.firewall` | `ok` com a regra "PcX Control - agente" ativa, de entrada, permitindo, no perfil Privado e apontando para o executável em uso; `problema` se faltar, estiver desativada ou apontar para outro programa; `info` rodando pelo código (sem instalador) | Criar regra de firewall |
| | `rede.vpn` | `atencao` com VPN ligada (lista os nomes); `ok` sem VPN | — |
| Agente acessível | `agente.local` | `ok` se o agente responde em `http://<IP da rede>:<porta>/v1/info` com o próprio `agent_id`; `problema` caso contrário. A explicação deixa claro que o teste parte do próprio PC e não prova o caminho do celular | — |
| Antivírus | `antivirus.terceiros` | `atencao` para cada antivírus ou firewall que não seja o do Windows, com o nome e "libere o PcX Control nele"; `ok` sem nenhum; `info` se não der para ler | — |
| Sensores | `sensores.gpu` | `info` por placa: nome, fabricante, VRAM, se é a mostrada no app e se há temperatura; `atencao` sem nenhuma placa | — |
| | `sensores.leitura` | `ok` se a última leitura trouxe CPU, RAM, discos e rede; `problema` com o erro | — |

### Correções

- **Abrir configurações de rede:** abre `ms-settings:network-status`.
- **Criar regra de firewall:** roda o `firewall.cmd add "<exe>"` do instalador com um pedido de
  administrador. Só aparece no agente instalado.
- Depois de usar uma correção e voltar à janela, o diagnóstico roda de novo.

### Relatório

**Copiar relatório** põe na área de transferência um texto com:
- a versão do agente e a do Windows;
- cada verificação, com a situação e a explicação;
- as placas de rede (nome, IP, ativa ou não, se foi tomada como VPN);
- as placas de vídeo (nome, fabricante, `VendorId`, VRAM, LUID) e os nomes das instâncias dos
  contadores PDH de GPU.

Nunca entram senha, código de pareamento ou token. Cada execução do diagnóstico também é
gravada no `agent.log`.

## 3. Logs de falhas e de placa de vídeo

| Evento | Onde | Conteúdo |
| --- | --- | --- |
| Exceção não tratada em qualquer thread (principal, servidor, bandeja, coletor) | `agent.log` (`CRITICAL`) | traceback completo, nome da thread |
| Erro na interface (botões, timers) | `agent.log` (`ERROR`) | já existe desde o agente 0.3.0 |
| Erro no laço do servidor (asyncio) | `agent.log` (`ERROR`) | mensagem e traceback |
| Travamento nativo (DLL de driver derruba o processo) | `logs\crash.log` | pilha de cada thread no momento do travamento (`faulthandler`) |
| Início do agente | `agent.log` (`INFO`) | versão do agente, versão do Windows e uma linha por placa: nome, fabricante, `VendorId`, VRAM e leituras disponíveis (uso, VRAM, temperatura e de onde vem) |
| Falha de leitura da GPU (contador PDH, DXGI, NVML) | `agent.log` (`WARNING`) | o que falhou e o motivo; no máximo uma linha por minuto por tipo de falha |
| Diagnóstico | `agent.log` (`INFO`) | uma linha por verificação |

O `crash.log` não passa pela rotação (é aberto em modo de acréscimo e cortado em 1 MiB ao
iniciar) e também passa pela regra de nunca gravar segredos.

## 4. Placas AMD e Intel

### Agente

- `GpuReading` ganha `vendor: "nvidia" | "amd" | "intel" | "outra"`, a partir do `VendorId` do
  DXGI (`0x10DE`, `0x1002`, `0x8086`). É um **acréscimo** ao protocolo 1: apps antigos ignoram.
- As placas saem ordenadas por VRAM dedicada, da maior para a menor. A primeira (a que o app
  mostra no modo painel e cujo histórico é gravado) passa a ser a dedicada.
- A temperatura passa a vir de **fontes por fabricante** atrás de uma interface:
  `GpuTemperatureSource` com `vendor` e `read() -> dict[str, float]`. NVIDIA (NVML) é a fonte
  atual. AMD e Intel ficam como fontes registradas que ainda não leem nada; a capacidade
  `gpu.temp` só aparece quando alguma fonte devolve valores.
- O relatório e o log de início trazem o que falta para a fonte AMD: nomes, `VendorId` e
  instâncias dos contadores.

### App

- Aceita `vendor` (opcional) e não quebra com agentes que não mandam.
- No histórico da GPU, sem a capacidade `gpu.temp`, mostra "Temperatura indisponível nesta placa"
  no lugar do gráfico de temperatura.

## 5. Interface

- Janela `DiagnosticsWindow`, herdando de `BaseWindow`, 560×640, com as cores e os textos de
  `theme.py` e `texts.py`. Ícones de situação desenhados com as cores do tema: `ok` em verde,
  `atencao` em amarelo, `problema` em `danger` e `info` em `text_muted`, todos com contraste de
  pelo menos 4,5:1 sobre o fundo.
- Lista com rolagem, agrupada por grupo; cada item mostra o título, a explicação e o botão de
  correção, quando houver.
- Rodapé: "Copiar relatório", "Verificar de novo" e "Fechar".

## 6. Arquitetura

```
agent/pcx_agent/
├─ diagnostics/
│  ├─ model.py        # CheckResult, Status, Fix
│  ├─ checks.py       # uma funcao por verificacao, com entradas injetaveis
│  ├─ windows.py      # leituras do Windows (firewall, Central de Seguranca, versao) via PowerShell
│  ├─ runner.py       # roda todas, registra no log, monta o relatorio
│  └─ report.py       # texto do relatorio, sem segredos
├─ crashlog.py        # excepthook, threading.excepthook, asyncio, faulthandler
└─ tray/diagnostics_window.py
```

As verificações recebem os dados prontos (placas, perfis de rede, regras de firewall,
antivírus, leitura de sensores) e são funções puras. As leituras do Windows ficam em
`diagnostics/windows.py` e são testadas com saídas gravadas.

## 7. Testes

- **Linux (pytest):** cada verificação com entradas falsas para cada situação; o parser de cada
  saída do PowerShell (regras de firewall, Central de Segurança, versão do Windows); o relatório
  sem segredos; a ordem das placas e o `vendor`; o registro de exceções de threads e o
  `crash.log`; o limite de uma linha por minuto nas falhas de GPU.
- **Janelas (Xvfb e CI do Windows):** a janela lista os resultados, mostra os botões de
  correção, copia o relatório e não corta nada.
- **CI do Windows:** as leituras reais de firewall, Central de Segurança e versão rodam sem erro
  e no prazo.
- **App (Jest):** `vendor` aceito e ignorado; aviso de temperatura indisponível.
- **Manual:** no PC do amigo (AMD), "Verificar conexão" com a rede Pública e com a VPN ligada;
  copiar o relatório.

## 8. Fora deste trabalho

Leitura de temperatura AMD e Intel (vem depois, com o relatório do PC do amigo), diagnóstico
rodando sozinho, correção automática sem clique, diagnóstico pelo app.
