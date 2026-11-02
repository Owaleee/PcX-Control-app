import {
  baseUrl,
  forgetMe,
  getHistory,
  getInfo,
  isApiError,
  pair,
  userMessage,
  type ApiError,
} from '../../src/api/http';
import * as fx from '../protocol/fixtures';

const BASE = baseUrl('192.168.0.10', 8765);
const NOT_FOUND =
  'PC não encontrado. Confira se o celular e o PC estão na mesma rede Wi-Fi, se o PcX Control está aberto e se a rede do PC está como Privada no Windows.';

function reply(status: number, body: unknown) {
  return Promise.resolve(
    new Response(typeof body === 'string' ? body : JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  );
}

let fetchMock: jest.SpyInstance;
beforeEach(() => {
  fetchMock = jest.spyOn(globalThis, 'fetch');
});
afterEach(() => {
  fetchMock.mockRestore();
  jest.useRealTimers();
});

async function failure(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (err) {
    expect(isApiError(err)).toBe(true);
    return err as ApiError;
  }
  throw new Error('esperava falha');
}

test('baseUrl', () => {
  expect(BASE).toBe('http://192.168.0.10:8765');
});

test('getInfo devolve a resposta validada', async () => {
  fetchMock.mockReturnValueOnce(reply(200, fx.info));
  expect((await getInfo(BASE)).agent_id).toBe(fx.info.agent_id);
  expect(fetchMock.mock.calls[0][0]).toBe('http://192.168.0.10:8765/v1/info');
});

test('pair envia so o codigo', async () => {
  fetchMock.mockReturnValueOnce(reply(200, fx.pair));
  await pair(BASE, { device_name: 'Moto G', code: 'abc' });
  const init = fetchMock.mock.calls[0][1];
  expect(init.method).toBe('POST');
  expect(JSON.parse(init.body)).toEqual({ device_name: 'Moto G', code: 'abc' });
});

test('pair envia so a senha', async () => {
  fetchMock.mockReturnValueOnce(reply(200, fx.pair));
  await pair(BASE, { device_name: 'Moto G', password: 'segredo-123' });
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
    device_name: 'Moto G',
    password: 'segredo-123',
  });
});

test.each([
  [401, fx.errorBadCredentials, 'bad_credentials', 'Senha incorreta. Restam 4 tentativas.'],
  [
    401,
    { code: 'bad_credentials', message: 'x', attempts_left: 1 },
    'bad_credentials',
    'Senha incorreta. Resta 1 tentativa.',
  ],
  [410, { code: 'code_invalid_or_expired', message: 'x' }, 'code_invalid_or_expired', 'Código expirado. Gere outro no PC.'],
  [429, { code: 'rate_limited', message: 'x', retry_after: 59.2 }, 'rate_limited', 'Muitas tentativas. Tente de novo em 60 s.'],
  [422, { code: 'invalid_name', message: 'x' }, 'invalid_name', 'Nome do aparelho inválido: use de 1 a 64 caracteres.'],
  [401, { code: 'invalid_token', message: 'x' }, 'invalid_token', 'Este celular foi desconectado no PC. Pareie de novo.'],
  [409, fx.errorSessionBusy, 'session_busy', 'PC em uso por Moto G.'],
  [503, { code: 'starting', message: 'x' }, 'starting', 'O PC está iniciando. Tente em alguns segundos.'],
  [500, 'erro interno', 'http', 'Algo deu errado. Tente de novo.'],
])('HTTP %p vira %p', async (status, body, kind, message) => {
  fetchMock.mockReturnValueOnce(reply(status, body));
  const err = await failure(pair(BASE, { device_name: 'Moto G', password: 'x' }));
  expect(err.kind).toBe(kind);
  expect(err.status).toBe(status);
  expect(userMessage(err)).toBe(message);
});

test('campos extras do erro ficam no ApiError', async () => {
  fetchMock.mockReturnValueOnce(reply(409, fx.errorSessionBusy));
  expect((await failure(getInfo(BASE))).activeDevice).toBe('Moto G');
  fetchMock.mockReturnValueOnce(reply(401, fx.errorBadCredentials));
  expect((await failure(getInfo(BASE))).attemptsLeft).toBe(4);
});

test('falha de rede vira network', async () => {
  fetchMock.mockRejectedValueOnce(new TypeError('Network request failed'));
  const err = await failure(getInfo(BASE));
  expect(err.kind).toBe('network');
  expect(userMessage(err)).toBe(NOT_FOUND);
});

test('sem resposta no prazo vira timeout', async () => {
  jest.useFakeTimers();
  fetchMock.mockImplementationOnce(
    (_url: string, init: RequestInit) =>
      new Promise((_resolve, reject) => {
        init.signal?.addEventListener('abort', () => reject(new DOMException('abort', 'AbortError')));
      }),
  );
  const pending = failure(getInfo(BASE, 5000));
  jest.advanceTimersByTime(5000);
  const err = await pending;
  expect(err.kind).toBe('timeout');
  expect(userMessage(err)).toBe(NOT_FOUND);
});

test('200 com corpo invalido vira invalid_response', async () => {
  fetchMock.mockReturnValueOnce(reply(200, { qualquer: 'coisa' }));
  expect((await failure(getInfo(BASE))).kind).toBe('invalid_response');
  fetchMock.mockReturnValueOnce(reply(200, 'nao e json'));
  expect((await failure(getInfo(BASE))).kind).toBe('invalid_response');
});

test('getHistory manda o token e os parametros', async () => {
  fetchMock.mockReturnValueOnce(reply(200, fx.history));
  const result = await getHistory(BASE, 'tok', 'cpu.total', '15m');
  expect(result.points).toHaveLength(2);
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe('http://192.168.0.10:8765/v1/history?metric=cpu.total&range=15m');
  expect(init.headers.Authorization).toBe('Bearer tok');
});

test('forgetMe usa DELETE e aceita 204', async () => {
  fetchMock.mockReturnValueOnce(Promise.resolve(new Response(null, { status: 204 })));
  await expect(forgetMe(BASE, 'tok')).resolves.toBeUndefined();
  expect(fetchMock.mock.calls[0][1].method).toBe('DELETE');
});

test('userMessage de erro desconhecido', () => {
  expect(userMessage(new Error('x'))).toBe('Algo deu errado. Tente de novo.');
  expect(userMessage('texto')).toBe('Algo deu errado. Tente de novo.');
});
