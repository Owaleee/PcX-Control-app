import { act, fireEvent, render, screen } from '@testing-library/react-native';

import AddPc from '../../app/add';
import * as fx from '../protocol/fixtures';
import { resetRouter, routerMock } from './mocks';

jest.mock('expo-router', () => jest.requireActual('./mocks').expoRouterMock());
jest.mock('expo-device', () => ({ modelName: 'Moto G' }));
jest.mock('expo-camera', () => {
  const camera: { onScan: ((e: { data: string }) => void) | undefined } = { onScan: undefined };
  return {
    __camera: camera,
    useCameraPermissions: () => [{ granted: true }, jest.fn()],
    CameraView: (props: { onBarcodeScanned?: (e: { data: string }) => void }) => {
      camera.onScan = props.onBarcodeScanned;
      return null;
    },
  };
});
jest.mock('../../src/storage/storage', () => ({
  savePc: jest.fn(async () => undefined),
  getPc: jest.fn(async () => null),
  getTheme: jest.fn(async () => 'dark'),
  setTheme: jest.fn(),
}));
jest.mock('../../src/api/http', () => ({ ...jest.requireActual('../../src/api/http'), pair: jest.fn() }));

const http = jest.requireMock('../../src/api/http') as { pair: jest.Mock };
const storage = jest.requireMock('../../src/storage/storage') as { savePc: jest.Mock; getPc: jest.Mock };
const camera = (jest.requireMock('expo-camera') as { __camera: { onScan?: (e: { data: string }) => void } })
  .__camera;

const AGENT = fx.pair.agent.id as string;
const QR = `pcx://pair?v=1&id=${AGENT}&h=192.168.0.10&p=8765&c=CODIGO`;
const apiError = (kind: string, extra = {}) =>
  Object.assign(new Error(kind), { name: 'ApiError', kind, ...extra });

beforeEach(() => {
  resetRouter();
  http.pair.mockReset();
  storage.savePc.mockClear();
  storage.getPc.mockReset();
  storage.getPc.mockResolvedValue(null);
  camera.onScan = undefined;
});

async function openManual() {
  await render(<AddPc />);
  await fireEvent.press(screen.getByText('Digitar IP e senha'));
}

async function fillManual(ip: string, password = 'segredo-123') {
  await fireEvent.changeText(screen.getByLabelText('IP do PC'), ip);
  await fireEvent.changeText(screen.getByLabelText('Senha do PC'), password);
}

test('nome do aparelho vem preenchido com o modelo', async () => {
  await openManual();
  expect(screen.getByLabelText('Nome deste celular').props.value).toBe('Moto G');
  expect(screen.getByLabelText('Porta').props.value).toBe('8765');
});

test('senha errada mostra as tentativas restantes', async () => {
  http.pair.mockRejectedValue(apiError('bad_credentials', { attemptsLeft: 4 }));
  await openManual();
  await fillManual('192.168.0.10');
  await fireEvent.press(screen.getByText('Conectar'));
  expect(await screen.findByText('Senha incorreta. Restam 4 tentativas.')).toBeTruthy();
  expect(storage.savePc).not.toHaveBeenCalled();
});

test('sucesso salva o PC e abre o painel', async () => {
  http.pair.mockResolvedValue(fx.clone(fx.pair));
  await openManual();
  await fillManual('192,168,0,010');
  await fireEvent.press(screen.getByText('Conectar'));
  await act(async () => undefined);
  expect(http.pair).toHaveBeenCalledWith('http://192.168.0.10:8765', {
    device_name: 'Moto G',
    password: 'segredo-123',
  });
  expect(storage.savePc).toHaveBeenCalledWith(
    expect.objectContaining({
      agentId: AGENT,
      host: '192.168.0.10',
      port: 8765,
      token: fx.pair.token,
      deviceId: fx.pair.device_id,
    }),
  );
  expect(routerMock.replace).toHaveBeenCalledWith(`/pc/${AGENT}`);
});

test('dois toques rapidos fazem um unico pedido', async () => {
  let release: (v: unknown) => void = () => undefined;
  http.pair.mockReturnValue(new Promise((resolve) => (release = resolve)));
  await openManual();
  await fillManual('192.168.0.10');
  const button = screen.getByText('Conectar');
  await act(async () => {
    void fireEvent.press(button);
    void fireEvent.press(button); // segundo toque antes da tela atualizar
  });
  expect(http.pair).toHaveBeenCalledTimes(1);
  expect(screen.getByText('Conectando…')).toBeTruthy();
  await act(async () => release(fx.clone(fx.pair)));
});

