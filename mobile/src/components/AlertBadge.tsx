import { StyleSheet, Text, View } from 'react-native';

import type { AlertBadge as Badge, AlertLevel } from '../alerts/levels';
import type { Theme } from '../theme/themes';
import { useTheme } from '../theme/ThemeProvider';

export const BADGE_HEIGHT = 18;
export const BADGE_GAP = 4;
const BADGE_FONT = 11;
const BADGE_PADDING = 8;

/** Cor do nivel: amarelo para alto, `danger` para critico, nada no normal. */
export function levelColor(theme: Theme, level: AlertLevel): string | null {
  if (level === 'critico') return theme.danger;
  if (level === 'alto') return theme.warning;
  return null;
}

/** Largura que a coluna de selos ocupa (para o nome da placa caber ao lado). */
export function badgesWidth(badges: Badge[]): number {
  if (badges.length === 0) return 0;
  const longest = Math.max(...badges.map((b) => b.label.length));
  return Math.ceil(longest * BADGE_FONT * 0.6) + 2 * BADGE_PADDING + 2;
}

/** Selo "Uso alto", "Temperatura critica"...: o alerta nunca depende so da cor. */
export function AlertBadgeView({ badge }: { badge: Badge }) {
  const { theme } = useTheme();
  const color = levelColor(theme, badge.level) ?? theme.text;
  return (
    <View
      testID={`badge-${badge.label}`}
      style={[styles.badge, { borderColor: color, backgroundColor: theme.background }]}
    >
      <Text style={[styles.text, { color }]} numberOfLines={1} allowFontScaling={false}>
        {badge.label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    height: BADGE_HEIGHT,
    borderRadius: BADGE_HEIGHT / 2,
    borderWidth: 1,
    paddingHorizontal: BADGE_PADDING,
    justifyContent: 'center',
  },
  text: { fontSize: BADGE_FONT, lineHeight: 14, fontWeight: '700' },
});
