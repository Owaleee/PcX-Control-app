// Gera os PNGs do app a partir de assets/icon.svg.  Uso: node scripts/render-icons.mjs
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { Resvg } from '@resvg/resvg-js';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const source = readFileSync(join(root, 'assets', 'icon.svg'), 'utf8');
const art = source.match(/<g id="art"[\s\S]*?<\/g>/)[0];
const BACKGROUND = '#0F172A';

function svg({ background, scale = 1, mono = false }) {
  const offset = (1024 * (1 - scale)) / 2;
  let body = art;
  if (mono) body = body.replace(/stroke="#[0-9A-Fa-f]{6}"/g, 'stroke="#FFFFFF"');
  const bg = background ? `<rect width="1024" height="1024" fill="${background}"/>` : '';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">${bg}<g transform="translate(${offset} ${offset}) scale(${scale})">${body}</g></svg>`;
}

function render(name, markup) {
  const png = new Resvg(markup, { fitTo: { mode: 'width', value: 1024 } }).render().asPng();
  writeFileSync(join(root, 'assets', name), png);
  console.log(`gerado assets/${name}`);
}

// Icone completo (lojas e Android antigo).
render('icon.png', svg({ background: BACKGROUND, scale: 0.86 }));
// Icone adaptativo: o Android corta as bordas, entao o desenho fica na area segura central.
render('android-icon-foreground.png', svg({ scale: 0.62 }));
render('android-icon-background.png', svg({ background: BACKGROUND, scale: 0 }).replace(/<g transform[\s\S]*<\/g><\/svg>$/, '</svg>'));
render('android-icon-monochrome.png', svg({ scale: 0.62, mono: true }));
// Splash: desenho sobre fundo transparente (a cor de fundo vem do app.json).
render('splash-icon.png', svg({ scale: 0.8 }));
