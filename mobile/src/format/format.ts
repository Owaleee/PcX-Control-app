// Formatacao em portugues (virgula decimal) sem depender de Intl.

const DASH = '—';
const ok = (v: number) => Number.isFinite(v) && v >= 0;
const comma = (v: number, digits = 1) => v.toFixed(digits).replace('.', ',');

/** Percentual inteiro por padrao (51%); com `precise`, uma casa decimal (50,5%). */
export function formatPercent(value: number, options: { precise?: boolean } = {}): string {
  if (!ok(value)) return DASH;
  return options.precise ? `${comma(value)}%` : `${Math.round(value)}%`;
}

export function formatBytes(value: number): string {
  if (!ok(value)) return DASH;
  const units = ['MiB', 'GiB', 'TiB'];
  let amount = value / 1024 ** 2;
  let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${comma(amount)} ${units[unit]}`;
}

export function formatRate(bytesPerSecond: number): string {
  if (!ok(bytesPerSecond)) return DASH;
  const units = ['KB/s', 'MB/s', 'GB/s'];
  let amount = bytesPerSecond / 1024;
  let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${comma(amount)} ${units[unit]}`;
}

export function formatTemp(celsius: number): string {
  return Number.isFinite(celsius) ? `${Math.round(celsius)} °C` : DASH;
}

export function formatUptime(seconds: number): string {
  if (!ok(seconds)) return DASH;
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days} d ${hours} h`;
  if (hours > 0) return `${hours} h ${minutes} min`;
  return `${minutes} min`;
}

export function formatAttempts(left: number): string {
  if (left <= 0) return 'Nenhuma tentativa restante.';
  return left === 1 ? 'Resta 1 tentativa.' : `Restam ${left} tentativas.`;
}

/** "usado / total" na unidade do total, por exemplo "14,0 / 31,9 GiB". */
export function formatUsage(used: number, total: number): string {
  if (!ok(used) || !ok(total)) return DASH;
  const units = ['MiB', 'GiB', 'TiB'];
  let divisor = 1024 ** 2;
  let unit = 0;
  while (total / divisor >= 1024 && unit < units.length - 1) {
    divisor *= 1024;
    unit += 1;
  }
  return `${comma(used / divisor)} / ${comma(total / divisor)} ${units[unit]}`;
}

/** Quanto sobra: "17,9 GiB livres". */
export function formatFree(used: number, total: number): string {
  if (!ok(used) || !ok(total)) return DASH;
  return `${formatBytes(Math.max(0, total - used))} livres`;
}
