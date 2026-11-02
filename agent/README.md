# Agente do PcX Control

Serviço que roda no PC Windows: lê os sensores, pareia celulares e transmite as leituras
pela rede local. O protocolo está descrito em `docs/specs/` na raiz do repositório.

## Rodar em modo demo (Linux, macOS ou Windows)

Usa sensores simulados e uma pasta de dados temporária. Não precisa de Windows nem de GPU.

```bash
cd agent
python -m venv .venv
.venv/bin/pip install -e ".[dev]"        # no Windows: .venv\Scripts\pip
.venv/bin/python -m pcx_agent --demo --port 8765
```

O terminal mostra um **código de pareamento** (vale 5 minutos) e a senha do modo demo.
Em outro terminal:

```bash
curl http://localhost:8765/v1/info
curl -X POST http://localhost:8765/v1/pair \
  -H "Content-Type: application/json" \
  -d '{"device_name": "Meu teste", "password": "demo-password"}'
# use o "token" devolvido:
curl http://localhost:8765/v1/snapshot -H "Authorization: Bearer <token>"
```

## Rodar no Windows com os sensores reais

```powershell
pip install -e ".[windows]"
pythonw -m pcx_agent            # bandeja (padrão)
python -m pcx_agent --console   # no terminal, sem bandeja
```

Na bandeja, a primeira execução abre o assistente para criar a senha e mostrar o QR code.
Clique com o botão direito no ícone para parear, ver os celulares, trocar a senha, ligar o
início com o Windows ou abrir os logs. Se o agente já estiver aberto, uma segunda cópia avisa
e sai.

Para capturar amostras reais da GPU (útil para novos testes):
`python tools/capture_gpu_samples.py > amostras.json`.

## Modos de execução

| Comando | O que faz |
| --- | --- |
| `pythonw -m pcx_agent` | Bandeja do Windows (padrão) |
| `python -m pcx_agent --console` | Terminal, com o QR em texto |
| `python -m pcx_agent --demo` | Sensores simulados, em qualquer sistema |
| `python -m pcx_agent --self-test saida.json` | Sobe o servidor, lê os sensores e grava o resultado (usado pela CI) |

## Pasta de dados

`%LOCALAPPDATA%\PcXControl\` (no Linux, `~/.local/share/pcx-control/`):

- `pcx.db`: senha (só o hash), celulares pareados e 24 h de histórico.
- `config.json`: `{"port": 8765}`. Porta inválida ou arquivo quebrado: o agente usa 8765.
- `logs\agent.log`: JSON por linha, 5 arquivos de até 1 MiB. Senha, código e token nunca
  aparecem.

## Interface da bandeja

Cores, fontes e tamanhos ficam em `pcx_agent/tray/theme.py` (as mesmas do tema escuro do app);
todos os textos em `pcx_agent/tray/texts.py`. Janelas novas herdam de `BaseWindow`
(`tray/widgets.py`) e só chamam o `AgentController`, onde ficam as regras.

## Testes

```bash
.venv/bin/pytest --cov=pcx_agent --cov-fail-under=80
.venv/bin/ruff check .
```

Os testes marcados `windows` só rodam no Windows (o GitHub Actions executa os dois sistemas).
