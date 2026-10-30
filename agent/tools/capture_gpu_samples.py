"""Grava no terminal as amostras brutas dos contadores de GPU (executar no Windows).

Uso:  python tools/capture_gpu_samples.py > pdh_samples.json
O arquivo serve para criar testes com os dados reais do seu PC.
"""

import json
import time

from pcx_agent.sensors.windows.native import PdhGpuCounters

counters = PdhGpuCounters()
time.sleep(1.0)
engines, memory = counters.read()
counters.close()
print(json.dumps({"engines": engines, "memory": memory}, indent=2))
