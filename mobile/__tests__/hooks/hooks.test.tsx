import { act, renderHook, waitFor } from '@testing-library/react-native';
import { AppState, type AppStateStatus } from 'react-native';

import type { ConnState } from '../../src/connection/ConnectionManager';
import { usePcConnection } from '../../src/hooks/usePcConnection';
import { appendWindow, useMetricHistory } from '../../src/hooks/useMetricHistory';
import type { SavedPc } from '../../src/storage/storage';
import * as fx from '../protocol/fixtures';

jest.mock('../../src/connection/ConnectionManager', () => {
  class FakeManager {
    static instances: FakeManager[] = [];
    options: { url: string; token: string };
    starts: { takeover?: boolean }[] = [];
    stops = 0;
    state: any = { kind: 'stopped' };
    lastSnapshot = null;
    stateListeners = new Set<any>();
    snapshotListeners = new Set<any>();
    constructor(options: { url: string; token: string }) {
      this.options = options;
      FakeManager.instances.push(this);
    }
    start(opts: { takeover?: boolean } = {}) {
      this.starts.push(opts);
      this.emit({ kind: 'connecting' });
    }
    stop() {
      this.stops += 1;
      this.emit({ kind: 'stopped' });
    }
    emit(next: any) {
      this.state = next;
      this.stateListeners.forEach((l: any) => l(next));
    }
    push(message: unknown) {
      this.snapshotListeners.forEach((l: any) => l(message));
    }
    onState(l: any) {
      this.stateListeners.add(l);
      return () => this.stateListeners.delete(l);
    }
    onSnapshot(l: any) {
      this.snapshotListeners.add(l);
      return () => this.snapshotListeners.delete(l);
    }
  }
  return { ConnectionManager: FakeManager };
});

jest.mock('../../src/api/http', () => ({
  ...jest.requireActual('../../src/api/http'),
  getHistory: jest.fn(),
}));

const { ConnectionManager: Fake } = jest.requireMock('../../src/connection/ConnectionManager') as {
  ConnectionManager: { instances: any[] };
};
const http = jest.requireMock('../../src/api/http') as { getHistory: jest.Mock };

const PC: SavedPc = {
  agentId: 'a',
  name: 'PC',
  host: '192.168.0.10',
  port: 8765,
  deviceId: 'd',
  token: 'tok',
  addedAt: 0,
};

let appStateHandler: ((s: AppStateStatus) => void) | null = null;
beforeEach(() => {
  Fake.instances = [];
  appStateHandler = null;
  jest.spyOn(AppState, 'addEventListener').mockImplementation((_type, handler) => {
    appStateHandler = handler as (s: AppStateStatus) => void;
    return { remove: jest.fn() } as any;
  });
  http.getHistory.mockReset();
});

describe('appendWindow', () => {
  const p = (t: number, v = 1) => ({ t, avg: v, max: v });

  test('descarta o que sai da janela', () => {
    expect(appendWindow([p(0), p(100), p(950)], p(1000), 900)).toEqual([p(100), p(950), p(1000)]);
  });

  test('ignora ponto mais antigo e substitui o do mesmo instante', () => {
    expect(appendWindow([p(10)], p(5), 900)).toEqual([p(10)]);
    expect(appendWindow([p(10, 1)], p(10, 7), 900)).toEqual([p(10, 7)]);
  });
});

