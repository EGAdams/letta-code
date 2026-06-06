export interface CliRunResult {
  stdout: string;
  stderr: string;
  exitCode: number | null;
}

export interface ICliRunner {
  run(prompt: string): Promise<CliRunResult>;
}
