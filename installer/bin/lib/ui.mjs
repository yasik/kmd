/**
 * UI plumbing for create-kmd: colors, the buffered prompt reader, command
 * execution, and the action log rendered in the final summary. Split from
 * the entry point so each file stays readable; still zero runtime
 * dependencies.
 */

import { spawnSync } from "node:child_process";
import { stdin, stdout } from "node:process";
import { createInterface } from "node:readline/promises";

export const color = {
  bold: (s) => `[1m${s}[0m`,
  dim: (s) => `[2m${s}[0m`,
  green: (s) => `[32m${s}[0m`,
  yellow: (s) => `[33m${s}[0m`,
  cyan: (s) => `[36m${s}[0m`,
};

/**
 * Buffered line reader for prompts.
 *
 * `readline/promises.question()` loses buffered lines with piped stdin and
 * leaves its promise unsettled on EOF — node then exits 0 mid-setup. This
 * reader owns the `line` event stream instead: answers arriving early are
 * queued, and EOF resolves every pending and future read as `null`, which
 * `ask`/`confirm` translate to "accept the default". Prompts are written to
 * stdout directly; terminal echo is left to the tty driver.
 */
export class Prompter {
  constructor() {
    this.pendingLines = [];
    this.waiters = [];
    this.closed = false;
    this.rl = createInterface({ input: stdin });
    this.rl.on("line", (line) => {
      const waiter = this.waiters.shift();
      if (waiter) {
        waiter(line);
        return;
      }
      this.pendingLines.push(line);
    });
    this.rl.on("close", () => {
      this.closed = true;
      for (const waiter of this.waiters.splice(0)) waiter(null);
    });
  }

  /** Next input line, or null once stdin has ended. */
  next() {
    if (this.pendingLines.length > 0)
      return Promise.resolve(this.pendingLines.shift());
    if (this.closed) return Promise.resolve(null);
    return new Promise((resolveLine) => this.waiters.push(resolveLine));
  }

  close() {
    this.rl.close();
  }
}

/** Interactive prompt session; created once, null in --yes mode. */
let prompter = null;

/** Create the prompt session (skip in --yes mode). */
export function initPrompter() {
  prompter = new Prompter();
}

/** Dispose the prompt session if one exists. */
export function closePrompter() {
  prompter?.close();
}

/**
 * Ask a free-text question; returns the default in --yes mode, on empty
 * input, or after stdin EOF.
 */
export async function ask(question, defaultValue) {
  if (prompter === null) return defaultValue;
  const suffix = defaultValue ? color.dim(` (${defaultValue})`) : "";
  stdout.write(`  ${question}${suffix} `);
  const line = await prompter.next();
  if (line === null) {
    stdout.write(color.dim("(end of input — using default)\n"));
    return defaultValue;
  }
  const answer = line.trim();
  return answer === "" ? defaultValue : answer;
}

/** Ask a yes/no question; returns the default in --yes mode or after EOF. */
export async function confirm(question, defaultValue) {
  if (prompter === null) return defaultValue;
  const hint = defaultValue ? "Y/n" : "y/N";
  stdout.write(`  ${question} ${color.dim(`[${hint}]`)} `);
  const line = await prompter.next();
  if (line === null) {
    stdout.write(color.dim("(end of input — using default)\n"));
    return defaultValue;
  }
  const answer = line.trim().toLowerCase();
  if (answer === "") return defaultValue;
  return answer === "y" || answer === "yes";
}

/** Check whether an executable exists on PATH. */
export function hasCommand(command) {
  const probe = process.platform === "win32" ? "where" : "which";
  return spawnSync(probe, [command], { stdio: "ignore" }).status === 0;
}

/**
 * Run an external command with inherited stdio so the user sees its output.
 * Returns true on exit code 0; failures are reported, never thrown — every
 * step must degrade to manual instructions rather than abort the setup.
 */
export function run(command, args, cwd) {
  stdout.write(color.dim(`  $ ${command} ${args.join(" ")}\n`));
  const result = spawnSync(command, args, { stdio: "inherit", cwd });
  if (result.status !== 0) {
    stdout.write(
      color.yellow(
        `  command failed (exit ${result.status ?? "?"}) — continuing\n`,
      ),
    );
    return false;
  }
  return true;
}

/** Actions performed, collected for the final summary. */
export const actions = [];

export function record(message) {
  actions.push(message);
  stdout.write(`  ${color.green("+")} ${message}\n`);
}

export function note(message) {
  stdout.write(`  ${color.yellow("•")} ${message}\n`);
}

export function heading(title) {
  stdout.write(`\n${color.bold(color.cyan(title))}\n`);
}
