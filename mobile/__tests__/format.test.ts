import {
  formatAttempts,
  formatBytes,
  formatFree,
  formatPercent,
  formatRate,
  formatTemp,
  formatUptime,
  formatUsage,
} from '../src/format/format';

test.each([
  [13, '13%'],
  [56.29, '56%'],
  [50.5, '51%'],
  [0.4, '0%'],
  [99.6, '100%'],
  [100, '100%'],
])('formatPercent(%p) por padrao e inteiro: %p', (value, text) => {
  expect(formatPercent(value)).toBe(text);
});

test.each([
  [13, '13,0%'],
  [56.29, '56,3%'],
  [50.5, '50,5%'],
  [0, '0,0%'],
])('formatPercent(%p, preciso) = %p', (value, text) => {
  expect(formatPercent(value, { precise: true })).toBe(text);
});

test.each([
  [15017385984, 34266001408, '17,9 GiB livres'],
  [900 * 1024 ** 2, 1024 ** 3, '124,0 MiB livres'],
  [10, 5, '0,0 MiB livres'],
])('formatFree(%p, %p) = %p', (used, total, text) => {
  expect(formatFree(used, total)).toBe(text);
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
  expect(formatPercent(Number.NaN, { precise: true })).toBe('—');
  expect(formatBytes(-1)).toBe('—');
  expect(formatRate(Number.POSITIVE_INFINITY)).toBe('—');
});

test.each([
  [15017385984, 34266001408, '14,0 / 31,9 GiB'],
  [2721603584, 8406433792, '2,5 / 7,8 GiB'],
  [512 * 1024 ** 2, 2 * 1024 ** 3, '0,5 / 2,0 GiB'],
  [100 * 1024 ** 2, 900 * 1024 ** 2, '100,0 / 900,0 MiB'],
])('formatUsage(%p, %p) = %p', (used, total, text) => {
  expect(formatUsage(used, total)).toBe(text);
});
