import { Stack, router } from 'expo-router';
import { useState } from 'react';
import { Alert } from 'react-native';

import { baseUrl, forgetMe, isApiError } from '../../../src/api/http';
import { Body, Button, Field, Message, Screen } from '../../../src/components/ui';
import { usePc } from '../../../src/hooks/PcContext';
import { removePc, updatePc } from '../../../src/storage/storage';

export default function PcSettings() {
  const { pc } = usePc();
  const [alias, setAlias] = useState(pc.alias ?? '');
  const [saved, setSaved] = useState<string | null>(null);

  async function saveAlias() {
    await updatePc(pc.agentId, { alias: alias.trim() || undefined });
    setSaved('Apelido salvo.');
  }

  async function removeLocal() {
    await removePc(pc.agentId);
    router.replace('/');
  }

  async function forget() {
    try {
      await forgetMe(baseUrl(pc.host, pc.port), pc.token);
      await removeLocal();
    } catch (err) {
      if (isApiError(err) && err.kind === 'invalid_token') {
        await removeLocal(); // o PC ja nao reconhece este celular
        return;
      }
      Alert.alert('PC fora do ar', 'Não foi possível falar com o PC. Remover só deste celular?', [
        { text: 'Cancelar', style: 'cancel' },
        { text: 'Remover', style: 'destructive', onPress: () => void removeLocal() },
      ]);
    }
  }

  function confirmForget() {
    Alert.alert('Esquecer este PC?', 'Será preciso parear de novo para usar este PC.', [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Esquecer', style: 'destructive', onPress: () => void forget() },
    ]);
  }

  return (
    <Screen>
      <Stack.Screen options={{ title: 'Ajustes do PC' }} />
      <Body>{`${pc.name} · ${pc.host}:${pc.port}`}</Body>
      <Field label="Apelido" value={alias} onChangeText={setAlias} placeholder={pc.name} maxLength={40} />
      <Button title="Salvar apelido" variant="secondary" onPress={() => void saveAlias()} />
      <Message text={saved} tone="info" />
      <Button title="Desconectar" variant="secondary" onPress={() => router.replace('/')} />
      <Button title="Esquecer este PC" variant="danger" onPress={confirmForget} />
    </Screen>
  );
}
