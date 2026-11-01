// Uma conexao por PC, compartilhada pelas telas (painel, detalhe, modo painel).
// Abrir uma conexao por tela faria o mesmo celular disputar a propria sessao.
import { router } from 'expo-router';
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
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
  takeover: () => void;
  reconnect: () => void;
};

const PcContext = createContext<PcContextValue | null>(null);

export function usePc(): PcContextValue {
  const value = useContext(PcContext);
  if (!value) throw new Error('usePc fora de PcProvider');
  return value;
}

export function PcProvider({ agentId, children }: { agentId: string; children: ReactNode }) {
  const [pc, setPc] = useState<SavedPc | null | undefined>(undefined);
  const { state, snapshot, takeover, reconnect } = usePcConnection(pc ?? null);
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const handled = useRef<ConnState['kind'] | null>(null);

  useEffect(() => {
    let active = true;
    getPc(agentId)
      .then((found) => active && setPc(found))
      .catch(() => active && setPc(null));
    return () => {
      active = false;
    };
  }, [agentId]);

  // Guarda as capacidades do ultimo hello (o modo painel usa mesmo durante uma reconexao).
  if (state.kind === 'connected' && state.hello.capabilities !== capabilities) {
    setCapabilities(state.hello.capabilities);
  }

  useEffect(() => {
    if (!pc) return;
    if (state.kind === 'revoked') {
      if (handled.current === 'revoked') return;
      handled.current = 'revoked';
      void removePc(pc.agentId).finally(() => {
        Alert.alert('Desconectado', 'Este celular foi desconectado no PC. Pareie de novo.');
        router.replace('/');
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
        <Button title="Voltar" onPress={() => router.replace('/')} />
      </Screen>
    );
  }
  return (
    <PcContext.Provider value={{ pc, state, snapshot, capabilities, takeover, reconnect }}>
      {children}
    </PcContext.Provider>
  );
}
