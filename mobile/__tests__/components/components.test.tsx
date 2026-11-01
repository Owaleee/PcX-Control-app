import { render, screen } from '@testing-library/react-native';
import { StyleSheet } from 'react-native';

import { Gauge } from '../../src/components/Gauge';
import { MetricCard } from '../../src/components/MetricCard';
import { Sparkline, sparklinePath } from '../../src/components/Sparkline';
import { StatusPill, statusLabel } from '../../src/components/StatusPill';
import type { ConnState } from '../../src/connection/ConnectionManager';
import * as fx from '../protocol/fixtures';

describe('sparklinePath', () => {
  test('coordenadas exatas', () => {
    expect(sparklinePath([0, 50, 100], 100, 50)).toBe('M0 50 L50 25 L100 0');
  });

  test('valores fora do intervalo sao limitados', () => {
    expect(sparklinePath([-20, 150], 100, 50)).toBe('M0 50 L100 0');
  });

  test('lista vazia e ponto unico', () => {
    expect(sparklinePath([], 100, 50)).toBe('');
    expect(sparklinePath([50], 100, 50)).toBe('M0 25 L100 25');
  });

  test('maximo proprio para taxas', () => {
    expect(sparklinePath([0, 2048], 100, 40, 0, 4096)).toBe('M0 40 L100 20');
  });

  test('intervalo sem largura nao gera NaN', () => {
    expect(sparklinePath([5, 5], 100, 40, 5, 5)).toBe('M0 40 L100 40');
  });

  test('arredonda para no maximo 2 casas', () => {
    expect(sparklinePath([0, 33.333, 100], 100, 30)).toBe('M0 30 L50 20 L100 0');
  });
});

test('Sparkline desenha o caminho calculado', async () => {
  const { toJSON } = await render(<Sparkline values={[0, 50, 100]} width={100} height={50} color="#fff" />);
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

test('Gauge mostra rotulo e valor', async () => {
  await render(<Gauge label="GPU" value="17,9%" percent={17.98} detail="49 °C" />);
  expect(screen.getByText('GPU')).toBeTruthy();
  expect(screen.getByText('17,9%')).toBeTruthy();
  expect(screen.getByText('49 °C')).toBeTruthy();
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
