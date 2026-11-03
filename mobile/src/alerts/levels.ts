// Cores de alerta: em que nivel cada dado esta, a partir dos limites escolhidos nas configuracoes.

export type AlertLevel = 'normal' | 'alto' | 'critico';

export type AlertLimits = {
  /** Chave "Cores de alerta". Desligada, nada de cor, selo ou borda. */
  enabled: boolean;
  usageHigh: number;
  usageCritical: number;
  tempHigh: number;
  tempCritical: number;
};

export const DEFAULT_LIMITS: AlertLimits = {
  enabled: true,
  usageHigh: 80,
  usageCritical: 95,
  tempHigh: 75,
  tempCritical: 85,
};

export const USAGE_RANGE = { min: 50, max: 100 } as const;
export const TEMP_RANGE = { min: 50, max: 110 } as const;

const ORDER: Record<AlertLevel, number> = { normal: 0, alto: 1, critico: 2 };

function levelFor(value: number | null | undefined, high: number, critical: number): AlertLevel {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'normal';
  if (value >= critical) return 'critico';
  if (value >= high) return 'alto';
  return 'normal';
}

/** Uso de CPU, GPU, RAM, VRAM ou disco, em %. */
export function usageLevel(value: number | null | undefined, limits: AlertLimits): AlertLevel {
  return limits.enabled ? levelFor(value, limits.usageHigh, limits.usageCritical) : 'normal';
}

/** Temperatura em graus Celsius. */
export function tempLevel(value: number | null | undefined, limits: AlertLimits): AlertLevel {
  return limits.enabled ? levelFor(value, limits.tempHigh, limits.tempCritical) : 'normal';
}

/** O mais grave: a borda do cartao da GPU usa o pior entre uso e temperatura. */
export function worst(...levels: AlertLevel[]): AlertLevel {
  return levels.reduce<AlertLevel>((a, b) => (ORDER[b] > ORDER[a] ? b : a), 'normal');
}

/** `short`: forma curta, usada quando o nome da placa nao caberia ao lado dos selos. */
export type AlertBadge = { label: string; short?: string; level: Exclude<AlertLevel, 'normal'> };

export function usageBadge(level: AlertLevel): AlertBadge | null {
  if (level === 'normal') return null;
  return { label: level === 'critico' ? 'Uso crítico' : 'Uso alto', level };
}

export function tempBadge(level: AlertLevel): AlertBadge | null {
  if (level === 'normal') return null;
  const critical = level === 'critico';
  return {
    label: critical ? 'Temperatura crítica' : 'Temperatura alta',
    short: critical ? 'Temp. crítica' : 'Temp. alta',
    level,
  };
}

export type LimitsDraft = { usageHigh: string; usageCritical: string; tempHigh: string; tempCritical: string };

export function toDraft(limits: AlertLimits): LimitsDraft {
  return {
    usageHigh: String(limits.usageHigh),
    usageCritical: String(limits.usageCritical),
    tempHigh: String(limits.tempHigh),
    tempCritical: String(limits.tempCritical),
  };
}

function parseWhole(text: string): number | null {
  const trimmed = text.trim();
  return /^\d{1,3}$/.test(trimmed) ? Number(trimmed) : null;
}

/** Confere o que foi digitado: numero inteiro, dentro da faixa, alto menor que critico. */
export function validateDraft(
  draft: LimitsDraft,
  enabled: boolean,
): { limits: AlertLimits; error: null } | { limits: null; error: string } {
  const values = {
    usageHigh: parseWhole(draft.usageHigh),
    usageCritical: parseWhole(draft.usageCritical),
    tempHigh: parseWhole(draft.tempHigh),
    tempCritical: parseWhole(draft.tempCritical),
  };
  if (Object.values(values).some((v) => v === null)) return { limits: null, error: 'Use só números inteiros.' };
  const v = values as Record<keyof LimitsDraft, number>;
  const inRange = (n: number, r: { min: number; max: number }) => n >= r.min && n <= r.max;
  if (!inRange(v.usageHigh, USAGE_RANGE) || !inRange(v.usageCritical, USAGE_RANGE)) {
    return { limits: null, error: `Uso: escolha valores de ${USAGE_RANGE.min}% a ${USAGE_RANGE.max}%.` };
  }
  if (!inRange(v.tempHigh, TEMP_RANGE) || !inRange(v.tempCritical, TEMP_RANGE)) {
    return { limits: null, error: `Temperatura: escolha valores de ${TEMP_RANGE.min} °C a ${TEMP_RANGE.max} °C.` };
  }
  if (v.usageHigh >= v.usageCritical) return { limits: null, error: 'Uso: o alto precisa ser menor que o crítico.' };
  if (v.tempHigh >= v.tempCritical) {
    return { limits: null, error: 'Temperatura: a alta precisa ser menor que a crítica.' };
  }
  return { limits: { enabled, ...v }, error: null };
}

/** Limites lidos do aparelho: qualquer coisa estranha volta ao padrao. */
export function sanitizeLimits(value: unknown): AlertLimits {
  if (typeof value !== 'object' || value === null) return DEFAULT_LIMITS;
  const raw = value as Record<string, unknown>;
  const enabled = typeof raw.enabled === 'boolean' ? raw.enabled : DEFAULT_LIMITS.enabled;
  const draft = {
    usageHigh: String(raw.usageHigh ?? ''),
    usageCritical: String(raw.usageCritical ?? ''),
    tempHigh: String(raw.tempHigh ?? ''),
    tempCritical: String(raw.tempCritical ?? ''),
  };
  const checked = validateDraft(draft, enabled);
  return checked.limits ?? { ...DEFAULT_LIMITS, enabled };
}
