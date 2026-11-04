import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { AlertBadge, AlertLevel } from '../alerts/levels';
import { worst } from '../alerts/levels';
import { useTheme } from '../theme/ThemeProvider';
import { AlertBadgeView, levelColor } from './AlertBadge';
import { Sparkline, type SeriesPoint } from './Sparkline';

type Props = {
  title: string;
  value: string;
  detail?: string;
  percent?: number;
  history?: SeriesPoint[];
  historyMax?: number;
  stale?: boolean;
  /** Nivel do numero e da barra (cores de alerta). */
  level?: AlertLevel;
  /** Selos ao lado do titulo; a GPU pode ter dois. */
  badges?: AlertBadge[];
  onPress?: () => void;
};

export function MetricCard({
  title,
  value,
  detail,
  percent,
  history,
  historyMax,
  stale,
  level = 'normal',
  badges = [],
  onPress,
}: Props) {
  const { theme } = useTheme();
  const safe = percent === undefined ? undefined : Math.min(100, Math.max(0, percent));
  const alertColor = levelColor(theme, worst(level, ...badges.map((b) => b.level)));
  const style = [
    styles.card,
    {
      backgroundColor: theme.surface,
      borderColor: alertColor ?? theme.border,
      borderWidth: alertColor ? 2 : 1,
      padding: alertColor ? 15 : 16,
      opacity: stale ? 0.5 : 1,
    },
  ];
  const content = (
    <>
      <View style={styles.top}>
        <Text style={[styles.title, { color: theme.textMuted }]}>{title}</Text>
        {badges.length > 0 ? (
          <View style={styles.badges}>
            {badges.map((badge) => (
              <AlertBadgeView key={badge.label} badge={badge} />
            ))}
          </View>
        ) : null}
      </View>
      <Text style={[styles.value, { color: levelColor(theme, level) ?? theme.text }]}>{value}</Text>
      {safe !== undefined ? (
        <View
          accessible
          accessibilityRole="progressbar"
          accessibilityLabel={title}
          accessibilityValue={{ min: 0, max: 100, now: Math.round(safe) }}
          style={[styles.track, { backgroundColor: theme.track }]}
        >
          <View style={[styles.fill, { width: `${safe}%`, backgroundColor: levelColor(theme, level) ?? theme.accent }]} />
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
  card: { borderRadius: 16, gap: 8 },
  top: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 },
  badges: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'flex-end', gap: 4, flexShrink: 1 },
  title: { fontSize: 15, flexShrink: 1 },
  value: { fontSize: 30, fontWeight: '700' },
  track: { height: 8, borderRadius: 4, overflow: 'hidden' },
  fill: { height: '100%' },
  detail: { fontSize: 14 },
});
