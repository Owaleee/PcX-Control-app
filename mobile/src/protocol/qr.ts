import { normalizeIpv4 } from './ip';

export type PairingTarget = { agentId: string; host: string; port: number; code: string };

/** Le pcx://pair?v=1&id=...&h=...&p=...&c=... (gerado pelo agente). Qualquer outra coisa: null. */
export function parsePairingUri(text: string): PairingTarget | null {
  const match = /^pcx:\/\/pair\?(.*)$/.exec(text.trim());
  if (!match) return null;
  const params = new Map<string, string>();
  for (const pair of (match[1] ?? '').split('&')) {
    const index = pair.indexOf('=');
    if (index <= 0) continue;
    try {
      params.set(pair.slice(0, index), decodeURIComponent(pair.slice(index + 1)));
    } catch {
      return null;
    }
  }
  if (params.get('v') !== '1') return null;
  const agentId = params.get('id') ?? '';
  const host = normalizeIpv4(params.get('h') ?? '');
  const portText = params.get('p') ?? '';
  const port = /^\d+$/.test(portText) ? Number(portText) : NaN;
  const code = params.get('c') ?? '';
  if (!agentId || !host || !code || !(port >= 1 && port <= 65535)) return null;
  return { agentId, host, port, code };
}
