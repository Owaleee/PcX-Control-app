import { act, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { Alert, StyleSheet } from 'react-native';

import Panel from '../../app/pc/[id]/index';
import MetricDetail from '../../app/pc/[id]/metric/[metric]';
import PcSettings from '../../app/pc/[id]/settings';
import type { ConnState } from '../../src/connection/ConnectionManager';
import { PcProvider } from '../../src/hooks/PcContext';
import type { SavedPc } from '../../src/storage/storage';
import * as fx from '../protocol/fixtures';
import { paramsMock, resetRouter, routerMock } from './mocks';

jest.mock('expo-router', () => jest.requireActual('./mocks').expoRouterMock());
jest.mock('../../src/storage/storage', () => ({
  getPc: jest.fn(),
  removePc: jest.fn(async () => undefined),
  updatePc: jest.fn(async () => undefined),
  getTheme: jest.fn(async () => 'dark'),
  setTheme: jest.fn(),
}));
jest.mock('../../src/hooks/usePcConnection', () => ({ usePcConnection: jest.fn() }));
jest.mock('../../src/hooks/useMetricHistory', () => ({
  ...jest.requireActual('../../src/hooks/useMetricHistory'),
  useMetricHistory: jest.fn(() => ({ points: [], loading: false, error: null })),
}));
jest.mock('../../src/api/http', () => ({ ...jest.requireActual('../../src/api/http'), forgetMe: jest.fn() }));

const storage = jest.requireMock('../../src/storage/storage') as Record<string, jest.Mock>;
const conn = jest.requireMock('../../src/hooks/usePcConnection') as { usePcConnection: jest.Mock };
const history = jest.requireMock('../../src/hooks/useMetricHistory') as { useMetricHistory: jest.Mock };
const http = jest.requireMock('../../src/api/http') as { forgetMe: jest.Mock };

const PC: SavedPc = {
  agentId: 'a1',
  name: 'PC-DEMO',
  host: '192.168.0.10',
  port: 8765,
  deviceId: 'd',
  token: 'tok',
  addedAt: 0,
};
const connected: ConnState = { kind: 'connected', hello: fx.clone(fx.hello) };
const takeover = jest.fn();
const reconnect = jest.fn();

function setConnection(state: ConnState, snapshot: unknown = fx.clone(fx.snapshotMessage)) {
  conn.usePcConnection.mockReturnValue({ state, snapshot, takeover, reconnect });
}

async function renderWith(node: React.ReactElement) {
  const view = await render(<PcProvider agentId="a1">{node}</PcProvider>);
  await waitFor(() => expect(storage.getPc).toHaveBeenCalled());
  await act(async () => undefined);
  return view;
}

let alertSpy: jest.SpyInstance;
beforeEach(() => {
  resetRouter();
  paramsMock.current = { id: 'a1' };
  storage.getPc!.mockResolvedValue(PC);
  storage.removePc!.mockClear();
  storage.updatePc!.mockClear();
  takeover.mockClear();
  http.forgetMe.mockReset();
  history.useMetricHistory.mockClear();
  setConnection(connected);
  alertSpy = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
});
afterEach(() => alertSpy.mockRestore());

describe('painel', () => {
  test('mostra os cartoes a partir da leitura', async () => {
    await renderWith(<Panel />);
    expect(screen.getByText('Conectado')).toBeTruthy();
    expect(screen.getByText('13,0%')).toBeTruthy();
    expect(screen.getByText('43,8%')).toBeTruthy();
    expect(screen.getByText('14,0 / 31,9 GiB')).toBeTruthy();
    expect(screen.getByText('NVIDIA GeForce RTX 3070')).toBeTruthy();
    expect(screen.getByText('VRAM 2,5 / 7,8 GiB · 49 °C')).toBeTruthy();
    expect(screen.getByText('Disco C:\\')).toBeTruthy();
    expect(screen.getByText('Disco E:\\')).toBeTruthy();
    expect(screen.getByText('↓ 4,0 KB/s  ↑ 0,4 KB/s')).toBeTruthy();
  });

  test('sem temperatura nao mostra graus', async () => {
    const snap = fx.clone(fx.snapshotMessage);
    snap.data.gpus[0].temp_c = null;
    setConnection(connected, snap);
    await renderWith(<Panel />);
    expect(screen.getByText('VRAM 2,5 / 7,8 GiB')).toBeTruthy();
    expect(screen.queryByText(/°C/)).toBeNull();
  });

  test('valores ficam esmaecidos fora do estado conectado', async () => {
    setConnection({ kind: 'reconnecting', attempt: 1, retryInMs: 1000 });
    await renderWith(<Panel />);
    const card = screen.getAllByTestId('metric-card')[0]!;
    expect(StyleSheet.flatten(card.props.style).opacity).toBe(0.5);
  });

  test('sessao ocupada pergunta e Assumir chama takeover', async () => {
    setConnection({ kind: 'busy', activeDevice: 'Pixel' }, null);
    await renderWith(<Panel />);
    expect(alertSpy).toHaveBeenCalledTimes(1);
    const [, message, buttons] = alertSpy.mock.calls[0];
    expect(message).toBe('PC em uso por Pixel. Assumir a sessão?');
    buttons.find((b: { text: string }) => b.text === 'Assumir').onPress();
    expect(takeover).toHaveBeenCalled();
  });

  test('sessao assumida mostra aviso com botao para assumir de volta', async () => {
    setConnection({ kind: 'taken_over' });
    await renderWith(<Panel />);
    expect(screen.getByText('Sessão assumida por outro aparelho')).toBeTruthy();
    await fireEvent.press(screen.getByText('Assumir de volta'));
    expect(takeover).toHaveBeenCalled();
  });

  test('revogado remove o PC e volta ao inicio uma unica vez', async () => {
    setConnection({ kind: 'revoked' }, null);
    const view = await renderWith(<Panel />);
    await view.rerender(
      <PcProvider agentId="a1">
        <Panel />
      </PcProvider>,
    );
    await act(async () => undefined);
    expect(storage.removePc).toHaveBeenCalledTimes(1);
    expect(storage.removePc).toHaveBeenCalledWith('a1');
    expect(routerMock.replace).toHaveBeenCalledTimes(1);
    expect(routerMock.replace).toHaveBeenCalledWith('/');
    expect(alertSpy.mock.calls[0][1]).toBe('Este celular foi desconectado no PC. Pareie de novo.');
  });

  test('PC inexistente mostra aviso', async () => {
    storage.getPc!.mockResolvedValue(null);
    await renderWith(<Panel />);
    expect(screen.getByText('PC não encontrado.')).toBeTruthy();
  });

  test('botao do modo painel e toque no cartao navegam', async () => {
    await renderWith(<Panel />);
    await fireEvent.press(screen.getByText('Modo painel'));
    expect(routerMock.push).toHaveBeenCalledWith('/pc/a1/panel');
    await fireEvent.press(screen.getByText('CPU'));
    expect(routerMock.push).toHaveBeenCalledWith('/pc/a1/metric/cpu.total');
  });
});

describe('detalhe da metrica', () => {
  test('mostra media e maximo do intervalo', async () => {
    paramsMock.current = { id: 'a1', metric: 'cpu.total' };
    history.useMetricHistory.mockReturnValue({ points: fx.clone(fx.history).points, loading: false, error: null });
    await renderWith(<MetricDetail />);
    expect(screen.getByText('Média: 13,3%')).toBeTruthy();
    expect(screen.getByText('Máximo: 31,5%')).toBeTruthy();
    await fireEvent.press(screen.getByText('1 h'));
    expect(history.useMetricHistory).toHaveBeenLastCalledWith(PC, 'cpu.total', '1h', expect.anything());
  });

  test('metrica desconhecida', async () => {
    paramsMock.current = { id: 'a1', metric: 'nada' };
    await renderWith(<MetricDetail />);
    expect(screen.getByText('Métrica desconhecida.')).toBeTruthy();
  });
});

describe('ajustes do PC', () => {
  test('salva o apelido', async () => {
    await renderWith(<PcSettings />);
    await fireEvent.changeText(screen.getByLabelText('Apelido'), 'PC da sala');
    await fireEvent.press(screen.getByText('Salvar apelido'));
    expect(storage.updatePc).toHaveBeenCalledWith('a1', { alias: 'PC da sala' });
  });

  test('esquecer com o PC online remove e volta', async () => {
    http.forgetMe.mockResolvedValue(undefined);
    await renderWith(<PcSettings />);
    await fireEvent.press(screen.getByText('Esquecer este PC'));
    const confirm = alertSpy.mock.calls[0][2].find((b: { text: string }) => b.text === 'Esquecer');
    await act(async () => confirm.onPress());
    expect(http.forgetMe).toHaveBeenCalledWith('http://192.168.0.10:8765', 'tok');
    expect(storage.removePc).toHaveBeenCalledWith('a1');
    expect(routerMock.replace).toHaveBeenCalledWith('/');
  });

  test('esquecer com o PC fora do ar pergunta antes de remover', async () => {
    http.forgetMe.mockRejectedValue(Object.assign(new Error('network'), { name: 'ApiError', kind: 'network' }));
    await renderWith(<PcSettings />);
    await fireEvent.press(screen.getByText('Esquecer este PC'));
    await act(async () => alertSpy.mock.calls[0][2].find((b: { text: string }) => b.text === 'Esquecer').onPress());
    expect(storage.removePc).not.toHaveBeenCalled();
    const [, message, buttons] = alertSpy.mock.calls[1];
    expect(message).toBe('Não foi possível falar com o PC. Remover só deste celular?');
    await act(async () => buttons.find((b: { text: string }) => b.text === 'Remover').onPress());
    expect(storage.removePc).toHaveBeenCalledWith('a1');
  });

  test('desconectar volta ao inicio sem apagar', async () => {
    await renderWith(<PcSettings />);
    await fireEvent.press(screen.getByText('Desconectar'));
    expect(routerMock.replace).toHaveBeenCalledWith('/');
    expect(storage.removePc).not.toHaveBeenCalled();
  });
});
