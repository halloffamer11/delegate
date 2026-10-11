#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const argv = process.argv.slice(2);
let briefPath = null;
let cdDir = process.cwd();
let outDir = null;
let model = null;
let effort = null;
let timeout = null;
let printTimeout = null;
let readOnly = false;
let dangerouslySkipPermissions = false;
let ignoreUserConfig = false;
let skipGitRepoCheck = false;
let lane = null;
let maxTurns = null;

for (let i = 0; i < argv.length; i++) {
  const arg = argv[i];
  if (arg === "--brief") briefPath = argv[++i];
  else if (arg === "--cd") cdDir = argv[++i];
  else if (arg === "--out-dir") outDir = argv[++i];
  else if (arg === "--model") model = argv[++i];
  else if (arg === "--effort") effort = argv[++i];
  else if (arg === "--timeout") timeout = argv[++i];
  else if (arg === "--print-timeout") printTimeout = argv[++i];
  else if (arg === "--read-only") readOnly = true;
  else if (arg === "--dangerously-skip-permissions") dangerouslySkipPermissions = true;
  else if (arg === "--ignore-user-config") ignoreUserConfig = true;
  else if (arg === "--skip-git-repo-check") skipGitRepoCheck = true;
  else if (arg === "--lane") lane = argv[++i];
  else if (arg === "--max-turns") maxTurns = argv[++i];
}

if (!outDir) {
  process.stderr.write("fake-relay: missing --out-dir\n");
  process.exit(2);
}
fs.mkdirSync(outDir, { recursive: true });

// 1. write argv.json
fs.writeFileSync(path.join(outDir, "argv.json"), JSON.stringify(argv, null, 2) + "\n");

// 1b. write env.json. A codex run points CODEX_HOME at delegate's own home, and
// the argv alone cannot show that, so record what the dispatcher handed us.
fs.writeFileSync(
  path.join(outDir, "env.json"),
  JSON.stringify({ CODEX_HOME: process.env.CODEX_HOME ?? null }, null, 2) + "\n"
);

// 2. copy brief to brief.txt
let briefContent = Buffer.alloc(0);
if (briefPath && fs.existsSync(briefPath)) {
  briefContent = fs.readFileSync(briefPath);
  fs.writeFileSync(path.join(outDir, "brief.txt"), briefContent);
}

// 3. parse directive line
const briefStr = briefContent.toString("utf8");
const match = briefStr.match(/fake-relay:\s*([^\r\n]+)/);
let status = "completed";
let finalFile = null;
let exitCode = null;
let errorText = null;
let violation = false;

if (match) {
  const directive = match[1].trim();
  const sMatch = directive.match(/\bstatus=(\S+)/);
  if (sMatch) status = sMatch[1];

  const fMatch = directive.match(/\bfinal=(\S+)/);
  if (fMatch) finalFile = fMatch[1];

  const eMatch = directive.match(/\bexit=(\d+)/);
  if (eMatch) exitCode = parseInt(eMatch[1], 10);

  const vMatch = directive.match(/\bviolation=(true|false)/);
  if (vMatch) violation = (vMatch[1] === "true");

  // hold=<path>: wait (up to 20 s) until that file exists, so a test can
  // look at dispatch's output while the relay is still running.
  const hMatch = directive.match(/\bhold=(\S+)/);
  if (hMatch) {
    const tick = new Int32Array(new SharedArrayBuffer(4));
    for (let i = 0; i < 400 && !fs.existsSync(hMatch[1]); i++) Atomics.wait(tick, 0, 0, 50);
  }

  const errMatch = directive.match(/\berror="([^"]+)"/) || directive.match(/\berror=([^\n\r]+?)(?=(\s+(?:status|final|exit|violation|hold|crash|replay)=|$))/);
  if (errMatch) errorText = errMatch[1].trim();

  // crash=<message>: throw before result.json, as a relay that hits a bug
  // does; node prints the error, its stack and its own version on stderr.
  const cMatch = directive.match(/\bcrash=([^\n\r]+?)(?=(\s+(?:status|final|exit|violation|hold|error|replay)=|$))/);
  if (cMatch) throw new Error(cMatch[1].trim());

  // replay=<dir>: leave the relay files of a run directory, as a real relay
  // left them, in --out-dir: result.json, events.jsonl and final.txt are
  // copied, and its relay.stdout and relay.stderr are written to this
  // process's own. Exits with exit=<n>, else the exitCode result.json holds,
  // else 0.
  const rMatch = directive.match(/\breplay=(\S+)/);
  if (rMatch) {
    const from = rMatch[1];
    for (const name of ["result.json", "events.jsonl", "final.txt"]) {
      const src = path.join(from, name);
      if (fs.existsSync(src)) fs.copyFileSync(src, path.join(outDir, name));
    }
    for (const [name, fd] of [["relay.stdout", 1], ["relay.stderr", 2]]) {
      const src = path.join(from, name);
      if (fs.existsSync(src)) fs.writeSync(fd, fs.readFileSync(src));
    }
    let replayed = null;
    try {
      replayed = JSON.parse(fs.readFileSync(path.join(from, "result.json"), "utf8"));
    } catch {
      replayed = null;
    }
    const code = exitCode !== null ? exitCode
      : (replayed && Number.isInteger(replayed.exitCode) ? replayed.exitCode : 0);
    process.exit(code);
  }
}

if (status === "none") {
  process.exit(exitCode !== null ? exitCode : 2);
}

let finalMessage = "";
if (finalFile) {
  if (fs.existsSync(finalFile)) {
    finalMessage = fs.readFileSync(finalFile, "utf8");
    fs.writeFileSync(path.join(outDir, "final.txt"), finalMessage);
  }
}

if (exitCode === null) {
  exitCode = (status === "completed") ? 0 : 1;
}

let readOnlyViolation = null;
if (violation) {
  readOnlyViolation = true;
} else if (readOnly) {
  readOnlyViolation = false;
}

const result = {
  status: status,
  exitCode: exitCode,
  signal: null,
  finalMessage: finalMessage,
  readOnlyViolation: readOnlyViolation,
  threadId: "fake-thread",
  touchedFiles: [],
  usage: null
};

if (errorText !== null) {
  result.error = errorText;
}

fs.writeFileSync(path.join(outDir, "result.json"), JSON.stringify(result, null, 2) + "\n");
process.exit(exitCode);
