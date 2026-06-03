import type { Post } from "@/lib/brief";

export const post: Post = {
  slug: "the-47000-dollar-agent",
  title: "The $47,000 agent that ran for eleven days",
  excerpt:
    "Autonomous agents fail in a way your dashboards are blind to: they keep working, keep returning 200s, and keep spending. Here's the anatomy of a runaway — and the unglamorous controls that actually stop one.",
  category: "Market",
  author: "Marcus Reyes",
  authorRole: "Writes about AI infrastructure economics",
  date: "2026-05-29",
  cover: "emerald",
  featured: true,
  tierCta: "pro",
  body: [
    { k: "p", t: "The number that should scare you isn't the $47,000. It's the eleven days." },
    { k: "p", t: "In a [widely-shared post-mortem](https://www.kognita.co/blog/ai-agent-runaway-cost-no-kill-switch), an engineering team described a multi-agent system that hit a failure condition, started retrying, and just… kept going. No spend limit per agent. No timeout. No alert. The retries quietly burned tokens for a week and a half, and the way the team found out was the invoice. The architecture that gave the agent its capability never included a mechanism to make it stop." },
    { k: "p", t: "If your reaction is “that would never happen to us,” I'd gently point out that it almost certainly already is happening to you, just smaller. The mechanism is ordinary. The size is the only variable." },
    { k: "h2", t: "Agents don't spend like chatbots" },
    { k: "p", t: "A chatbot turn is roughly one request in, one response out. An agent turn is a loop: think, call a tool, read the result, think again. And here's the part that wrecks budgets — most agent frameworks re-send the entire accumulated context on every step. So token usage doesn't grow with the work done. It grows with the number of steps, and each step is heavier than the last." },
    { k: "p", t: "Reported multipliers vary, but they're all ugly. [LeanOps pegs agent token burn at 10–100x a chatbot](https://leanopstech.com/blog/agentic-ai-cost-runaway-token-budget-2026/) for the same task; a Goldman Sachs analysis cited in the runaway write-up above landed around 24x. Pick whichever number you like. The point is that a loop isn't a linear cost — it's a compounding one, and nobody set an upper bound on it." },
    { k: "h2", t: "The failure mode nothing instruments" },
    { k: "p", t: "Here's what makes runaways so expensive: from your monitoring stack's point of view, everything is fine. The API calls return `200 OK`. Latency is steady. CPU is near zero, because the model is doing the heavy lifting somewhere else. [One team watched an agent burn ~$2,800 in four hours while every dashboard stayed green](https://explore.n1n.ai/blog/prevent-runaway-ai-agent-costs-token-spirals-2026-05-25)." },
    { k: "p", t: "Traditional APM was built to answer “is the system up?” It was never built to answer “is this agent making progress, or is it paying full price to fail in a circle?” Those are different questions, and the second one is the one that empties your account." },
    { k: "ul", items: [
      "A retry loop looks identical to healthy traffic — same endpoint, same 200s, just more of them.",
      "Billing alerts arrive after the spend, not during it. By the time the email lands, the damage is done.",
      "Multi-agent chains amplify it: one stuck upstream agent can keep ten downstream agents busy and billable.",
    ] },
    { k: "h2", t: "The fix is boring. That's why it works." },
    { k: "p", t: "Nobody wants to hear that the answer to a frontier-AI problem is the same thing we've used to tame every other runaway process: limits and a kill switch. But it is. The teams who don't get surprised by their invoice are the ones who treat an autonomous run as a high-risk process that needs hard bounds, not a clever assistant that deserves the benefit of the doubt." },
    { k: "ul", items: [
      "**Hard budget caps, not alerts.** A per-run and per-tenant token/dollar ceiling that actually halts execution. An alert is a notification that you're already losing money.",
      "**Repetition detection.** If the last N tool calls are identical and the result keeps coming back the same, stop. That's not progress; that's a spin cycle.",
      "**A real kill switch.** Something that turns an eleven-day incident into an eleven-minute one. As the post-mortem put it, the difference comes entirely from whether your runtime has one.",
    ] },
    { k: "quote", t: "A kill switch is not a nice-to-have for agentic AI. It is the difference between an eleven-day incident and an eleven-minute one.", cite: "Kognita post-mortem" },
    { k: "h2", t: "Where Vantio fits" },
    { k: "p", t: "I'll be straight about this, because the alternative is insulting: Vantio is not magic, and it won't make a badly-designed agent smart. What it does is enforce the boring controls where your agent actually runs. You set a per-run spend cap in a policy; the SDK halts further spend locally when the agent crosses it — before the next expensive call, not after the invoice. And because every action is recorded as metadata, a stuck loop shows up as a burst of repeated, blocked, or severed events you can alert on, instead of a silent green dashboard." },
    { k: "p", t: "The free tier gives you the visibility — you can watch what your agents actually do and spot the spin cycle yourself. The paid tier adds the brakes. Either way, the goal is the same: make “it ran for eleven days” a sentence you never get to say." },
  ],
  sources: [
    { label: "Kognita — A Runaway AI Agent Ran for 11 Days and Cost $47,000", url: "https://www.kognita.co/blog/ai-agent-runaway-cost-no-kill-switch" },
    { label: "LeanOps — AI Agents Burn 50x More Tokens Than Chats", url: "https://leanopstech.com/blog/agentic-ai-cost-runaway-token-budget-2026/" },
    { label: "n1n.ai — Preventing Runaway AI Agent Costs and Token Spirals", url: "https://explore.n1n.ai/blog/prevent-runaway-ai-agent-costs-token-spirals-2026-05-25" },
    { label: "Cencori — Circuit Breakers for AI Agents", url: "https://cencori.com/blog/circuit-breakers-for-ai-agents" },
  ],
};
