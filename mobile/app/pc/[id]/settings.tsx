import { Stack, router } from 'expo-router';
import { useState } from 'react';
import { Alert } from 'react-native';

import { baseUrl, forgetMe, getInfo, isApiError, userMessage } from '../../../src/api/http';
import { Body, Button, Field, Message, Screen } from '../../../src/components/ui';
import { usePc } from '../../../src/hooks/PcContext';
import { normalizeIpv4 } from '../../../src/protocol/ip';
import { removePc, updatePc } from '../../../src/storage/storage';

export default function PcSettings() {
  const { pc, stop, refresh } = usePc();
  const [alias, setAlias] = useState(pc.alias ?? '');
  const [host, setHost] = useState(pc.host);
  const [port, setPort] = useState(String(pc.port));
  const [aliasMessage, setAliasMessage] = useState<string | null>(null);
  const [address, setAddress] = useState<{ text: string; tone: 'info' | 'error' } | null>(null);
  const [checking, setChecking] = useState(false);

  async function saveAlias() {
    await updatePc(pc.agentId, { alias: alias.trim() || undefined });
    refresh();
    setAliasMessage('Apelido salvo.');
  }

  // O token vale para o PC (agent_id), nao para o IP: trocar o endereco nao exige parear de novo.
  async function saveAddress() {
    const ip = normalizeIpv4(host);
    if (!ip) {
      setAddress({ text: 'Digite o IP do PC, como 192.168.0.10.', tone: 'error' });
      return;
    }
    const portNumber = /^\d+$/.test(port.trim()) ? Number(port.trim()) : NaN;
    if (!(portNumber >= 1 && portNumber <= 65535)) {
      setAddress({ text: 'Porta inválida. O padrão é 8765.', tone: 'error' });
      return;
    }
    setChecking(true);
    try {
      const info = await getInfo(baseUrl(ip, portNumber));
      if (info.agent_id !== pc.agentId) {
        setAddress({ text: 'Esse endereço é de outro PC.', tone: 'error' });
        return;
      }
      await updatePc(pc.agentId, { host: ip, port: portNumber });
      refresh();
      setAddress({ text: 'Endereço salvo.', tone: 'info' });
    } catch (err) {
      setAddress({ text: userMessage(err), tone: 'error' });
    } finally {
      setChecking(false);
    }
  }

  async function removeLocal() {
    await removePc(pc.agentId);
    router.dismissTo('/');
  }

  async function forget() {
    stop(); // sem isso, o 4401 da propria revogacao viraria o alerta de "desconectado no PC"
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
      <Body>{pc.name}</Body>
      <Field label="Apelido" value={alias} onChangeText={setAlias} placeholder={pc.name} maxLength={40} />
      <Button title="Salvar apelido" variant="secondary" onPress={() => void saveAlias()} />
      <Message text={aliasMessage} tone="info" />
      <Body>Se o IP do PC mudar, atualize aqui. Não é preciso parear de novo.</Body>
      <Field label="IP do PC" value={host} onChangeText={setHost} placeholder="192.168.0.10" />
      <Field label="Porta" value={port} onChangeText={setPort} keyboardType="number-pad" maxLength={5} />
      <Button
        title={checking ? 'Verificando…' : 'Salvar endereço'}
        variant="secondary"
        onPress={() => void saveAddress()}
        disabled={checking}
      />
      <Message text={address?.text ?? null} tone={address?.tone} />
      <Button title="Desconectar" variant="secondary" onPress={() => router.dismissTo('/')} />
      <Button title="Esquecer este PC" variant="danger" onPress={confirmForget} />
    </Screen>
  );
}
