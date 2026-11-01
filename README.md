# PcX Control

> Turn your Android phone into a live sensor panel for your Windows PC. Pair in seconds with a QR code.

Transforme o celular Android em um painel de sensores do seu PC Windows, na rede local, com pareamento por QR code.

**Status:** em desenvolvimento. O agente (backend) está na versão **0.1.0**; o app Android e o instalador ainda não existem.

## Experimentar o agente (qualquer sistema)

```bash
cd agent
python -m venv .venv
.venv/bin/pip install -e ".[dev]"      # no Windows: .venv\Scripts\pip
.venv/bin/python -m pcx_agent --demo
```

Mais detalhes em [agent/README.md](agent/README.md).

## Documentação

| Documento | Conteúdo |
| --- | --- |
| [Especificação v1](docs/specs/2026-10-30-pcx-control-v1-design.md) | O que será construído e por quê |
| [Plano 1: agente](docs/plans/2026-10-30-plano-1-agente.md) | Tarefas, testes e ordem de implementação |
| [Decisões e pendências](docs/decisoes-e-pendencias.md) | O que mudou no caminho e o que falta |
| [Changelog](CHANGELOG.md) | Histórico de versões |

Licença: [MIT](LICENSE).
