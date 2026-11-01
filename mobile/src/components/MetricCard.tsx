import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useTheme } from '../theme/ThemeProvider';
import { Sparkline, type SeriesPoint } from './Sparkline';

type Props = {
  title: string;
  value: string;
  detail?: string;
  percent?: number;
  history?: SeriesPoint[];
  historyMax?: number;
  stale?: boolean;
  onPress?: () => void;
};

export function MetricCard({ title, value, detail, percent, history, historyMax, stale, onPress }: Props) {
  const { theme } = useTheme();
  const safe = percent === undefined ? undefined : Math.min(100, Math.max(0, percent));
  const style = [
    styles.card,
    { backgroundColor: theme.surface, borderColor: theme.border, opacity: stale ? 0.5 : 1 },
  ];
  const content = (
    <>
      <Text style={[styles.title, { color: theme.textMuted }]}>{title}</Text>
      <Text style={[styles.value, { color: theme.text }]}>{value}</Text>
      {safe !== undefined ? (
        <View
          accessible
          accessibilityRole="progressbar"
          accessibilityLabel={title}
          accessibilityValue={{ min: 0, max: 100, now: Math.round(safe) }}
          style={[styles.track, { backgroundColor: theme.track }]}
        >
          <View style={[styles.fill, { width: `${safe}%`, backgroundColor: theme.accent }]} />
        </View>
      ) : null}
      {history && history.length > 1 ? (
        <Sparkline points={history} color={theme.accent} max={historyMax ?? 100} span={900} />
      ) : null}
      {detail ? <Text style={[styles.detail, { color: theme.textMuted }]}>{detail}</Text> : null}
    </>
  );
  // Sem acao, o cartao e uma View comum: assim a barra continua visivel para o leitor de tela.
  if (!onPress) {
    return (
      <View testID="metric-card" style={style}>
        {content}
      </View>
    );
  }
  return (
    <Pressable testID="metric-card" onPress={onPress} accessibilityRole="button" style={style}>
      {content}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: 16, borderWidth: 1, padding: 16, gap: 8 },
  title: { fontSize: 15 },
  value: { fontSize: 30, fontWeight: '700' },
  track: { height: 8, borderRadius: 4, overflow: 'hidden' },
  fill: { height: '100%' },
  detail: { fontSize: 14 },
});
