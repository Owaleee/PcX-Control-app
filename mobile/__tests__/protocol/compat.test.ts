import { RELEASES_URL, SUPPORTED_PROTOCOL, checkProtocol, hasCapability, helloProtocol } from '../../src/protocol/compat';
import { parseHello } from '../../src/protocol/validate';
import * as fx from './fixtures';

test('constantes', () => {
  expect(SUPPORTED_PROTOCOL).toBe(1);
  expect(RELEASES_URL).toBe('https://github.com/Owaleee/PcX-Control-app/releases');
});

test.each([
  [1, 'ok'],
  [2, 'app'],
  [0, 'agent'],
])('checkProtocol(%i) = %s', (protocol, expected) => {
  expect(checkProtocol(protocol)).toBe(expected);
});

describe('hasCapability', () => {
  const hello = parseHello(fx.clone(fx.hello));
  test('capacidade presente e ausente', () => {
    expect(hasCapability(hello, 'cpu')).toBe(true);
    expect(hasCapability(hello, 'coisa.nova')).toBe(false);
  });
  test('sem hello nao ha capacidade', () => {
    expect(hasCapability(null, 'cpu')).toBe(false);
  });
});

describe('helloProtocol', () => {
  test('le so type e protocol', () => {
    expect(helloProtocol({ type: 'hello', protocol: 2 })).toBe(2);
    expect(helloProtocol({ type: 'hello', protocol: 0, agent: 7 })).toBe(0);
  });
  test('recusa o que nao e hello com protocolo numerico', () => {
    expect(helloProtocol({ type: 'snapshot', protocol: 2 })).toBeNull();
    expect(helloProtocol({ type: 'hello', protocol: '2' })).toBeNull();
    expect(helloProtocol({ type: 'hello' })).toBeNull();
    expect(helloProtocol(null)).toBeNull();
    expect(helloProtocol([1])).toBeNull();
  });
});
