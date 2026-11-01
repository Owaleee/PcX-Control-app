// Pecas basicas de interface, sempre no tema atual.
import type { ReactNode } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type TextInputProps,
} from 'react-native';

import { useTheme } from '../theme/ThemeProvider';

export function Screen({ children, scroll = true }: { children: ReactNode; scroll?: boolean }) {
  const { theme } = useTheme();
  if (!scroll) {
    return <View style={[styles.screen, styles.content, { backgroundColor: theme.background }]}>{children}</View>;
  }
  return (
    <ScrollView
      style={[styles.screen, { backgroundColor: theme.background }]}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
    >
      {children}
    </ScrollView>
  );
}

type ButtonProps = {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'link' | 'danger';
  disabled?: boolean;
};

export function Button({ title, onPress, variant = 'primary', disabled }: ButtonProps) {
  const { theme } = useTheme();
  const filled = variant === 'primary' || variant === 'danger';
  const background = variant === 'primary' ? theme.accent : variant === 'danger' ? theme.danger : 'transparent';
  const color = filled ? theme.background : variant === 'link' ? theme.accent : theme.text;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: Boolean(disabled) }}
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.button,
        variant === 'link' ? styles.link : null,
        {
          backgroundColor: background,
          borderColor: variant === 'secondary' ? theme.border : 'transparent',
          opacity: disabled ? 0.5 : pressed ? 0.8 : 1,
        },
      ]}
    >
      <Text style={[styles.buttonText, { color }]}>{title}</Text>
    </Pressable>
  );
}

export function Field({ label, ...props }: TextInputProps & { label: string }) {
  const { theme } = useTheme();
  return (
    <View style={styles.field}>
      <Text style={[styles.label, { color: theme.textMuted }]}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={theme.textMuted}
        autoCapitalize="none"
        autoCorrect={false}
        {...props}
        style={[styles.input, { color: theme.text, borderColor: theme.border, backgroundColor: theme.surface }]}
      />
    </View>
  );
}

export function Message({ text, tone = 'error' }: { text: string | null; tone?: 'error' | 'info' }) {
  const { theme } = useTheme();
  if (!text) return null;
  return (
    <Text accessibilityLiveRegion="polite" style={[styles.message, { color: tone === 'error' ? theme.danger : theme.textMuted }]}>
      {text}
    </Text>
  );
}

export function Title({ children }: { children: ReactNode }) {
  const { theme } = useTheme();
  return <Text style={[styles.title, { color: theme.text }]}>{children}</Text>;
}

export function Body({ children }: { children: ReactNode }) {
  const { theme } = useTheme();
  return <Text style={[styles.body, { color: theme.textMuted }]}>{children}</Text>;
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  content: { padding: 20, gap: 14, width: '100%', maxWidth: 640, alignSelf: 'center' },
  button: { borderRadius: 12, borderWidth: 1, paddingVertical: 14, paddingHorizontal: 16, alignItems: 'center' },
  link: { paddingVertical: 8 },
  buttonText: { fontSize: 16, fontWeight: '600' },
  field: { gap: 6 },
  label: { fontSize: 14 },
  input: { borderWidth: 1, borderRadius: 10, padding: 12, fontSize: 16 },
  message: { fontSize: 15 },
  title: { fontSize: 22, fontWeight: '700' },
  body: { fontSize: 15, lineHeight: 21 },
});
