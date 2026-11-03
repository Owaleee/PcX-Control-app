import { Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

import { HistoryChart } from '../../../../src/components/HistoryChart';
import { RangeTabs } from '../../../../src/components/RangeTabs';
import { Screen, Title } from '../../../../src/components/ui';
import { METRIC_TITLES } from '../../../../src/format/metric';
import { METRIC_NAMES } from '../../../../src/protocol/metrics';
import type { MetricName, Range } from '../../../../src/protocol/types';

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
  const [range, setRange] = useState<Range>('15m');
  return (
    <Screen>
      <Stack.Screen options={{ title: METRIC_TITLES[metric] }} />
      <RangeTabs value={range} onChange={setRange} />
      <HistoryChart metric={metric} range={range} />
    </Screen>
  );
}
