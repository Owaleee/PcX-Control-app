// Mocks compartilhados das telas: roteador, camera, dispositivo.
import * as React from 'react';

export const routerMock = { push: jest.fn(), replace: jest.fn(), back: jest.fn(), dismissTo: jest.fn() };
export const paramsMock: { current: Record<string, string> } = { current: {} };

export function expoRouterMock() {
  return {
    router: routerMock,
    useRouter: () => routerMock,
    useLocalSearchParams: () => paramsMock.current,
    useFocusEffect: (effect: () => void | (() => void)) => React.useEffect(effect, [effect]),
    Stack: { Screen: () => null },
    Link: ({ children }: { children: React.ReactNode }) => children,
  };
}

export function resetRouter() {
  Object.values(routerMock).forEach((fn) => fn.mockReset());
}
