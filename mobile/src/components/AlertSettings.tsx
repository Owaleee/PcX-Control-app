// Secao "Alertas" das configuracoes: liga e desliga as cores e ajusta os limites.
import { useState } from 'react';
import { StyleSheet, Switch, Text, View } from 'react-native';

import { DEFAULT_LIMITS, type LimitsDraft, toDraft, validateDraft } from '../alerts/levels';
import { useTheme } from '../theme/ThemeProvider';
import { Body, Button, Field, Message, Title } from './ui';

const FIELDS: { key: keyof LimitsDraft; label: string }[] = [
  { key: 'usageHigh', label: 'Uso alto a partir de (%)' },
  { key: 'usageCritical', label: 'Uso crítico a partir de (%)' },
  { key: 'tempHigh', label: 'Temperatura alta a partir de (°C)' },
  { key: 'tempCritical', label: 'Temperatura crítica a partir de (°C)' },
];

export function AlertSettings() {
  const { theme, alerts, setAlerts } = useTheme();
  const [draft, setDraft] = useState<LimitsDraft>(() => toDraft(alerts));
  const [error, setError] = useState<string | null>(null);

  // Os limites salvos chegam depois da primeira tela (ou mudam pelo "Restaurar padrão"):
  // o rascunho acompanha. Estado derivado, ajustado durante a renderização.
  const [syncedFrom, setSyncedFrom] = useState(alerts);
  if (syncedFrom !== alerts) {
    setSyncedFrom(alerts);
    setDraft(toDraft(alerts));
  }

  const change = (key: keyof LimitsDraft, text: string) => {
    const next = { ...draft, [key]: text };
    setDraft(next);
    const checked = validateDraft(next, alerts.enabled);
    setError(checked.error);
    // So salva o que e valido; com erro, o que esta salvo continua valendo.
    if (checked.limits) setAlerts(checked.limits);
  };

  const restore = () => {
    setError(null);
    setAlerts({ ...DEFAULT_LIMITS, enabled: alerts.enabled });
  };

  return (
    <>
      <Title>Alertas</Title>
      <View style={[styles.row, { backgroundColor: theme.surface, borderColor: theme.border }]}>
        <View style={styles.texts}>
          <Text style={[styles.title, { color: theme.text }]}>Cores de alerta</Text>
          <Text style={[styles.description, { color: theme.textMuted }]}>
            Destaca em amarelo (alto) e vermelho (crítico) o uso e a temperatura, com um selo no cartão.
          </Text>
        </View>
        <Switch
          accessibilityLabel="Cores de alerta"
          accessibilityRole="switch"
          value={alerts.enabled}
          onValueChange={(enabled) => setAlerts({ ...alerts, enabled })}
          trackColor={{ true: theme.accent, false: theme.track }}
          thumbColor={theme.text}
        />
      </View>
      {alerts.enabled ? (
        <View style={styles.limits}>
          <Body>Vale para CPU, GPU, VRAM, memória e discos. A temperatura é a da placa de vídeo.</Body>
          {FIELDS.map((field) => (
            <Field
              key={field.key}
              label={field.label}
              value={draft[field.key]}
              onChangeText={(text) => change(field.key, text)}
              keyboardType="number-pad"
              maxLength={3}
            />
          ))}
          <Message text={error} />
          <Button title="Restaurar padrão" variant="secondary" onPress={restore} />
        </View>
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 14, borderWidth: 1, borderRadius: 14, padding: 14 },
  texts: { flex: 1, gap: 2 },
  title: { fontSize: 17, fontWeight: '700' },
  description: { fontSize: 14 },
  limits: { gap: 14 },
});
