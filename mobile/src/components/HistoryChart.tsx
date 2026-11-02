import { StyleSheet, Text, View } from 'react-native';

import { formatMetric, metricScale } from '../format/metric';
import { usePc } from '../hooks/PcContext';
import { useMetricHistory } from '../hooks/useMetricHistory';
import type { MetricName, Range } from '../protocol/types';
import { useTheme } from '../theme/ThemeProvider';
import { SPAN_S } from './RangeTabs';
import { Sparkline } from './Sparkline';
import { Body, Message } from './ui';

type Props = { metric: MetricName; range: Range; title?: string; height?: number };

/** Grafico do historico de uma metrica, com media e maximo do intervalo. */
export function HistoryChart({ metric, range, title, height = 180 }: Props) {
  const { theme, precise } = useTheme();
  const { pc, snapshot, session } = usePc();
  const { points, loading, error } = useMetricHistory(pc, metric, range, snapshot, session);
  const averages = points.map((p) => p.avg);
  const mean = averages.length ? averages.reduce((a, b) => a + b, 0) / averages.length : null;
  const peak = points.length ? Math.max(...points.map((p) => p.max)) : null;

  return (
    <View style={styles.block}>
      {title ? <Text style={[styles.title, { color: theme.text }]}>{title}</Text> : null}
      <View style={[styles.chart, { backgroundColor: theme.surface, borderColor: theme.border }]}>
        <Sparkline
          points={points.map((p) => ({ t: p.t, v: p.avg }))}
          height={height}
          color={theme.accent}
          max={metricScale(metric, averages)}
          span={SPAN_S[range]}
        />
      </View>
      {loading ? <Body>Carregando histórico…</Body> : null}
      <Message text={error} />
      {mean !== null ? <Body>{`Média: ${formatMetric(metric, mean, precise)}`}</Body> : null}
      {peak !== null ? <Body>{`Máximo: ${formatMetric(metric, peak, precise)}`}</Body> : null}
      {!loading && !error && points.length === 0 ? <Body>Ainda não há dados neste intervalo.</Body> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  block: { gap: 8 },
  title: { fontSize: 18, fontWeight: '700' },
  chart: { borderRadius: 16, borderWidth: 1, padding: 12 },
});
