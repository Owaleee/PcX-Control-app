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

const SEPARATORS = /[.,\s]/;

/**
 * Formata o IP enquanto a pessoa digita: o ponto entra sozinho quando o bloco nao aceita
 * mais digitos (3 digitos, um "0" ou valor x 10 > 255). Ponto, virgula ou espaco fecham um
 * bloco curto. Apagando (`deleting`), so limpa: o ponto automatico nao volta.
 */
export function formatIpInput(text: string, deleting: boolean): string {
  const cleaned = text.replace(/[^\d.,\s]/g, '');
  if (deleting) return cleaned.replace(/[,\s]/g, '.').replace(/\.{2,}/g, '.').replace(/^\./, '');
  // Colou um IP inteiro (talvez com zeros a esquerda ou virgulas): normaliza de uma vez.
  const pasted = normalizeIpv4(cleaned.replace(/^[.,\s]+|[.,\s]+$/g, ''));
  if (pasted) return pasted;

  const blocks: string[] = [''];
  const full = (block: string) => block.length === 3 || block === '0' || Number(block) * 10 > 255;
  for (const char of cleaned) {
    const current = blocks[blocks.length - 1] ?? '';
    if (SEPARATORS.test(char)) {
      if (current !== '' && blocks.length < 4) blocks.push('');
      continue;
    }
    if (full(current)) continue; // so acontece no quarto bloco
    blocks[blocks.length - 1] = current + char;
    if (full(current + char) && blocks.length < 4) blocks.push('');
  }
  return blocks.join('.');
}
