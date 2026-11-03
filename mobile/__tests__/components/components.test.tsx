import { act, render, screen } from '@testing-library/react-native';
import { StyleSheet } from 'react-native';

import { FONT_SCALE_CAP, Gauge, subtitleFontSize, valueFontSize } from '../../src/components/Gauge';
import { MetricCard } from '../../src/components/MetricCard';
import { Sparkline, sparklinePath } from '../../src/components/Sparkline';
import { StatusPill, statusLabel } from '../../src/components/StatusPill';
import { CardGrid, WIDE_MIN_WIDTH } from '../../src/components/ui';
import type { ConnState } from '../../src/connection/ConnectionManager';
import * as fx from '../protocol/fixtures';

// Tamanho da tela controlado pelo teste (o padrao e o do ambiente de teste do React Native)
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: jest.fn(() => ({ width: 750, height: 1334, scale: 2, fontScale: 2 })),
}));
const windowSize = jest.requireMock('react-native/Libraries/Utilities/useWindowDimensions').default as jest.Mock;


const pts = (pairs: [number, number][]) => pairs.map(([t, v]) => ({ t, v }));

describe('sparklinePath', () => {
  test('coordenadas exatas', () => {
    expect(sparklinePath(pts([[0, 0], [5, 50], [10, 100]]), 100, 50)).toBe('M0 50 L50 25 L100 0');
  });

  test('o eixo X segue o tempo, nao a ordem dos pontos', () => {
    expect(sparklinePath(pts([[0, 0], [5, 0], [6, 0], [7, 0]]), 70, 10)).toBe('M0 10 L50 10 L60 10 L70 10');
  });

  test('janela fixa: pontos antigos ficam a esquerda do fim', () => {
    expect(sparklinePath(pts([[100, 0], [190, 0]]), 100, 10, 0, 100, 100)).toBe('M10 10 L100 10');
  });

  test('valores fora do intervalo sao limitados', () => {
    expect(sparklinePath(pts([[0, -20], [1, 150]]), 100, 50)).toBe('M0 50 L100 0');
  });

  test('lista vazia e ponto unico', () => {
    expect(sparklinePath([], 100, 50)).toBe('');
    expect(sparklinePath(pts([[3, 50]]), 100, 50)).toBe('M0 25 L100 25');
  });

  test('maximo proprio para taxas', () => {
    expect(sparklinePath(pts([[0, 0], [1, 2048]]), 100, 40, 0, 4096)).toBe('M0 40 L100 20');
  });

  test('intervalo sem largura nao gera NaN', () => {
    expect(sparklinePath(pts([[0, 5], [1, 5]]), 100, 40, 5, 5)).toBe('M0 40 L100 40');
  });
});

test('Sparkline desenha o caminho calculado', async () => {
  const { toJSON } = await render(
    <Sparkline points={pts([[0, 0], [5, 50], [10, 100]])} width={100} height={50} color="#fff" />,
  );
  expect(JSON.stringify(toJSON())).toContain('M0 50 L50 25 L100 0');
});

test('MetricCard mostra titulo, valor e detalhe', async () => {
  await render(<MetricCard title="Memória RAM" value="43,8%" detail="14,0 / 31,9 GiB" percent={43.8} />);
  expect(screen.getByText('Memória RAM')).toBeTruthy();
  expect(screen.getByText('43,8%')).toBeTruthy();
  expect(screen.getByText('14,0 / 31,9 GiB')).toBeTruthy();
  expect(screen.getByRole('progressbar')).toBeTruthy();
});

test('MetricCard esmaece quando os dados sao antigos', async () => {
  const { rerender } = await render(<MetricCard title="CPU" value="13,0%" />);
  expect(StyleSheet.flatten(screen.getByTestId('metric-card').props.style).opacity).toBe(1);
  await rerender(<MetricCard title="CPU" value="13,0%" stale />);
  expect(StyleSheet.flatten(screen.getByTestId('metric-card').props.style).opacity).toBe(0.5);
});

test('MetricCard sem percentual nao mostra barra', async () => {
  await render(<MetricCard title="Rede" value="↓ 4,0 KB/s" />);
  expect(screen.queryByRole('progressbar')).toBeNull();
});

test('Gauge mostra o nome, o que o numero indica e os dados com rotulo', async () => {
  await render(
    <Gauge
      testID="g"
      label="GPU"
      caption="uso"
      subtitle="NVIDIA GeForce RTX 4070 Ti SUPER"
      value="17,9%"
      percent={17.98}
      stats={[{ label: 'Temperatura', value: '49 °C' }]}
    />,
  );
  expect(screen.getByText('GPU')).toBeTruthy();
  expect(screen.getByText(' · uso')).toBeTruthy();
  expect(screen.getByText('17,9%')).toBeTruthy();
  expect(screen.getByText('Temperatura')).toBeTruthy();
  expect(screen.getByText('49 °C')).toBeTruthy();
  // O nome da placa aparece inteiro: a letra diminui, mas nunca vira "..."
  const name = screen.getByTestId('g-subtitle');
  expect(name.props.children).toBe('NVIDIA GeForce RTX 4070 Ti SUPER');
  expect(name.props.adjustsFontSizeToFit).toBeUndefined();
  expect(name.props.ellipsizeMode).toBe('clip');
  // O ambiente de teste usa a fonte do sistema em 200%; o cartao limita a 115%
  expect(StyleSheet.flatten(name.props.style).fontSize).toBe(Math.round(16 * FONT_SCALE_CAP));
});

