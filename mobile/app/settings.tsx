import { Stack } from 'expo-router';
import { Pressable, StyleSheet, Switch, Text, View } from 'react-native';

import { Body, Screen, Title } from '../src/components/ui';
import { THEME_NAMES, type ThemeName } from '../src/theme/names';
import { useTheme } from '../src/theme/ThemeProvider';
import { THEMES } from '../src/theme/themes';

const LABELS: Record<ThemeName, { title: string; description: string }> = {
  dark: { title: 'Escuro', description: 'Fundo azul-escuro, confortável à noite.' },
  light: { title: 'Claro', description: 'Fundo claro, bom em ambientes iluminados.' },
  amoled: { title: 'AMOLED', description: 'Preto puro. Economiza bateria em telas OLED e AMOLED.' },
};

export default function Settings() {
  const { theme, name, setName, precise, setPrecise } = useTheme();
  return (
    <Screen>
      <Stack.Screen options={{ title: 'Configurações' }} />
      <Title>Aparência</Title>
      <Body>O tema vale para o app inteiro, inclusive o modo painel.</Body>
      {THEME_NAMES.map((option) => {
        const preview = THEMES[option];
        const selected = option === name;
        return (
          <Pressable
            key={option}
            accessibilityRole="radio"
            accessibilityLabel={LABELS[option].title}
            accessibilityState={{ checked: selected }}
            onPress={() => setName(option)}
            style={[
              styles.option,
              { backgroundColor: theme.surface, borderColor: selected ? theme.accent : theme.border },
            ]}
          >
            <View style={[styles.swatch, { backgroundColor: preview.background, borderColor: preview.border }]}>
              <View style={[styles.swatchBar, { backgroundColor: preview.accent }]} />
            </View>
            <View style={styles.texts}>
              <Text style={[styles.title, { color: theme.text }]}>{LABELS[option].title}</Text>
              <Text style={[styles.description, { color: theme.textMuted }]}>{LABELS[option].description}</Text>
            </View>
          </Pressable>
        );
      })}
      <Title>Números</Title>
      <View style={[styles.row, { backgroundColor: theme.surface, borderColor: theme.border }]}>
        <View style={styles.texts}>
          <Text style={[styles.title, { color: theme.text }]}>Números precisos</Text>
          <Text style={[styles.description, { color: theme.textMuted }]}>
            Mostra uma casa decimal nos percentuais (50,5% em vez de 51%).
          </Text>
        </View>
        <Switch
          accessibilityLabel="Números precisos"
          accessibilityRole="switch"
          value={precise}
          onValueChange={setPrecise}
          trackColor={{ true: theme.accent, false: theme.track }}
          thumbColor={theme.text}
        />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 14, borderWidth: 1, borderRadius: 14, padding: 14 },
  option: { flexDirection: 'row', alignItems: 'center', gap: 14, borderWidth: 2, borderRadius: 14, padding: 14 },
  swatch: { width: 52, height: 52, borderRadius: 10, borderWidth: 1, justifyContent: 'flex-end', padding: 8 },
  swatchBar: { height: 6, borderRadius: 3 },
  texts: { flex: 1, gap: 2 },
  title: { fontSize: 17, fontWeight: '700' },
  description: { fontSize: 14 },
});
