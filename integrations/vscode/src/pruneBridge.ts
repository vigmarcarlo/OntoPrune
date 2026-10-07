import { execFile } from "child_process";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";

export interface PruneResult {
  success: boolean;
  contract: string;
  durationMs: number;
  error?: string;
}

export interface CheckResult {
  success: boolean;
  violations: string[];
  durationMs: number;
  error?: string;
}

/**
 * Bridge that executes OntoPrune CLI commands.
 */
export class OntoPruneBridge {
  constructor(private pythonPath: string = "python3") {}

  public updatePythonPath(newPath: string): void {
    this.pythonPath = newPath;
  }

  private getEffectivePython(filePath?: string): string {
    // 1. If configured pythonPath exists and is an absolute path, use it
    if (path.isAbsolute(this.pythonPath) && fs.existsSync(this.pythonPath)) {
      return this.pythonPath;
    }

    // 2. Walk up directory tree from active file, but ONLY use .venv if ontoprune is installed in it
    if (filePath) {
      let currentDir = path.dirname(filePath);
      for (let i = 0; i < 6; i++) {
        const venvOntoPrune = path.join(currentDir, ".venv", "bin", "ontoprune");
        const venvPy = path.join(currentDir, ".venv", "bin", "python");
        if (fs.existsSync(venvOntoPrune) && fs.existsSync(venvPy)) {
          return venvPy;
        }
        const parent = path.dirname(currentDir);
        if (parent === currentDir) {
          break;
        }
        currentDir = parent;
      }
    }

    // 3. Check default OntoPrune project venv
    const projectVenv = path.join("/home/vigmarcarlo/Proyectos/OntoPrune", ".venv", "bin", "python");
    if (fs.existsSync(projectVenv)) {
      return projectVenv;
    }

    // 4. Check global python3
    if (fs.existsSync("/usr/bin/python3")) {
      return "/usr/bin/python3";
    }

    return this.pythonPath;
  }

  /**
   * Translates a file and target symbol into a pruned minimal contract.
   */
  public async pruneSymbol(filePath: string, targetSymbol: string, format: string = "stubs", includeBody: boolean = true): Promise<PruneResult> {
    const t0 = Date.now();
    const effectivePython = this.getEffectivePython(filePath);

    return new Promise((resolve) => {
      const args = ["-m", "ontoprune.cli", "translate", filePath, targetSymbol, "--format", format];
      if (includeBody) {
        args.push("--include-body");
      }
      execFile(effectivePython, args, { maxBuffer: 10 * 1024 * 1024 }, (err, stdout, stderr) => {
        const durationMs = Date.now() - t0;
        if (err) {
          resolve({
            success: false,
            contract: "",
            durationMs,
            error: stderr || err.message,
          });
          return;
        }

        resolve({
          success: true,
          contract: stdout.trim(),
          durationMs,
        });
      });
    });
  }

  /**
   * Verifies code response against a contract using ontoprune check.
   */
  public async checkResponse(generatedCode: string, contract: string, extension: string = ".py"): Promise<CheckResult> {
    const t0 = Date.now();
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "ontoprune-check-"));
    const codePath = path.join(tempDir, `generated${extension}`);
    const contractPath = path.join(tempDir, `contract${extension}`);

    fs.writeFileSync(codePath, generatedCode, "utf8");
    fs.writeFileSync(contractPath, contract, "utf8");

    const effectivePython = this.getEffectivePython(codePath);
    return new Promise((resolve) => {
      const args = ["-m", "ontoprune.cli", "check", "--file", codePath, "--contract", contractPath];
      execFile(effectivePython, args, (err, stdout, stderr) => {
        const durationMs = Date.now() - t0;
        try {
          fs.rmSync(tempDir, { recursive: true, force: true });
        } catch {
          // ignore cleanup errors
        }

        if (err && err.code !== 1) {
          resolve({
            success: false,
            violations: [],
            durationMs,
            error: stderr || err.message,
          });
          return;
        }

        const lines = stdout.split("\n");
        const violations: string[] = [];
        let capturing = false;

        for (const line of lines) {
          if (line.includes("VIOLACIONES ENCONTRADAS") || line.includes("VIOLATIONS DETECTED")) {
            capturing = true;
            continue;
          }
          if (capturing && line.trim().startsWith("-")) {
            violations.push(line.trim());
          }
        }

        resolve({
          success: violations.length === 0,
          violations,
          durationMs,
        });
      });
    });
  }
}
