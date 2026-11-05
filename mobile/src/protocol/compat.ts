// Compatibilidade de versoes entre o app e o agente (spec 8).
import type { Hello } from './types';

export const SUPPORTED_PROTOCOL = 1;
export const RELEASES_URL = 'https://github.com/Owaleee/PcX-Control-app/releases';

/** 'app': o PC e mais novo, falta atualizar o app. 'agent': o PC e mais antigo. */
export function checkProtocol(protocol: number): 'ok' | 'app' | 'agent' {
  if (protocol > SUPPORTED_PROTOCOL) return 'app';
  if (protocol < SUPPORTED_PROTOCOL) return 'agent';
  return 'ok';
}

export function hasCapability(hello: Hello | null, cap: string): boolean {
  return hello !== null && hello.capabilities.includes(cap);
}

/** Le so `type` e `protocol`: o parseHello recusa um hello de outro protocolo. */
export function helloProtocol(raw: unknown): number | null {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) return null;
  const { type, protocol } = raw as { type?: unknown; protocol?: unknown };
  return type === 'hello' && typeof protocol === 'number' && Number.isFinite(protocol) ? protocol : null;
}
