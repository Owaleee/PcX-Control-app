import { StyleSheet, Text, View } from 'react-native';

import { useTheme } from '../theme/ThemeProvider';

type Props = { label: string; value: string; percent?: number; detail?: string };

/** Indicador grande do modo painel. */
export function Gauge({ label, value, percent, detail }: Props) {
  const { theme } = useTheme();
  const safe = percent === undefined ? undefined : Math.min(100, Math.max(0, percent));
  return (
    <View style={[styles.box, { backgroundColor: theme.surface, borderColor: theme.border }]}>
      <Text style={[styles.label, { color: theme.textMuted }]}>{label}</Text>
      <Text style={[styles.value, { color: theme.text }]} adjustsFontSizeToFit numberOfLines={1}>
        {value}
      </Text>
      {safe !== undefined ? (
        <View style={[styles.track, { backgroundColor: theme.track }]}>
          <View style={[styles.fill, { width: `${safe}%`, backgroundColor: theme.accent }]} />
        </View>
      ) : null}
      {detail ? <Text style={[styles.detail, { color: theme.textMuted }]}>{detail}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  box: { flex: 1, borderRadius: 20, borderWidth: 1, padding: 16, justifyContent: 'center', gap: 8 },
  label: { fontSize: 18 },
  value: { fontSize: 52, fontWeight: '700' },
  track: { height: 10, borderRadius: 5, overflow: 'hidden' },
  fill: { height: '100%' },
  detail: { fontSize: 18 },
});
