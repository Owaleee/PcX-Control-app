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
const SCHEME = /^[a-z]+:\/\//i;

/** Tira "http://", ":porta" e "/caminho" de um endereco colado, deixando so o host. */
function hostPart(text: string): string {
  // Mantem o espaco do fim: digitado, ele e um separador de bloco.
  return text.replace(/^\s+/, '').replace(SCHEME, '').replace(/:\d{1,5}(\/\S*)?\s*$/, '').replace(/\/\S*/, '');
}

/** A porta de um endereco colado ("192.168.0.10:8765", "http://...:9000/"), ou null. */
export function portFromAddress(text: string): string | null {
  const match = text.trim().replace(SCHEME, '').match(/^[^:/]*:(\d{1,5})(?:\/.*)?$/);
  return match?.[1] ?? null;
}
const dots = (text: string) => (text.match(/\./g) ?? []).length;
const validBlock = (block: string) => /^\d{0,3}$/.test(block) && (block === '' || Number(block) <= 255);

/**
 * Formata o IP enquanto a pessoa digita, comparando com o valor anterior do campo:
 * - colar (ou completar) um IP valido normaliza de uma vez (zeros a esquerda, virgulas);
 * - apagando, so limpa: os pontos ficam onde estao e o ponto automatico nao volta;
 * - com os 4 blocos ja na tela, edicoes no meio nao redistribuem os digitos: uma edicao que
 *   deixaria um bloco invalido e recusada;
 * - digitando, o ponto entra sozinho quando o bloco nao aceita mais digitos (3 digitos ou
 *   valor x 10 > 255), e ponto, virgula ou espaco fecham um bloco curto;
 * - "http://", ":porta" e "/caminho" colados junto sao descartados (a porta e lida a parte).
 */
export function formatIpInput(text: string, previous: string): string {
  const cleaned = hostPart(text).replace(/[^\d.,\s]/g, '');
  const asDots = cleaned.replace(/[,\s]/g, '.');
  const pasted = normalizeIpv4(cleaned.replace(/^[.,\s]+|[.,\s]+$/g, ''));
  if (pasted) return pasted;
  if (asDots.length < previous.length) return asDots.replace(/^\./, '');
  // Colou algo que nao e um IPv4: fica como esta, para a validacao avisar ao conectar.
  if (text.length - previous.length > 1) return text.trim();
  if (dots(previous) === 3 && dots(asDots) >= 3) {
    const blocks = asDots.split('.');
    return blocks.length === 4 && blocks.every(validBlock) ? asDots : previous;
  }

  const blocks: string[] = [''];
  const full = (block: string) => block.length === 3 || Number(block) * 10 > 255;
  for (const char of cleaned) {
    const current = blocks[blocks.length - 1] ?? '';
    if (SEPARATORS.test(char)) {
      if (current !== '' && blocks.length < 4) blocks.push('');
      continue;
    }
    // Zero a esquerda ("010") e descartado, como no normalizeIpv4: o bloco vira so o novo digito.
    const next = current === '0' ? char : current + char;
    if (full(current) || Number(next) > 255) continue;
    blocks[blocks.length - 1] = next;
    if (full(next) && blocks.length < 4) blocks.push('');
  }
  return blocks.join('.');
}
