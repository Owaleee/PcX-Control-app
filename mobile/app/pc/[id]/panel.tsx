import { useKeepAwake } from 'expo-keep-awake';
import { router } from 'expo-router';
import * as ScreenOrientation from 'expo-screen-orientation';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Gauge } from '../../../src/components/Gauge';
import { statusLabel } from '../../../src/components/StatusPill';
import { formatPercent, formatRate, formatTemp, formatUsage } from '../../../src/format/format';
import { usePc } from '../../../src/hooks/PcContext';
import { pixelShiftOffset } from '../../../src/theme/pixelShift';
import { useTheme } from '../../../src/theme/ThemeProvider';
import { nextTheme } from '../../../src/theme/themes';

const CONTROLS_MS = 3000;
const SHIFT_MS = 180_000;
const GAP = 16;

export default function PanelMode() {
  useKeepAwake();
  const { theme, name, setName } = useTheme();
  const { snapshot, capabilities, state } = usePc();
  const insets = useSafeAreaInsets();
  const stale = state.kind !== 'connected';
  const [controlsAt, setControlsAt] = useState<number | null>(null);
  const [dim, setDim] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    ScreenOrientation.lockAsync(ScreenOrientation.OrientationLock.LANDSCAPE).catch(() => undefined);
    return () => {
      ScreenOrientation.unlockAsync().catch(() => undefined);
    };
  }, []);

  useEffect(() => {
    const timer = setInterval(() => setStep((s) => s + 1), SHIFT_MS);
    return () => clearInterval(timer);
  }, []);

  // Cada toque reinicia a contagem de 3 s dos controles.
  useEffect(() => {
    if (controlsAt === null) return undefined;
    const timer = setTimeout(() => setControlsAt(null), CONTROLS_MS);
    return () => clearTimeout(timer);
  }, [controlsAt]);

  const touch = () => setControlsAt((count) => (count ?? 0) + 1);
  const shift = pixelShiftOffset(step);
  const data = snapshot?.data;
  const gpu = data?.gpus[0];
  const temp = capabilities.includes('gpu.temp') ? gpu?.temp_c ?? null : null;

  return (
    <View style={[styles.root, { backgroundColor: theme.background }]}>
      <StatusBar hidden />
      <Pressable testID="panel-touch" accessibilityLabel="Mostrar controles" style={styles.root} onPress={touch}>
        <View
          testID="panel-grid"
          style={[
            styles.grid,
            {
              paddingTop: GAP + insets.top,
              paddingBottom: GAP + insets.bottom,
              paddingLeft: GAP + insets.left,
              paddingRight: GAP + insets.right,
              transform: [{ translateX: shift.x }, { translateY: shift.y }],
            },
          ]}
        >
          {stale ? (
            <Text style={[styles.status, { color: theme.text, backgroundColor: theme.surface }]}>
              {statusLabel(state)}
            </Text>
          ) : null}
          {data ? (
            <View testID="panel-gauges" style={[styles.gauges, { opacity: stale ? 0.5 : 1 }]}>
              <View style={styles.row}>
                <Gauge label="CPU" value={formatPercent(data.cpu_total)} percent={data.cpu_total} />
                {gpu ? <Gauge label="GPU" value={formatPercent(gpu.usage_percent)} percent={gpu.usage_percent} /> : null}
                {temp !== null ? <Gauge label="Temperatura GPU" value={formatTemp(temp)} percent={temp} /> : null}
              </View>
              <View style={styles.row}>
                <Gauge
                  label="RAM"
                  value={formatPercent(data.ram_percent)}
                  percent={data.ram_percent}
                  detail={formatUsage(data.ram_used_bytes, data.ram_total_bytes)}
                />
                <Gauge label="Rede" value={`↓ ${formatRate(data.net_down_bps)}`} detail={`↑ ${formatRate(data.net_up_bps)}`} />
              </View>
            </View>
          ) : (
            <Text style={[styles.waiting, { color: theme.textMuted }]}>Aguardando dados do PC…</Text>
          )}
        </View>
      </Pressable>
      {dim ? <View testID="dim-overlay" pointerEvents="none" style={[StyleSheet.absoluteFill, styles.dim]} /> : null}
      {controlsAt !== null ? (
        <View
          testID="panel-controls"
          style={[
            styles.controls,
            { bottom: GAP + insets.bottom, backgroundColor: theme.surface, borderColor: theme.border },
          ]}
        >
          {[
            { label: 'Sair', onPress: () => router.back() },
            {
              label: 'Tema',
              onPress: () => {
                setName(nextTheme(name));
                touch();
              },
            },
            {
              label: dim ? 'Clarear' : 'Escurecer',
              onPress: () => {
                setDim((d) => !d);
                touch();
              },
            },
          ].map((control) => (
            <Pressable key={control.label} accessibilityRole="button" onPress={control.onPress} style={styles.control}>
              <Text style={[styles.controlText, { color: theme.text }]}>{control.label}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  grid: { flex: 1, gap: GAP },
  gauges: { flex: 1, gap: GAP },
  row: { flex: 1, flexDirection: 'row', gap: 16 },
  waiting: { fontSize: 22, textAlign: 'center', marginTop: 40 },
  status: {
    alignSelf: 'center',
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 999,
    fontSize: 16,
    overflow: 'hidden',
  },
  dim: { backgroundColor: '#000000', opacity: 0.6 },
  controls: {
    position: 'absolute',
    alignSelf: 'center',
    flexDirection: 'row',
    gap: 8,
    borderWidth: 1,
    borderRadius: 16,
    padding: 8,
  },
  control: { paddingVertical: 12, paddingHorizontal: 20 },
  controlText: { fontSize: 18, fontWeight: '600' },
});
