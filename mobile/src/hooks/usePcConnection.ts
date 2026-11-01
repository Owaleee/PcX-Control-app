import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState } from 'react-native';

import { ConnectionManager, type ConnState } from '../connection/ConnectionManager';
import type { SnapshotMessage } from '../protocol/types';
import type { SavedPc } from '../storage/storage';

/** Estados em que o app nao reconecta sozinho ao voltar do segundo plano. */
const FINAL: ReadonlySet<ConnState['kind']> = new Set(['revoked', 'taken_over', 'busy']);

export function usePcConnection(pc: SavedPc | null) {
  const [state, setState] = useState<ConnState>({ kind: 'stopped' });
  const [snapshot, setSnapshot] = useState<SnapshotMessage | null>(null);
  const managerRef = useRef<ConnectionManager | null>(null);
  const pausedRef = useRef(false);
  const stoppedRef = useRef(false); // parado de proposito: nao volta sozinho

  const host = pc?.host;
  const port = pc?.port;
  const token = pc?.token;

  useEffect(() => {
    if (!host || !port || !token) return undefined;
    const manager = new ConnectionManager({ url: `ws://${host}:${port}/v1/stream`, token });
    stoppedRef.current = false;
    managerRef.current = manager;
    const offState = manager.onState(setState);
    const offSnapshot = manager.onSnapshot(setSnapshot);
    manager.start();

    const subscription = AppState.addEventListener('change', (next) => {
      if (next === 'background') {
        if (!stoppedRef.current && !FINAL.has(manager.state.kind)) {
          pausedRef.current = true;
          manager.stop();
        }
      } else if (next === 'active' && pausedRef.current) {
        pausedRef.current = false;
        manager.start();
      }
    });

    return () => {
      subscription.remove();
      offState();
      offSnapshot();
      manager.stop();
      managerRef.current = null;
    };
  }, [host, port, token]);

  const takeover = useCallback(() => {
    stoppedRef.current = false;
    managerRef.current?.start({ takeover: true });
  }, []);
  /** Para de vez (ex.: antes de esquecer o PC); nao volta sozinho do segundo plano. */
  const stop = useCallback(() => {
    stoppedRef.current = true;
    pausedRef.current = false;
    managerRef.current?.stop();
  }, []);
  const reconnect = useCallback(() => {
    stoppedRef.current = false;
    managerRef.current?.start();
  }, []);

  return { state, snapshot, takeover, reconnect, stop };
}
