// PCs pareados e preferencias, no armazenamento seguro do Android (o token nunca sai daqui).
import * as SecureStore from 'expo-secure-store';

import { isThemeName, type ThemeName } from '../theme/names';

export type SavedPc = {
  agentId: string;
  name: string;
  alias?: string;
  host: string;
  port: number;
  deviceId: string;
  token: string;
  addedAt: number;
};

const INDEX_KEY = 'pcx.index';
const THEME_KEY = 'pcx.theme';
const PRECISE_KEY = 'pcx.precise';

/** O secure-store so aceita letras, numeros, ponto, hifen e sublinhado nas chaves. */
function pcKey(agentId: string): string {
  return `pcx.pc.${agentId.replace(/[^\w.-]/g, (c) => `_${c.codePointAt(0)}_`)}`;
}

async function readJson(key: string): Promise<unknown> {
  const raw = await SecureStore.getItemAsync(key);
  if (raw === null) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function readIndex(): Promise<string[]> {
  const value = await readJson(INDEX_KEY);
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [];
}

function isSavedPc(value: unknown): value is SavedPc {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.agentId === 'string' &&
    typeof v.name === 'string' &&
    typeof v.host === 'string' &&
    typeof v.port === 'number' &&
    typeof v.deviceId === 'string' &&
    typeof v.token === 'string' &&
    typeof v.addedAt === 'number'
  );
}

export async function getPc(agentId: string): Promise<SavedPc | null> {
  const value = await readJson(pcKey(agentId));
  return isSavedPc(value) ? value : null;
}

export async function listPcs(): Promise<SavedPc[]> {
  const pcs: SavedPc[] = [];
  for (const id of await readIndex()) {
    const pc = await getPc(id);
    if (pc) pcs.push(pc);
  }
  return pcs;
}

export async function savePc(pc: SavedPc): Promise<void> {
  await SecureStore.setItemAsync(pcKey(pc.agentId), JSON.stringify(pc));
  const index = await readIndex();
  if (!index.includes(pc.agentId)) {
    await SecureStore.setItemAsync(INDEX_KEY, JSON.stringify([...index, pc.agentId]));
  }
}

export async function updatePc(agentId: string, patch: Partial<Omit<SavedPc, 'agentId'>>): Promise<void> {
  const current = await getPc(agentId);
  if (current) await savePc({ ...current, ...patch, agentId });
}

export async function removePc(agentId: string): Promise<void> {
  await SecureStore.deleteItemAsync(pcKey(agentId));
  const index = await readIndex();
  await SecureStore.setItemAsync(INDEX_KEY, JSON.stringify(index.filter((id) => id !== agentId)));
}

export async function getTheme(): Promise<ThemeName> {
  const value = await SecureStore.getItemAsync(THEME_KEY);
  return isThemeName(value) ? value : 'dark';
}

export async function setTheme(name: ThemeName): Promise<void> {
  await SecureStore.setItemAsync(THEME_KEY, name);
}

/** "Numeros precisos": percentuais com uma casa decimal. Desligado por padrao. */
export async function getPrecise(): Promise<boolean> {
  return (await SecureStore.getItemAsync(PRECISE_KEY)) === '1';
}

export async function setPrecise(precise: boolean): Promise<void> {
  await SecureStore.setItemAsync(PRECISE_KEY, precise ? '1' : '0');
}
