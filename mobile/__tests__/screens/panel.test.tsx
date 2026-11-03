import { act, fireEvent, render, screen } from '@testing-library/react-native';
import { StyleSheet } from 'react-native';

import PanelMode from '../../app/pc/[id]/panel';
import { usePc } from '../../src/hooks/PcContext';
import { useTheme } from '../../src/theme/ThemeProvider';
import * as fx from '../protocol/fixtures';
import { resetRouter, routerMock } from './mocks';

jest.mock('expo-router', () => jest.requireActual('./mocks').expoRouterMock());
jest.mock('expo-screen-orientation', () => ({
  lockAsync: jest.fn(async () => undefined),
  unlockAsync: jest.fn(async () => undefined),
  OrientationLock: { LANDSCAPE: 'LANDSCAPE' },
}));
jest.mock('expo-keep-awake', () => ({ useKeepAwake: jest.fn() }));
jest.mock('react-native-safe-area-context', () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 24, left: 48, right: 0 }),
}));
jest.mock('../../src/hooks/PcContext', () => ({ usePc: jest.fn() }));
jest.mock('../../src/theme/ThemeProvider', () => ({
  ...jest.requireActual('../../src/theme/ThemeProvider'),
  useTheme: jest.fn(),
}));

const orientation = jest.requireMock('expo-screen-orientation') as Record<string, jest.Mock>;
const keepAwake = jest.requireMock('expo-keep-awake') as { useKeepAwake: jest.Mock };
const { THEMES } = jest.requireActual('../../src/theme/themes');
const setName = jest.fn();

function setup({ capabilities = fx.hello.capabilities as string[], temp = 49 as number | null } = {}) {
  const snapshot = fx.clone(fx.snapshotMessage);
  snapshot.data.gpus[0].temp_c = temp;
  (usePc as jest.Mock).mockReturnValue({
    pc: { agentId: 'a1', name: 'PC-DEMO' },
    state: { kind: 'connected', hello: fx.clone(fx.hello) },
    snapshot,
    capabilities,
  });
  (useTheme as jest.Mock).mockReturnValue({ theme: THEMES.dark, name: 'dark', setName, precise: false });
}

beforeEach(() => {
  jest.useFakeTimers();
  resetRouter();
  setName.mockClear();
  Object.values(orientation).forEach((fn) => typeof fn === 'function' && fn.mockClear?.());
  setup();
});
afterEach(() => jest.useRealTimers());

test('trava em paisagem, mantem a tela ligada e libera ao sair', async () => {
  const { unmount } = await render(<PanelMode />);
  expect(orientation.lockAsync).toHaveBeenCalledWith('LANDSCAPE');
  expect(keepAwake.useKeepAwake).toHaveBeenCalled();
  await unmount();
  expect(orientation.unlockAsync).toHaveBeenCalled();
});

test('cada cartao diz o que o numero indica', async () => {
  await render(<PanelMode />);
  expect(screen.getByText('CPU')).toBeTruthy();
  expect(screen.getByText(' · uso total')).toBeTruthy();
  expect(screen.getByText('13%')).toBeTruthy();
  expect(screen.getByText('Memória RAM')).toBeTruthy();
  expect(screen.getByText(' · em uso')).toBeTruthy();
  expect(screen.getByText('Usada / total')).toBeTruthy();
  expect(screen.getByText('14,0 / 31,9 GiB')).toBeTruthy();
  expect(screen.getByText('Livre')).toBeTruthy();
  expect(screen.getByText('17,9 GiB')).toBeTruthy();
  expect(screen.getByText('Rede')).toBeTruthy();
  expect(screen.getByText(' · download (recebendo)')).toBeTruthy();
  expect(screen.getByText('↓ 4,0 KB/s')).toBeTruthy();
  expect(screen.getByText('Upload (enviando)')).toBeTruthy();
  expect(screen.getByText('↑ 0,4 KB/s')).toBeTruthy();
});

test('um cartao so de GPU com o nome inteiro da placa, uso, VRAM e temperatura', async () => {
  await render(<PanelMode />);
  expect(screen.getByTestId('gpu-card')).toBeTruthy();
  expect(screen.getByText('GPU')).toBeTruthy();
  expect(screen.getByText(' · uso')).toBeTruthy();
  expect(screen.getByTestId('gpu-card-subtitle').props.children).toBe(fx.snapshotMessage.data.gpus[0].name);
  expect(screen.getByText('18%')).toBeTruthy();
  expect(screen.getByText('VRAM usada')).toBeTruthy();
  expect(screen.getByText('2,5 / 7,8 GiB · 32%')).toBeTruthy();
  expect(screen.getByText('Temperatura')).toBeTruthy();
  expect(screen.getByText('49 °C')).toBeTruthy();
});

test('tocar no cartao da GPU abre o grafico com uso, VRAM e temperatura', async () => {
  await render(<PanelMode />);
  await fireEvent.press(screen.getByTestId('gpu-card'));
  expect(routerMock.push).toHaveBeenCalledWith('/pc/a1/gpu');
  expect(screen.queryByText('Sair')).toBeNull();
});

test('sem a capacidade gpu.temp a temperatura aparece como indisponivel', async () => {
  setup({ capabilities: ['cpu', 'ram', 'disk', 'net', 'gpu'] });
  await render(<PanelMode />);
  expect(screen.getByText('Temperatura')).toBeTruthy();
  expect(screen.getByText('indisponível')).toBeTruthy();
  expect(screen.getByText('2,5 / 7,8 GiB · 32%')).toBeTruthy();
});