test('Gauge diminui o numero grande para caber num cartao baixo', async () => {
  await render(<Gauge testID="g" label="GPU" subtitle="RX 7600" value="16%" percent={16} stats={[{ label: 'VRAM', value: '1 GiB' }]} />);
  const box = screen.getByTestId('g');
  const size = () => StyleSheet.flatten(screen.getByTestId('g-value').props.style).fontSize;
  expect(size()).toBe(56); // antes de medir o cartao
  await act(async () => box.props.onLayout({ nativeEvent: { layout: { width: 380, height: 150 } } }));
  expect(size()).toBeLessThan(56);
});

test.each([
  // [altura do cartao, barra, dados, nome] -> o conteudo cabe na altura
  [160, true, true, true],
  // Altura minima em que o cartao da GPU (com nome, barra e dados) cabe inteiro
  [154, true, true, true],
  [150, true, true, false],
  [110, true, false, false],
  [300, true, true, true],
])('valueFontSize: cartao de %ipx com tudo dentro', (height, bar, stats, subtitle) => {
  const size = valueFontSize(height, { bar, stats, subtitle });
  // padding 12+12, titulo 22, nome 20, barra 8, dados 32, espaco de 4 entre cada um
  let used = 24 + 22 + 4 + size * 1.2;
  if (subtitle) used += 20 + 4;
  if (bar) used += 8 + 4;
  if (stats) used += 32 + 4;
  expect(size).toBeGreaterThanOrEqual(20);
  expect(used).toBeLessThanOrEqual(height);
});

const hello = fx.clone(fx.hello);
test.each<[ConnState, string]>([
  [{ kind: 'connecting' }, 'Conectando…'],
  [{ kind: 'connected', hello }, 'Conectado'],
  [{ kind: 'reconnecting', attempt: 2, retryInMs: 2000 }, 'Reconectando…'],
  [{ kind: 'busy', activeDevice: 'Moto G' }, 'Em uso por outro celular'],
  [{ kind: 'taken_over' }, 'Sessão assumida por outro aparelho'],
  [{ kind: 'revoked' }, 'Desconectado no PC'],
  [{ kind: 'stopped' }, 'Desconectado'],
])('StatusPill %#', async (state, text) => {
  expect(statusLabel(state)).toBe(text);
  await render(<StatusPill state={state} />);
  expect(screen.getByText(text)).toBeTruthy();
});

test.each([
  // [largura do cartao, nome, tamanho esperado]
  [380, 'NVIDIA GeForce RTX 3070', 16],
  [380, 'AMD Radeon RX 7600', 16],
  [300, 'NVIDIA GeForce RTX 4070 Ti SUPER', 14],
  [200, 'NVIDIA GeForce RTX 4070 Ti SUPER', 11],
  [0, 'NVIDIA GeForce RTX 3070', 16],
])('subtitleFontSize: cartao de %ipx com "%s" usa %i', (width, name, expected) => {
  const size = subtitleFontSize(width, name);
  expect(size).toBe(expected);
  // Nunca abaixo de 11: legivel no celular
  expect(size).toBeGreaterThanOrEqual(11);
  if (width > 0 && size > 11) expect(name.length * size * 0.6).toBeLessThanOrEqual(width - 24);
});

test('valueFontSize com a fonte do Android aumentada: o cartao da GPU ainda cabe em 160px', () => {
  const scale = FONT_SCALE_CAP;
  const size = valueFontSize(160, { bar: true, stats: true, subtitle: true }, { scale });
  const used = 24 + 22 * scale + 4 + 20 * scale + 4 + 8 + 4 + 32 * scale + 4 + size * 1.2;
  expect(used).toBeLessThanOrEqual(160);
});

test('valueFontSize cresce com o cartao (tablet) e respeita a largura', () => {
  const layout = { bar: true, stats: true, subtitle: true };
  expect(valueFontSize(500, layout)).toBeGreaterThan(100);
  expect(valueFontSize(2000, layout)).toBe(140);
  // "↓ 23,3 KB/s" num cartao de 300px de largura nao passa da largura
  const text = '↓ 23,3 KB/s';
  const size = valueFontSize(500, layout, { width: 300, text });
  expect(text.length * size * 0.6).toBeLessThanOrEqual(300 - 24);
});

describe('CardGrid', () => {
  const dims = (width: number) => windowSize.mockReturnValue({ width, height: 800, scale: 2, fontScale: 1 });
  afterEach(() => windowSize.mockReturnValue({ width: 750, height: 1334, scale: 2, fontScale: 2 }));

  test('em pe (tela estreita) os cartoes ficam um embaixo do outro', async () => {
    dims(400);
    await render(
      <CardGrid>
        <MetricCard title="CPU" value="13%" />
        <MetricCard title="RAM" value="44%" />
      </CardGrid>,
    );
    expect(screen.queryByTestId('card-grid')).toBeNull();
    expect(screen.getAllByTestId('metric-card')).toHaveLength(2);
  });

  test('deitado ou em tablet os cartoes ficam em duas colunas', async () => {
    dims(WIDE_MIN_WIDTH);
    await render(
      <CardGrid>
        <MetricCard title="CPU" value="13%" />
        <MetricCard title="RAM" value="44%" />
        <MetricCard title="Rede" value="↓ 1 KB/s" />
      </CardGrid>,
    );
    const grid = screen.getByTestId('card-grid');
    expect(StyleSheet.flatten(grid.props.style)).toMatchObject({ flexDirection: 'row', flexWrap: 'wrap' });
    expect(screen.getAllByTestId('metric-card')).toHaveLength(3);
  });
});
