import type { Post } from "@/lib/brief";

export const post: Post = {
  slug: "audit-trail-for-ai-agents",
  title: "Your agent returned 200. That tells you almost nothing.",
  excerpt:
    "An agent can return a clean HTTP 200 while hallucinating, calling a tool it was never allowed to touch, and drifting off-policy for weeks — and your APM will smile the whole time. What an agent audit trail actually needs to capture.",
  category: "Guide",
  author: "Sam Okafor",
  authorRole: "Platform engineering",
  date: "2026-05-21",
  cover: "violet",
  tierCta: "developers",
  body: [
    { k: "p", t: "Traditional monitoring asks one question: is the system up? For agents, that's the wrong question, and the gap between it and the right one is where the trouble lives. As one engineering team writing about regulated workloads [put it](https://predictionguard.com/blog/agentic-ai-monitoring-observability-metrics): an agent can return HTTP 200 with a hallucinated response, call an unauthorized tool while latency metrics stay flat, and drift from its policy baseline over weeks without tripping a single alert." },
    { k: "p", t: "Your dashboard isn't lying, exactly. It's answering the question it was designed for. It just has no idea what the agent actually did." },
    { k: "h2", t: "Telemetry, observability, and an actual record" },
    { k: "p", t: "These get used interchangeably and they shouldn't. Infrastructure telemetry is CPU, memory, latency, error rate. Useful, and completely blind to agent behavior. DataRobot's framing is the one I keep coming back to: [if you can't see reasoning, tool calls, and behavior over time, you don't have observability — you have infrastructure telemetry](https://www.datarobot.com/blog/ai-agent-observability-leading-platforms/)." },
    { k: "p", t: "But even rich observability isn't the same as a record you can hand to someone who doesn't trust you. A dashboard is for you, now. An audit trail is for an auditor, a regulator, or your own incident review, six months from now. Those need different things." },
    { k: "h2", t: "What an agent audit trail has to capture" },
    { k: "p", t: "The clearest articulation I've seen of the gap comes from Siddhant Khare's [piece on agent observability](https://siddhantkhare.com/writing/agent-observability-gap), and it maps cleanly onto OpenTelemetry's data model. The shape you want:" },
    { k: "ul", items: [
      "**A trace ID per task, a span per tool call**, with parent/child relationships — so a chain of “the agent read this, which led it to change that, which failed a test, which triggered a retry” is reconstructable, not lost.",
      "**Structured, not scrollback.** JSON lines you can query and replay, not terminal output you scrolled past. Background execution is the default now — headless runs, async tasks, background agents — and nobody is watching the terminal when it matters.",
      "**Every tool call, LLM request, and file access** with timestamp, inputs, outputs, duration, and result.",
      "**The permission decision itself**: what was requested, what policy applied, what was allowed or blocked. That's the line auditors actually ask about.",
    ] },
    { k: "h2", t: "Why this stops being optional" },
    { k: "p", t: "Two forces are converging. Compliance is the loud one: high-risk-AI audit-trail expectations under the EU AI Act, SOC 2 auditors now asking pointed questions about agent governance, enterprise buyers who simply won't sign until you can show what your agent did and prove it. If you can't answer with structured data, that deal stalls." },
    { k: "p", t: "The quieter force is a design choice you make early and regret late: where does the record live? Cloud observability tools generate plenty of visibility, but many of them delegate the governance decision — and the data — to someone else's platform. For anything sensitive, you want the trail inside your own boundary, in a format you control, that you can hand over without also handing over your prompts." },
    { k: "h2", t: "Where Vantio fits" },
    { k: "p", t: "Here's the honest pitch: the free tier is the audit trail people keep hand-rolling. Wrap your agent and every action becomes a structured, metadata-only event — trace ID, target host, action taken, bytes, an HMAC receipt you can verify — with zero prompt or completion content ever leaving your environment. No “send us your data so we can show you a graph.” You get the record, queryable and exportable, and you get it before a regulator or a customer asks for it. Start there; you can add enforcement later. The record is the part you'll wish you'd had from day one." },
  ],
  sources: [
    { label: "Prediction Guard — Monitoring and observability for autonomous AI agents", url: "https://predictionguard.com/blog/agentic-ai-monitoring-observability-metrics" },
    { label: "Siddhant Khare — The agent observability gap", url: "https://siddhantkhare.com/writing/agent-observability-gap" },
    { label: "DataRobot — AI agent observability: what enterprises need to know", url: "https://www.datarobot.com/blog/ai-agent-observability-leading-platforms/" },
  ],
};
