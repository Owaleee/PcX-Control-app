import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';

import Appearance from '../../app/settings';
import { ThemeProvider } from '../../src/theme/ThemeProvider';

jest.mock('expo-router', () => jest.requireActual('./mocks').expoRouterMock());
jest.mock('../../src/storage/storage', () => ({
  getTheme: jest.fn(async () => 'dark'),
  setTheme: jest.fn(async () => undefined),
}));
const storage = jest.requireMock('../../src/storage/storage') as { setTheme: jest.Mock };

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
