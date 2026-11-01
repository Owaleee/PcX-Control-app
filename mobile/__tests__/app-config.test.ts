import appJson from '../app.json';
import pkg from '../package.json';

const expo = appJson.expo as Record<string, any>;
const plugins = expo.plugins as (string | [string, Record<string, any>])[];

function pluginOptions(name: string): Record<string, any> | undefined {
  const entry = plugins.find((p) => (Array.isArray(p) ? p[0] : p) === name);
  return Array.isArray(entry) ? entry[1] : entry ? {} : undefined;
}

test('cleartext HTTP is enabled for the LAN agent', () => {
  expect(pluginOptions('expo-build-properties')?.android?.usesCleartextTraffic).toBe(true);
});

test('camera permission text is in Portuguese and explains the QR code', () => {
  expect(pluginOptions('expo-camera')?.cameraPermission).toBe(
    'O PcX Control usa a câmera só para ler o QR code de pareamento.',
  );
});

test('android package, slug and project identity', () => {
  expect(expo.name).toBe('PcX Control');
  expect(expo.slug).toBe('pcx-control');
  expect(expo.owner).toBe('owaleez');
  expect(expo.android.package).toBe('com.owaleee.pcxcontrol');
  expect(expo.extra.eas.projectId).toBe('647fca70-2a36-40b8-8fe3-ebd6b1e3bf5c');
  expect(expo.orientation).toBe('default');
  expect(expo.userInterfaceStyle).toBe('automatic');
});

test('router entry and scheme', () => {
  expect(pkg.main).toBe('expo-router/entry');
  expect(expo.scheme).toBe('pcxcontrol');
  expect(pluginOptions('expo-router')).toBeDefined();
});
