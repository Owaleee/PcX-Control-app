import {
  DEFAULT_LIMITS,
  sanitizeLimits,
  tempBadge,
  tempLevel,
  toDraft,
  usageBadge,
  usageLevel,
  validateDraft,
  worst,
} from '../../src/alerts/levels';

const OFF = { ...DEFAULT_LIMITS, enabled: false };

test.each([
  [79.9, 'normal'],
  [80, 'alto'],
  [94.9, 'alto'],
  [95, 'critico'],
  [100, 'critico'],
  [null, 'normal'],
  [Number.NaN, 'normal'],
])('uso %s -> %s nos limites padrao (80/95%%)', (value, expected) => {
  expect(usageLevel(value, DEFAULT_LIMITS)).toBe(expected);
});

test.each([
  [74, 'normal'],
  [75, 'alto'],
  [84, 'alto'],
  [85, 'critico'],
  [null, 'normal'],
])('temperatura %s -> %s nos limites padrao (75/85 °C)', (value, expected) => {
  expect(tempLevel(value, DEFAULT_LIMITS)).toBe(expected);
});

test('chave desligada: nenhum alerta', () => {
  expect(usageLevel(99, OFF)).toBe('normal');
  expect(tempLevel(99, OFF)).toBe('normal');
});

test('limites escolhidos valem', () => {
  const custom = { ...DEFAULT_LIMITS, tempHigh: 85, tempCritical: 95 };
  expect(tempLevel(84, custom)).toBe('normal');
  expect(tempLevel(90, custom)).toBe('alto');
});

test('o mais grave vence', () => {
  expect(worst('normal', 'alto')).toBe('alto');
  expect(worst('alto', 'critico', 'normal')).toBe('critico');
  expect(worst()).toBe('normal');
});

test('selos de uso e de temperatura, cada um com o proprio nivel', () => {
  expect(usageBadge('normal')).toBeNull();
  expect(usageBadge('alto')).toEqual({ label: 'Uso alto', level: 'alto' });
  expect(usageBadge('critico')).toEqual({ label: 'Uso crítico', level: 'critico' });
  expect(tempBadge('alto')).toEqual({ label: 'Temperatura alta', short: 'Temp. alta', level: 'alto' });
  expect(tempBadge('critico')).toEqual({ label: 'Temperatura crítica', short: 'Temp. crítica', level: 'critico' });
});

describe('validateDraft', () => {
  const ok = toDraft(DEFAULT_LIMITS);

  test('padrao e valido e guarda a chave', () => {
    expect(validateDraft(ok, false)).toEqual({ limits: { ...DEFAULT_LIMITS, enabled: false }, error: null });
  });

  test.each([
    [{ usageHigh: 'oitenta' }, 'números inteiros'],
    [{ usageHigh: '80.5' }, 'números inteiros'],
    [{ usageHigh: '' }, 'números inteiros'],
    [{ usageHigh: '40' }, '50% a 100%'],
    [{ usageCritical: '101' }, '50% a 100%'],
    [{ tempHigh: '45' }, '50 °C a 110 °C'],
    [{ tempCritical: '120' }, '50 °C a 110 °C'],
    [{ usageHigh: '95', usageCritical: '95' }, 'alto precisa ser menor'],
    [{ tempHigh: '90', tempCritical: '80' }, 'alta precisa ser menor'],
  ])('%j recusado com "%s"', (change, message) => {
    const result = validateDraft({ ...ok, ...change }, true);
    expect(result.limits).toBeNull();
    expect(result.error).toContain(message);
  });

  test('aceita espacos em volta', () => {
    expect(validateDraft({ ...ok, usageHigh: ' 70 ' }, true).limits?.usageHigh).toBe(70);
  });
});

describe('sanitizeLimits', () => {
  test('salvo valido volta igual', () => {
    const saved = { enabled: false, usageHigh: 70, usageCritical: 90, tempHigh: 80, tempCritical: 90 };
    expect(sanitizeLimits(saved)).toEqual(saved);
  });

  test('lixo volta ao padrao, mantendo a chave se der', () => {
    expect(sanitizeLimits(null)).toEqual(DEFAULT_LIMITS);
    expect(sanitizeLimits('x')).toEqual(DEFAULT_LIMITS);
    expect(sanitizeLimits({ enabled: false, usageHigh: 99, usageCritical: 10 })).toEqual({
      ...DEFAULT_LIMITS,
      enabled: false,
    });
  });
});