test('o campo de IP coloca os pontos sozinho e usa o teclado numerico', async () => {
  await openManual();
  const field = screen.getByLabelText('IP do PC');
  expect(field.props.keyboardType).toBe('decimal-pad');
  let typed = '';
  for (const char of '192168') {
    typed = screen.getByLabelText('IP do PC').props.value + char;
    await fireEvent.changeText(screen.getByLabelText('IP do PC'), typed);
  }
  expect(screen.getByLabelText('IP do PC').props.value).toBe('192.168.');
  await fireEvent.changeText(screen.getByLabelText('IP do PC'), '192.168');
  expect(screen.getByLabelText('IP do PC').props.value).toBe('192.168');
});

test('IP invalido mostra erro sem chamar a rede', async () => {
  await openManual();
  await fillManual('192.168.0');
  await fireEvent.press(screen.getByText('Conectar'));
  expect(screen.getByText('Digite o IP do PC, como 192.168.0.10.')).toBeTruthy();
  expect(http.pair).not.toHaveBeenCalled();
});

test('senha vazia mostra erro sem chamar a rede', async () => {
  await openManual();
  await fillManual('192.168.0.10', '');
  await fireEvent.press(screen.getByText('Conectar'));
  expect(screen.getByText('Digite a senha do PC.')).toBeTruthy();
  expect(http.pair).not.toHaveBeenCalled();
});

test('QR de outra coisa e ignorado com aviso', async () => {
  await render(<AddPc />);
  await act(async () => camera.onScan?.({ data: 'WIFI:S:casa;T:WPA;P:x;;' }));
  expect(screen.getByText('Este QR code não é do PcX Control.')).toBeTruthy();
  expect(http.pair).not.toHaveBeenCalled();
});

test('QR do agente pareia com o codigo', async () => {
  http.pair.mockResolvedValue(fx.clone(fx.pair));
  await render(<AddPc />);
  await act(async () => camera.onScan?.({ data: QR }));
  expect(http.pair).toHaveBeenCalledWith('http://192.168.0.10:8765', {
    device_name: 'Moto G',
    code: 'CODIGO',
  });
  expect(routerMock.replace).toHaveBeenCalledWith(`/pc/${AGENT}`);
});

test('QR lido varias vezes seguidas gera um unico pedido', async () => {
  let release: (v: unknown) => void = () => undefined;
  http.pair.mockReturnValue(new Promise((resolve) => (release = resolve)));
  await render(<AddPc />);
  await act(async () => {
    camera.onScan?.({ data: QR });
    camera.onScan?.({ data: QR });
    camera.onScan?.({ data: QR });
  });
  expect(http.pair).toHaveBeenCalledTimes(1);
  await act(async () => release(fx.clone(fx.pair)));
});

test('QR de outro PC (id diferente da resposta) nao e salvo', async () => {
  http.pair.mockResolvedValue({ ...fx.clone(fx.pair), agent: { ...fx.pair.agent, id: 'outro-id' } });
  await render(<AddPc />);
  await act(async () => camera.onScan?.({ data: QR }));
  expect(screen.getByText('O QR code não corresponde a este PC.')).toBeTruthy();
  expect(storage.savePc).not.toHaveBeenCalled();
});


test('QR expirado diante da camera nao vira uma sequencia de pedidos', async () => {
  http.pair.mockRejectedValue(apiError('code_invalid_or_expired'));
  await render(<AddPc />);
  await act(async () => camera.onScan?.({ data: QR }));
  await act(async () => camera.onScan?.({ data: QR }));
  await act(async () => camera.onScan?.({ data: QR }));
  expect(http.pair).toHaveBeenCalledTimes(1);
  expect(screen.getByText('Código expirado. Gere outro no PC.')).toBeTruthy();
  // Um QR novo (outro codigo) volta a ser aceito.
  http.pair.mockResolvedValue(fx.clone(fx.pair));
  await act(async () => camera.onScan?.({ data: QR.replace('CODIGO', 'NOVO') }));
  expect(http.pair).toHaveBeenCalledTimes(2);
});

test('parear de novo o mesmo PC preserva o apelido', async () => {
  storage.getPc.mockResolvedValue({ agentId: AGENT, alias: 'PC da sala' });
  http.pair.mockResolvedValue(fx.clone(fx.pair));
  await render(<AddPc />);
  await act(async () => camera.onScan?.({ data: QR }));
  expect(storage.savePc).toHaveBeenCalledWith(expect.objectContaining({ agentId: AGENT, alias: 'PC da sala' }));
});
