import { backoffDelay } from '../../src/connection/backoff';
import { ConnectionManager, type ConnState } from '../../src/connection/ConnectionManager';
import * as fx from '../protocol/fixtures';
import { FakeSocket } from './fake-socket';

const URL = 'ws://192.168.0.10:8765/v1/stream';

function setup() {
  const states: ConnState[] = [];
  const snapshots: number[] = [];
  const manager = new ConnectionManager({
    url: URL,
    token: 'tok',
    createSocket: (url) => new FakeSocket(url),
    random: () => 0.5,
  });
  manager.onState((s) => states.push(s));
  manager.onSnapshot((m) => snapshots.push(m.seq));
  return { manager, states, snapshots, last: () => states[states.length - 1] };
}

function connect(manager: ConnectionManager) {
  manager.start();
  FakeSocket.last.open();
  FakeSocket.last.receive(fx.hello);
}

beforeEach(() => {
  FakeSocket.all = [];
  jest.useFakeTimers();
});
afterEach(() => jest.useRealTimers());

test('envia auth ao abrir', () => {
  const { manager, last } = setup();
  manager.start();
  expect(last()).toEqual({ kind: 'connecting' });
  expect(FakeSocket.last.url).toBe(URL);
  FakeSocket.last.open();
  expect(JSON.parse(FakeSocket.last.sent[0]!)).toEqual({ type: 'auth', token: 'tok', takeover: false });
});

test('hello leva a connected', () => {
  const { manager, last } = setup();
  connect(manager);
  const state = last();
  expect(state?.kind).toBe('connected');
  expect(state?.kind === 'connected' && state.hello.capabilities).toContain('cpu');
  expect(manager.state.kind).toBe('connected');
});

test('snapshot e emitido e guardado', () => {
  const { manager, snapshots } = setup();
  connect(manager);
  FakeSocket.last.receive(fx.snapshotMessage);
  expect(snapshots).toEqual([42]);
  expect(manager.lastSnapshot?.data.cpu_total).toBe(13);
});

test('mensagens invalidas sao ignoradas', () => {
  const { manager, snapshots, last } = setup();
  connect(manager);
  FakeSocket.last.receive('nao e json');
  FakeSocket.last.receive({ type: 'snapshot', seq: 1 });
  FakeSocket.last.receive({ type: 'desconhecido' });
  FakeSocket.last.onmessage?.({ data: new ArrayBuffer(4) });
  expect(snapshots).toEqual([]);
  expect(last()?.kind).toBe('connected');
});

test.each([
  [4401, '', { kind: 'revoked' }],
  [4409, 'Sessão assumida por outro aparelho', { kind: 'taken_over' }],
  [4423, 'Moto G', { kind: 'busy', activeDevice: 'Moto G' }],
  [4423, '', { kind: 'busy', activeDevice: 'outro aparelho' }],
])('fechamento %p vai para o estado final sem tentar de novo', (code, reason, expected) => {
  const { manager, last } = setup();
  connect(manager);
  FakeSocket.last.drop(code as number, reason as string);
  expect(last()).toEqual(expected);
  jest.advanceTimersByTime(60_000);
  expect(FakeSocket.all).toHaveLength(1);
});

test('queda anormal reconecta com espera crescente ate 15 s', () => {
  const { manager, states } = setup();
  connect(manager);
  const delays: number[] = [];
  for (let i = 0; i < 6; i += 1) {
    FakeSocket.last.drop(1006);
    const state = states[states.length - 1];
    expect(state?.kind).toBe('reconnecting');
    if (state?.kind === 'reconnecting') {
      expect(state.attempt).toBe(i + 1);
      delays.push(state.retryInMs);
      jest.advanceTimersByTime(state.retryInMs);
    }
  }
  expect(delays).toEqual([1000, 2000, 4000, 8000, 15000, 15000]);
  expect(FakeSocket.all).toHaveLength(7);
});

