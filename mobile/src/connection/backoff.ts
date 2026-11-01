const BASE_MS = [1000, 2000, 4000, 8000, 15000] as const;
export const MAX_DELAY_MS = 15000;

/** Espera antes da tentativa `attempt` (0 = primeira): 1, 2, 4, 8, 15 s, com +-20% e teto de 15 s. */
export function backoffDelay(attempt: number, random: () => number = Math.random): number {
  const base = BASE_MS[Math.min(Math.max(attempt, 0), BASE_MS.length - 1)] ?? MAX_DELAY_MS;
  const factor = 0.8 + 0.4 * Math.min(Math.max(random(), 0), 1);
  return Math.min(MAX_DELAY_MS, Math.round(base * factor));
}
