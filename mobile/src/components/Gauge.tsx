import { useState } from 'react';
import { type LayoutChangeEvent, Pressable, StyleSheet, Text, View } from 'react-native';

import { useTheme } from '../theme/ThemeProvider';

/** Um dado extra do cartao, sempre com o nome do que mostra (ex.: "VRAM" e "3,3 / 7,8 GiB"). */
export type GaugeStat = { label: string; value: string };

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
const MAX_VALUE = 56;
const MIN_VALUE = 24;

/**
 * Tamanho do numero grande para caber na altura do cartao. Em paisagem, num celular baixo, um
 * tamanho fixo empurrava o titulo e as ultimas linhas para fora do cartao.
 */
export function valueFontSize(
  height: number,
  { bar, stats, subtitle = false }: { bar: boolean; stats: boolean; subtitle?: boolean },
): number {
  if (height <= 0) return MAX_VALUE;
  let fixed = 2 * PADDING + HEADER + GAP;
  if (subtitle) fixed += SUBTITLE + GAP;
  if (bar) fixed += TRACK + GAP;
  if (stats) fixed += STATS + GAP;
  const size = Math.floor((height - fixed) / 1.25);
  return Math.max(MIN_VALUE, Math.min(MAX_VALUE, size));
}

/**
 * Tamanho da letra para o nome caber inteiro na largura do cartao. O ajuste automatico do Android
 * tambem olha a altura da linha e encolhia o nome ate ficar ilegivel.
 */
export function subtitleFontSize(width: number, text: string): number {
  if (width <= 0 || text.length === 0) return MAX_SUBTITLE;
  const available = width - 2 * PADDING;
  const size = Math.floor(available / (text.length * CHAR_WIDTH));
  return Math.max(MIN_SUBTITLE, Math.min(MAX_SUBTITLE, size));
}

/** Indicador grande do modo painel. Com `onPress`, o cartao abre um detalhe. */
export function Gauge({ label, caption, subtitle, value, percent, stats = [], onPress, testID }: Props) {
  const { theme } = useTheme();
  const [size, setSize] = useState({ width: 0, height: 0 });
  const height = size.height;
  const safe = percent === undefined ? undefined : Math.min(100, Math.max(0, percent));
  const fontSize = valueFontSize(height, {
    bar: safe !== undefined,
    stats: stats.length > 0,
    subtitle: subtitle !== undefined,
  });
  const onLayout = (event: LayoutChangeEvent) => {
    const { width, height: h } = event.nativeEvent.layout;
    setSize({ width, height: h });
  };
  const subtitleSize = subtitleFontSize(size.width, subtitle ?? '');
  const box = [styles.box, { backgroundColor: theme.surface, borderColor: theme.border }];
  const content = (
    <>
      <Text style={styles.header} numberOfLines={1}>
        <Text style={[styles.label, { color: theme.text }]}>{label}</Text>
        {caption ? <Text style={[styles.caption, { color: theme.textMuted }]}>{` · ${caption}`}</Text> : null}
      </Text>
      {subtitle !== undefined ? (
        <Text
          testID={testID ? `${testID}-subtitle` : undefined}
          style={[styles.subtitle, { color: theme.textMuted, fontSize: subtitleSize }]}
          numberOfLines={1}
          ellipsizeMode="clip"
        >
          {subtitle}
        </Text>
      ) : null}
      <Text
        testID={testID ? `${testID}-value` : undefined}
        style={[styles.value, { color: theme.text, fontSize, lineHeight: Math.round(fontSize * 1.2) }]}
        adjustsFontSizeToFit
        numberOfLines={1}
      >
        {value}
      </Text>
      {safe !== undefined ? (
        <View style={[styles.track, { backgroundColor: theme.track }]}>
          <View style={[styles.fill, { width: `${safe}%`, backgroundColor: theme.accent }]} />
        </View>
      ) : null}
      {stats.length > 0 ? (
        <View style={styles.stats}>
          {stats.map((stat) => (
            <View key={stat.label} style={styles.stat}>
              <Text style={[styles.statLabel, { color: theme.textMuted }]} numberOfLines={1}>
                {stat.label}
              </Text>
              <Text style={[styles.statValue, { color: theme.text }]} numberOfLines={1} adjustsFontSizeToFit>
                {stat.value}
              </Text>
            </View>
          ))}
        </View>
      ) : null}
    </>
  );
  const spoken = [`${label}${caption ? ` ${caption}` : ''}${subtitle ? `, ${subtitle}` : ''}: ${value}`, ...stats.map((s) => `${s.label}: ${s.value}`)].join(', ');
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
  header: { height: HEADER, lineHeight: HEADER, fontSize: 18 },
  label: { fontSize: 18, fontWeight: '600' },
  caption: { fontSize: 16 },
  subtitle: { height: SUBTITLE, lineHeight: SUBTITLE },
  value: { fontWeight: '700' },
  track: { height: TRACK, borderRadius: 4, overflow: 'hidden' },
  fill: { height: '100%' },
  stats: { height: STATS, flexDirection: 'row', gap: 16 },
  stat: { flex: 1, minWidth: 0, justifyContent: 'center' },
  statLabel: { fontSize: 12, lineHeight: 14 },
  statValue: { fontSize: 15, lineHeight: 18, fontWeight: '600' },
});
