import { CameraView, useCameraPermissions } from 'expo-camera';
import * as Device from 'expo-device';
import { Stack, router } from 'expo-router';
import { useRef, useState } from 'react';
import { StyleSheet, useWindowDimensions, View } from 'react-native';

import { baseUrl, pair, userMessage } from '../src/api/http';
import { Body, Button, Field, Message, Screen, Title } from '../src/components/ui';
import { formatIpInput, normalizeIpv4, portFromAddress } from '../src/protocol/ip';
import { parsePairingUri } from '../src/protocol/qr';
import { getPc, savePc } from '../src/storage/storage';

const DEFAULT_PORT = '8765';

type Target = { host: string; port: number };
type Credentials = { code: string } | { password: string };

export default function AddPc() {
  const window = useWindowDimensions();
  const [permission, requestPermission] = useCameraPermissions();
  const [mode, setMode] = useState<'qr' | 'manual'>('qr');
  const [host, setHost] = useState('');
  const [port, setPort] = useState(DEFAULT_PORT);
  const [password, setPassword] = useState('');
  const [deviceName, setDeviceName] = useState(Device.modelName ?? 'Celular Android');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const inFlight = useRef(false);
  // O ultimo QR que deu erro: a camera o le varias vezes por segundo, e cada tentativa
  // conta no limite de tentativas do PC.
  const failedQr = useRef<string | null>(null);

  async function connect(target: Target, credentials: Credentials, expectedAgentId?: string): Promise<boolean> {
    if (inFlight.current) return false;
    const name = deviceName.trim();
    if (!name) {
      setMessage('Digite um nome para este celular.');
      return false;
    }
    inFlight.current = true;
    setBusy(true);
    setMessage(null);
    try {
      const result = await pair(baseUrl(target.host, target.port), { device_name: name, ...credentials });
      if (expectedAgentId && result.agent.id !== expectedAgentId) {
        setMessage('O QR code não corresponde a este PC.');
        return false;
      }
      const previous = await getPc(result.agent.id).catch(() => null);
      await savePc({
        alias: previous?.alias,
        agentId: result.agent.id,
        name: result.agent.name,
        host: target.host,
        port: target.port,
        deviceId: result.device_id,
        token: result.token,
        addedAt: Date.now(),
      });
      router.replace(`/pc/${encodeURIComponent(result.agent.id)}`);
      return true;
    } catch (err) {
      setMessage(userMessage(err));
      return false;
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  function onScan({ data }: { data: string }) {
    if (inFlight.current || data === failedQr.current) return;
    const target = parsePairingUri(data);
    if (!target) {
      failedQr.current = data;
      setMessage('Este QR code não é do PcX Control.');
      return;
    }
    void connect({ host: target.host, port: target.port }, { code: target.code }, target.agentId).then((ok) => {
      if (!ok) failedQr.current = data;
    });
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

  // Com o celular deitado, um quadrado da largura da tela ficaria maior que a tela.
  const cameraMax = Math.round(window.height * 0.6);

  return (
    <Screen>
      <Stack.Screen options={{ title: 'Adicionar PC' }} />
      {mode === 'qr' ? (
        <>
          <Title>Escaneie o QR code</Title>
          <Body>No PC, abra o PcX Control e escolha “Parear celular”. Aponte a câmera para o código.</Body>
          {permission?.granted ? (
            <View testID="camera-box" style={[styles.camera, { maxWidth: cameraMax }]}>
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
          <Field
            label="IP do PC"
            value={host}
            onChangeText={(text) => {
              const pastedPort = portFromAddress(text);
              if (pastedPort) setPort(pastedPort);
              setHost((previous) => formatIpInput(text, previous));
            }}
            placeholder="192.168.0.10"
            keyboardType="decimal-pad"
          />
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
  camera: { width: '100%', aspectRatio: 1, alignSelf: 'center', borderRadius: 16, overflow: 'hidden' },
});
