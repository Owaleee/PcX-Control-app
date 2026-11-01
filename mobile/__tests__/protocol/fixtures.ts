// Contrato compartilhado: gerado pelo agente (agent/tools/write_fixtures.py).
export const snapshotMessage = require('../../../docs/protocol/fixtures/snapshot_message.json');
export const hello = require('../../../docs/protocol/fixtures/hello.json');
export const info = require('../../../docs/protocol/fixtures/info.json');
export const pair = require('../../../docs/protocol/fixtures/pair.json');
export const history = require('../../../docs/protocol/fixtures/history.json');
export const metrics = require('../../../docs/protocol/fixtures/metrics.json');
export const errorBadCredentials = require('../../../docs/protocol/fixtures/error_bad_credentials.json');
export const errorSessionBusy = require('../../../docs/protocol/fixtures/error_session_busy.json');

export function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value));
}
