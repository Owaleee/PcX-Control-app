import { act, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { Alert, StyleSheet } from 'react-native';

import Panel from '../../app/pc/[id]/index';
import GpuDetail from '../../app/pc/[id]/gpu';
import MetricDetail from '../../app/pc/[id]/metric/[metric]';
import PcSettings from '../../app/pc/[id]/settings';
import type { ConnState } from '../../src/connection/ConnectionManager';
import { PcProvider } from '../../src/hooks/PcContext';
import { ThemeProvider } from '../../src/theme/ThemeProvider';
import { THEMES } from '../../src/theme/themes';
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
  getPrecise: jest.fn(async () => false),
  setPrecise: jest.fn(),
  getAlertLimits: jest.fn(async () => jest.requireActual('../../src/alerts/levels').DEFAULT_LIMITS),
  setAlertLimits: jest.fn(),
}));
jest.mock('../../src/hooks/usePcConnection', () => ({ usePcConnection: jest.fn() }));
jest.mock('../../src/hooks/useMetricHistory', () => ({
  ...jest.requireActual('../../src/hooks/useMetricHistory'),
  useMetricHistory: jest.fn(() => ({ points: [], loading: false, error: null })),
}));
jest.mock('../../src/api/http', () => ({
  ...jest.requireActual('../../src/api/http'),
  forgetMe: jest.fn(),
  getInfo: jest.fn(),
}));

const storage = jest.requireMock('../../src/storage/storage') as Record<string, jest.Mock>;
const conn = jest.requireMock('../../src/hooks/usePcConnection') as { usePcConnection: jest.Mock };
const history = jest.requireMock('../../src/hooks/useMetricHistory') as { useMetricHistory: jest.Mock };
const http = jest.requireMock('../../src/api/http') as { forgetMe: jest.Mock; getInfo: jest.Mock };

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
const stop = jest.fn();

function setConnection(state: ConnState, snapshot: unknown = fx.clone(fx.snapshotMessage)) {
  conn.usePcConnection.mockReturnValue({ state, snapshot, takeover, reconnect, stop });
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
  stop.mockClear();
  http.getInfo.mockReset();
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
    expect(screen.getByText('13%')).toBeTruthy();
    expect(screen.getByText('44%')).toBeTruthy();
    expect(screen.getByText('18%')).toBeTruthy();
    expect(screen.getByText('81%')).toBeTruthy();
    expect(screen.getByText('14,0 / 31,9 GiB · 17,9 GiB livres')).toBeTruthy();
    expect(screen.getByText('GPU · NVIDIA GeForce RTX 3070')).toBeTruthy();
    expect(screen.getByText('VRAM usada 2,5 / 7,8 GiB · Temperatura 49 °C')).toBeTruthy();
    expect(screen.getByText('Disco C:\\')).toBeTruthy();
    expect(screen.getByText('Disco E:\\')).toBeTruthy();
    expect(screen.getByText('↓ 4,0 KB/s  ↑ 0,4 KB/s')).toBeTruthy();
    expect(screen.getByText('↓ recebendo (download) · ↑ enviando (upload)')).toBeTruthy();
  });

  test('sem temperatura mostra indisponivel, sem graus', async () => {
    const snap = fx.clone(fx.snapshotMessage);
    snap.data.gpus[0].temp_c = null;
    setConnection(connected, snap);
    await renderWith(<Panel />);
    expect(screen.getByText('VRAM usada 2,5 / 7,8 GiB · Temperatura indisponível')).toBeTruthy();
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
    expect(routerMock.dismissTo).toHaveBeenCalledTimes(1);
    expect(routerMock.dismissTo).toHaveBeenCalledWith('/');
    expect(routerMock.replace).not.toHaveBeenCalled();
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
    await fireEvent.press(screen.getByText('GPU · NVIDIA GeForce RTX 3070'));
    expect(routerMock.push).toHaveBeenCalledWith('/pc/a1/gpu');
  });
});

