import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';

import Home from '../../app/index';
import type { SavedPc } from '../../src/storage/storage';
import * as fx from '../protocol/fixtures';
import { resetRouter, routerMock } from './mocks';

jest.mock('expo-router', () => jest.requireActual('./mocks').expoRouterMock());
jest.mock('../../src/storage/storage', () => ({
  listPcs: jest.fn(),
  getTheme: jest.fn(async () => 'dark'),
  setTheme: jest.fn(),
}));
jest.mock('../../src/api/http', () => ({ ...jest.requireActual('../../src/api/http'), getInfo: jest.fn() }));

const storage = jest.requireMock('../../src/storage/storage') as { listPcs: jest.Mock };
const http = jest.requireMock('../../src/api/http') as { getInfo: jest.Mock };

const pc = (agentId: string, host: string, extra: Partial<SavedPc> = {}): SavedPc => ({
  agentId,
  name: `PC ${agentId}`,
  host,
  port: 8765,
  deviceId: 'd',
  token: 't',
  addedAt: 0,
  ...extra,
});

beforeEach(() => {
  resetRouter();
  http.getInfo.mockReset();
});

test('lista vazia mostra boas-vindas e o botao de adicionar', async () => {
  storage.listPcs.mockResolvedValue([]);
  await render(<Home />);
  expect(await screen.findByText('Nenhum PC pareado ainda.')).toBeTruthy();
  await fireEvent.press(screen.getAllByText('Adicionar PC')[0]!);
  expect(routerMock.push).toHaveBeenCalledWith('/add');
});

test('mostra os PCs salvos com o estado de cada um', async () => {
  storage.listPcs.mockResolvedValue([
    pc('a', '192.168.0.10', { alias: 'PC da sala' }),
    pc('b', '192.168.0.11'),
    pc('c', '192.168.0.12'),
  ]);
  http.getInfo.mockImplementation(async (base: string) => {
    if (base.endsWith('.10:8765')) return { ...fx.clone(fx.info), busy: false };
    if (base.endsWith('.11:8765')) return { ...fx.clone(fx.info), busy: true };
    throw Object.assign(new Error('network'), { name: 'ApiError', kind: 'network' });
  });
  await render(<Home />);
  expect(await screen.findByText('PC da sala')).toBeTruthy();
  expect(screen.getByText('PC b')).toBeTruthy();
  await waitFor(() => expect(screen.getByText('Online')).toBeTruthy());
  expect(screen.getByText('Em uso')).toBeTruthy();
  expect(screen.getByText('Offline')).toBeTruthy();
});

test('tocar no PC abre o painel', async () => {
  storage.listPcs.mockResolvedValue([pc('abc', '192.168.0.10')]);
  http.getInfo.mockResolvedValue(fx.clone(fx.info));
  await render(<Home />);
  await fireEvent.press(await screen.findByText('PC abc'));
  expect(routerMock.push).toHaveBeenCalledWith('/pc/abc');
});


test('botao Configuracoes abre a tela de configuracoes', async () => {
  storage.listPcs.mockResolvedValue([]);
  await render(<Home />);
  await fireEvent.press(await screen.findByText('Configurações'));
  expect(routerMock.push).toHaveBeenCalledWith('/settings');
});
