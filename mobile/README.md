# App Android do PcX Control

App em Expo (SDK 58), React Native e TypeScript. Pareia com o agente do PC por QR code ou
IP + senha e mostra os sensores em tempo real, inclusive no modo painel em paisagem.

## Estrutura

| Pasta | Conteúdo |
| --- | --- |
| `app/` | Telas (expo-router): Meus PCs, Adicionar PC, Aparência, Painel, Detalhe, Ajustes e Modo painel |
| `src/protocol/` | Tipos e validação de tudo que chega do agente, QR code e IP |
| `src/api/` | Cliente HTTP com mensagens de erro em português |
| `src/connection/` | `ConnectionManager`: WebSocket, reconexão e códigos de fechamento |
| `src/hooks/` | Conexão compartilhada por PC (`PcProvider`) e histórico das métricas |
| `src/storage/` | PCs pareados e tema no armazenamento seguro do Android |
| `src/theme/` | Temas Escuro, Claro e AMOLED e proteção contra burn-in |
| `__tests__/` | Testes (Jest), incluindo o contrato com o agente em `docs/protocol/fixtures` |

## Desenvolvimento com o Expo Go

1. Instale o **Expo Go** no celular (Play Store). Ele precisa ser compatível com o SDK 58.
2. No PC, dentro de `mobile/`:

```bash
npm ci
npx expo start --lan
```

3. No celular, abra o Expo Go e escaneie o QR code **do Expo** que aparece no terminal. Esse QR
   abre o app; o QR **do PcX Control** (impresso pelo agente) é lido dentro do app, na tela
   "Adicionar PC".

O celular e o PC precisam estar na mesma rede Wi-Fi.

## Verificações

```bash
npm run typecheck
npm run lint
npx jest
```

## Gerar o APK

Com uma conta Expo com acesso ao projeto:

```bash
npm install -g eas-cli
eas login
eas build -p android --profile preview
```

O perfil `preview` gera um APK para instalar direto no celular. O perfil `production` gera o
AAB da Play Store. O `versionCode` é controlado pelo EAS (`appVersionSource: remote`).

## Ícones

A fonte é `assets/icon.svg`. Depois de alterar o desenho, gere os PNGs com
`node scripts/render-icons.mjs`.
