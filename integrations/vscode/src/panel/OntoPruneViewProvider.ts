import * as vscode from "vscode";
import { OntoPruneBridge } from "../pruneBridge";
import { UnifiedLLMClient, LLMProvider, DEFAULT_MODELS_BY_PROVIDER } from "../llmClient";

export class OntoPruneViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "ontoprune.sidebarView";
  private _view?: vscode.WebviewView;

  private currentContract: string = "";
  private currentSymbol: string = "";
  private currentFilePath: string = "";
  private currentGeneratedCode: string = "";

  constructor(
    private readonly _extensionUri: vscode.Uri,
    private readonly bridge: OntoPruneBridge,
    private readonly llm: UnifiedLLMClient,
    private readonly secrets: vscode.SecretStorage
  ) {}

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ) {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri],
    };

    webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

    webviewView.webview.onDidReceiveMessage(async (data) => {
      switch (data.type) {
        case "refreshModels": {
          const models = await this.llm.getOllamaModels();
          this.postMessage({ type: "ollamaModelsList", models });
          break;
        }
        case "generate": {
          await this.handleGenerate(data.prompt, data.model, data.provider || "ollama");
          break;
        }
        case "verify": {
          await this.handleVerify();
          break;
        }
        case "apply": {
          await this.handleApplyCode();
          break;
        }
        case "quickAction": {
          await this.handleQuickAction(data.action, data.model, data.provider || "ollama");
          break;
        }
        case "checkApiKey": {
          const key = await this.getApiKey(data.provider);
          this.postMessage({
            type: "apiKeyStatus",
            provider: data.provider,
            configured: Boolean(key && key.trim().length > 0),
          });
          break;
        }
        case "setApiKey": {
          await this.promptAndSaveApiKey(data.provider);
          break;
        }
      }
    });

    // Send initial configuration
    const config = vscode.workspace.getConfiguration("ontoprune");
    const defaultProvider = config.get<LLMProvider>("defaultProvider", "ollama");
    this.postMessage({
      type: "initSettings",
      defaultProvider,
    });
  }

  public postMessage(message: unknown): void {
    if (this._view) {
      this._view.webview.postMessage(message);
    }
  }

  public async setPrunedContext(symbol: string, filePath: string, contract: string, durationMs: number): Promise<void> {
    this.currentSymbol = symbol;
    this.currentFilePath = filePath;
    this.currentContract = contract;

    const estimatedTokens = Math.max(1, Math.round(contract.length / 4));

    this.postMessage({
      type: "contextLoaded",
      symbol,
      filePath,
      contract,
      durationMs,
      tokens: estimatedTokens,
    });
  }

  public async getApiKey(provider: string): Promise<string> {
    if (provider === "ollama") return "local";

    // 1. Check SecretStorage
    const secretKey = await this.secrets.get(`ontoprune.${provider}ApiKey`);
    if (secretKey && secretKey.trim().length > 0) {
      return secretKey.trim();
    }

    // 2. Check settings configuration
    const config = vscode.workspace.getConfiguration("ontoprune");
    const configKey = config.get<string>(`${provider}ApiKey`, "");
    return (configKey || "").trim();
  }

  public async promptAndSaveApiKey(provider: string): Promise<void> {
    let name = "Google Gemini";
    let placeholder = "AIzaSy...";
    if (provider === "openai") {
      name = "OpenAI";
      placeholder = "sk-...";
    } else if (provider === "anthropic") {
      name = "Anthropic Claude";
      placeholder = "sk-ant-...";
    }

    const key = await vscode.window.showInputBox({
      prompt: `Introduce tu API Key para ${name}:`,
      password: true,
      placeHolder: placeholder,
    });

    if (key !== undefined) {
      await this.secrets.store(`ontoprune.${provider}ApiKey`, key.trim());
      vscode.window.showInformationMessage(`API Key para ${name} guardada de forma segura.`);
      this.postMessage({
        type: "apiKeyStatus",
        provider,
        configured: Boolean(key.trim().length > 0),
      });
    }
  }

  private async handleGenerate(userPrompt: string, model: string, provider: LLMProvider): Promise<void> {
    if (!this.currentContract) {
      vscode.window.showWarningMessage("Por favor, selecciona primero un método para podar su contexto.");
      return;
    }

    const apiKey = await this.getApiKey(provider);
    if (provider !== "ollama" && (!apiKey || apiKey.length === 0)) {
      const action = await vscode.window.showWarningMessage(
        `Se requiere API Key para ${provider.toUpperCase()}.`,
        "Configurar Ahora"
      );
      if (action === "Configurar Ahora") {
        await this.promptAndSaveApiKey(provider);
      }
      return;
    }

    const fullPrompt = `// === ONTOPRUNE MINIMAL DEPENDENCY CONTRACT ===\n${this.currentContract}\n\n// === TASK INSTRUCTION ===\nTarget Symbol: ${this.currentSymbol}\nInstruction: ${userPrompt}\n\nProvide only the code implementation inside a markdown code block.`;

    this.postMessage({ type: "streamStart" });
    this.currentGeneratedCode = "";

    const config = vscode.workspace.getConfiguration("ontoprune");
    const numThreads = config.get<number>("numThreads", 4);

    this.llm.generateStream({
      provider,
      model,
      prompt: fullPrompt,
      apiKey,
      numThreads,
      onChunk: (chunk) => {
        this.currentGeneratedCode += chunk;
        this.postMessage({ type: "streamChunk", chunk });
      },
      onComplete: async (fullText, ttftMs, totalMs) => {
        this.currentGeneratedCode = fullText;
        this.postMessage({
          type: "streamComplete",
          fullText,
          ttftMs,
          totalMs,
        });

        // Auto verify contract
        await this.handleVerify();
      },
      onError: (error) => {
        this.postMessage({ type: "streamError", error: error.message });
        vscode.window.showErrorMessage(`Error de IA (${provider}): ${error.message}`);
      },
    });
  }

  private async handleQuickAction(action: string, model: string, provider: LLMProvider): Promise<void> {
    let prompt = "";
    switch (action) {
      case "test":
        prompt = `Generate a comprehensive unit test suite with mocks for the method '${this.currentSymbol}', ensuring all branches in the contract are covered.`;
        break;
      case "refactor":
        prompt = `Refactor '${this.currentSymbol}' to improve robustness, performance, and clean architecture without altering its public contract.`;
        break;
      case "document":
        prompt = `Write clean, production-grade documentation/docstring for '${this.currentSymbol}' detailing parameters, return types, and exceptions.`;
        break;
      default:
        prompt = action;
    }

    await this.handleGenerate(prompt, model, provider);
  }

  private async handleVerify(): Promise<void> {
    if (!this.currentGeneratedCode || !this.currentContract) {
      return;
    }

    const ext = this.currentFilePath.slice(this.currentFilePath.lastIndexOf("."));
    const result = await this.bridge.checkResponse(this.currentGeneratedCode, this.currentContract, ext || ".py");

    this.postMessage({
      type: "verifyResult",
      success: result.success,
      violations: result.violations,
      durationMs: result.durationMs,
    });
  }

  private async handleApplyCode(): Promise<void> {
    if (!this.currentGeneratedCode) {
      return;
    }

    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage("No hay ningún editor activo.");
      return;
    }

    let codeToApply = this.currentGeneratedCode;
    const match = this.currentGeneratedCode.match(/```(?:\w+)?\n([\s\S]*?)```/);
    if (match && match[1]) {
      codeToApply = match[1];
    }

    const selection = editor.selection;
    await editor.edit((editBuilder) => {
      if (!selection.isEmpty) {
        editBuilder.replace(selection, codeToApply);
      } else {
        editBuilder.insert(selection.active, codeToApply);
      }
    });

    vscode.window.showInformationMessage("¡Código aplicado con éxito en el editor!");
  }

  private _getHtmlForWebview(_webview: vscode.Webview): string {
    const modelsJson = JSON.stringify(DEFAULT_MODELS_BY_PROVIDER);

    return `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OntoPrune AI</title>
  <style>
    :root {
      --bg: var(--vscode-editor-background);
      --fg: var(--vscode-editor-foreground);
      --accent: #3b82f6;
      --accent-hover: #2563eb;
      --border: var(--vscode-panel-border, #334155);
      --success: #10b981;
      --danger: #ef4444;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      padding: 12px;
      color: var(--fg);
      background-color: var(--bg);
      font-size: 13px;
      line-height: 1.5;
    }

    .badge-card {
      background: rgba(59, 130, 246, 0.1);
      border: 1px solid rgba(59, 130, 246, 0.3);
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 12px;
    }

    .badge-title {
      font-size: 11px;
      text-transform: uppercase;
      font-weight: 700;
      color: #60a5fa;
      letter-spacing: 0.5px;
    }

    .symbol-name {
      font-weight: 600;
      font-size: 14px;
      margin: 4px 0;
      color: var(--fg);
      font-family: monospace;
    }

    .stats-row {
      display: flex;
      gap: 10px;
      font-size: 11px;
      color: #94a3b8;
      margin-top: 4px;
    }

    .stat-pill {
      background: rgba(255, 255, 255, 0.05);
      padding: 2px 6px;
      border-radius: 4px;
    }

    .quick-actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
      margin-bottom: 12px;
    }

    .btn-quick {
      background: rgba(255, 255, 255, 0.04);
      color: var(--fg);
      border: 1px solid var(--border);
      padding: 6px 8px;
      border-radius: 6px;
      font-size: 11px;
      cursor: pointer;
      text-align: center;
      transition: background 0.15s ease;
    }

    .btn-quick:hover {
      background: rgba(255, 255, 255, 0.1);
    }

    .btn-primary {
      background: var(--accent);
      color: #fff;
      border: none;
      padding: 8px 14px;
      border-radius: 6px;
      width: 100%;
      cursor: pointer;
      font-weight: 600;
      margin-top: 8px;
      transition: background 0.15s ease;
    }

    .btn-primary:hover {
      background: var(--accent-hover);
    }

    .btn-success {
      background: #059669;
      color: #fff;
      border: none;
      padding: 8px 12px;
      border-radius: 6px;
      width: 100%;
      cursor: pointer;
      font-weight: 600;
      margin-top: 8px;
    }

    .btn-success:hover {
      background: #047857;
    }

    .btn-key {
      background: rgba(255, 255, 255, 0.08);
      color: #93c5fd;
      border: 1px solid rgba(147, 197, 253, 0.3);
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 10px;
      cursor: pointer;
    }

    .btn-key:hover {
      background: rgba(255, 255, 255, 0.15);
    }

    .field-label {
      font-size: 11px;
      font-weight: 600;
      color: #94a3b8;
      margin-top: 8px;
      margin-bottom: 3px;
      display: block;
    }

    textarea {
      width: 100%;
      box-sizing: border-box;
      background: var(--vscode-input-background, #1e293b);
      color: var(--vscode-input-foreground, #fff);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px;
      font-family: inherit;
      font-size: 12px;
      resize: vertical;
      min-height: 55px;
    }

    select {
      width: 100%;
      background: var(--vscode-dropdown-background, #1e293b);
      color: var(--vscode-dropdown-foreground, #fff);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 6px;
      font-size: 12px;
      margin-bottom: 6px;
    }

    .key-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 5px 8px;
      margin-bottom: 8px;
      font-size: 11px;
    }

    .response-container {
      margin-top: 14px;
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px;
      max-height: 320px;
      overflow-y: auto;
      font-family: monospace;
      font-size: 12px;
      white-space: pre-wrap;
      word-break: break-all;
    }

    .verification-badge {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      font-weight: 600;
      padding: 6px 10px;
      border-radius: 6px;
      margin-top: 8px;
    }

    .verify-ok {
      background: rgba(16, 185, 129, 0.15);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.3);
    }

    .verify-fail {
      background: rgba(239, 68, 68, 0.15);
      color: #f87171;
      border: 1px solid rgba(239, 68, 68, 0.3);
    }

    details {
      margin-bottom: 12px;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 6px 8px;
      background: rgba(255, 255, 255, 0.02);
    }

    summary {
      cursor: pointer;
      font-weight: 600;
      font-size: 11px;
      color: #94a3b8;
    }

    pre {
      margin: 6px 0 0 0;
      font-size: 11px;
      overflow-x: auto;
    }
  </style>
</head>
<body>
  <div id="no-context" class="badge-card" style="text-align: center; color: #94a3b8;">
    <p>Haz clic derecho en cualquier método en tu editor:</p>
    <p style="font-weight: 600; color: #60a5fa;">"OntoPrune: Prune Context for Method"</p>
  </div>

  <div id="context-card" class="badge-card" style="display: none;">
    <div class="badge-title">⚡ Contrato Podado Activo</div>
    <div id="symbol-display" class="symbol-name">-</div>
    <div class="stats-row">
      <span id="token-badge" class="stat-pill">- tokens</span>
      <span id="latency-badge" class="stat-pill">< 10 ms</span>
      <span class="stat-pill" style="color: #34d399;">~90% ahorro</span>
    </div>
  </div>

  <details id="contract-details" style="display: none;">
    <summary>Ver Contrato Mínimo de APIs</summary>
    <pre id="contract-code"></pre>
  </details>

  <div class="quick-actions">
    <button class="btn-quick" onclick="triggerQuick('test')">🧪 Test Suite</button>
    <button class="btn-quick" onclick="triggerQuick('refactor')">⚡ Refactorizar</button>
    <button class="btn-quick" onclick="triggerQuick('document')">📝 Documentar</button>
    <button class="btn-quick" onclick="clearOutput()">🧹 Limpiar</button>
  </div>

  <label class="field-label">Proveedor de IA:</label>
  <select id="provider-select" onchange="onProviderChange()">
    <option value="ollama" selected>🖥️ Ollama (Local - 100% Offline)</option>
    <option value="gemini">♊ Google Gemini (Nube - Gratis)</option>
    <option value="openai">🤖 OpenAI (GPT-4o / o3-mini)</option>
    <option value="anthropic">🧠 Anthropic (Claude 3.5 Sonnet)</option>
  </select>

  <div id="key-bar" class="key-bar" style="display: none;">
    <span id="key-status" style="color: #94a3b8;">Comprobando API Key...</span>
    <button class="btn-key" onclick="promptApiKey()">🔑 Configurar</button>
  </div>

  <label class="field-label">Modelo:</label>
  <select id="model-select"></select>

  <textarea id="prompt-input" placeholder="Instrucción (ej. Quita los comentarios, optimiza loops, agrega validación...)"></textarea>
  <button id="generate-btn" class="btn-primary" onclick="submitGenerate()">🚀 Generar con Ollama Local</button>

  <div id="response-box" class="response-container" style="display: none;"></div>

  <div id="verify-badge" style="display: none;"></div>

  <button id="apply-btn" class="btn-success" style="display: none;" onclick="applyToEditor()">
    ✨ Aplicar Código en Editor
  </button>

  <script>
    const vscode = acquireVsCodeApi();
    const PROVIDER_MODELS = ${modelsJson};

    let currentProvider = 'ollama';

    function initModels(provider) {
      currentProvider = provider;
      const select = document.getElementById('model-select');
      select.innerHTML = '';

      const models = PROVIDER_MODELS[provider] || [];
      models.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.id;
        opt.innerText = m.label;
        select.appendChild(opt);
      });

      // Update Key Bar & Generate Button
      const keyBar = document.getElementById('key-bar');
      const genBtn = document.getElementById('generate-btn');

      if (provider === 'ollama') {
        keyBar.style.display = 'none';
        genBtn.innerText = '🚀 Generar con Ollama Local';
      } else {
        keyBar.style.display = 'flex';
        vscode.postMessage({ type: 'checkApiKey', provider });

        if (provider === 'gemini') genBtn.innerText = '🚀 Generar con Google Gemini';
        else if (provider === 'openai') genBtn.innerText = '🚀 Generar con OpenAI';
        else if (provider === 'anthropic') genBtn.innerText = '🚀 Generar con Claude';
      }
    }

    function onProviderChange() {
      const provider = document.getElementById('provider-select').value;
      initModels(provider);
    }

    function promptApiKey() {
      vscode.postMessage({ type: 'setApiKey', provider: currentProvider });
    }

    function triggerQuick(action) {
      const model = document.getElementById('model-select').value;
      vscode.postMessage({ type: 'quickAction', action, model, provider: currentProvider });
    }

    function submitGenerate() {
      const prompt = document.getElementById('prompt-input').value.trim() || 'Implement or refactor the target method.';
      const model = document.getElementById('model-select').value;
      vscode.postMessage({ type: 'generate', prompt, model, provider: currentProvider });
    }

    function applyToEditor() {
      vscode.postMessage({ type: 'apply' });
    }

    function clearOutput() {
      document.getElementById('response-box').style.display = 'none';
      document.getElementById('response-box').innerText = '';
      document.getElementById('verify-badge').style.display = 'none';
      document.getElementById('apply-btn').style.display = 'none';
    }

    window.addEventListener('message', (event) => {
      const msg = event.data;
      switch (msg.type) {
        case 'initSettings': {
          if (msg.defaultProvider) {
            document.getElementById('provider-select').value = msg.defaultProvider;
            initModels(msg.defaultProvider);
          }
          break;
        }
        case 'apiKeyStatus': {
          if (msg.provider === currentProvider) {
            const keyStatus = document.getElementById('key-status');
            if (msg.configured) {
              keyStatus.innerHTML = '<span style="color: #34d399;">●</span> API Key configurada';
            } else {
              keyStatus.innerHTML = '<span style="color: #f87171;">●</span> Sin API Key configurada';
            }
          }
          break;
        }
        case 'ollamaModelsList': {
          if (currentProvider === 'ollama' && msg.models && msg.models.length > 0) {
            const select = document.getElementById('model-select');
            select.innerHTML = '';
            msg.models.forEach(m => {
              const opt = document.createElement('option');
              opt.value = m;
              opt.innerText = m;
              if (m.includes('7b')) opt.selected = true;
              select.appendChild(opt);
            });
          }
          break;
        }
        case 'contextLoaded': {
          document.getElementById('no-context').style.display = 'none';
          document.getElementById('context-card').style.display = 'block';
          document.getElementById('contract-details').style.display = 'block';
          document.getElementById('symbol-display').innerText = msg.symbol;
          document.getElementById('token-badge').innerText = msg.tokens + ' tokens';
          document.getElementById('latency-badge').innerText = msg.durationMs.toFixed(1) + ' ms';
          document.getElementById('contract-code').innerText = msg.contract;
          break;
        }
        case 'streamStart': {
          const box = document.getElementById('response-box');
          box.style.display = 'block';
          box.innerText = '';
          document.getElementById('verify-badge').style.display = 'none';
          document.getElementById('apply-btn').style.display = 'none';
          break;
        }
        case 'streamChunk': {
          const box = document.getElementById('response-box');
          box.innerText += msg.chunk;
          box.scrollTop = box.scrollHeight;
          break;
        }
        case 'streamComplete': {
          document.getElementById('apply-btn').style.display = 'block';
          break;
        }
        case 'verifyResult': {
          const badge = document.getElementById('verify-badge');
          badge.style.display = 'flex';
          if (msg.success) {
            badge.className = 'verification-badge verify-ok';
            badge.innerText = '✅ 0 Violaciones (100% Conforme al Contrato)';
          } else {
            badge.className = 'verification-badge verify-fail';
            badge.innerText = '⚠️ Violaciones detectadas: ' + (msg.violations || []).join(', ');
          }
          break;
        }
      }
    });

    // Initialize default models on load
    initModels('ollama');
  </script>
</body>
</html>`;
  }
}
