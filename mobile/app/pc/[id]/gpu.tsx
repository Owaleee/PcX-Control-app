import { Stack } from 'expo-router';
import { useState } from 'react';

import { HistoryChart } from '../../../src/components/HistoryChart';
import { RangeTabs } from '../../../src/components/RangeTabs';
import { Screen } from '../../../src/components/ui';
import { usePc } from '../../../src/hooks/PcContext';
import type { Range } from '../../../src/protocol/types';

const CHART_HEIGHT = 140;

/** Historico da GPU: uso, VRAM e temperatura no mesmo intervalo. */
export default function GpuDetail() {
  const { snapshot, capabilities } = usePc();
  const [range, setRange] = useState<Range>('15m');
  const name = snapshot?.data.gpus[0]?.name ?? 'GPU';
  return (
    <Screen>
      <Stack.Screen options={{ title: name }} />
      <RangeTabs value={range} onChange={setRange} />
      <HistoryChart metric="gpu.usage" range={range} title="Uso da GPU" height={CHART_HEIGHT} />
      <HistoryChart metric="gpu.vram_percent" range={range} title="VRAM" height={CHART_HEIGHT} />
      {capabilities.includes('gpu.temp') ? (
        <HistoryChart metric="gpu.temp" range={range} title="Temperatura" height={CHART_HEIGHT} />
      ) : null}
    </Screen>
  );
}
