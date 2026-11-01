import { act, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { Pressable, Text } from 'react-native';

import { ThemeProvider, useTheme } from '../../src/theme/ThemeProvider';
import { pixelShiftOffset } from '../../src/theme/pixelShift';
import { THEMES, contrastRatio, nextTheme } from '../../src/theme/themes';
import { THEME_NAMES } from '../../src/theme/names';

jest.mock('../../src/storage/storage', () => ({
  getTheme: jest.fn(async () => 'light'),
  setTheme: jest.fn(async () => undefined),
}));
const storage = jest.requireMock('../../src/storage/storage') as {
  getTheme: jest.Mock;
  setTheme: jest.Mock;
};

test('AMOLED usa fundo preto puro', () => {
  expect(THEMES.amoled.background).toBe('#000000');
});

test.each(THEME_NAMES)('tema %s tem contraste de leitura', (name) => {
  const t = THEMES[name];
  expect(contrastRatio(t.text, t.background)).toBeGreaterThanOrEqual(4.5);
  expect(contrastRatio(t.text, t.surface)).toBeGreaterThanOrEqual(4.5);
  expect(contrastRatio(t.textMuted, t.surface)).toBeGreaterThanOrEqual(4.5);
  expect(contrastRatio(t.accent, t.surface)).toBeGreaterThanOrEqual(3);
  expect(contrastRatio(t.danger, t.surface)).toBeGreaterThanOrEqual(4.5);
});

test('contrastRatio conhece os extremos', () => {
  expect(contrastRatio('#000000', '#FFFFFF')).toBeCloseTo(21, 1);
  expect(contrastRatio('#777777', '#777777')).toBeCloseTo(1, 5);
});

test('nextTheme cicla escuro, claro, AMOLED', () => {
  expect(nextTheme('dark')).toBe('light');
  expect(nextTheme('light')).toBe('amoled');
  expect(nextTheme('amoled')).toBe('dark');
});

function Probe() {
  const { name, theme, setName } = useTheme();
  return (
    <Pressable onPress={() => setName('amoled')}>
      <Text>{`${name}:${theme.background}`}</Text>
    </Pressable>
  );
}

test('ThemeProvider carrega o tema salvo e persiste a troca', async () => {
  render(
    <ThemeProvider>
      <Probe />
    </ThemeProvider>,
  );
  await waitFor(() => expect(screen.getByText(`light:${THEMES.light.background}`)).toBeTruthy());
  await act(async () => {
    fireEvent.press(screen.getByText(/light/));
  });
  expect(screen.getByText(`amoled:${THEMES.amoled.background}`)).toBeTruthy();
  expect(storage.setTheme).toHaveBeenCalledWith('amoled');
});

describe('pixelShiftOffset', () => {
  test('fica dentro de +-4 px', () => {
    for (let step = 0; step < 32; step += 1) {
      const { x, y } = pixelShiftOffset(step);
      expect(Math.abs(x)).toBeLessThanOrEqual(4);
      expect(Math.abs(y)).toBeLessThanOrEqual(4);
    }
  });

  test('passos seguidos mudam de posicao e o ciclo tem 8 passos', () => {
    for (let step = 0; step < 8; step += 1) {
      expect(pixelShiftOffset(step)).not.toEqual(pixelShiftOffset(step + 1));
    }
    expect(pixelShiftOffset(8)).toEqual(pixelShiftOffset(0));
    expect(pixelShiftOffset(-1)).toEqual(pixelShiftOffset(7));
  });

  test('respeita o limite pedido', () => {
    expect(Math.max(...Array.from({ length: 8 }, (_, s) => Math.abs(pixelShiftOffset(s, 2).x)))).toBe(2);
  });
});
