import {
  formatAttempts,
  formatBytes,
  formatPercent,
  formatRate,
  formatTemp,
  formatUptime,
} from '../src/format/format';

test.each([
  [13, '13,0%'],
  [56.29, '56,3%'],
  [0, '0,0%'],
  [100, '100,0%'],
])('formatPercent(%p) = %p', (value, text) => {
  expect(formatPercent(value)).toBe(text);
});

test.each([
  [34266001408, '31,9 GiB'],
  [512 * 1024 ** 2, '512,0 MiB'],
  [8406433792, '7,8 GiB'],
  [1024 ** 4 * 2, '2,0 TiB'],
  [0, '0,0 MiB'],
])('formatBytes(%p) = %p', (value, text) => {
  expect(formatBytes(value)).toBe(text);
});

test.each([
  [0, '0,0 KB/s'],
  [4099.7, '4,0 KB/s'],
  [12_582_912, '12,0 MB/s'],
  [3 * 1024 ** 3, '3,0 GB/s'],
  [1023 * 1024, '1023,0 KB/s'],
])('formatRate(%p) = %p', (value, text) => {
  expect(formatRate(value)).toBe(text);
});

test.each([
  [49, '49 °C'],
  [61.6, '62 °C'],
])('formatTemp(%p) = %p', (value, text) => {
  expect(formatTemp(value)).toBe(text);
});

test.each([
  [29186, '8 h 6 min'],
  [59, '0 min'],
  [3 * 86400 + 3600, '3 d 1 h'],
])('formatUptime(%p) = %p', (value, text) => {
  expect(formatUptime(value)).toBe(text);
});

test.each([
  [1, 'Resta 1 tentativa.'],
  [3, 'Restam 3 tentativas.'],
  [0, 'Nenhuma tentativa restante.'],
])('formatAttempts(%p) = %p', (value, text) => {
  expect(formatAttempts(value)).toBe(text);
});

test('valores invalidos nao quebram a tela', () => {
  expect(formatPercent(Number.NaN)).toBe('—');
  expect(formatBytes(-1)).toBe('—');
  expect(formatRate(Number.POSITIVE_INFINITY)).toBe('—');
});
