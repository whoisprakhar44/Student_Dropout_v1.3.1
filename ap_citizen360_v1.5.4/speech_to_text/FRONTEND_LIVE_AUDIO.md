# Live Audio Transcription — Frontend Integration Guide

The backend exposes a **WebSocket endpoint** for live microphone transcription that any frontend framework can use:

```
ws://<backend-host>/ws/transcribe/live
wss://<backend-host>/ws/transcribe/live   ← if served over HTTPS
```

---

## CORS

By default the backend allows **any origin** (`CORS_ORIGINS=["*"]`).
To restrict in production, set the env variable before starting the server:

```bash
CORS_ORIGINS='["https://your-app.example.com"]' python3 -m uvicorn app.main:app ...
```

---

## Audio Requirements

The backend only accepts raw PCM — **no containers** (no WebM, no WAV, no MP3):

| Property | Value |
|---|---|
| Channels | 1 (mono) |
| Sample rate | 16 000 Hz |
| Bit depth | 16-bit signed little-endian |
| Format | Raw `ArrayBuffer` — NOT a container format |

---

## WebSocket Protocol

### 1 — Open socket and send `start`

```ts
const socket = new WebSocket('ws://<backend-host>/ws/transcribe/live');
socket.binaryType = 'arraybuffer';

socket.onopen = () => {
  socket.send(JSON.stringify({ type: 'start', sample_rate: 16000 }));
};
```

### 2 — Wait for `ready`

The backend responds once the model is ready:

```json
{ "type": "ready" }
```

### 3 — Stream binary PCM chunks

Send raw 16-bit PCM `ArrayBuffer` frames as frequently as you like (every 100–500 ms recommended):

```ts
socket.send(pcmArrayBuffer);   // ArrayBuffer of int16 samples
```

### 4 — Receive transcription events

```ts
socket.onmessage = (message: MessageEvent) => {
  const event: LiveTranscriptionEvent = JSON.parse(message.data as string);

  switch (event.type) {
    case 'ready':   /* model loaded, streaming can begin */ break;
    case 'partial': /* incremental transcription update  */ break;
    case 'final':   /* complete transcript after stop    */ break;
    case 'error':   /* backend error detail              */ break;
  }
};
```

#### Event types (TypeScript)

```ts
type LiveTranscriptionEvent =
  | { type: 'ready' }
  | {
      type: 'partial';
      text: string;
      language: string;
      duration: number | null;
      segments: Array<{ id: number; start: number; end: number; text: string }>;
    }
  | { type: 'final'; text: string }
  | { type: 'error'; detail: string };
```

### 5 — Stop recording

```ts
// flush remaining audio and close cleanly
socket.send(JSON.stringify({ type: 'stop' }));
```

The backend will:
1. Transcribe any buffered audio still in the queue
2. Send a `{ type: 'final', text: '...' }` event with the complete session transcript
3. Close the WebSocket with code `1000`

---

## Angular Service (complete example)

