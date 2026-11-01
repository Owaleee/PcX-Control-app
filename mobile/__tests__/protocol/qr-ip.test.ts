import { normalizeIpv4 } from '../../src/protocol/ip';
import { parsePairingUri } from '../../src/protocol/qr';

const ID = '8e3c523e-8ee9-4e80-b25f-411510ac887f';
const VALID = `pcx://pair?v=1&id=${ID}&h=192.168.0.10&p=8765&c=MnCHP7Ky8pv1RI7XrybKIw`;

describe('parsePairingUri', () => {
  test('aceita a URI do agente', () => {
    expect(parsePairingUri(VALID)).toEqual({
      agentId: ID,
      host: '192.168.0.10',
      port: 8765,
      code: 'MnCHP7Ky8pv1RI7XrybKIw',
    });
  });

  test('decodifica caracteres escapados do codigo', () => {
    expect(parsePairingUri(VALID.replace(/c=.*$/, 'c=a-b_c%2Bd%2Fe%3D'))?.code).toBe('a-b_c+d/e=');
  });

  test.each([
    ['link comum', 'https://github.com/Owaleee'],
    ['Wi-Fi', 'WIFI:S:casa;T:WPA;P:senha;;'],
    ['texto', 'ola'],
    ['versao 2', VALID.replace('v=1', 'v=2')],
    ['porta 0', VALID.replace('p=8765', 'p=0')],
    ['porta enorme', VALID.replace('p=8765', 'p=70000')],
    ['IP invalido', VALID.replace('192.168.0.10', '300.1.1.1')],
    ['sem codigo', VALID.replace(/&c=.*$/, '')],
    ['sem id', VALID.replace(`id=${ID}&`, '')],
    ['outro caminho', VALID.replace('pcx://pair', 'pcx://outra')],
  ])('recusa %s', (_name, text) => {
    expect(parsePairingUri(text)).toBeNull();
  });
});

describe('normalizeIpv4', () => {
  test.each([
    ['192,168,0,10', '192.168.0.10'],
    ['192.168.001.010', '192.168.1.10'],
    [' 10.0.0.5 ', '10.0.0.5'],
    ['0.0.0.0', '0.0.0.0'],
  ])('%p vira %p', (input, expected) => {
    expect(normalizeIpv4(input)).toBe(expected);
  });

  test.each(['1.2.3', '1.2.3.256', '1.2.3.4.5', 'a.b.c.d', '', '1..2.3', '-1.2.3.4', '1.2.3.4:8765'])(
    'recusa %p',
    (input) => {
      expect(normalizeIpv4(input)).toBeNull();
    },
  );
});
