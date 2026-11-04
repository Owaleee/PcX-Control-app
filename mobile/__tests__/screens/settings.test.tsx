import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';

import Appearance from '../../app/settings';
import { ThemeProvider } from '../../src/theme/ThemeProvider';

jest.mock('expo-router', () => jest.requireActual('./mocks').expoRouterMock());
jest.mock('../../src/storage/storage', () => ({
  getTheme: jest.fn(async () => 'dark'),
  setTheme: jest.fn(async () => undefined),
  getPrecise: jest.fn(async () => false),
  setPrecise: jest.fn(async () => undefined),
  getAlertLimits: jest.fn(async () => jest.requireActual('../../src/alerts/levels').DEFAULT_LIMITS),
  setAlertLimits: jest.fn(async () => undefined),
}));
const storage = jest.requireMock('../../src/storage/storage') as {
  setTheme: jest.Mock;
  setPrecise: jest.Mock;
  getAlertLimits: jest.Mock;
  setAlertLimits: jest.Mock;
};
const { DEFAULT_LIMITS } = jest.requireActual('../../src/alerts/levels');

test('lista os tres temas e salva a escolha', async () => {
  await render(
    <ThemeProvider>
      <Appearance />
    </ThemeProvider>,
  );
  expect(screen.getByText('Escuro')).toBeTruthy();
  expect(screen.getByText('Claro')).toBeTruthy();
  expect(screen.getByText('AMOLED')).toBeTruthy();
  await fireEvent.press(screen.getByText('AMOLED'));
  await waitFor(() => expect(storage.setTheme).toHaveBeenCalledWith('amoled'));
  expect(screen.getByRole('radio', { name: 'AMOLED' }).props.accessibilityState.checked).toBe(true);
});


test('chave de numeros precisos vem desligada e salva ao ligar', async () => {
  await render(
    <ThemeProvider>
      <Appearance />
    </ThemeProvider>,
  );
  expect(screen.getByText('Números')).toBeTruthy();
  const toggle = screen.getByRole('switch', { name: 'Números precisos' });
  expect(toggle.props.value).toBe(false);
  await fireEvent(toggle, 'valueChange', true);
  await waitFor(() => expect(storage.setPrecise).toHaveBeenCalledWith(true));
  expect(screen.getByRole('switch', { name: 'Números precisos' }).props.value).toBe(true);
});


describe('alertas', () => {
  beforeEach(() => {
    storage.setAlertLimits.mockClear();
    storage.getAlertLimits.mockImplementation(async () => DEFAULT_LIMITS);
  });

  const open = async () => {
    await render(
      <ThemeProvider>
        <Appearance />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByText('Alertas')).toBeTruthy());
  };

  test('cores de alerta vem ligadas com os limites padrao', async () => {
    await open();
    expect(screen.getByRole('switch', { name: 'Cores de alerta' }).props.value).toBe(true);
    expect(screen.getByLabelText('Uso alto a partir de (%)').props.value).toBe('80');
    expect(screen.getByLabelText('Uso crítico a partir de (%)').props.value).toBe('95');
    expect(screen.getByLabelText('Temperatura alta a partir de (°C)').props.value).toBe('75');
    expect(screen.getByLabelText('Temperatura crítica a partir de (°C)').props.value).toBe('85');
  });

  test('desligar esconde os limites e guarda os valores para quando religar', async () => {
    storage.getAlertLimits.mockImplementation(async () => ({ ...DEFAULT_LIMITS, tempHigh: 82 }));
    await open();
    await waitFor(() => expect(screen.getByLabelText('Temperatura alta a partir de (°C)').props.value).toBe('82'));
    await fireEvent(screen.getByRole('switch', { name: 'Cores de alerta' }), 'valueChange', false);
    expect(storage.setAlertLimits).toHaveBeenLastCalledWith({ ...DEFAULT_LIMITS, tempHigh: 82, enabled: false });
    expect(screen.queryByLabelText('Temperatura alta a partir de (°C)')).toBeNull();
    await fireEvent(screen.getByRole('switch', { name: 'Cores de alerta' }), 'valueChange', true);
    expect(screen.getByLabelText('Temperatura alta a partir de (°C)').props.value).toBe('82');
  });

  test('valor valido salva na hora', async () => {
    await open();
    await fireEvent.changeText(screen.getByLabelText('Temperatura alta a partir de (°C)'), '80');
    expect(storage.setAlertLimits).toHaveBeenLastCalledWith({ ...DEFAULT_LIMITS, tempHigh: 80 });
    expect(screen.getByLabelText('Temperatura alta a partir de (°C)').props.value).toBe('80');
  });

  test('valor invalido mostra o erro e nao salva', async () => {
    await open();
    await fireEvent.changeText(screen.getByLabelText('Uso alto a partir de (%)'), '99');
    expect(screen.getByText('Uso: o alto precisa ser menor que o crítico.')).toBeTruthy();
    expect(storage.setAlertLimits).not.toHaveBeenCalled();
    // O campo continua com o que foi digitado, para a pessoa corrigir
    expect(screen.getByLabelText('Uso alto a partir de (%)').props.value).toBe('99');
    await fireEvent.changeText(screen.getByLabelText('Uso alto a partir de (%)'), '85');
    expect(screen.queryByText('Uso: o alto precisa ser menor que o crítico.')).toBeNull();
    expect(storage.setAlertLimits).toHaveBeenLastCalledWith({ ...DEFAULT_LIMITS, usageHigh: 85 });
  });

  test('o erro some quando os limites sao ressincronizados', async () => {
    await open();
    await fireEvent.changeText(screen.getByLabelText('Uso alto a partir de (%)'), '8');
    expect(screen.getByText(/Uso: escolha valores/)).toBeTruthy();
    await fireEvent(screen.getByRole('switch', { name: 'Cores de alerta' }), 'valueChange', false);
    await fireEvent(screen.getByRole('switch', { name: 'Cores de alerta' }), 'valueChange', true);
    expect(screen.getByLabelText('Uso alto a partir de (%)').props.value).toBe('80');
    expect(screen.queryByText(/Uso: escolha valores/)).toBeNull();
  });

  test('restaurar padrao volta os quatro limites', async () => {
    storage.getAlertLimits.mockImplementation(async () => ({ ...DEFAULT_LIMITS, usageHigh: 60, tempCritical: 100 }));
    await open();
    await waitFor(() => expect(screen.getByLabelText('Uso alto a partir de (%)').props.value).toBe('60'));
    await fireEvent.press(screen.getByText('Restaurar padrão'));
    expect(storage.setAlertLimits).toHaveBeenLastCalledWith(DEFAULT_LIMITS);
    expect(screen.getByLabelText('Uso alto a partir de (%)').props.value).toBe('80');
    expect(screen.getByLabelText('Temperatura crítica a partir de (°C)').props.value).toBe('85');
  });
});
