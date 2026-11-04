import {
  parseErrorBody,
  parseHello,
  parseHistory,
  parseInfo,
  parsePair,
  parseSnapshotMessage,
} from '../../src/protocol/validate';
import * as fx from './fixtures';

describe('aceita as fixtures do agente', () => {
  test.each([
    ['hello', parseHello, fx.hello],
    ['snapshot', parseSnapshotMessage, fx.snapshotMessage],
    ['info', parseInfo, fx.info],
    ['pair', parsePair, fx.pair],
    ['history', parseHistory, fx.history],
    ['erro senha', parseErrorBody, fx.errorBadCredentials],
    ['erro ocupado', parseErrorBody, fx.errorSessionBusy],
  ])('%s', (_name, parse, fixture) => {
    expect((parse as (raw: unknown) => unknown)(fx.clone(fixture))).not.toBeNull();
  });
});

describe('parseSnapshotMessage', () => {
  test('aceita campos extras de um agente mais novo', () => {
    const msg = fx.clone(fx.snapshotMessage);
    msg.data.fan_rpm = 1200;
    msg.extra = true;
    msg.data.gpus[0].power_w = 120;
    expect(parseSnapshotMessage(msg)?.data.cpu_total).toBe(13);
  });

  test('aceita sem GPU e com temperatura nula', () => {
    const noGpu = fx.clone(fx.snapshotMessage);
    noGpu.data.gpus = [];
    expect(parseSnapshotMessage(noGpu)?.data.gpus).toEqual([]);
    const noTemp = fx.clone(fx.snapshotMessage);
    noTemp.data.gpus[0].temp_c = null;
    noTemp.data.gpus[0].vram_used_bytes = null;
    expect(parseSnapshotMessage(noTemp)?.data.gpus[0]?.temp_c).toBeNull();
  });

  test('temp_warn_c da GPU: ausente, null ou numero aceitos; texto recusado', () => {
    expect(parseSnapshotMessage(fx.snapshotMessage)?.data.gpus[0]?.temp_warn_c).toBe(83);
    const absent = fx.clone(fx.snapshotMessage);
    delete absent.data.gpus[0].temp_warn_c;
    expect(parseSnapshotMessage(absent)?.data.gpus[0]?.temp_warn_c).toBeNull();
    const nul = fx.clone(fx.snapshotMessage);
    nul.data.gpus[0].temp_warn_c = null;
    expect(parseSnapshotMessage(nul)?.data.gpus[0]?.temp_warn_c).toBeNull();
    const text = fx.clone(fx.snapshotMessage);
    text.data.gpus[0].temp_warn_c = '83';
    expect(parseSnapshotMessage(text)).toBeNull();
  });

  test('vendor da GPU (agente 0.5.0) e opcional e nao derruba a leitura', () => {
    expect(parseSnapshotMessage(fx.snapshotMessage)?.data.gpus[0]?.vendor).toBe('nvidia');
    const old = fx.clone(fx.snapshotMessage) as { data: { gpus: Record<string, unknown>[] } };
    delete old.data.gpus[0]!.vendor;
    expect(parseSnapshotMessage(old)?.data.gpus[0]?.vendor).toBeNull();
    const odd = fx.clone(fx.snapshotMessage) as { data: { gpus: Record<string, unknown>[] } };
    odd.data.gpus[0]!.vendor = 42;
    const parsed = parseSnapshotMessage(odd);
    expect(parsed?.data.gpus[0]?.usage_percent).toBe(fx.snapshotMessage.data.gpus[0]!.usage_percent);
    expect(parsed?.data.gpus[0]?.vendor).toBeNull();
  });

  test.each([
    ['cpu acima de 100', (m: any) => (m.data.cpu_total = 101)],
    ['NaN', (m: any) => (m.data.ram_percent = Number.NaN)],
    ['sem data', (m: any) => delete m.data],
    ['tipo errado', (m: any) => (m.type = 'hello')],
    ['seq texto', (m: any) => (m.seq = '1')],
    ['disco sem mount', (m: any) => (m.data.disks[0].mount = '')],
    ['gpu acima de 100', (m: any) => (m.data.gpus[0].usage_percent = 150)],
    ['taxa negativa', (m: any) => (m.data.net_down_bps = -1)],
  ])('recusa: %s', (_name, mutate) => {
    const msg = fx.clone(fx.snapshotMessage);
    mutate(msg);
    expect(parseSnapshotMessage(msg)).toBeNull();
  });

  test.each([null, undefined, 'texto', 42, []])('recusa %p', (raw) => {
    expect(parseSnapshotMessage(raw)).toBeNull();
  });
});

test('parseHello exige protocolo 1 e lista de capacidades', () => {
  const ok = parseHello(fx.clone(fx.hello));
  expect(ok?.capabilities).toContain('gpu.temp');
  expect(parseHello({ ...fx.clone(fx.hello), protocol: 2 })).toBeNull();
  expect(parseHello({ ...fx.clone(fx.hello), capabilities: 'cpu' })).toBeNull();
});

test('parsePair exige token e id do agente', () => {
  expect(parsePair({ ...fx.clone(fx.pair), token: '' })).toBeNull();
  const noAgent = fx.clone(fx.pair);
  delete noAgent.agent.id;
  expect(parsePair(noAgent)).toBeNull();
});

test('parseErrorBody le os campos extras', () => {
  expect(parseErrorBody(fx.clone(fx.errorBadCredentials))?.attempts_left).toBe(4);
  expect(parseErrorBody(fx.clone(fx.errorSessionBusy))?.active_device).toBe('Moto G');
  expect(parseErrorBody({ message: 'sem code' })).toBeNull();
});

test('parseHistory recusa pontos invalidos', () => {
  const bad = fx.clone(fx.history);
  bad.points[0].avg = 'x';
  expect(parseHistory(bad)).toBeNull();
  expect(parseHistory({ ...fx.clone(fx.history), range: '2h' })).toBeNull();
});
