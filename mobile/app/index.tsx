import { Stack, router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { baseUrl, getInfo } from '../src/api/http';
import { Body, Button, Screen, Title } from '../src/components/ui';
import { listPcs, type SavedPc } from '../src/storage/storage';
import { useTheme } from '../src/theme/ThemeProvider';

type Availability = 'checking' | 'online' | 'busy' | 'offline';
const LABEL: Record<Availability, string> = {
  checking: 'Verificando…',
  online: 'Online',
  busy: 'Em uso',
  offline: 'Offline',
};
const POLL_MS = 10_000;

export default function Home() {
  const { theme } = useTheme();
  const [pcs, setPcs] = useState<SavedPc[] | null>(null);
  const [status, setStatus] = useState<Record<string, Availability>>({});

  useFocusEffect(
    useCallback(() => {
      let active = true;
      let timer: ReturnType<typeof setTimeout> | undefined;

      const check = async (list: SavedPc[]) => {
        const results = await Promise.all(
          list.map(async (pc): Promise<[string, Availability]> => {
            try {
              const info = await getInfo(baseUrl(pc.host, pc.port), 3000);
              return [pc.agentId, info.busy ? 'busy' : 'online'];
            } catch {
              return [pc.agentId, 'offline'];
            }
          }),
        );
        if (!active) return;
        setStatus(Object.fromEntries(results));
        timer = setTimeout(() => void check(list), POLL_MS);
      };

      listPcs()
        .then((list) => {
          if (!active) return;
          setPcs(list);
          void check(list);
        })
        .catch(() => active && setPcs([]));

      return () => {
        active = false;
        if (timer) clearTimeout(timer);
      };
    }, []),
  );

  return (
    <Screen>
      <Stack.Screen options={{ title: 'Meus PCs' }} />
      {pcs !== null && pcs.length === 0 ? (
        <View style={styles.empty}>
          <Title>Nenhum PC pareado ainda.</Title>
          <Body>
            Abra o PcX Control no computador e escaneie o QR code que aparece nele, ou digite o IP e a
            senha do PC.
          </Body>
        </View>
      ) : null}
      {(pcs ?? []).map((pc) => {
        const availability = status[pc.agentId] ?? 'checking';
        const color = availability === 'online' ? theme.accent : theme.textMuted;
        return (
          <Pressable
            key={pc.agentId}
            accessibilityRole="button"
            onPress={() => router.push(`/pc/${encodeURIComponent(pc.agentId)}`)}
            style={[styles.card, { backgroundColor: theme.surface, borderColor: theme.border }]}
          >
            <Text style={[styles.name, { color: theme.text }]}>{pc.alias || pc.name}</Text>
            <Text style={[styles.detail, { color: theme.textMuted }]}>
              {pc.host}:{pc.port}
            </Text>
            <Text style={[styles.status, { color }]}>{LABEL[availability]}</Text>
          </Pressable>
        );
      })}
      <Button title="Adicionar PC" onPress={() => router.push('/add')} />
      <Button title="Aparência" variant="secondary" onPress={() => router.push('/settings')} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  empty: { gap: 10, paddingVertical: 12 },
  card: { borderRadius: 16, borderWidth: 1, padding: 16, gap: 4 },
  name: { fontSize: 18, fontWeight: '700' },
  detail: { fontSize: 14 },
  status: { fontSize: 14, fontWeight: '600' },
});
