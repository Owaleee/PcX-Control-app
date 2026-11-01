// Uma conexao por PC, compartilhada pelas telas (painel, detalhe, modo painel).
// Abrir uma conexao por tela faria o mesmo celular disputar a propria sessao.
import { router } from 'expo-router';
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { Alert } from 'react-native';

import { Body, Button, Screen, Title } from '../components/ui';
import type { ConnState } from '../connection/ConnectionManager';
import type { SnapshotMessage } from '../protocol/types';
import { getPc, removePc, type SavedPc } from '../storage/storage';
import { usePcConnection } from './usePcConnection';

type PcContextValue = {
  pc: SavedPc;
  state: ConnState;
  snapshot: SnapshotMessage | null;
  capabilities: string[];
  /** Muda a cada hello: telas que buscam dados (historico) refazem a busca. */
  session: number;
  takeover: () => void;
  reconnect: () => void;
  stop: () => void;
  /** Rele o PC salvo (depois de mudar apelido ou endereco). */
  refresh: () => void;
};

const PcContext = createContext<PcContextValue | null>(null);

export function usePc(): PcContextValue {
  const value = useContext(PcContext);
  if (!value) throw new Error('usePc fora de PcProvider');
  return value;
}

export function PcProvider({ agentId, children }: { agentId: string; children: ReactNode }) {
  const [pc, setPc] = useState<SavedPc | null | undefined>(undefined);
  const { state, snapshot, takeover, reconnect, stop } = usePcConnection(pc ?? null);
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const [session, setSession] = useState(0);
  const [lastHello, setLastHello] = useState<unknown>(null);
  const [reload, setReload] = useState(0);
  const handled = useRef<ConnState['kind'] | null>(null);

  useEffect(() => {
    let active = true;
    getPc(agentId)
      .then((found) => active && setPc(found))
      .catch(() => active && setPc(null));
    return () => {
      active = false;
    };
  }, [agentId, reload]);

  const refresh = useCallback(() => setReload((n) => n + 1), []);

  // Cada hello novo e uma sessao nova; guarda tambem as capacidades (o modo painel as usa
  // durante uma reconexao).
  if (state.kind === 'connected' && state.hello !== lastHello) {
    setLastHello(state.hello);
    setSession((n) => n + 1);
    setCapabilities(state.hello.capabilities);
  }

  useEffect(() => {
    if (!pc) return;
    if (state.kind === 'revoked') {
      if (handled.current === 'revoked') return;
      handled.current = 'revoked';
      removePc(pc.agentId)
        .catch(() => undefined)
        .finally(() => {
          Alert.alert('Desconectado', 'Este celular foi desconectado no PC. Pareie de novo.');
          router.dismissTo('/');
        });
    } else if (state.kind === 'busy') {
      if (handled.current === 'busy') return;
      handled.current = 'busy';
      Alert.alert('PC em uso', `PC em uso por ${state.activeDevice}. Assumir a sessão?`, [
        { text: 'Cancelar', style: 'cancel', onPress: () => router.back() },
        { text: 'Assumir', onPress: takeover },
      ]);
    } else {
      handled.current = null;
    }
  }, [pc, state, takeover]);

  if (pc === undefined) {
    return (
      <Screen>
        <Body>Carregando…</Body>
      </Screen>
    );
  }
  if (pc === null) {
    return (
      <Screen>
        <Title>PC não encontrado.</Title>
        <Body>Ele pode ter sido removido deste celular.</Body>
        <Button title="Voltar" onPress={() => router.dismissTo('/')} />
      </Screen>
    );
  }
  return (
    <PcContext.Provider value={{ pc, state, snapshot, capabilities, session, takeover, reconnect, stop, refresh }}>
      {children}
    </PcContext.Provider>
  );
}
