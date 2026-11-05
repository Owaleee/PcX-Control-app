import { Linking, StyleSheet, View } from 'react-native';

import { RELEASES_URL } from '../protocol/compat';
import { Body, Button } from './ui';

/** Aviso de protocolo diferente: `app` = o PC e mais novo; `agent` = o PC e mais antigo. */
export function OutdatedNotice({ who, agentVersion }: { who: 'app' | 'agent'; agentVersion: string }) {
  return (
    <View style={styles.box}>
      {who === 'app' ? (
        <>
          <Body>Este PC usa uma versão mais nova do PcX Control. Atualize o app.</Body>
          <Button title="Baixar a versão nova" onPress={() => void Linking.openURL(RELEASES_URL)} />
        </>
      ) : (
        <Body>Este PC usa uma versão antiga do PcX Control. Atualize o programa no PC.</Body>
      )}
      <Body>{`Versão no PC: ${agentVersion}`}</Body>
    </View>
  );
}

const styles = StyleSheet.create({ box: { gap: 8 } });
