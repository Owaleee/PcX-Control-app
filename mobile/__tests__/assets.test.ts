import { createHash } from 'crypto';
import { existsSync, readFileSync } from 'fs';
import { join } from 'path';

import appJson from '../app.json';

const ROOT = join(__dirname, '..');
// Hashes dos icones do template do Expo: nenhum deles pode ir para a loja.
const TEMPLATE_HASHES = new Set([
  'cb975bba2216ce10a60e6c0ffe9941a2',
  '2d65569cc0e2afdcea0af9f9902d4173',
  '72e71a9c846c6aa4ae32476641a00e18',
  '1e097dab989759fc0b69440092ca22cd',
  '97dae5a0e62ad8551d8a31897b425e63',
]);

function pngSize(file: string): { width: number; height: number } {
  const data = readFileSync(file);
  expect(data.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a');
  return { width: data.readUInt32BE(16), height: data.readUInt32BE(20) };
}

const expo = appJson.expo as Record<string, any>;
const splash = (expo.plugins as unknown[]).find(
  (p): p is [string, { image: string }] => Array.isArray(p) && p[0] === 'expo-splash-screen',
);

const images: [string, string][] = [
  ['icone', expo.icon],
  ['adaptativo frente', expo.android.adaptiveIcon.foregroundImage],
  ['adaptativo fundo', expo.android.adaptiveIcon.backgroundImage],
  ['monocromatico', expo.android.adaptiveIcon.monochromeImage],
  ['splash', splash?.[1].image ?? ''],
];

test('splash configurado', () => {
  expect(splash).toBeDefined();
});

test.each(images)('%s existe, e PNG 1024x1024 e nao e do template', (_name, path) => {
  const file = join(ROOT, path);
  expect(existsSync(file)).toBe(true);
  expect(pngSize(file)).toEqual({ width: 1024, height: 1024 });
  const hash = createHash('md5').update(readFileSync(file)).digest('hex');
  expect(TEMPLATE_HASHES.has(hash)).toBe(false);
});

test('a fonte do icone esta no repositorio', () => {
  expect(existsSync(join(ROOT, 'assets', 'icon.svg'))).toBe(true);
});
