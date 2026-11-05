import { StyleSheet, View } from 'react-native';

import { Body } from './ui';

/** Para uma tela que depende de algo que o agente instalado ainda nao tem. */
export function NeedsAgentUpdate({ agentVersion }: { agentVersion: string }) {
  return (
    <View style={styles.box}>
      <Body>Atualize o PcX Control no PC para usar isto.</Body>
      <Body>{`Versão no PC: ${agentVersion}`}</Body>
    </View>
  );
}

const styles = StyleSheet.create({ box: { gap: 8 } });