test('nao reconecta antes da hora', () => {
  const { manager } = setup();
  connect(manager);
  FakeSocket.last.drop(1006);
  jest.advanceTimersByTime(999);
  expect(FakeSocket.all).toHaveLength(1);
  jest.advanceTimersByTime(1);
  expect(FakeSocket.all).toHaveLength(2);
});

test('hello bem-sucedido zera as tentativas', () => {
  const { manager, states } = setup();
  connect(manager);
  FakeSocket.last.drop(1006);
  jest.advanceTimersByTime(1000);
  FakeSocket.last.drop(1006);
  jest.advanceTimersByTime(2000);
  FakeSocket.last.open();
  FakeSocket.last.receive(fx.hello);
  FakeSocket.last.drop(1001);
  const state = states[states.length - 1];
  expect(state).toEqual({ kind: 'reconnecting', attempt: 1, retryInMs: 1000 });
});

test('sem hello em 10 s fecha e tenta de novo', () => {
  const { manager, last } = setup();
  manager.start();
  FakeSocket.last.open();
  jest.advanceTimersByTime(10_000);
  expect(FakeSocket.all[0]?.closedWith).not.toBeNull();
  expect(last()?.kind).toBe('reconnecting');
  FakeSocket.all[0]?.drop(1006); // o fechamento atrasado do socket velho nao conta de novo
  expect(last()).toEqual({ kind: 'reconnecting', attempt: 1, retryInMs: 1000 });
});

test('assumir envia takeover true e depois volta ao normal', () => {
  const { manager } = setup();
  manager.start();
  FakeSocket.last.open();
  FakeSocket.last.drop(4423, 'Moto G');
  manager.start({ takeover: true });
  FakeSocket.last.open();
  expect(JSON.parse(FakeSocket.last.sent[0]!).takeover).toBe(true);
  FakeSocket.last.receive(fx.hello);
  FakeSocket.last.drop(1006);
  jest.advanceTimersByTime(1000);
  FakeSocket.last.open();
  expect(JSON.parse(FakeSocket.last.sent[0]!).takeover).toBe(false);
});

test('stop cancela a reconexao pendente e fecha o socket', () => {
  const { manager, last } = setup();
  connect(manager);
  FakeSocket.last.drop(1006);
  manager.stop();
  expect(last()).toEqual({ kind: 'stopped' });
  jest.advanceTimersByTime(60_000);
  expect(FakeSocket.all).toHaveLength(1);
});

test('stop durante a conexao fecha o socket e ignora eventos atrasados', () => {
  const { manager, last, snapshots } = setup();
  connect(manager);
  const socket = FakeSocket.last;
  manager.stop();
  expect(socket.closedWith?.code).toBe(1000);
  socket.receive(fx.snapshotMessage);
  socket.drop(1006);
  expect(snapshots).toEqual([]);
  expect(last()).toEqual({ kind: 'stopped' });
});

test('listeners podem sair', () => {
  const { manager } = setup();
  const seen: string[] = [];
  const off = manager.onState((s) => seen.push(s.kind));
  manager.start();
  off();
  FakeSocket.last.open();
  FakeSocket.last.receive(fx.hello);
  expect(seen).toEqual(['connecting']);
});

describe('backoffDelay', () => {
  test('base sem variacao (random = 0.5)', () => {
    expect([0, 1, 2, 3, 4, 9].map((a) => backoffDelay(a, () => 0.5))).toEqual([
      1000, 2000, 4000, 8000, 15000, 15000,
    ]);
  });

  test('variacao fica em +-20%', () => {
    expect(backoffDelay(0, () => 0)).toBe(800);
    expect(backoffDelay(0, () => 1)).toBe(1200);
    expect(backoffDelay(4, () => 1)).toBe(15000); // o teto do spec vale depois da variacao
    expect(backoffDelay(4, () => 0)).toBe(12000);
  });
});
