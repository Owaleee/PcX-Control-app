import { METRIC_NAMES, snapshotMetrics } from '../../src/protocol/metrics';
import { parseSnapshotMessage } from '../../src/protocol/validate';
import * as fx from './fixtures';

test('os nomes das metricas sao os mesmos do agente', () => {
  expect([...METRIC_NAMES].sort()).toEqual([...fx.metrics.names].sort());
});

test('snapshotMetrics calcula exatamente o que o agente calcula', () => {
  const msg = parseSnapshotMessage(fx.clone(fx.snapshotMessage));
  expect(msg).not.toBeNull();
  const ours = snapshotMetrics(msg!.data);
  const theirs = fx.metrics.from_snapshot as Record<string, number>;
  expect(Object.keys(ours).sort()).toEqual(Object.keys(theirs).sort());
  for (const [key, value] of Object.entries(theirs)) {
    expect(ours[key as keyof typeof ours]).toBeCloseTo(value, 9);
  }
});

test('sem GPU nao ha metricas gpu.*', () => {
  const msg = parseSnapshotMessage({ ...fx.clone(fx.snapshotMessage) })!;
  const keys = Object.keys(snapshotMetrics({ ...msg.data, gpus: [] }));
  expect(keys.some((k) => k.startsWith('gpu.'))).toBe(false);
});

test('sem temperatura e sem VRAM essas metricas somem', () => {
  const msg = parseSnapshotMessage(fx.clone(fx.snapshotMessage))!;
  const gpu = { ...msg.data.gpus[0]!, temp_c: null, vram_used_bytes: null };
  const metrics = snapshotMetrics({ ...msg.data, gpus: [gpu] });
  expect(metrics['gpu.usage']).toBe(gpu.usage_percent);
  expect(metrics['gpu.temp']).toBeUndefined();
  expect(metrics['gpu.vram_percent']).toBeUndefined();
});
