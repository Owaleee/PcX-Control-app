// Formato das mensagens do agente (protocolo 1). Ver docs/protocolo.md.

export type Range = '15m' | '1h' | '24h';
export const RANGES: readonly Range[] = ['15m', '1h', '24h'];

export type MetricName =
  | 'cpu.total'
  | 'ram.percent'
  | 'net.down_bps'
  | 'net.up_bps'
  | 'disk.read_bps'
  | 'disk.write_bps'
  | 'gpu.usage'
  | 'gpu.temp'
  | 'gpu.vram_percent';

export type GpuReading = {
  id: string;
  name: string;
  usage_percent: number;
  vram_used_bytes: number | null;
  vram_total_bytes: number | null;
  temp_c: number | null;
  /** Agente 0.5.0+: "nvidia", "amd", "intel" ou "outra". So para relatorio; a tela nao mostra. */
  vendor?: string | null;
  /** Agente 0.6.0+: limite de temperatura que o proprio PC considera alto. */
  temp_warn_c?: number | null;
};

export type DiskVolume = {
  mount: string;
  percent: number;
  used_bytes: number;
  total_bytes: number;
};

export type Snapshot = {
  t: string;
  cpu_total: number;
  ram_percent: number;
  ram_used_bytes: number;
  ram_total_bytes: number;
  disks: DiskVolume[];
  disk_read_bps: number;
  disk_write_bps: number;
  net_down_bps: number;
  net_up_bps: number;
  gpus: GpuReading[];
  host_name: string;
  uptime_s: number;
};

export type AgentRef = { id: string; name: string; version: string };

export type Hello = {
  type: 'hello';
  protocol: 1;
  agent: AgentRef;
  capabilities: string[];
};

export type SnapshotMessage = { type: 'snapshot'; seq: number; t: string; data: Snapshot };

export type AgentInfo = {
  agent_id: string;
  name: string;
  version: string;
  protocol: number;
  busy: boolean;
};

export type PairResponse = {
  device_id: string;
  token: string;
  agent: AgentRef & { protocol: number };
};

export type HistoryPoint = { t: number; avg: number; max: number };
export type HistoryResponse = { metric: string; range: Range; points: HistoryPoint[] };

export type ApiErrorBody = {
  code: string;
  message: string;
  attempts_left?: number;
  retry_after?: number;
  active_device?: string;
};
