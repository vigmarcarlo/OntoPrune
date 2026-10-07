import * as vscode from "vscode";
import { OntoPruneBridge } from "./pruneBridge";
import { UnifiedLLMClient } from "./llmClient";
import { OntoPruneViewProvider } from "./panel/OntoPruneViewProvider";

export function activate(context: vscode.ExtensionContext) {
  const config = vscode.workspace.getConfiguration("ontoprune");
  const pythonPath = config.get<string>("pythonPath", "python3");
  const ollamaHost = config.get<string>("ollamaHost", "http://localhost:11434");

  const bridge = new OntoPruneBridge(pythonPath);
  const llm = new UnifiedLLMClient(ollamaHost);

  const provider = new OntoPruneViewProvider(
    context.extensionUri,
    bridge,
    llm,
    context.secrets
  );

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(OntoPruneViewProvider.viewType, provider)
  );

  // Command: Prune current symbol under cursor
  const pruneCommand = vscode.commands.registerCommand("ontoprune.pruneCurrentSymbol", async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage("Abre un archivo de código para podar su contexto.");
      return;
    }

    const document = editor.document;
    const selection = editor.selection;
    let targetSymbol = "";

    if (!selection.isEmpty) {
      targetSymbol = document.getText(selection).trim();
    } else {
      const wordRange = document.getWordRangeAtPosition(selection.active);
      if (wordRange) {
        targetSymbol = document.getText(wordRange).trim();
      }
    }

    if (!targetSymbol) {
      targetSymbol = (await vscode.window.showInputBox({
        prompt: "Introduce el nombre de la función o método a podar:",
        placeHolder: "ej. processCheckout o procesar_orden",
      })) || "";
    }

    if (!targetSymbol) {
      return;
    }

    // Open sidebar
    await vscode.commands.executeCommand("workbench.view.extension.ontoprune-sidebar");

    vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: `OntoPrune: Podando contexto para '${targetSymbol}'...`,
        cancellable: false,
      },
      async () => {
        const result = await bridge.pruneSymbol(document.fileName, targetSymbol, "stubs");
        if (!result.success) {
          vscode.window.showErrorMessage(`Error al podar contexto: ${result.error}`);
          return;
        }

        await provider.setPrunedContext(targetSymbol, document.fileName, result.contract, result.durationMs);
        vscode.window.showInformationMessage(
          `⚡ Contexto podado en ${result.durationMs.toFixed(1)} ms para '${targetSymbol}'`
        );
      }
    );
  });

  // Command: Refactor method
  const refactorCommand = vscode.commands.registerCommand("ontoprune.refactorMethod", async () => {
    await vscode.commands.executeCommand("ontoprune.pruneCurrentSymbol");
  });

  // Command: Generate Unit Test
  const testCommand = vscode.commands.registerCommand("ontoprune.generateUnitTest", async () => {
    await vscode.commands.executeCommand("ontoprune.pruneCurrentSymbol");
  });

  // Commands for Cloud API Keys
  const setGeminiKeyCommand = vscode.commands.registerCommand("ontoprune.setGeminiKey", async () => {
    await provider.promptAndSaveApiKey("gemini");
  });

  const setOpenAiKeyCommand = vscode.commands.registerCommand("ontoprune.setOpenAiKey", async () => {
    await provider.promptAndSaveApiKey("openai");
  });

  const setAnthropicKeyCommand = vscode.commands.registerCommand("ontoprune.setAnthropicKey", async () => {
    await provider.promptAndSaveApiKey("anthropic");
  });

  context.subscriptions.push(
    pruneCommand,
    refactorCommand,
    testCommand,
    setGeminiKeyCommand,
    setOpenAiKeyCommand,
    setAnthropicKeyCommand
  );

  // Update configuration when changed
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("ontoprune.pythonPath")) {
        const newPython = vscode.workspace.getConfiguration("ontoprune").get<string>("pythonPath", "python");
        bridge.updatePythonPath(newPython);
      }
      if (e.affectsConfiguration("ontoprune.ollamaHost")) {
        const newHost = vscode.workspace.getConfiguration("ontoprune").get<string>("ollamaHost", "http://localhost:11434");
        llm.updateOllamaHost(newHost);
      }
    })
  );
}

export function deactivate() {}
