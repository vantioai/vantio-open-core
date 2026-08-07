const vscode = require("vscode");
const { execFile } = require("child_process");
const { promisify } = require("util");
const execFileAsync = promisify(execFile);

async function runVantio(args) {
  try {
    const { stdout, stderr } = await execFileAsync("vantio", args, {
      maxBuffer: 4 * 1024 * 1024,
      env: process.env,
    });
    return (stdout || stderr || "").trim() || "(no output)";
  } catch (e) {
    const msg = e.stderr || e.message || String(e);
    if (/ENOENT|not found/i.test(msg) || e.code === "ENOENT") {
      return "vantio CLI not found. Install: npm install -g @vantio/cli";
    }
    return msg;
  }
}

function show(docTitle, body) {
  const doc = vscode.window.createOutputChannel(docTitle);
  doc.clear();
  doc.appendLine(body);
  doc.show(true);
}

function activate(context) {
  context.subscriptions.push(
    vscode.commands.registerCommand("vantio.prove", async () => {
      const out = await runVantio(["prove", "--format=md"]);
      show("Vantio Optics · Prove", out);
    }),
    vscode.commands.registerCommand("vantio.discoverLocal", async () => {
      const out = await runVantio(["discover", "--local"]);
      show("Vantio Optics · Discover", out);
    }),
    vscode.commands.registerCommand("vantio.upgradePath", async () => {
      show(
        "Vantio Optics · Upgrade path",
        [
          "Vantio Optics (Free) — Sight Loop · observe only",
          "  prove · discover local · this residual cue",
          "",
          "Honest residual: Optics does not enforce.",
          "Ungoverned paths stay silent — that gap is the upgrade signal.",
          "",
          "When observe is not enough:",
          "  → Pro · Vantio Gate — Policy Latch (enforce) — see pricing",
          "  → Enterprise · Vantio Phantom Engine — Absolute Control",
          "",
          "https://vantio.ai/pricing",
        ].join("\n"),
      );
    }),
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
