import { Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Sparkline } from '../../../../src/components/Sparkline';
import { Body, Message, Screen, Title } from '../../../../src/components/ui';
import { METRIC_TITLES, formatMetric, metricScale } from '../../../../src/format/metric';
import { usePc } from '../../../../src/hooks/PcContext';
import { useMetricHistory } from '../../../../src/hooks/useMetricHistory';
import { METRIC_NAMES } from '../../../../src/protocol/metrics';
import type { MetricName, Range } from '../../../../src/protocol/types';
import { useTheme } from '../../../../src/theme/ThemeProvider';

const TABS: { range: Range; label: string }[] = [
  { range: '15m', label: '15 min' },
  { range: '1h', label: '1 h' },
  { range: '24h', label: '24 h' },
];

export default function MetricDetail() {
  const { metric } = useLocalSearchParams<{ metric: string }>();
  const known = (METRIC_NAMES as readonly string[]).includes(String(metric));
  if (!known) {
    return (
      <Screen>
        <Title>Métrica desconhecida.</Title>
      </Screen>
    );
  }
  return <MetricChart metric={metric as MetricName} />;
}

function MetricChart({ metric }: { metric: MetricName }) {
  const { theme } = useTheme();
  const { pc, snapshot } = usePc();
  const [range, setRange] = useState<Range>('15m');
  const { points, loading, error } = useMetricHistory(pc, metric, range, snapshot);
  const averages = points.map((p) => p.avg);
  const mean = averages.length ? averages.reduce((a, b) => a + b, 0) / averages.length : null;
  const peak = points.length ? Math.max(...points.map((p) => p.max)) : null;

  return (
    <Screen>
      <Stack.Screen options={{ title: METRIC_TITLES[metric] }} />
      <View style={styles.tabs} accessibilityRole="tablist">
        {TABS.map((tab) => (
          <Pressable
            key={tab.range}
            accessibilityRole="tab"
            accessibilityState={{ selected: tab.range === range }}
            onPress={() => setRange(tab.range)}
            style={[
              styles.tab,
              { borderColor: tab.range === range ? theme.accent : theme.border, backgroundColor: theme.surface },
            ]}
          >
            <Text style={{ color: theme.text, fontWeight: tab.range === range ? '700' : '400' }}>{tab.label}</Text>
          </Pressable>
        ))}
      </View>
      <View style={[styles.chart, { backgroundColor: theme.surface, borderColor: theme.border }]}>
        <Sparkline values={averages} height={180} color={theme.accent} max={metricScale(metric, averages)} />
      </View>
      {loading ? <Body>Carregando histórico…</Body> : null}
      <Message text={error} />
      {mean !== null ? <Body>{`Média: ${formatMetric(metric, mean)}`}</Body> : null}
      {peak !== null ? <Body>{`Máximo: ${formatMetric(metric, peak)}`}</Body> : null}
      {!loading && !error && points.length === 0 ? <Body>Ainda não há dados neste intervalo.</Body> : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  tabs: { flexDirection: 'row', gap: 8 },
  tab: { flex: 1, alignItems: 'center', paddingVertical: 10, borderRadius: 10, borderWidth: 2 },
  chart: { borderRadius: 16, borderWidth: 1, padding: 12 },
});
