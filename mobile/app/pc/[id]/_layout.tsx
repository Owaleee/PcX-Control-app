import { Stack, useLocalSearchParams } from 'expo-router';

import { PcProvider } from '../../../src/hooks/PcContext';
import { useTheme } from '../../../src/theme/ThemeProvider';

export default function PcLayout() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { theme } = useTheme();
  return (
    <PcProvider agentId={String(id)}>
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: theme.background },
          headerTintColor: theme.text,
          headerShadowVisible: false,
          contentStyle: { backgroundColor: theme.background },
        }}
      >
        <Stack.Screen name="panel" options={{ headerShown: false, animation: 'fade' }} />
      </Stack>
    </PcProvider>
  );
}
