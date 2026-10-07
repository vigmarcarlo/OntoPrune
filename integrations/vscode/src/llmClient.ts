import * as http from "http";
import * as https from "https";

export type LLMProvider = "ollama" | "gemini" | "openai" | "anthropic";

export interface StreamChunkCallback {
  (chunk: string): void;
}

export interface StreamCompleteCallback {
  (fullText: string, ttftMs: number, totalMs: number): void;
}

export interface StreamErrorCallback {
  (error: Error): void;
}

export interface LLMRequestOptions {
  provider: LLMProvider;
  model: string;
  prompt: string;
  apiKey?: string;
  ollamaHost?: string;
  numThreads?: number;
  onChunk: StreamChunkCallback;
  onComplete: StreamCompleteCallback;
  onError: StreamErrorCallback;
}

export const DEFAULT_MODELS_BY_PROVIDER: Record<LLMProvider, { id: string; label: string }[]> = {
  ollama: [
    { id: "qwen2.5-coder:7b", label: "qwen2.5-coder:7b (Máxima Calidad - Recomendado)" },
    { id: "qwen2.5-coder:3b", label: "qwen2.5-coder:3b (Equilibrado)" },
    { id: "qwen2.5-coder:1.5b", label: "qwen2.5-coder:1.5b (Ultra Rápido)" },
  ],
  gemini: [
    { id: "gemini-3.8-flash", label: "gemini-3.8-flash (Ultra Rápido - Recomendado)" },
    { id: "gemini-flash-latest", label: "gemini-flash-latest (Último Flash)" },
    { id: "gemini-pro-latest", label: "gemini-pro-latest (Máxima Calidad)" },
  ],
  openai: [
    { id: "gpt-4o", label: "gpt-4o (Omni State-of-the-Art)" },
    { id: "gpt-4o-mini", label: "gpt-4o-mini (Rápido y Liviano)" },
    { id: "o3-mini", label: "o3-mini (Razonamiento de Código)" },
  ],
  anthropic: [
    { id: "claude-3-5-sonnet-20241022", label: "claude-3-5-sonnet (Referente en Programación)" },
    { id: "claude-3-5-haiku-20241022", label: "claude-3-5-haiku (Ultra Rápido)" },
  ],
};

export class UnifiedLLMClient {
  constructor(private ollamaHost: string = "http://localhost:11434") {}

  public updateOllamaHost(newHost: string): void {
    this.ollamaHost = newHost.replace(/\/+$/, "");
  }

  public generateStream(opts: LLMRequestOptions): { cancel: () => void } {
    switch (opts.provider) {
      case "gemini":
        return this.streamGemini(opts);
      case "openai":
        return this.streamOpenAI(opts);
      case "anthropic":
        return this.streamAnthropic(opts);
      case "ollama":
      default:
        return this.streamOllama(opts);
    }
  }

