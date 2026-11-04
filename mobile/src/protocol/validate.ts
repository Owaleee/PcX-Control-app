// Validacao de tudo que chega da rede. Campos extras sao aceitos; tipos errados, nao.
import {
  RANGES,
  type AgentInfo,
  type ApiErrorBody,
  type DiskVolume,
  type GpuReading,
  type Hello,
  type HistoryPoint,
  type HistoryResponse,
  type PairResponse,
  type Range,
  type Snapshot,
  type SnapshotMessage,
} from './types';

type Obj = Record<string, unknown>;

const isObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v);
const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const isNonNeg = (v: unknown): v is number => isNum(v) && v >= 0;
const isPercent = (v: unknown): v is number => isNum(v) && v >= 0 && v <= 100;
const isText = (v: unknown): v is string => typeof v === 'string' && v.trim().length > 0;
const isNullableNonNeg = (v: unknown): v is number | null => v === null || v === undefined || isNonNeg(v);
const isNullableNum = (v: unknown): v is number | null => v === null || v === undefined || isNum(v);

function parseGpu(v: unknown): GpuReading | null {
  if (!isObj(v)) return null;
  const { id, name, usage_percent, vram_used_bytes, vram_total_bytes, temp_c, vendor, temp_warn_c } = v;
  if (!isText(id) || !isText(name) || !isPercent(usage_percent)) return null;
  if (!isNullableNonNeg(vram_used_bytes) || !isNullableNonNeg(vram_total_bytes)) return null;
  if (!isNullableNum(temp_c)) return null;
  return {
    id,
    name,
    usage_percent,
    vram_used_bytes: vram_used_bytes ?? null,
    vram_total_bytes: vram_total_bytes ?? null,
    temp_c: temp_c ?? null,
    // Campos opcionais: agente antigo nao manda, e um valor estranho nao derruba a leitura.
    temp_warn_c: isNum(temp_warn_c) ? temp_warn_c : null,
    vendor: isText(vendor) ? vendor : null,
  };
}

function parseDisk(v: unknown): DiskVolume | null {
  if (!isObj(v)) return null;
  const { mount, percent, used_bytes, total_bytes } = v;
  if (!isText(mount) || !isPercent(percent) || !isNonNeg(used_bytes) || !isNonNeg(total_bytes)) {
    return null;
  }
  return { mount, percent, used_bytes, total_bytes };
}

function parseList<T>(v: unknown, item: (x: unknown) => T | null): T[] | null {
  if (!Array.isArray(v)) return null;
  const out: T[] = [];
  for (const raw of v) {
    const parsed = item(raw);
    if (parsed === null) return null;
    out.push(parsed);
  }
  return out;
}

function parseSnapshot(v: unknown): Snapshot | null {
  if (!isObj(v)) return null;
  const percents = [v.cpu_total, v.ram_percent];
  const nonNeg = [
    v.ram_used_bytes,
    v.ram_total_bytes,
    v.disk_read_bps,
    v.disk_write_bps,
    v.net_down_bps,
    v.net_up_bps,
    v.uptime_s,
  ];
  if (!percents.every(isPercent) || !nonNeg.every(isNonNeg)) return null;
  if (!isText(v.t) || Number.isNaN(Date.parse(v.t)) || typeof v.host_name !== 'string') return null;
  const disks = parseList(v.disks, parseDisk);
  const gpus = parseList(v.gpus, parseGpu);
  if (!disks || !gpus) return null;
  return {
    t: v.t,
    cpu_total: v.cpu_total as number,
    ram_percent: v.ram_percent as number,
    ram_used_bytes: v.ram_used_bytes as number,
    ram_total_bytes: v.ram_total_bytes as number,
    disks,
    disk_read_bps: v.disk_read_bps as number,
    disk_write_bps: v.disk_write_bps as number,
    net_down_bps: v.net_down_bps as number,
    net_up_bps: v.net_up_bps as number,
    gpus,
    host_name: v.host_name,
    uptime_s: v.uptime_s as number,
  };
}

export function parseSnapshotMessage(raw: unknown): SnapshotMessage | null {
  if (!isObj(raw) || raw.type !== 'snapshot' || !isNonNeg(raw.seq) || !isText(raw.t)) return null;
  const data = parseSnapshot(raw.data);
  return data ? { type: 'snapshot', seq: raw.seq, t: raw.t, data } : null;
}

function parseAgentRef(v: unknown): { id: string; name: string; version: string } | null {
  if (!isObj(v) || !isText(v.id) || typeof v.name !== 'string' || typeof v.version !== 'string') {
    return null;
  }
  return { id: v.id, name: v.name, version: v.version };
}

export function parseHello(raw: unknown): Hello | null {
  if (!isObj(raw) || raw.type !== 'hello' || raw.protocol !== 1) return null;
  const agent = parseAgentRef(raw.agent);
  const caps = raw.capabilities;
  if (!agent || !Array.isArray(caps) || !caps.every((c) => typeof c === 'string')) return null;
  return { type: 'hello', protocol: 1, agent, capabilities: caps as string[] };
}

export function parseInfo(raw: unknown): AgentInfo | null {
  if (!isObj(raw)) return null;
  const { agent_id, name, version, protocol, busy } = raw;
  if (!isText(agent_id) || typeof name !== 'string' || typeof version !== 'string') return null;
  if (!isNum(protocol) || typeof busy !== 'boolean') return null;
  return { agent_id, name, version, protocol, busy };
}

export function parsePair(raw: unknown): PairResponse | null {
  if (!isObj(raw) || !isText(raw.device_id) || !isText(raw.token)) return null;
  const agent = parseAgentRef(raw.agent);
  const protocol = isObj(raw.agent) ? raw.agent.protocol : undefined;
  if (!agent || !isNum(protocol)) return null;
  return { device_id: raw.device_id, token: raw.token, agent: { ...agent, protocol } };
}

function parsePoint(v: unknown): HistoryPoint | null {
  if (!isObj(v) || !isNum(v.t) || !isNum(v.avg) || !isNum(v.max)) return null;
  return { t: v.t, avg: v.avg, max: v.max };
}

export function parseHistory(raw: unknown): HistoryResponse | null {
  if (!isObj(raw) || !isText(raw.metric)) return null;
  if (!RANGES.includes(raw.range as Range)) return null;
  const points = parseList(raw.points, parsePoint);
  return points ? { metric: raw.metric, range: raw.range as Range, points } : null;
}

export function parseErrorBody(raw: unknown): ApiErrorBody | null {
  if (!isObj(raw) || !isText(raw.code) || typeof raw.message !== 'string') return null;
  const body: ApiErrorBody = { code: raw.code, message: raw.message };
  if (isNum(raw.attempts_left)) body.attempts_left = raw.attempts_left;
  if (isNum(raw.retry_after)) body.retry_after = raw.retry_after;
  if (typeof raw.active_device === 'string') body.active_device = raw.active_device;
  return body;
}