test('sem VRAM informada o cartao mostra so o que existe', async () => {
  const snapshot = fx.clone(fx.snapshotMessage);
  snapshot.data.gpus[0].vram_used_bytes = null;
  (usePc as jest.Mock).mockReturnValue({
    pc: { agentId: 'a1', name: 'PC' },
    state: { kind: 'connected', hello: fx.clone(fx.hello) },
    snapshot,
    capabilities: fx.hello.capabilities,
  });
  await render(<PanelMode />);
  expect(screen.queryByText(/VRAM/)).toBeNull();
  expect(screen.getByText('49 °C')).toBeTruthy();
});

test('temperatura nula tambem aparece como indisponivel', async () => {
  setup({ temp: null });
  await render(<PanelMode />);
  expect(screen.getByText('indisponível')).toBeTruthy();
});

test('num celular baixo o numero da GPU diminui para caber no cartao', async () => {
  await render(<PanelMode />);
  const card = screen.getByTestId('gpu-card');
  const size = () => StyleSheet.flatten(screen.getByTestId('gpu-card-value').props.style).fontSize;
  await act(async () => card.props.onLayout({ nativeEvent: { layout: { width: 360, height: 160 } } }));
  // padding, titulo, nome, barra e dados ocupam 122 px; o numero fica com o resto
  expect(size() * 1.2 + 122).toBeLessThanOrEqual(160);
  // O nome da placa continua no tamanho normal
  expect(StyleSheet.flatten(screen.getByTestId('gpu-card-subtitle').props.style).fontSize).toBe(16);
});

test('um toque mostra os controles por 3 s', async () => {
  await render(<PanelMode />);
  expect(screen.queryByText('Sair')).toBeNull();
  await fireEvent.press(screen.getByTestId('panel-touch'));
  expect(screen.getByText('Sair')).toBeTruthy();
  await act(async () => jest.advanceTimersByTime(2999));
  expect(screen.getByText('Sair')).toBeTruthy();
  await act(async () => jest.advanceTimersByTime(1));
  expect(screen.queryByText('Sair')).toBeNull();
});

test('Tema troca para o proximo e Sair volta', async () => {
  await render(<PanelMode />);
  await fireEvent.press(screen.getByTestId('panel-touch'));
  await fireEvent.press(screen.getByText('Tema'));
  expect(setName).toHaveBeenCalledWith('light');
  await fireEvent.press(screen.getByText('Sair'));
  expect(routerMock.back).toHaveBeenCalled();
});

test('Escurecer liga e desliga a sobreposicao', async () => {
  await render(<PanelMode />);
  expect(screen.queryByTestId('dim-overlay')).toBeNull();
  await fireEvent.press(screen.getByTestId('panel-touch'));
  await fireEvent.press(screen.getByText('Escurecer'));
  expect(StyleSheet.flatten(screen.getByTestId('dim-overlay').props.style).opacity).toBe(0.6);
  await fireEvent.press(screen.getByText('Clarear'));
  expect(screen.queryByTestId('dim-overlay')).toBeNull();
});

test('o painel se desloca a cada 3 minutos', async () => {
  await render(<PanelMode />);
  const position = () => JSON.stringify(StyleSheet.flatten(screen.getByTestId('panel-grid').props.style).transform);
  const before = position();
  await act(async () => jest.advanceTimersByTime(179_999));
  expect(position()).toBe(before);
  await act(async () => jest.advanceTimersByTime(1));
  expect(position()).not.toBe(before);
});

test('sem conexao mostra o estado sobre o painel', async () => {
  (usePc as jest.Mock).mockReturnValue({
    pc: { agentId: 'a1', name: 'PC' },
    state: { kind: 'reconnecting', attempt: 1, retryInMs: 1000 },
    snapshot: null,
    capabilities: [],
  });
  await render(<PanelMode />);
  expect(screen.getByText('Reconectando…')).toBeTruthy();
  expect(screen.getByText('Aguardando dados do PC…')).toBeTruthy();
});


test('sem conexao os medidores esmaecem e o aviso anda junto com o painel', async () => {
  (usePc as jest.Mock).mockReturnValue({
    pc: { agentId: 'a1', name: 'PC' },
    state: { kind: 'reconnecting', attempt: 1, retryInMs: 1000 },
    snapshot: fx.clone(fx.snapshotMessage),
    capabilities: fx.hello.capabilities,
  });
  await render(<PanelMode />);
  expect(StyleSheet.flatten(screen.getByTestId('panel-gauges').props.style).opacity).toBe(0.5);
  expect(screen.getByText('Reconectando…')).toBeTruthy();
  // O aviso fica dentro do bloco deslocado (protecao contra burn-in).
  expect(screen.getByTestId('panel-grid')).toContainElement(screen.getByText('Reconectando…'));
});

test('respeita as areas seguras da tela (recorte da camera e barra de navegacao)', async () => {
  await render(<PanelMode />);
  const style = StyleSheet.flatten(screen.getByTestId('panel-grid').props.style);
  expect(style.paddingLeft).toBe(16 + 48);
  expect(style.paddingBottom).toBe(16 + 24);
  await fireEvent.press(screen.getByTestId('panel-touch'));
  expect(StyleSheet.flatten(screen.getByTestId('panel-controls').props.style).bottom).toBe(16 + 24);
});


test('com numeros precisos, uma casa decimal', async () => {
  (useTheme as jest.Mock).mockReturnValue({ theme: THEMES.dark, name: 'dark', setName, precise: true });
  await render(<PanelMode />);
  expect(screen.getByText('13,0%')).toBeTruthy();
  expect(screen.getByText('43,8%')).toBeTruthy();
});
