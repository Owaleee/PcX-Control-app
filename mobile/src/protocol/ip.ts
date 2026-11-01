/** Normaliza um IPv4 digitado: apara espacos, aceita virgula e remove zeros a esquerda. */
export function normalizeIpv4(input: string): string | null {
  const parts = input.trim().replace(/,/g, '.').split('.');
  if (parts.length !== 4) return null;
  const numbers: number[] = [];
  for (const part of parts) {
    if (!/^\d{1,3}$/.test(part)) return null;
    const value = Number(part);
    if (value > 255) return null;
    numbers.push(value);
  }
  return numbers.join('.');
}