describe('usePcConnection', () => {
  test('cria o gerenciador com a URL do PC e comeca', async () => {
    const { result } = await renderHook(() => usePcConnection(PC));
    const manager = Fake.instances[0];
    expect(manager.options).toEqual(
      expect.objectContaining({ url: 'ws://192.168.0.10:8765/v1/stream', token: 'tok' }),
    );
    expect(manager.starts).toEqual([{}]);
    expect(result.current.state.kind).toBe('connecting');
  });

  test('repassa estado e leituras', async () => {
    const { result } = await renderHook(() => usePcConnection(PC));
    const manager = Fake.instances[0];
    await act(async () => {
      manager.emit({ kind: 'connected', hello: fx.clone(fx.hello) });
      manager.push(fx.clone(fx.snapshotMessage));
    });
    expect(result.current.state.kind).toBe('connected');
    expect(result.current.snapshot?.seq).toBe(42);
  });

  test('para em segundo plano e volta ao reabrir', async () => {
    await renderHook(() => usePcConnection(PC));
    const manager = Fake.instances[0];
    await act(async () => appStateHandler?.('background'));
    expect(manager.stops).toBe(1);
    await act(async () => appStateHandler?.('active'));
    expect(manager.starts).toHaveLength(2);
  });

  test('nao volta sozinho depois de revogado ou assumido', async () => {
    await renderHook(() => usePcConnection(PC));
    const manager = Fake.instances[0];
    for (const kind of ['revoked', 'taken_over', 'busy'] as const) {
      await act(async () => manager.emit(kind === 'busy' ? { kind, activeDevice: 'X' } : { kind }));
      await act(async () => appStateHandler?.('background'));
      await act(async () => appStateHandler?.('active'));
    }
    expect(manager.starts).toHaveLength(1);
  });

  test('assumir e reconectar', async () => {
    const { result } = await renderHook(() => usePcConnection(PC));
    const manager = Fake.instances[0];
    await act(async () => result.current.takeover());
    await act(async () => result.current.reconnect());
    expect(manager.starts).toEqual([{}, { takeover: true }, {}]);
  });

  test('para ao desmontar e nada sem PC', async () => {
    const { unmount } = await renderHook(() => usePcConnection(PC));
    await unmount();
    expect(Fake.instances[0].stops).toBe(1);
    Fake.instances = [];
    const { result } = await renderHook(() => usePcConnection(null));
    expect(Fake.instances).toHaveLength(0);
    expect(result.current.state.kind).toBe('stopped');
  });
});

describe('useMetricHistory', () => {
  test('junta o historico buscado com as leituras ao vivo', async () => {
    http.getHistory.mockResolvedValue(fx.clone(fx.history));
    const snapshot = fx.clone(fx.snapshotMessage);
    snapshot.t = new Date((fx.history.points[1].t + 5) * 1000).toISOString();
    const { result, rerender } = await renderHook(
      ({ snap }: { snap: any }) => useMetricHistory(PC, 'cpu.total', '15m', snap),
      { initialProps: { snap: null } },
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(http.getHistory).toHaveBeenCalledWith('http://192.168.0.10:8765', 'tok', 'cpu.total', '15m');
    expect(result.current.points).toHaveLength(2);
    await rerender({ snap: snapshot });
    expect(result.current.points).toHaveLength(3);
    expect(result.current.points[2]?.avg).toBe(13);
  });

  test('metrica ausente na leitura nao adiciona ponto', async () => {
    http.getHistory.mockResolvedValue({ metric: 'gpu.temp', range: '15m', points: [] });
    const snapshot = fx.clone(fx.snapshotMessage);
    snapshot.data.gpus[0].temp_c = null;
    const { result } = await renderHook(() => useMetricHistory(PC, 'gpu.temp', '15m', snapshot));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.points).toEqual([]);
  });

  test('erro na busca vira mensagem', async () => {
    const err = Object.assign(new Error('network'), { name: 'ApiError', kind: 'network' });
    http.getHistory.mockRejectedValue(err);
    const { result } = await renderHook(() => useMetricHistory(PC, 'cpu.total', '1h', null));
    await waitFor(() => expect(result.current.error).toMatch(/^PC não encontrado/));
  });
});


test('uma sessao nova busca o historico de novo (ex.: depois de assumir)', async () => {
  const busy = Object.assign(new Error('session_busy'), {
    name: 'ApiError',
    kind: 'session_busy',
    activeDevice: 'Pixel',
  });
  http.getHistory.mockRejectedValueOnce(busy).mockResolvedValueOnce(fx.clone(fx.history));
  const { result, rerender } = await renderHook(
    ({ session }: { session: number }) => useMetricHistory(PC, 'cpu.total', '15m', null, session),
    { initialProps: { session: 1 } },
  );
  await waitFor(() => expect(result.current.error).toBe('PC em uso por Pixel.'));
  await rerender({ session: 2 });
  await waitFor(() => expect(result.current.points).toHaveLength(2));
  expect(result.current.error).toBeNull();
  expect(http.getHistory).toHaveBeenCalledTimes(2);
});

test('usePcConnection expoe stop, que nao reconecta ao voltar do segundo plano', async () => {
  const { result } = await renderHook(() => usePcConnection(PC));
  const manager = Fake.instances[0];
  await act(async () => result.current.stop());
  expect(manager.stops).toBe(1);
  await act(async () => appStateHandler?.('background'));
  await act(async () => appStateHandler?.('active'));
  expect(manager.starts).toHaveLength(1);
});
