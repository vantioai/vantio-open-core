import type { Post } from "@/lib/brief";

export const post: Post = {
  slug: "coding-agents-stuck-in-loops",
  title: "Your coding agent is stuck in a loop. Here's how to get it out.",
  excerpt:
    "One of the most common ways agentic coding tools fail isn't bad code — it's an agent that runs the same failing command, gets the same error, and tries again. Forever. A field guide to convergence.",
  category: "Guide",
  author: "Priya Nadkarni",
  authorRole: "Dev-tools engineer, recovering SRE",
  date: "2026-05-27",
  cover: "blue",
  tierCta: "pro",
  body: [
    { k: "p", t: "You've watched it happen. The agent runs a command, the command fails, and instead of stepping back, it runs the same command again. Same arguments. Same error. Then a third time. You're watching a very expensive program rediscover the definition of insanity in real time." },
    { k: "p", t: "This is not a fringe glitch. In a triage of roughly 200 open Claude Code issues, [“agent loop non-termination” came out as the #2 bug category](https://github.com/anthropics/claude-code/issues/30150): the model calls a tool, the tool fails, and it retries the identical call, burning tokens without ever converging." },
    { k: "h2", t: "Why a capable model does such a dumb thing" },
    { k: "p", t: "The honest answer is that the generation loop usually has no idea it's stuck. It checks the things that are easy to check — step count under the max, token budget not exhausted, no hook telling it to stop — and none of those catch a spin cycle. The loop never asks the questions that matter:" },
    { k: "ul", items: [
      "Were the last few tool calls identical (same tool, same arguments)?",
      "Did anything actually change between rounds, or is the output byte-for-byte the same?",
      "Has this exact tool returned this exact error K times in a row?",
    ] },
    { k: "p", t: "There's a nastier version, too. During the Opus 4.8 rollout, engineers reported the model not just repeating calls but [claiming work was done — a build passed, a file was written — when it wasn't](https://readysolutions.ai/blog/2026-05-31-opus-4-8-tool-state-regression/). When the agent can't trust its own tool results, it can't self-correct, and the loop becomes load-bearing." },
    { k: "h2", t: "Getting unstuck, today" },
    { k: "p", t: "You don't need to wait for a model update. Most of the fix is harness discipline you can add around whatever agent you're running:" },
    { k: "ul", items: [
      "**Cap the iterations.** A hard ceiling on steps (and a wall-clock timeout) turns an infinite loop into a bounded, recoverable failure.",
      "**Fingerprint tool calls.** Hash `(tool_name, args)`. If the same fingerprint shows up N turns in a row, inject a nudge — “you've tried this; try something else” — or stop with a diagnostic.",
      "**Bind verification to artifacts, not narration.** Don't accept “the tests pass” because the model said so. Tie every claim to an exit code, a file you read back, an output hash. A “done” the model produced is a claim; a “done” your gate produced is a fact.",
      "**Pin a known-good harness.** When a release regresses, pin the version that worked and avoid the configurations (huge parallel tool batches) that correlate with the corruption.",
    ] },
    { k: "p", t: "If you want the deeper version of the “run it in a loop overnight” pattern done safely, Addy Osmani's [write-up on self-improving agents](https://addyosmani.com/blog/self-improving-agents/) is the clearest I've read on stop conditions and live logs. The recurring theme: assume the loop will get stuck, and build the exit before you build the autonomy." },
    { k: "h2", t: "The part that hits your invoice" },
    { k: "p", t: "Loops aren't just annoying; they're the single most expensive bug class in agentic systems, precisely because they produce no output to tell you they've gone wrong. A stuck agent looks busy. It looks productive. It is neither, and it is billing you the whole time." },
    { k: "h2", t: "Where Vantio fits" },
    { k: "p", t: "We don't fix your agent's reasoning — that's on the model and your harness. What we do is make the spin cycle visible and bounded. Every action your agent takes is recorded as metadata, so a loop shows up as the same call, repeated, again and again — exactly the pattern an anomaly alert should fire on. Set a per-run spend cap and the loop stops costing you the moment it crosses the line. Start on the free tier just to see the repetition in your own traces; most people are surprised how often it's already happening." },
  ],
  sources: [
    { label: "anthropics/claude-code #30150 — Agent loop non-termination", url: "https://github.com/anthropics/claude-code/issues/30150" },
    { label: "Ready Solutions AI — Opus 4.8 tool-state regression", url: "https://readysolutions.ai/blog/2026-05-31-opus-4-8-tool-state-regression/" },
    { label: "Addy Osmani — Self-Improving Coding Agents", url: "https://addyosmani.com/blog/self-improving-agents/" },
  ],
};
