import { Stack, router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { type AlertBadge, tempBadge, tempLevel, usageBadge, usageLevel } from '../../../src/alerts/levels';
import { MetricCard } from '../../../src/components/MetricCard';
import { StatusPill } from '../../../src/components/StatusPill';
import { Body, Button, CardGrid, Message, Screen } from '../../../src/components/ui';
import { formatFree, formatPercent, formatRate, formatTemp, formatUptime, formatUsage } from '../../../src/format/format';
import { metricScale } from '../../../src/format/metric';
import { usePc } from '../../../src/hooks/PcContext';
import { useMetricHistory } from '../../../src/hooks/useMetricHistory';
import type { MetricName } from '../../../src/protocol/types';
import { useTheme } from '../../../src/theme/ThemeProvider';

function useSeries(metric: MetricName) {
  const { pc, snapshot, session } = usePc();
  const { points } = useMetricHistory(pc, metric, '15m', snapshot, session);
  return points.map((p) => ({ t: p.t, v: p.avg }));
}

export default function PcPanel() {
  const { theme, precise, alerts } = useTheme();
  const percent = (value: number) => formatPercent(value, { precise });
  const { pc, state, snapshot, takeover } = usePc();
  const cpu = useSeries('cpu.total');
  const ram = useSeries('ram.percent');
  const gpu = useSeries('gpu.usage');
  const net = useSeries('net.down_bps');
  const base = `/pc/${encodeURIComponent(pc.agentId)}`;
  const open = (metric: MetricName) => () => router.push(`${base}/metric/${metric}`);
  const stale = state.kind !== 'connected';
  const data = snapshot?.data;
  const only = (...badges: (AlertBadge | null)[]) => badges.filter((b): b is AlertBadge => b !== null);
  const usage = (value: number | null | undefined) => {
    const level = usageLevel(value, alerts);
    return { level, badges: only(usageBadge(level)) };
  };

  return (
    <Screen wide>
      <Stack.Screen
        options={{
          title: pc.alias || pc.name,
          headerRight: () => (
            <Pressable accessibilityRole="button" onPress={() => router.push(`${base}/settings`)}>
              <Text style={{ color: theme.accent, fontSize: 16 }}>Ajustes</Text>
            </Pressable>
          ),
        }}
      />
      <StatusPill state={state} />
      {state.kind === 'taken_over' ? (
        <View style={styles.notice}>
          <Message text="Este celular foi trocado por outro aparelho nesta sessão." tone="info" />
          <Button title="Assumir de volta" variant="secondary" onPress={takeover} />
        </View>
      ) : null}
      {state.kind === 'busy' ? (
        <View style={styles.notice}>
          <Message text={`PC em uso por ${state.activeDevice}.`} tone="info" />
          <Button title="Assumir a sessão" variant="secondary" onPress={takeover} />
        </View>
      ) : null}
      {!data ? <Body>Aguardando a primeira leitura do PC…</Body> : null}
      {data ? (
        <>
          <Text style={[styles.updated, { color: theme.textMuted }]}>
            {`${data.host_name} · ligado há ${formatUptime(data.uptime_s)}`}
            {stale ? ' · valores anteriores' : ''}
          </Text>
          <CardGrid>
            <MetricCard
              title="CPU"
              value={percent(data.cpu_total)}
              percent={data.cpu_total}
              {...usage(data.cpu_total)}
              history={cpu}
              stale={stale}
              onPress={open('cpu.total')}
            />
            <MetricCard
              title="Memória RAM"
              value={percent(data.ram_percent)}
              percent={data.ram_percent}
              {...usage(data.ram_percent)}
              detail={`${formatUsage(data.ram_used_bytes, data.ram_total_bytes)} · ${formatFree(data.ram_used_bytes, data.ram_total_bytes)}`}
              history={ram}
              stale={stale}
              onPress={open('ram.percent')}
            />
            {data.gpus.map((g, index) => {
              const vram =
                g.vram_used_bytes !== null && g.vram_total_bytes
                  ? `VRAM usada ${formatUsage(g.vram_used_bytes, g.vram_total_bytes)}`
                  : null;
              const temp = `Temperatura ${g.temp_c !== null ? formatTemp(g.temp_c) : 'indisponível'}`;
              return (
                <MetricCard
                  key={g.id}
                  title={`GPU · ${g.name}`}
                  value={percent(g.usage_percent)}
                  percent={g.usage_percent}
                  level={usageLevel(g.usage_percent, alerts)}
                  badges={only(usageBadge(usageLevel(g.usage_percent, alerts)), tempBadge(tempLevel(g.temp_c, alerts)))}
                  detail={[vram, temp].filter(Boolean).join(' · ') || undefined}
                  history={index === 0 ? gpu : undefined}
                  stale={stale}
                  onPress={index === 0 ? () => router.push(`${base}/gpu`) : undefined}
                />
              );
            })}
            <MetricCard
              title="Rede"
              value={`↓ ${formatRate(data.net_down_bps)}  ↑ ${formatRate(data.net_up_bps)}`}
              detail="↓ recebendo (download) · ↑ enviando (upload)"
              history={net}
              historyMax={metricScale('net.down_bps', net.map((p) => p.v))}
              stale={stale}
              onPress={open('net.down_bps')}
            />
            {data.disks.map((d) => (
              <MetricCard
                key={d.mount}
                title={`Disco ${d.mount}`}
                value={percent(d.percent)}
                percent={d.percent}
                {...usage(d.percent)}
                detail={formatUsage(d.used_bytes, d.total_bytes)}
                stale={stale}
              />
            ))}
          </CardGrid>
        </>
      ) : null}
      <Button title="Modo painel" onPress={() => router.push(`${base}/panel`)} disabled={!data} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  notice: { gap: 8 },
  updated: { fontSize: 13 },
});