  /**
   * Google Gemini streaming API via OpenAI-compatible endpoint.
   * Fully supports Google's AQ. and AIza keys with Bearer token authentication.
   */
  private streamGemini(opts: LLMRequestOptions): { cancel: () => void } {
    let apiKey = (opts.apiKey || "").trim();
    apiKey = apiKey.replace(/^Bearer\s+/i, "").replace(/^["']|["']$/g, "").trim();

    if (!apiKey) {
      opts.onError(
        new Error(
          "Falta la API Key de Google Gemini. Configúrala con el botón '🔑 Configurar' o regístrala desde Google AI Studio (aistudio.google.com)."
        )
      );
      return { cancel: () => {} };
    }

    const cleanModel = opts.model || "gemini-3.8-flash";
    const endpoint = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions";
    const url = new URL(endpoint);

    const payload = JSON.stringify({
      model: cleanModel,
      messages: [
        {
          role: "system",
          content:
            "You are an expert programming assistant working with OntoPrune minimal dependency contracts. Return only the clean, requested implementation inside markdown code blocks.",
        },
        { role: "user", content: opts.prompt },
      ],
      temperature: 0.1,
      stream: true,
    });

    const requestOptions: https.RequestOptions = {
      hostname: url.hostname,
      port: 443,
      path: url.pathname,
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`,
        "Content-Length": Buffer.byteLength(payload),
      },
      timeout: 60000,
    };

    const tStart = Date.now();
    let ttftMs = 0;
    let fullText = "";
    let isCancelled = false;

    const req = https.request(requestOptions, (res) => {
      if (res.statusCode && res.statusCode >= 400) {
        let errBody = "";
        res.on("data", (c) => (errBody += c.toString()));
        res.on("end", () => {
          let msg = `HTTP ${res.statusCode}: ${res.statusMessage}`;
          try {
            const parsed = JSON.parse(errBody);
            const errObj = Array.isArray(parsed) ? parsed[0]?.error : parsed.error;
            if (errObj && errObj.message) {
              msg = `Gemini Error: ${errObj.message}`;
            }
          } catch {
            if (errBody) msg += ` - ${errBody}`;
          }
          opts.onError(new Error(msg));
        });
        return;
      }

      let buffer = "";

      res.on("data", (chunk: Buffer) => {
        if (isCancelled) return;

        buffer += chunk.toString("utf8");
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data:")) continue;

          const dataStr = trimmed.slice(5).trim();
          if (dataStr === "[DONE]") {
            const totalMs = Date.now() - tStart;
            opts.onComplete(fullText, ttftMs || totalMs, totalMs);
            return;
          }

          try {
            const data = JSON.parse(dataStr);
            const content = data.choices?.[0]?.delta?.content;
            if (content) {
              if (!ttftMs) ttftMs = Date.now() - tStart;
              fullText += content;
              opts.onChunk(content);
            }
          } catch {
            // Partial JSON buffer
          }
        }
      });

      res.on("end", () => {
        if (!isCancelled) {
          const totalMs = Date.now() - tStart;
          opts.onComplete(fullText, ttftMs || totalMs, totalMs);
        }
      });
    });

    req.on("error", (err) => {
      if (!isCancelled) opts.onError(err);
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
   * Streams via OpenAI Chat Completions API.
   */
  private streamOpenAI(opts: LLMRequestOptions): { cancel: () => void } {
    const apiKey = (opts.apiKey || "").trim();
    if (!apiKey) {
      opts.onError(
        new Error(
          "Falta la API Key para OpenAI. Configúrala en la extensión o haz clic en 'Configurar API Key'."
        )
      );
      return { cancel: () => {} };
    }

    const endpoint = "https://api.openai.com/v1/chat/completions";
    const url = new URL(endpoint);
    const payload = JSON.stringify({
      model: opts.model,
      messages: [
        {
          role: "system",
          content:
            "You are an expert programming assistant working with OntoPrune minimal dependency contracts. Return only the clean, requested implementation inside markdown code blocks.",
        },
        { role: "user", content: opts.prompt },
      ],
      temperature: 0.1,
      stream: true,
    });

    const requestOptions: https.RequestOptions = {
      hostname: url.hostname,
      port: 443,
      path: url.pathname + url.search,
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`,
        "Content-Length": Buffer.byteLength(payload),
      },
      timeout: 60000,
    };

    const tStart = Date.now();
    let ttftMs = 0;
    let fullText = "";
    let isCancelled = false;

    const req = https.request(requestOptions, (res) => {
      if (res.statusCode && res.statusCode >= 400) {
        let errBody = "";
        res.on("data", (c) => (errBody += c.toString()));
        res.on("end", () => {
          let msg = `HTTP ${res.statusCode}: ${res.statusMessage}`;
          try {
            const parsed = JSON.parse(errBody);
            const errObj = Array.isArray(parsed) ? parsed[0]?.error : parsed.error;
            if (errObj && errObj.message) {
              msg = `OpenAI Error: ${errObj.message}`;
            }
          } catch {
            if (errBody) msg += ` - ${errBody}`;
          }
          opts.onError(new Error(msg));
        });
        return;
      }

      let buffer = "";

      res.on("data", (chunk: Buffer) => {
        if (isCancelled) return;

        buffer += chunk.toString("utf8");
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data:")) continue;

          const dataStr = trimmed.slice(5).trim();
          if (dataStr === "[DONE]") {
            const totalMs = Date.now() - tStart;
            opts.onComplete(fullText, ttftMs || totalMs, totalMs);
            return;
          }

          try {
            const data = JSON.parse(dataStr);
            const content = data.choices?.[0]?.delta?.content;
            if (content) {
              if (!ttftMs) ttftMs = Date.now() - tStart;
              fullText += content;
              opts.onChunk(content);
            }
          } catch {
            // Partial JSON buffer
          }
        }
      });

      res.on("end", () => {
        if (!isCancelled) {
          const totalMs = Date.now() - tStart;
          opts.onComplete(fullText, ttftMs || totalMs, totalMs);
        }
      });
    });

    req.on("error", (err) => {
      if (!isCancelled) opts.onError(err);
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
   * Streams via Anthropic Claude messages API.
   */
  private streamAnthropic(opts: LLMRequestOptions): { cancel: () => void } {
    const apiKey = (opts.apiKey || "").trim();
    if (!apiKey) {
      opts.onError(
        new Error(
          "Falta la API Key para Anthropic Claude. Configúrala en la extensión o haz clic en 'Configurar API Key'."
        )
      );
      return { cancel: () => {} };
    }

    const url = new URL("https://api.anthropic.com/v1/messages");
    const payload = JSON.stringify({
      model: opts.model,
      max_tokens: 4096,
      temperature: 0.1,
      system:
        "You are an expert programming assistant working with OntoPrune minimal dependency contracts. Return only the clean, requested implementation inside markdown code blocks.",
      messages: [{ role: "user", content: opts.prompt }],
      stream: true,
    });

    const requestOptions: https.RequestOptions = {
      hostname: url.hostname,
      port: 443,
      path: url.pathname,
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
        "Content-Length": Buffer.byteLength(payload),
      },
      timeout: 60000,
    };

    const tStart = Date.now();
    let ttftMs = 0;
    let fullText = "";
    let isCancelled = false;

    const req = https.request(requestOptions, (res) => {
      if (res.statusCode && res.statusCode >= 400) {
        let errBody = "";
        res.on("data", (c) => (errBody += c.toString()));
        res.on("end", () => {
          let msg = `Anthropic HTTP ${res.statusCode}: ${res.statusMessage}`;
          try {
            const parsed = JSON.parse(errBody);
            const errObj = Array.isArray(parsed) ? parsed[0]?.error : parsed.error;
            if (errObj && errObj.message) {
              msg = `Anthropic Error: ${errObj.message}`;
            }
          } catch {
            if (errBody) msg += ` - ${errBody}`;
          }
          opts.onError(new Error(msg));
        });
        return;
      }

      let buffer = "";

      res.on("data", (chunk: Buffer) => {
        if (isCancelled) return;

        buffer += chunk.toString("utf8");
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data:")) continue;

          const dataStr = trimmed.slice(5).trim();
          try {
            const data = JSON.parse(dataStr);
            if (data.type === "content_block_delta" && data.delta?.text) {
              if (!ttftMs) ttftMs = Date.now() - tStart;
              fullText += data.delta.text;
              opts.onChunk(data.delta.text);
            } else if (data.type === "message_stop") {
              const totalMs = Date.now() - tStart;
              opts.onComplete(fullText, ttftMs || totalMs, totalMs);
            }
          } catch {
            // Partial JSON buffer
          }
        }
      });

      res.on("end", () => {
        if (!isCancelled) {
          const totalMs = Date.now() - tStart;
          opts.onComplete(fullText, ttftMs || totalMs, totalMs);
        }
      });
    });

    req.on("error", (err) => {
      if (!isCancelled) opts.onError(err);
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
   * Streams via Ollama local API (/api/generate).
   */
  private streamOllama(opts: LLMRequestOptions): { cancel: () => void } {
    const url = new URL(`${this.ollamaHost}/api/generate`);
    const isHttps = url.protocol === "https:";
    const requestLib = isHttps ? https : http;

    const payload = JSON.stringify({
      model: opts.model,
      prompt: opts.prompt,
      stream: true,
      options: {
        temperature: 0.1,
        num_thread: opts.numThreads || 4,
      },
    });

    const requestOptions: http.RequestOptions = {
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

    const req = requestLib.request(requestOptions, (res) => {
      if (res.statusCode && res.statusCode >= 400) {
        opts.onError(new Error(`Ollama server returned HTTP ${res.statusCode}: ${res.statusMessage}`));
        return;
      }

      let buffer = "";

      res.on("data", (chunk: Buffer) => {
        if (isCancelled) return;

        buffer += chunk.toString("utf8");
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line);
            const token = data.response;
            if (token) {
              if (!ttftMs) ttftMs = Date.now() - tStart;
              fullText += token;
              opts.onChunk(token);
            }
            if (data.done) {
              const totalMs = Date.now() - tStart;
              opts.onComplete(fullText, ttftMs || totalMs, totalMs);
            }
          } catch {
            // Incomplete JSON
          }
        }
      });

      res.on("end", () => {
        if (!isCancelled && buffer.trim()) {
          try {
            const data = JSON.parse(buffer);
            if (data.response) {
              fullText += data.response;
              opts.onChunk(data.response);
            }
            const totalMs = Date.now() - tStart;
            opts.onComplete(fullText, ttftMs || totalMs, totalMs);
          } catch {
            // Done
          }
        }
      });
    });

    req.on("error", (err) => {
      if (!isCancelled) opts.onError(err);
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
  public async getOllamaModels(): Promise<string[]> {
    return new Promise((resolve) => {
      const url = new URL(`${this.ollamaHost}/api/tags`);
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
