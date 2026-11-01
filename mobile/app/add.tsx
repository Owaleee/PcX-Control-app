import { CameraView, useCameraPermissions } from 'expo-camera';
import * as Device from 'expo-device';
import { Stack, router } from 'expo-router';
import { useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { baseUrl, pair, userMessage } from '../src/api/http';
import { Body, Button, Field, Message, Screen, Title } from '../src/components/ui';
import { normalizeIpv4 } from '../src/protocol/ip';
import { parsePairingUri } from '../src/protocol/qr';
import { savePc } from '../src/storage/storage';

const DEFAULT_PORT = '8765';

type Target = { host: string; port: number };
type Credentials = { code: string } | { password: string };

export default function AddPc() {
  const [permission, requestPermission] = useCameraPermissions();
  const [mode, setMode] = useState<'qr' | 'manual'>('qr');
  const [host, setHost] = useState('');
  const [port, setPort] = useState(DEFAULT_PORT);
  const [password, setPassword] = useState('');
  const [deviceName, setDeviceName] = useState(Device.modelName ?? 'Celular Android');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const inFlight = useRef(false);

  async function connect(target: Target, credentials: Credentials, expectedAgentId?: string) {
    if (inFlight.current) return;
    const name = deviceName.trim();
    if (!name) {
      setMessage('Digite um nome para este celular.');
      return;
    }
    inFlight.current = true;
    setBusy(true);
    setMessage(null);
    try {
      const result = await pair(baseUrl(target.host, target.port), { device_name: name, ...credentials });
      if (expectedAgentId && result.agent.id !== expectedAgentId) {
        setMessage('O QR code não corresponde a este PC.');
        return;
      }
      await savePc({
        agentId: result.agent.id,
        name: result.agent.name,
        host: target.host,
        port: target.port,
        deviceId: result.device_id,
        token: result.token,
        addedAt: Date.now(),
      });
      router.replace(`/pc/${encodeURIComponent(result.agent.id)}`);
    } catch (err) {
      setMessage(userMessage(err));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  function onScan({ data }: { data: string }) {
    if (inFlight.current) return;
    const target = parsePairingUri(data);
    if (!target) {
      setMessage('Este QR code não é do PcX Control.');
      return;
    }
    void connect({ host: target.host, port: target.port }, { code: target.code }, target.agentId);
  }

  function onManual() {
    const ip = normalizeIpv4(host);
    if (!ip) {
      setMessage('Digite o IP do PC, como 192.168.0.10.');
      return;
    }
    const portNumber = /^\d+$/.test(port.trim()) ? Number(port.trim()) : NaN;
    if (!(portNumber >= 1 && portNumber <= 65535)) {
      setMessage('Porta inválida. O padrão é 8765.');
      return;
    }
    if (!password) {
      setMessage('Digite a senha do PC.');
      return;
    }
    void connect({ host: ip, port: portNumber }, { password });
  }

  return (
    <Screen>
      <Stack.Screen options={{ title: 'Adicionar PC' }} />
      {mode === 'qr' ? (
        <>
          <Title>Escaneie o QR code</Title>
          <Body>No PC, abra o PcX Control e escolha “Parear celular”. Aponte a câmera para o código.</Body>
          {permission?.granted ? (
            <View style={styles.camera}>
              <CameraView
                style={StyleSheet.absoluteFill}
                facing="back"
                barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
                onBarcodeScanned={busy ? undefined : onScan}
              />
            </View>
          ) : permission ? (
            <>
              <Body>Permita o uso da câmera para ler o QR code.</Body>
              <Button title="Permitir câmera" variant="secondary" onPress={() => void requestPermission()} />
            </>
          ) : null}
          <Message text={message} />
          <Field label="Nome deste celular" value={deviceName} onChangeText={setDeviceName} maxLength={64} />
          <Button title="Digitar IP e senha" variant="link" onPress={() => { setMode('manual'); setMessage(null); }} />
        </>
      ) : (
        <>
          <Title>Conectar por IP e senha</Title>
          <Body>O IP aparece no PcX Control do PC. Use a senha criada na instalação.</Body>
          <Field label="IP do PC" value={host} onChangeText={setHost} placeholder="192.168.0.10" keyboardType="default" />
          <Field label="Porta" value={port} onChangeText={setPort} keyboardType="number-pad" maxLength={5} />
          <Field label="Senha do PC" value={password} onChangeText={setPassword} secureTextEntry />
          <Field label="Nome deste celular" value={deviceName} onChangeText={setDeviceName} maxLength={64} />
          <Message text={message} />
          <Button title={busy ? 'Conectando…' : 'Conectar'} onPress={onManual} disabled={busy} />
          <Button title="Ler QR code" variant="link" onPress={() => { setMode('qr'); setMessage(null); }} />
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  camera: { width: '100%', aspectRatio: 1, borderRadius: 16, overflow: 'hidden' },
});