describe('detalhe da metrica', () => {
  test('mostra media e maximo do intervalo', async () => {
    paramsMock.current = { id: 'a1', metric: 'cpu.total' };
    history.useMetricHistory.mockReturnValue({ points: fx.clone(fx.history).points, loading: false, error: null });
    await renderWith(<MetricDetail />);
    expect(screen.getByText('Média: 13%')).toBeTruthy();
    expect(screen.getByText('Máximo: 32%')).toBeTruthy();
    await fireEvent.press(screen.getByText('1 h'));
    expect(history.useMetricHistory).toHaveBeenLastCalledWith(PC, 'cpu.total', '1h', expect.anything(), 1);
  });

  test('metrica desconhecida', async () => {
    paramsMock.current = { id: 'a1', metric: 'nada' };
    await renderWith(<MetricDetail />);
    expect(screen.getByText('Métrica desconhecida.')).toBeTruthy();
  });
});

describe('detalhe da GPU', () => {
  test('mostra uso, VRAM e temperatura no mesmo intervalo', async () => {
    paramsMock.current = { id: 'a1' };
    history.useMetricHistory.mockReturnValue({ points: fx.clone(fx.history).points, loading: false, error: null });
    await renderWith(<GpuDetail />);
    expect(screen.getByText('Uso da GPU')).toBeTruthy();
    expect(screen.getByText('VRAM')).toBeTruthy();
    expect(screen.getByText('Temperatura')).toBeTruthy();
    const metrics = history.useMetricHistory.mock.calls.map((call) => call[1]);
    expect(metrics).toEqual(expect.arrayContaining(['gpu.usage', 'gpu.vram_percent', 'gpu.temp']));
    await fireEvent.press(screen.getByText('24 h'));
    for (const metric of ['gpu.usage', 'gpu.vram_percent', 'gpu.temp']) {
      expect(history.useMetricHistory).toHaveBeenCalledWith(PC, metric, '24h', expect.anything(), 1);
    }
  });

  test('sem a capacidade gpu.temp, o aviso fica no lugar do grafico de temperatura', async () => {
    paramsMock.current = { id: 'a1' };
    const hello = fx.clone(fx.hello);
    hello.capabilities = ['cpu', 'ram', 'disk', 'net', 'gpu'];
    setConnection({ kind: 'connected', hello });
    await renderWith(<GpuDetail />);
    expect(screen.getByText('Uso da GPU')).toBeTruthy();
    expect(screen.getByText(/Temperatura indisponível nesta placa/)).toBeTruthy();
    const history = jest.requireMock('../../src/hooks/useMetricHistory').useMetricHistory as jest.Mock;
    expect(history.mock.calls.map((call) => call[1])).not.toContain('gpu.temp');
  });
});

describe('ajustes do PC', () => {
  test('o campo de IP dos ajustes tambem coloca os pontos e aceita IP com porta', async () => {
    await renderWith(<PcSettings />);
    const field = () => screen.getByLabelText('IP do PC');
    expect(field().props.keyboardType).toBe('decimal-pad');
    await fireEvent.changeText(field(), '');
    for (const char of '192168') {
      await fireEvent.changeText(field(), field().props.value + char);
    }
    expect(field().props.value).toBe('192.168.');
    await fireEvent.changeText(field(), '10.0.0.7:9100');
    expect(field().props.value).toBe('10.0.0.7');
    expect(screen.getByLabelText('Porta').props.value).toBe('9100');
  });

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
    expect(stop.mock.invocationCallOrder[0]).toBeLessThan(http.forgetMe.mock.invocationCallOrder[0]!);
    expect(storage.removePc).toHaveBeenCalledWith('a1');
    expect(routerMock.dismissTo).toHaveBeenCalledWith('/');
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
    expect(routerMock.dismissTo).toHaveBeenCalledWith('/');
    expect(routerMock.replace).not.toHaveBeenCalled();
    expect(storage.removePc).not.toHaveBeenCalled();
  });
});


