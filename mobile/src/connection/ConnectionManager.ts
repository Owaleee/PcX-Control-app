// Conexao WebSocket com o agente: autenticacao, reconexao e os codigos de fechamento do protocolo.
import type { Hello, SnapshotMessage } from '../protocol/types';
import { checkProtocol, helloProtocol } from '../protocol/compat';
import { parseHello, parseSnapshotMessage } from '../protocol/validate';
import { backoffDelay } from './backoff';

export type SocketLike = {
  send(data: string): void;
  close(code?: number, reason?: string): void;
  onopen: (() => void) | null;
  onmessage: ((e: { data: unknown }) => void) | null;
  onclose: ((e: { code: number; reason: string }) => void) | null;
  onerror: ((e: unknown) => void) | null;
};

export type ConnState =
  | { kind: 'connecting' }
  | { kind: 'connected'; hello: Hello }
  | { kind: 'reconnecting'; attempt: number; retryInMs: number }
  | { kind: 'busy'; activeDevice: string }
  | { kind: 'taken_over' }
  | { kind: 'revoked' }
  | { kind: 'outdated'; who: 'app' | 'agent'; agentVersion: string }
  | { kind: 'stopped' };

export const CLOSE_REVOKED = 4401;
export const CLOSE_TAKEN_OVER = 4409;
export const CLOSE_BUSY = 4423;
const HELLO_TIMEOUT_MS = 10_000;
/** O agente manda 1 leitura por segundo: 8 s de silencio significam conexao morta. */
export const SILENCE_TIMEOUT_MS = 8_000;

type Options = {
  url: string;
  token: string;
  createSocket?: (url: string) => SocketLike;
  random?: () => number;
};

export class ConnectionManager {
  private readonly url: string;
  private readonly token: string;
  private readonly createSocket: (url: string) => SocketLike;
  private readonly random: () => number;
  private socket: SocketLike | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private helloTimer: ReturnType<typeof setTimeout> | null = null;
  private silenceTimer: ReturnType<typeof setTimeout> | null = null;
  private attempt = 0;
  private takeover = false;
  private stateListeners = new Set<(s: ConnState) => void>();
  private snapshotListeners = new Set<(m: SnapshotMessage) => void>();
  private current: ConnState = { kind: 'stopped' };
  private last: SnapshotMessage | null = null;

  constructor(options: Options) {
    this.url = options.url;
    this.token = options.token;
    this.createSocket = options.createSocket ?? ((url) => new WebSocket(url) as unknown as SocketLike);
    this.random = options.random ?? Math.random;
  }

  get state(): ConnState {
    return this.current;
  }

  get lastSnapshot(): SnapshotMessage | null {
    return this.last;
  }

  onState(listener: (s: ConnState) => void): () => void {
    this.stateListeners.add(listener);
    return () => this.stateListeners.delete(listener);
  }

  onSnapshot(listener: (m: SnapshotMessage) => void): () => void {
    this.snapshotListeners.add(listener);
    return () => this.snapshotListeners.delete(listener);
  }

  start(options: { takeover?: boolean } = {}): void {
    this.teardown();
    this.takeover = options.takeover === true;
    this.attempt = 0;
    this.setState({ kind: 'connecting' });
    this.open();
  }

  stop(): void {
    this.teardown();
    this.setState({ kind: 'stopped' });
  }

  private setState(state: ConnState): void {
    this.current = state;
    for (const listener of [...this.stateListeners]) listener(state);
  }

  private clearTimers(): void {
    if (this.retryTimer) clearTimeout(this.retryTimer);
    if (this.helloTimer) clearTimeout(this.helloTimer);
    if (this.silenceTimer) clearTimeout(this.silenceTimer);
    this.retryTimer = null;
    this.helloTimer = null;
    this.silenceTimer = null;
  }

  /** Fecha o socket atual sem que os eventos atrasados dele afetem o estado. */
  private abandonSocket(code = 1000): void {
    const socket = this.socket;
    this.socket = null;
    if (!socket) return;
    socket.onopen = null;
    socket.onmessage = null;
    socket.onclose = null;
    socket.onerror = null;
    try {
      socket.close(code);
    } catch {
      // o socket pode ja estar fechado
    }
  }

  private teardown(): void {
    this.clearTimers();
    this.abandonSocket();
  }

  private open(): void {
    const socket = this.createSocket(this.url);
    this.socket = socket;
    socket.onopen = () => {
      socket.send(JSON.stringify({ type: 'auth', token: this.token, takeover: this.takeover }));
    };
    socket.onmessage = (event) => this.handleMessage(event.data);
    socket.onclose = (event) => this.handleClose(socket, event.code, event.reason);
    socket.onerror = () => undefined; // o onclose sempre vem em seguida
    this.helloTimer = setTimeout(() => {
      this.abandonSocket(4000);
      this.scheduleRetry();
    }, HELLO_TIMEOUT_MS);
  }

  /** Conexao meio-aberta (PC suspenso, roteador reiniciado) nao gera onclose: o vigia detecta. */
  private armSilenceWatch(): void {
    if (this.silenceTimer) clearTimeout(this.silenceTimer);
    this.silenceTimer = setTimeout(() => {
      this.silenceTimer = null;
      this.abandonSocket(4000);
      this.scheduleRetry();
    }, SILENCE_TIMEOUT_MS);
  }

  private handleMessage(data: unknown): void {
    if (typeof data !== 'string') return;
    let message: unknown;
    try {
      message = JSON.parse(data);
    } catch {
      return;
    }
    const type = (message as { type?: unknown } | null)?.type;
    if (type === 'hello') {
      const protocol = helloProtocol(message);
      const side = protocol === null ? 'ok' : checkProtocol(protocol);
      if (side !== 'ok') {
        this.markOutdated(side, message);
        return;
      }
      const hello = parseHello(message);
      if (!hello) return;
      if (this.helloTimer) clearTimeout(this.helloTimer);
      this.helloTimer = null;
      this.attempt = 0;
      this.takeover = false;
      this.armSilenceWatch();
      this.setState({ kind: 'connected', hello });
    } else if (type === 'snapshot') {
      const snapshot = parseSnapshotMessage(message);
      if (!snapshot) return;
      this.armSilenceWatch();
      this.last = snapshot;
      for (const listener of [...this.snapshotListeners]) listener(snapshot);
    }
  }

  /** Protocolo diferente: reconectar nao resolve, so atualizar o app ou o agente. */
  private markOutdated(who: 'app' | 'agent', hello: unknown): void {
    const agent = (hello as { agent?: { version?: unknown } | null }).agent;
    const version = typeof agent?.version === 'string' && agent.version ? agent.version : 'desconhecida';
    this.teardown();
    this.setState({ kind: 'outdated', who, agentVersion: version });
  }

  private handleClose(socket: SocketLike, code: number, reason: string): void {
    if (socket !== this.socket) return;
    this.socket = null;
    this.clearTimers();
    if (code === CLOSE_REVOKED) {
      this.setState({ kind: 'revoked' });
    } else if (code === CLOSE_TAKEN_OVER) {
      this.setState({ kind: 'taken_over' });
    } else if (code === CLOSE_BUSY) {
      this.setState({ kind: 'busy', activeDevice: reason || 'outro aparelho' });
    } else {
      this.scheduleRetry();
    }
  }

  private scheduleRetry(): void {
    this.clearTimers();
    const delay = backoffDelay(this.attempt, this.random);
    this.attempt += 1;
    this.setState({ kind: 'reconnecting', attempt: this.attempt, retryInMs: delay });
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      this.open();
    }, delay);
  }
}
