import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useTheme } from '../theme/ThemeProvider';

type Props = {
  label: string;
  value: string;
  percent?: number;
  /** Uma linha ou varias (ex.: VRAM e temperatura no cartao da GPU). */
  detail?: string | string[];
  onPress?: () => void;
  testID?: string;
};

/** Indicador grande do modo painel. Com `onPress`, o cartao abre um detalhe. */
export function Gauge({ label, value, percent, detail, onPress, testID }: Props) {
  const { theme } = useTheme();
  const safe = percent === undefined ? undefined : Math.min(100, Math.max(0, percent));
  const lines = detail === undefined ? [] : Array.isArray(detail) ? detail : [detail];
  const box = [styles.box, { backgroundColor: theme.surface, borderColor: theme.border }];
  const content = (
    <>
      <Text style={[styles.label, { color: theme.textMuted }]}>{label}</Text>
      <Text style={[styles.value, { color: theme.text }]} adjustsFontSizeToFit numberOfLines={1}>
        {value}
      </Text>
      {safe !== undefined ? (
        <View style={[styles.track, { backgroundColor: theme.track }]}>
          <View style={[styles.fill, { width: `${safe}%`, backgroundColor: theme.accent }]} />
        </View>
      ) : null}
      {lines.map((line) => (
        <Text key={line} style={[styles.detail, { color: theme.textMuted }]} numberOfLines={1}>
          {line}
        </Text>
      ))}
    </>
  );
  if (onPress) {
    return (
      <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={`${label}: ${value}`} onPress={onPress} style={box}>
        {content}
      </Pressable>
    );
  }
  return (
    <View testID={testID} style={box}>
      {content}
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
