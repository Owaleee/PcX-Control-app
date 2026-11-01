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
python -m pcx_agent
```

Na primeira execução o terminal pede para criar a senha do PC. Para capturar amostras
reais da GPU (útil para novos testes): `python tools/capture_gpu_samples.py > amostras.json`.

## Testes

```bash
.venv/bin/pytest --cov=pcx_agent --cov-fail-under=80
.venv/bin/ruff check .
```

Os testes marcados `windows` só rodam no Windows (o GitHub Actions executa os dois sistemas).
