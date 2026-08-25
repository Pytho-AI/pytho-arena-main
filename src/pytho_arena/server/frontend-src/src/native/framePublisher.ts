import { sceneStateToFrameV1, type ArenaSceneState, type NativeFrameV1 } from "../arena";

export const FRAME_V1_LOOPBACK_URL = "ws://127.0.0.1:46000/";
export const FRAME_V1_PUBLISH_HZ = 20;
export const FRAME_V1_BUFFER_HIGH_WATER_BYTES = 1_048_576;

export type NativeLinkStatus = "offline" | "connecting" | "linked" | "error";

interface SocketBoundary {
  readonly readyState: number;
  readonly bufferedAmount?: number;
  onopen: ((event: Event) => void) | null;
  onclose: ((event: CloseEvent) => void) | null;
  onerror: ((event: Event) => void) | null;
  send(payload: string): void;
  close(): void;
}

export type SocketFactory = (url: string) => SocketBoundary;

export class FrameV1Publisher {
  private socket: SocketBoundary | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private running = false;
  private runId = "";
  private sequence = 0;
  private scene: ArenaSceneState | null = null;

  constructor(
    private readonly socketFactory: SocketFactory,
    private readonly onStatus: (status: NativeLinkStatus) => void = () => undefined,
    private readonly onError: (message: string) => void = () => undefined,
  ) {}

  start(): void {
    if (this.running) return;
    this.running = true;
    this.connect();
    this.timer = setInterval(() => this.publishCurrent(), 1_000 / FRAME_V1_PUBLISH_HZ);
  }

  stop(): void {
    this.running = false;
    if (this.timer) clearInterval(this.timer);
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.timer = null;
    this.reconnectTimer = null;
    this.socket?.close();
    this.socket = null;
    this.onStatus("offline");
  }

  setFrame(runId: string, scene: ArenaSceneState, publishNow = false): void {
    if (runId !== this.runId) {
      this.runId = runId;
      this.sequence = 0;
    }
    this.scene = scene;
    if (publishNow) this.publishCurrent();
  }

  publishCurrent(): NativeFrameV1 | null {
    if (!this.scene || !this.runId || this.socket?.readyState !== 1) return null;
    if ((this.socket.bufferedAmount ?? 0) > FRAME_V1_BUFFER_HIGH_WATER_BYTES) return null;
    try {
      const frame = sceneStateToFrameV1(this.runId, this.sequence, this.scene);
      this.socket.send(JSON.stringify(frame));
      this.sequence += 1;
      this.onError("");
      return frame;
    } catch (error) {
      this.onStatus("error");
      this.onError((error as Error).message);
      return null;
    }
  }

  private connect(): void {
    if (!this.running) return;
    this.onStatus("connecting");
    try {
      const socket = this.socketFactory(FRAME_V1_LOOPBACK_URL);
      this.socket = socket;
      socket.onopen = () => {
        this.onStatus("linked");
        this.publishCurrent();
      };
      socket.onerror = () => this.onStatus("error");
      socket.onclose = () => {
        if (this.socket === socket) this.socket = null;
        if (!this.running) return;
        this.onStatus("offline");
        this.reconnectTimer = setTimeout(() => this.connect(), 2_000);
      };
    } catch {
      this.onStatus("error");
      this.reconnectTimer = setTimeout(() => this.connect(), 2_000);
    }
  }
}
