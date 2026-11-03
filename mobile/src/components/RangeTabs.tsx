import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { Range } from '../protocol/types';
import { useTheme } from '../theme/ThemeProvider';

/** Duracao de cada intervalo, em segundos (eixo do grafico). */
export const SPAN_S: Record<Range, number> = { '15m': 900, '1h': 3600, '24h': 86400 };

const TABS: { range: Range; label: string }[] = [
  { range: '15m', label: '15 min' },
  { range: '1h', label: '1 h' },
  { range: '24h', label: '24 h' },
];

/** Abas 15 min / 1 h / 24 h dos graficos. */
export function RangeTabs({ value, onChange }: { value: Range; onChange: (range: Range) => void }) {
  const { theme } = useTheme();
  return (
    <View style={styles.tabs} accessibilityRole="tablist">
      {TABS.map((tab) => (
        <Pressable
          key={tab.range}
          accessibilityRole="tab"
          accessibilityState={{ selected: tab.range === value }}
          onPress={() => onChange(tab.range)}
          style={[
            styles.tab,
            { borderColor: tab.range === value ? theme.accent : theme.border, backgroundColor: theme.surface },
          ]}
        >
          <Text style={{ color: theme.text, fontWeight: tab.range === value ? '700' : '400' }}>{tab.label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  tabs: { flexDirection: 'row', gap: 8 },
  tab: { flex: 1, alignItems: 'center', paddingVertical: 10, borderRadius: 10, borderWidth: 2 },
});
