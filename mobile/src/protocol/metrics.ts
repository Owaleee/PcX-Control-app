import type { MetricName, Snapshot } from './types';

export const METRIC_NAMES: readonly MetricName[] = [
  'cpu.total',
  'ram.percent',
  'net.down_bps',
  'net.up_bps',
  'disk.read_bps',
  'disk.write_bps',
  'gpu.usage',
  'gpu.temp',
  'gpu.vram_percent',
];

/** Mesma regra de Snapshot.metrics() do agente: primeira GPU; gpu.temp e VRAM so com dado. */
export function snapshotMetrics(s: Snapshot): Partial<Record<MetricName, number>> {
  const values: Partial<Record<MetricName, number>> = {
    'cpu.total': s.cpu_total,
    'ram.percent': s.ram_percent,
    'net.down_bps': s.net_down_bps,
    'net.up_bps': s.net_up_bps,
    'disk.read_bps': s.disk_read_bps,
    'disk.write_bps': s.disk_write_bps,
  };
  const gpu = s.gpus[0];
  if (gpu) {
    values['gpu.usage'] = gpu.usage_percent;
    if (gpu.temp_c !== null) values['gpu.temp'] = gpu.temp_c;
    if (gpu.vram_used_bytes !== null && gpu.vram_total_bytes) {
      values['gpu.vram_percent'] = (100 * gpu.vram_used_bytes) / gpu.vram_total_bytes;
    }
  }
  return values;
}
