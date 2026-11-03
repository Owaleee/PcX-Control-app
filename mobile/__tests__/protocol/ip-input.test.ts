import { formatIpInput, portFromAddress } from '../../src/protocol/ip';

/** Simula a digitacao caractere por caractere, como no teclado. */
function type(text: string, start = ''): string {
  let value = start;
  for (const char of text) value = formatIpInput(value + char, value);
  return value;
}

describe('formatIpInput (pontos automaticos)', () => {
  test.each([
    ['192168', '192.168.'],
    ['192', '192.'],
    ['26', '26.'],
    ['0', '0'],
    ['10', '10'],
    ['25', '25'],
  ])('digitando %s fica %s', (typed, expected) => {
    expect(type(typed)).toBe(expected);
  });

  test('separador fecha um bloco curto', () => {
    expect(type('192168.18.22'.replace(/\./g, '.'))).toBe('192.168.18.22');
    expect(type('10.0.1.5')).toBe('10.0.1.5');
  });

  test('virgula e espaco viram ponto', () => {
    expect(type('10,1 2')).toBe('10.1.2');
  });

  test('separador repetido e ignorado', () => {
    expect(type('192..')).toBe('192.');
    expect(type('.')).toBe('');
  });

  test('para no quarto bloco', () => {
    expect(type('192.168.18.229')).toBe('192.168.18.229');
    expect(type('192.168.18.2299.5')).toBe('192.168.18.229');
  });

  test('colar um IP sujo vira um IP limpo', () => {
    expect(formatIpInput(' 192,168,018,22 ', '')).toBe('192.168.18.22');
    expect(formatIpInput('ip: 192.168.0.10', '')).toBe('192.168.0.10');
  });

  test('apagando, o ponto nao volta sozinho', () => {
    expect(formatIpInput('192', '192.')).toBe('192');
    expect(formatIpInput('192.168.0', '192.168.0.')).toBe('192.168.0');
  });

  test('apagar um bloco no meio nao junta os outros', () => {
    expect(formatIpInput('192.168..10', '192.168.0.10')).toBe('192.168..10');
    expect(formatIpInput('192.168.1.10', '192.168..10')).toBe('192.168.1.10');
  });

  test('digitar no meio de um IP completo nao embaralha os blocos', () => {
    expect(formatIpInput('192.1681.0.10', '192.168.0.10')).toBe('192.168.0.10');
    expect(formatIpInput('192.168.0.150', '192.168.0.15')).toBe('192.168.0.150');
    expect(formatIpInput('192.168.0.1x0', '192.168.0.10')).toBe('192.168.0.10');
  });

  test('colar um IP mais curto por cima do atual', () => {
    expect(formatIpInput(' 10,0,0,5 ', '192.168.100.100')).toBe('10.0.0.5');
  });

  test('um bloco nunca passa de 255', () => {
    expect(type('259')).toBe('25');
    expect(type('192.168.18.256')).toBe('192.168.18.25');
  });
});

describe('colar endereco com porta ou URL (achado da bateria de testes)', () => {
  test.each([
    ['192.168.0.10:8765', '192.168.0.10'],
    ['http://192.168.0.10:8765/', '192.168.0.10'],
    ['192.168.18.22:8765', '192.168.18.22'],
    ['  https://10.0.0.5/v1/info ', '10.0.0.5'],
  ])('%s vira %s', (pasted, expected) => {
    expect(formatIpInput(pasted, '')).toBe(expected);
  });

  test('a porta colada junto e reconhecida', () => {
    expect(portFromAddress('192.168.0.10:8765')).toBe('8765');
    expect(portFromAddress('http://192.168.0.10:9000/')).toBe('9000');
    expect(portFromAddress('192.168.0.10')).toBeNull();
  });

  test('colar algo que nao e IPv4 fica como esta, para a validacao avisar', () => {
    expect(formatIpInput('1.2.3.4.5', '')).toBe('1.2.3.4.5');
    expect(formatIpInput('fe80::1', '')).toBe('fe80::1');
  });

  test('zero a esquerda digitado nao desloca os blocos', () => {
    expect(type('192.168.010.5')).toBe('192.168.10.5');
    expect(type('10.0.1.5')).toBe('10.0.1.5');
  });
});