describe('troca de IP do PC (sem parear de novo)', () => {
  test('salva o novo endereco quando o PC confirma que e o mesmo', async () => {
    http.getInfo.mockResolvedValue({ ...fx.clone(fx.info), agent_id: 'a1' });
    await renderWith(<PcSettings />);
    await fireEvent.changeText(screen.getByLabelText('IP do PC'), '192.168.0.55');
    await fireEvent.press(screen.getByText('Salvar endereço'));
    await act(async () => undefined);
    expect(http.getInfo).toHaveBeenCalledWith('http://192.168.0.55:8765');
    expect(storage.updatePc).toHaveBeenCalledWith('a1', { host: '192.168.0.55', port: 8765 });
    expect(screen.getByText('Endereço salvo.')).toBeTruthy();
  });

  test('recusa o endereco de outro PC', async () => {
    http.getInfo.mockResolvedValue({ ...fx.clone(fx.info), agent_id: 'outro' });
    await renderWith(<PcSettings />);
    await fireEvent.changeText(screen.getByLabelText('IP do PC'), '192.168.0.55');
    await fireEvent.press(screen.getByText('Salvar endereço'));
    await act(async () => undefined);
    expect(screen.getByText('Esse endereço é de outro PC.')).toBeTruthy();
    expect(storage.updatePc).not.toHaveBeenCalled();
  });

  test('IP invalido nao consulta a rede', async () => {
    await renderWith(<PcSettings />);
    await fireEvent.changeText(screen.getByLabelText('IP do PC'), '999.1.1.1');
    await fireEvent.press(screen.getByText('Salvar endereço'));
    expect(screen.getByText('Digite o IP do PC, como 192.168.0.10.')).toBeTruthy();
    expect(http.getInfo).not.toHaveBeenCalled();
  });
});

test('o painel recarrega o PC salvo depois de um ajuste (apelido aparece na hora)', async () => {
  await renderWith(<PcSettings />);
  const before = storage.getPc!.mock.calls.length;
  storage.getPc!.mockResolvedValue({ ...PC, alias: 'PC da sala' });
  await fireEvent.changeText(screen.getByLabelText('Apelido'), 'PC da sala');
  await fireEvent.press(screen.getByText('Salvar apelido'));
  await act(async () => undefined);
  expect(storage.getPc!.mock.calls.length).toBe(before + 1);
});


describe('cores de alerta na tela do PC', () => {
  const hot = () => {
    const snap = fx.clone(fx.snapshotMessage);
    snap.data.cpu_total = 10;
    snap.data.ram_percent = 96;
    snap.data.gpus[0].usage_percent = 88;
    snap.data.gpus[0].temp_c = 76;
    snap.data.disks[0]!.percent = 97;
    return snap;
  };

  test('GPU com os dois selos, RAM e disco criticos, CPU normal', async () => {
    setConnection(connected, hot());
    await renderWith(<Panel />);
    expect(screen.getByTestId('badge-Uso alto')).toBeTruthy();
    expect(screen.getByTestId('badge-Temperatura alta')).toBeTruthy();
    expect(screen.getAllByTestId('badge-Uso crítico')).toHaveLength(2); // RAM e disco
    expect(screen.getByText('88%').props.style).toEqual(
      expect.arrayContaining([expect.objectContaining({ color: THEMES.dark.warning })]),
    );
    expect(screen.getByText('10%').props.style).toEqual(
      expect.arrayContaining([expect.objectContaining({ color: THEMES.dark.text })]),
    );
  });

  test('chave desligada: a tela do PC fica sem selos nem cores', async () => {
    storage.getAlertLimits!.mockImplementationOnce(async () => ({
      ...jest.requireActual('../../src/alerts/levels').DEFAULT_LIMITS,
      enabled: false,
    }));
    setConnection(connected, hot());
    await render(
      <ThemeProvider>
        <PcProvider agentId="a1">
          <Panel />
        </PcProvider>
      </ThemeProvider>,
    );
    await waitFor(() => expect(storage.getAlertLimits).toHaveBeenCalled());
    await act(async () => undefined);
    await waitFor(() => expect(screen.queryByTestId(/^badge-/)).toBeNull());
    expect(screen.getByText('88%').props.style).toEqual(
      expect.arrayContaining([expect.objectContaining({ color: THEMES.dark.text })]),
    );
  });
});