```ts
// live-transcription.service.ts
import { Injectable, NgZone, OnDestroy } from '@angular/core';
import { Subject, BehaviorSubject } from 'rxjs';

export interface TranscriptEvent {
  type: 'partial' | 'final' | 'error';
  text?: string;
  detail?: string;
}

@Injectable({ providedIn: 'root' })
export class LiveTranscriptionService implements OnDestroy {
  private readonly SAMPLE_RATE = 16_000;
  private readonly SEND_INTERVAL_MS = 250;

  private socket: WebSocket | null = null;
  private audioContext: AudioContext | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private processor: ScriptProcessorNode | null = null;
  private mediaStream: MediaStream | null = null;
  private sendTimer: ReturnType<typeof setInterval> | null = null;
  private pendingSamples: Float32Array[] = [];
  private stopTimeout: ReturnType<typeof setTimeout> | null = null;

  readonly events$ = new Subject<TranscriptEvent>();
  readonly status$ = new BehaviorSubject<string>('idle');

  constructor(private ngZone: NgZone) {}

  async start(backendWsUrl: string): Promise<void> {
    this.status$.next('connecting');

    this.socket = new WebSocket(backendWsUrl);
    this.socket.binaryType = 'arraybuffer';

    await this.waitForOpen(this.socket);

    this.socket.onmessage = (msg) => this.ngZone.run(() => this.onMessage(msg));
    this.socket.onclose   = ()    => this.ngZone.run(() => this.onClose());
    this.socket.onerror   = ()    => this.ngZone.run(() => this.status$.next('error'));

    this.socket.send(JSON.stringify({ type: 'start', sample_rate: this.SAMPLE_RATE }));

    this.mediaStream  = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.audioContext = new AudioContext();
    this.source       = this.audioContext.createMediaStreamSource(this.mediaStream);
    this.processor    = this.audioContext.createScriptProcessor(4096, 1, 1);

    this.processor.onaudioprocess = (e) => {
      const input    = e.inputBuffer.getChannelData(0);
      const resampled = this.resample(input, this.audioContext!.sampleRate, this.SAMPLE_RATE);
      this.pendingSamples.push(resampled);
    };

    this.source.connect(this.processor);
    this.processor.connect(this.audioContext.destination);
    this.sendTimer = setInterval(() => this.flush(), this.SEND_INTERVAL_MS);
    this.status$.next('listening');
  }

  stop(): void {
    this.status$.next('stopping');
    this.flush();  // send any buffered samples immediately

    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type: 'stop' }));
    } else {
      this.cleanup();
      return;
    }

    this.cleanupAudio();

    // Fallback: recover UI if server doesn't respond within 30 s
    this.stopTimeout = setTimeout(() => {
      this.cleanupSocket();
      this.status$.next('idle');
    }, 30_000);
  }

  private onMessage(msg: MessageEvent): void {
    const event: TranscriptEvent = JSON.parse(msg.data as string);
    this.events$.next(event);
    if (event.type === 'partial') this.status$.next('transcribing');
    if (event.type === 'final')   this.status$.next('idle');
  }

  private onClose(): void {
    if (this.stopTimeout) clearTimeout(this.stopTimeout);
    this.cleanupAudio();
    this.socket = null;
    this.status$.next('idle');
  }

  private flush(): void {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return;
    if (this.pendingSamples.length === 0) return;

    const merged = this.merge(this.pendingSamples);
    this.pendingSamples = [];
    this.socket.send(this.toPcm16(merged));
  }

  private cleanup(): void {
    this.cleanupAudio();
    this.cleanupSocket();
    this.status$.next('idle');
  }

  private cleanupAudio(): void {
    if (this.sendTimer)   { clearInterval(this.sendTimer);   this.sendTimer   = null; }
    if (this.processor)   { this.processor.disconnect();      this.processor   = null; }
    if (this.source)      { this.source.disconnect();         this.source      = null; }
    if (this.audioContext){ this.audioContext.close();        this.audioContext = null; }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(t => t.stop());
      this.mediaStream = null;
    }
    this.pendingSamples = [];
  }

  private cleanupSocket(): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) this.socket.close();
    this.socket = null;
  }

  // ── Audio utilities ──────────────────────────────────────────────────────

  private resample(input: Float32Array, fromRate: number, toRate: number): Float32Array {
    if (fromRate === toRate) return new Float32Array(input);
    const ratio  = fromRate / toRate;
    const length = Math.floor(input.length / ratio);
    const output = new Float32Array(length);
    for (let i = 0; i < length; i++) {
      const idx    = i * ratio;
      const before = Math.floor(idx);
      const after  = Math.min(before + 1, input.length - 1);
      output[i]    = input[before] * (1 - (idx - before)) + input[after] * (idx - before);
    }
    return output;
  }

  private merge(chunks: Float32Array[]): Float32Array {
    const total  = chunks.reduce((n, c) => n + c.length, 0);
    const merged = new Float32Array(total);
    let offset   = 0;
    for (const c of chunks) { merged.set(c, offset); offset += c.length; }
    return merged;
  }

  private toPcm16(samples: Float32Array): ArrayBuffer {
    const buf  = new ArrayBuffer(samples.length * 2);
    const view = new DataView(buf);
    for (let i = 0; i < samples.length; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return buf;
  }

  private waitForOpen(ws: WebSocket): Promise<void> {
    return new Promise((resolve, reject) => {
      ws.onopen  = () => resolve();
      ws.onerror = () => reject(new Error('WebSocket failed to open'));
    });
  }

  ngOnDestroy(): void { this.cleanup(); }
}
```

### Using it in a component

```ts
// record.component.ts
@Component({ ... })
export class RecordComponent {
  transcript = '';
  partialText = '';

  constructor(public svc: LiveTranscriptionService) {
    svc.events$.subscribe(evt => {
      if (evt.type === 'partial') this.partialText = evt.text ?? '';
      if (evt.type === 'final')   { this.transcript += ' ' + (evt.text ?? ''); this.partialText = ''; }
    });
  }

  start() { this.svc.start('ws://your-rhel-server/ws/transcribe/live'); }
  stop()  { this.svc.stop(); }
}
```

---

## Backend behaviour

| Setting | Default | Override via env var |
|---|---|---|
| Chunk window | 2 s | `LIVE_CHUNK_SECONDS` |
| Max session | 30 min | `LIVE_MAX_SESSION_SECONDS` |
| Model dir | `models/faster-whisper` | `MODEL_DIR` |
| CPU threads | 4 | `CPU_THREADS` |
| Allowed origins | `*` | `CORS_ORIGINS` |

Partial events arrive **after each 2-second window** is transcribed.
The `final` event contains the **complete concatenated transcript** for the session.

### Expected latency (whisper-medium.en, CPU-only)

| Hardware | Per-chunk latency |
|---|---|
| Mac (M-series, 4 cores) | ~5–10 s / 2 s chunk |
| RHEL (8–16 cores) | ~2–5 s / 2 s chunk |

Set `CPU_THREADS` to match available cores for best throughput.

---

## Notes

- Send audio chunks **at real-time rate** (every 200–500 ms). Sending faster just buffers on the server.
- Do **not** send `MediaRecorder` WebM/Opus blobs directly — they must be decoded to raw 16 kHz PCM first.
- The backend transcribes English only (`language: en`). Override with `LANGUAGE=fr` etc.
- After `stop` the server may take several seconds to flush buffered audio before sending `final`. The frontend should remain connected (keep the socket open) until it receives `final` or the socket closes.
