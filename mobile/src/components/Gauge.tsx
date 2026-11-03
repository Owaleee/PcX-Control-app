import { useState } from 'react';
import { type LayoutChangeEvent, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { type AlertBadge, type AlertLevel, worst } from '../alerts/levels';
import { useTheme } from '../theme/ThemeProvider';
import { AlertBadgeView, BADGE_GAP, badgesWidth, levelColor } from './AlertBadge';

/** Um dado extra do cartao, sempre com o nome do que mostra (ex.: "VRAM" e "3,3 / 7,8 GiB"). */
export type GaugeStat = { label: string; value: string; level?: AlertLevel };

/** O que um cartao tem alem do titulo e do numero: define quanto sobra para o numero. */
export type GaugeLayout = { bar: boolean; stats: boolean; subtitle?: boolean };

type Props = {
  /** Nome do cartao (ex.: "GPU"). */
  label: string;
  /** O que o numero grande indica (ex.: "uso"). */
  caption?: string;
  /** Linha propria, sempre inteira (ex.: o nome da placa de video). A letra diminui se precisar. */
  subtitle?: string;
  value: string;
  percent?: number;
  stats?: GaugeStat[];
  /**
   * Calcula o numero como se o cartao tivesse este conteudo. No modo painel todos os cartoes usam
   * o do cartao mais cheio, para os numeros ficarem do mesmo tamanho.
   */
  layoutAs?: GaugeLayout;
  /** Nivel do numero grande e da barra (cores de alerta). */
  level?: AlertLevel;
  /** Selos no canto, empilhados (a GPU pode ter "Uso" e "Temperatura"). */
  badges?: AlertBadge[];
  onPress?: () => void;
  testID?: string;
};

const PADDING = 12;
const GAP = 4;
const HEADER = 22;
const SUBTITLE = 20;
const TRACK = 8;
const STATS = 32;
const MAX_SUBTITLE = 16;
const MIN_SUBTITLE = 11;
/** Largura media de uma letra em relacao ao tamanho da fonte (com folga para letras largas). */
const CHAR_WIDTH = 0.6;
/** O numero cresce com o cartao (tablet, TV box), ate este limite. */
const MAX_VALUE = 140;
const MIN_VALUE = 20;
/** Ate quanto os textos acompanham o tamanho de fonte escolhido no Android. */
export const FONT_SCALE_CAP = 1.15;

/**
 * Tamanho do numero grande para caber no cartao. Em paisagem, num celular baixo, um tamanho fixo
 * empurrava o titulo e as ultimas linhas para fora do cartao. `scale` e o tamanho de fonte do
 * Android (ja limitado): os textos fixos crescem com ele e sobra menos para o numero.
 */
export function valueFontSize(
  height: number,
  { bar, stats, subtitle = false }: GaugeLayout,
  { scale = 1, width = 0, text = '' }: { scale?: number; width?: number; text?: string } = {},
): number {
  let size = 56;
  if (height > 0) {
    let fixed = 2 * PADDING + HEADER * scale + GAP;
    if (subtitle) fixed += SUBTITLE * scale + GAP;
    if (bar) fixed += TRACK + GAP;
    if (stats) fixed += STATS * scale + GAP;
    size = Math.floor((height - fixed) / 1.25);
  }
  // Tambem na largura: "↓ 23,3 KB/s" num cartao estreito
  if (width > 0 && text.length > 0) {
    size = Math.min(size, Math.floor((width - 2 * PADDING) / (text.length * CHAR_WIDTH)));
  }
  return Math.max(MIN_VALUE, Math.min(MAX_VALUE, size));
}

/**
 * Tamanho da letra para o nome caber inteiro na largura do cartao. O ajuste automatico do Android
 * tambem olha a altura da linha e encolhia o nome ate ficar ilegivel.
 */
export function subtitleFontSize(width: number, text: string, scale = 1): number {
  const max = Math.round(MAX_SUBTITLE * scale);
  if (width <= 0 || text.length === 0) return max;
  const available = width - 2 * PADDING;
  const size = Math.floor(available / (text.length * CHAR_WIDTH));
  return Math.max(MIN_SUBTITLE, Math.min(max, size));
}

/** Indicador grande do modo painel. Com `onPress`, o cartao abre um detalhe. */
export function Gauge({
  label,
  caption,
  subtitle,
  value,
  percent,
  stats = [],
  layoutAs,
  level = 'normal',
  badges = [],
  onPress,
  testID,
}: Props) {
  const { theme } = useTheme();
  const scale = Math.min(FONT_SCALE_CAP, Math.max(1, useWindowDimensions().fontScale || 1));
  const [size, setSize] = useState({ width: 0, height: 0 });
  const safe = percent === undefined ? undefined : Math.min(100, Math.max(0, percent));
  const layout = layoutAs ?? { bar: safe !== undefined, stats: stats.length > 0, subtitle: subtitle !== undefined };
  const fontSize = valueFontSize(size.height, layout, { scale, width: size.width, text: value });
  const onLayout = (event: LayoutChangeEvent) => {
    const { width, height: h } = event.nativeEvent.layout;
    setSize({ width, height: h });
  };
  // Os selos ficam ao lado do titulo e do nome: o nome tem a largura que sobra.
  const nameWidth = (compact: boolean) => {
    const column = badgesWidth(badges, compact);
    return size.width - (column ? column + 8 : 0);
  };
  const fits = (width: number) => {
    const font = subtitleFontSize(width, subtitle ?? '', scale);
    return (subtitle ?? '').length * font * CHAR_WIDTH <= width - 2 * PADDING;
  };
  // Selos por extenso; se o nome da placa nao couber ao lado, a forma curta ("Temp. alta").
  const compactBadges = subtitle !== undefined && size.width > 0 && !fits(nameWidth(false));
  const subtitleSize = subtitleFontSize(nameWidth(compactBadges), subtitle ?? '', scale);
  const valueColor = levelColor(theme, level) ?? theme.text;
  // A borda segue so o numero e os selos: um alerta nunca aparece so pela cor.
  const border = worst(level, ...badges.map((b) => b.level));
  const borderColor = levelColor(theme, border);
  const fixedHeight = (base: number) => Math.ceil(base * scale);
  const box = [
    styles.box,
    borderColor
      ? { backgroundColor: theme.surface, borderColor, borderWidth: 2, padding: PADDING - 1 }
      : { backgroundColor: theme.surface, borderColor: theme.border },
  ];
  const content = (
    <>
      <View style={styles.top}>
        <View style={styles.titles}>
          <Text
            style={[styles.header, { height: fixedHeight(HEADER), lineHeight: fixedHeight(HEADER) }]}
            numberOfLines={1}
            maxFontSizeMultiplier={FONT_SCALE_CAP}
          >
            <Text style={[styles.label, { color: theme.text }]}>{label}</Text>
            {caption ? <Text style={[styles.caption, { color: theme.textMuted }]}>{` · ${caption}`}</Text> : null}
          </Text>
          {subtitle !== undefined ? (
            <Text
              testID={testID ? `${testID}-subtitle` : undefined}
              style={{
                color: theme.textMuted,
                fontSize: subtitleSize,
                height: fixedHeight(SUBTITLE),
                lineHeight: fixedHeight(SUBTITLE),
              }}
              numberOfLines={1}
              ellipsizeMode="clip"
              allowFontScaling={false}
            >
              {subtitle}
            </Text>
          ) : null}
        </View>
        {badges.length > 0 ? (
          <View testID={testID ? `${testID}-badges` : undefined} style={styles.badges}>
            {badges.map((badge) => (
              <AlertBadgeView key={badge.label} badge={badge} compact={compactBadges} />
            ))}
          </View>
        ) : null}
      </View>
      <Text
        testID={testID ? `${testID}-value` : undefined}
        style={[styles.value, { color: valueColor, fontSize, lineHeight: Math.round(fontSize * 1.2) }]}
        numberOfLines={1}
        allowFontScaling={false}
      >
        {value}
      </Text>
      {safe !== undefined ? (
        <View style={[styles.track, { backgroundColor: theme.track }]}>
          <View style={[styles.fill, { width: `${safe}%`, backgroundColor: levelColor(theme, level) ?? theme.accent }]} />
        </View>
      ) : null}
      {stats.length > 0 ? (
        <View style={[styles.stats, { height: fixedHeight(STATS) }]}>
          {stats.map((stat) => (
            <View key={stat.label} style={styles.stat}>
              <Text
                style={[styles.statLabel, { color: theme.textMuted, lineHeight: fixedHeight(14) }]}
                numberOfLines={1}
                maxFontSizeMultiplier={FONT_SCALE_CAP}
              >
                {stat.label}
              </Text>
              <Text
                style={[
                  styles.statValue,
                  { color: levelColor(theme, stat.level ?? 'normal') ?? theme.text, lineHeight: fixedHeight(18) },
                ]}
                numberOfLines={1}
                adjustsFontSizeToFit
                maxFontSizeMultiplier={FONT_SCALE_CAP}
              >
                {stat.value}
              </Text>
            </View>
          ))}
        </View>
      ) : null}
    </>
  );
  const spoken = [
    `${label}${caption ? ` ${caption}` : ''}${subtitle ? `, ${subtitle}` : ''}: ${value}`,
    ...badges.map((b) => b.label),
    ...stats.map((s) => `${s.label}: ${s.value}`),
  ].join(', ');
  if (onPress) {
    return (
      <Pressable
        testID={testID}
        accessibilityRole="button"
        accessibilityLabel={spoken}
        onPress={onPress}
        onLayout={onLayout}
        style={box}
      >
        {content}
      </Pressable>
    );
  }
  return (
    <View testID={testID} accessible accessibilityLabel={spoken} onLayout={onLayout} style={box}>
      {content}
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    flex: 1,
    borderRadius: 20,
    borderWidth: 1,
    padding: PADDING,
    justifyContent: 'center',
    gap: GAP,
    overflow: 'hidden',
  },
  top: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  titles: { flex: 1, minWidth: 0, gap: GAP },
  badges: { gap: BADGE_GAP, alignItems: 'flex-end' },
  header: { fontSize: 18 },
  label: { fontSize: 18, fontWeight: '600' },
  caption: { fontSize: 16 },
  value: { fontWeight: '700' },
  track: { height: TRACK, borderRadius: 4, overflow: 'hidden' },
  fill: { height: '100%' },
  stats: { flexDirection: 'row', gap: 16 },
  stat: { flex: 1, minWidth: 0, justifyContent: 'center' },
  statLabel: { fontSize: 12 },
  statValue: { fontSize: 15, fontWeight: '600' },
});
