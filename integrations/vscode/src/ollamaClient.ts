import * as http from "http";
import * as https from "https";

export interface StreamChunkCallback {
  (chunk: string): void;
}

export interface StreamCompleteCallback {
  (fullText: string, ttftMs: number, totalMs: number): void;
}

export interface StreamErrorCallback {
  (error: Error): void;
}

/**
 * Lightweight native streaming HTTP client for Ollama API (/api/generate).
 */
export class OllamaClient {
  constructor(private host: string = "http://localhost:11434") {}

  public updateHost(newHost: string): void {
    this.host = newHost.replace(/\/+$/, "");
  }

  /**
   * Generates code stream from local Ollama model.
   */
  public generateStream(
    model: string,
    prompt: string,
    onChunk: StreamChunkCallback,
    onComplete: StreamCompleteCallback,
    onError: StreamErrorCallback,
    numThread?: number
  ): { cancel: () => void } {
    const url = new URL(`${this.host}/api/generate`);
    const isHttps = url.protocol === "https:";
    const requestLib = isHttps ? https : http;

    const payload = JSON.stringify({
      model,
      prompt,
      stream: true,
      options: {
        temperature: 0.1,
        ...(numThread ? { num_thread: numThread } : { num_thread: 4 }),
      },
    });

    const options: http.RequestOptions = {
      hostname: url.hostname,
      port: url.port || (isHttps ? 443 : 80),
      path: url.pathname,
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(payload),
      },
      timeout: 120000,
    };

    const tStart = Date.now();
    let ttftMs = 0;
    let fullText = "";
    let isCancelled = false;

    const req = requestLib.request(options, (res) => {
      if (res.statusCode && res.statusCode >= 400) {
        onError(new Error(`Ollama server returned HTTP ${res.statusCode}: ${res.statusMessage}`));
        return;
      }

      let buffer = "";

      res.on("data", (chunk: Buffer) => {
        if (isCancelled) {
          return;
        }

        buffer += chunk.toString("utf8");
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) {
            continue;
          }
          try {
            const data = JSON.parse(line);
            const token = data.response;
            if (token) {
              if (!ttftMs) {
                ttftMs = Date.now() - tStart;
              }
              fullText += token;
              onChunk(token);
            }
            if (data.done) {
              const totalMs = Date.now() - tStart;
              onComplete(fullText, ttftMs || totalMs, totalMs);
            }
          } catch {
            // Ignore incomplete line parse errors
          }
        }
      });

      res.on("end", () => {
        if (!isCancelled && buffer.trim()) {
          try {
            const data = JSON.parse(buffer);
            if (data.response) {
              fullText += data.response;
              onChunk(data.response);
            }
            const totalMs = Date.now() - tStart;
            onComplete(fullText, ttftMs || totalMs, totalMs);
          } catch {
            // Done
          }
        }
      });
    });

    req.on("error", (err) => {
      if (!isCancelled) {
        onError(err);
      }
    });

    req.write(payload);
    req.end();

    return {
      cancel: () => {
        isCancelled = true;
        req.destroy();
      },
    };
  }

  /**
   * Lists available local models from Ollama (/api/tags).
   */
  public async getAvailableModels(): Promise<string[]> {
    return new Promise((resolve) => {
      const url = new URL(`${this.host}/api/tags`);
      const isHttps = url.protocol === "https:";
      const requestLib = isHttps ? https : http;

      const req = requestLib.get(url, (res) => {
        let body = "";
        res.on("data", (chunk) => (body += chunk));
        res.on("end", () => {
          try {
            const json = JSON.parse(body);
            const models = (json.models || []).map((m: { name: string }) => m.name);
            resolve(models);
          } catch {
            resolve([]);
          }
        });
      });

      req.on("error", () => resolve([]));
    });
  }
}
