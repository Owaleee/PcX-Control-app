import { StyleSheet, Text, View } from 'react-native';

import type { ConnState } from '../connection/ConnectionManager';
import { useTheme } from '../theme/ThemeProvider';

const LABELS: Record<ConnState['kind'], string> = {
  connecting: 'Conectando…',
  connected: 'Conectado',
  reconnecting: 'Reconectando…',
  busy: 'Em uso por outro celular',
  taken_over: 'Sessão assumida por outro aparelho',
  revoked: 'Desconectado no PC',
  stopped: 'Desconectado',
};

export function statusLabel(state: ConnState): string {
  return LABELS[state.kind];
}

export function StatusPill({ state }: { state: ConnState }) {
  const { theme } = useTheme();
  const color =
    state.kind === 'connected' ? theme.accent : state.kind === 'revoked' ? theme.danger : theme.textMuted;
  return (
    <View
      style={[styles.pill, { borderColor: theme.border }]}
      accessibilityRole="text"
      accessibilityLiveRegion="polite"
    >
      <View style={[styles.dot, { backgroundColor: color }]} />
      <Text style={[styles.text, { color: theme.text }]}>{statusLabel(state)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 8,
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  dot: { width: 10, height: 10, borderRadius: 5 },
  text: { fontSize: 14, fontWeight: '600' },
});
