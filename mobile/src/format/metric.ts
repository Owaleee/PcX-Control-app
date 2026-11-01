import type { MetricName } from '../protocol/types';
import { formatPercent, formatRate, formatTemp } from './format';

export const METRIC_TITLES: Record<MetricName, string> = {
  'cpu.total': 'CPU',
  'ram.percent': 'Memória RAM',
  'net.down_bps': 'Rede (download)',
  'net.up_bps': 'Rede (upload)',
  'disk.read_bps': 'Discos (leitura)',
  'disk.write_bps': 'Discos (escrita)',
  'gpu.usage': 'GPU',
  'gpu.temp': 'Temperatura da GPU',
  'gpu.vram_percent': 'VRAM da GPU',
};

/** Formata um valor da metrica na unidade certa. */
export function formatMetric(metric: MetricName, value: number, precise = false): string {
  if (metric.endsWith('_bps')) return formatRate(value);
  if (metric === 'gpu.temp') return formatTemp(value);
  return formatPercent(value, { precise });
}

/** Percentuais e temperatura usam escala fixa; taxas usam o maior valor visto. */
export function metricScale(metric: MetricName, values: number[]): number {
  // Taxas nao tem teto natural: usa o maior valor da janela.
  if (metric === 'gpu.temp') return 100;
  if (metric.endsWith('_bps')) return Math.max(1024, ...values);
  return 100;
}
