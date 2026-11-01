import {
  getPc,
  getTheme,
  listPcs,
  removePc,
  savePc,
  setTheme,
  updatePc,
  type SavedPc,
} from '../src/storage/storage';
import { THEME_NAMES } from '../src/theme/names';

jest.mock('expo-secure-store', () => {
  const store = new Map<string, string>();
  return {
    __store: store,
    getItemAsync: jest.fn(async (key: string) => store.get(key) ?? null),
    setItemAsync: jest.fn(async (key: string, value: string) => {
      if (!/^[\w.-]+$/.test(key)) throw new Error(`chave invalida: ${key}`);
      store.set(key, value);
    }),
    deleteItemAsync: jest.fn(async (key: string) => {
      store.delete(key);
    }),
  };
});

const secure = jest.requireMock('expo-secure-store') as { __store: Map<string, string> };

function pc(agentId: string, extra: Partial<SavedPc> = {}): SavedPc {
  return {
    agentId,
    name: `PC ${agentId}`,
    host: '192.168.0.10',
    port: 8765,
    deviceId: `dev-${agentId}`,
    token: `tok-${agentId}`,
    addedAt: 1000,
    ...extra,
  };
}

beforeEach(() => secure.__store.clear());

test('salvar e listar na ordem de inclusao', async () => {
  await savePc(pc('a'));
  await savePc(pc('b'));
  expect((await listPcs()).map((p) => p.agentId)).toEqual(['a', 'b']);
  expect(await getPc('b')).toEqual(pc('b'));
});

test('salvar o mesmo PC substitui sem duplicar', async () => {
  await savePc(pc('a'));
  await savePc(pc('a', { token: 'novo', host: '10.0.0.2' }));
  const all = await listPcs();
  expect(all).toHaveLength(1);
  expect(all[0]?.token).toBe('novo');
});

test('atualizar o apelido', async () => {
  await savePc(pc('a'));
  await updatePc('a', { alias: 'PC da sala' });
  expect((await getPc('a'))?.alias).toBe('PC da sala');
  await expect(updatePc('inexistente', { alias: 'x' })).resolves.toBeUndefined();
});

test('remover tira da lista e apaga o token', async () => {
  await savePc(pc('a'));
  await savePc(pc('b'));
  await removePc('a');
  expect((await listPcs()).map((p) => p.agentId)).toEqual(['b']);
  expect([...secure.__store.values()].join()).not.toContain('tok-a');
});

test('tema padrao e escuro e persiste', async () => {
  expect(await getTheme()).toBe('dark');
  await setTheme('amoled');
  expect(await getTheme()).toBe('amoled');
  expect(THEME_NAMES).toEqual(['dark', 'light', 'amoled']);
});

test('tema invalido salvo volta ao escuro', async () => {
  secure.__store.set('pcx.theme', 'roxo');
  expect(await getTheme()).toBe('dark');
});

test('entrada corrompida e ignorada sem quebrar', async () => {
  await savePc(pc('a'));
  secure.__store.set('pcx.index', JSON.stringify(['a', 'quebrado', 'sumiu']));
  secure.__store.set('pcx.pc.quebrado', '{nao e json');
  expect((await listPcs()).map((p) => p.agentId)).toEqual(['a']);
  secure.__store.set('pcx.index', 'lixo');
  expect(await listPcs()).toEqual([]);
});

test('agentId com caracteres estranhos nao gera chave invalida', async () => {
  await savePc(pc('id com espaço/barra'));
  expect((await listPcs())[0]?.agentId).toBe('id com espaço/barra');
});
