// Cliente HTTP do agente: timeouts, validacao das respostas e mensagens em portugues.
import { formatAttempts } from '../format/format';
import type { AgentInfo, HistoryResponse, MetricName, PairResponse, Range } from '../protocol/types';
import { parseErrorBody, parseHistory, parseInfo, parsePair } from '../protocol/validate';

export type ApiErrorKind =
  | 'network'
  | 'timeout'
  | 'bad_credentials'
  | 'code_invalid_or_expired'
  | 'rate_limited'
  | 'invalid_name'
  | 'invalid_token'
  | 'session_busy'
  | 'starting'
  | 'invalid_response'
  | 'http';

export type ApiError = Error & {
  kind: ApiErrorKind;
  status?: number;
  attemptsLeft?: number;
  retryAfter?: number;
  activeDevice?: string;
};

const KNOWN_CODES: readonly ApiErrorKind[] = [
  'bad_credentials',
  'code_invalid_or_expired',
  'rate_limited',
  'invalid_name',
  'invalid_token',
  'session_busy',
  'starting',
];

export const NOT_FOUND_MESSAGE =
  'PC não encontrado. Confira se o celular e o PC estão na mesma rede Wi-Fi e se o PcX Control está aberto.';
const GENERIC_MESSAGE = 'Algo deu errado. Tente de novo.';
const DEFAULT_TIMEOUT_MS = 5000;

function apiError(kind: ApiErrorKind, extra: Partial<ApiError> = {}): ApiError {
  const err = new Error(kind) as ApiError;
  err.name = 'ApiError';
  err.kind = kind;
  Object.assign(err, extra);
  return err;
}

export function isApiError(value: unknown): value is ApiError {
  return (
    typeof value === 'object' &&
    value !== null &&
    (value as { name?: unknown }).name === 'ApiError' &&
    typeof (value as { kind?: unknown }).kind === 'string'
  );
}

export function baseUrl(host: string, port: number): string {
  return `http://${host}:${port}`;
}

async function request(url: string, init: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(url, { ...init, signal: controller.signal });
  } catch {
    throw apiError(controller.signal.aborted ? 'timeout' : 'network');
  } finally {
    clearTimeout(timer);
  }
  if (response.ok) return response;

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  const parsed = parseErrorBody(body);
  const kind = parsed && (KNOWN_CODES as string[]).includes(parsed.code) ? (parsed.code as ApiErrorKind) : 'http';
  throw apiError(kind, {
    status: response.status,
    attemptsLeft: parsed?.attempts_left,
    retryAfter: parsed?.retry_after,
    activeDevice: parsed?.active_device,
  });
}

async function json<T>(response: Response, parse: (raw: unknown) => T | null): Promise<T> {
  let raw: unknown;
  try {
    raw = await response.json();
  } catch {
    throw apiError('invalid_response', { status: response.status });
  }
  const value = parse(raw);
  if (value === null) throw apiError('invalid_response', { status: response.status });
  return value;
}

const bearer = (token: string) => ({ Authorization: `Bearer ${token}` });

export async function getInfo(base: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<AgentInfo> {
  return json(await request(`${base}/v1/info`, {}, timeoutMs), parseInfo);
}

export async function pair(
  base: string,
  body: { device_name: string; code?: string; password?: string },
): Promise<PairResponse> {
  const payload =
    body.code !== undefined
      ? { device_name: body.device_name, code: body.code }
      : { device_name: body.device_name, password: body.password };
  const response = await request(`${base}/v1/pair`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return json(response, parsePair);
}

export async function getHistory(
  base: string,
  token: string,
  metric: MetricName,
  range: Range,
): Promise<HistoryResponse> {
  const query = `metric=${encodeURIComponent(metric)}&range=${encodeURIComponent(range)}`;
  return json(await request(`${base}/v1/history?${query}`, { headers: bearer(token) }), parseHistory);
}

export async function forgetMe(base: string, token: string): Promise<void> {
  await request(`${base}/v1/devices/me`, { method: 'DELETE', headers: bearer(token) });
}

export function userMessage(err: unknown): string {
  if (!isApiError(err)) return GENERIC_MESSAGE;
  switch (err.kind) {
    case 'network':
    case 'timeout':
      return NOT_FOUND_MESSAGE;
    case 'bad_credentials':
      return `Senha incorreta. ${formatAttempts(err.attemptsLeft ?? 0)}`;
    case 'rate_limited':
      return `Muitas tentativas. Tente de novo em ${Math.ceil(err.retryAfter ?? 60)} s.`;
    case 'code_invalid_or_expired':
      return 'Código expirado. Gere outro no PC.';
    case 'invalid_name':
      return 'Nome do aparelho inválido: use de 1 a 64 caracteres.';
    case 'invalid_token':
      return 'Este celular foi desconectado no PC. Pareie de novo.';
    case 'session_busy':
      return `PC em uso por ${err.activeDevice ?? 'outro aparelho'}.`;
    case 'starting':
      return 'O PC está iniciando. Tente em alguns segundos.';
    default:
      return GENERIC_MESSAGE;
  }
}
