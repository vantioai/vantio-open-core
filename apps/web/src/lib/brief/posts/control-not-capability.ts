import type { Post } from "@/lib/brief";

export const post: Post = {
  slug: "control-not-capability",
  title: "The race that matters isn't capability. It's control.",
  excerpt:
    "Nobody has built superintelligence. But the gap between what frontier agents can already do and what we can actually oversee is widening — and you don't close it by getting a smarter model. You close it by bounding what the model is allowed to touch.",
  category: "Deep Dive",
  author: "Dani Brooks",
  authorRole: "Security & governance",
  date: "2026-05-30",
  cover: "violet",
  tierCta: "enterprise",
  body: [
    { k: "p", t: "Let's be precise, because this topic attracts more heat than light: as of mid-2026, artificial superintelligence does not exist. ASI is a theoretical stage where AI exceeds human performance across every domain, and we are not there. So this isn't a doomsday post. It's a post about a gap that's real right now." },
    { k: "p", t: "That gap has a name. One widely-read [2026 analysis calls it the capability overhang](https://medium.com/@mikhailbukhtoyarov/artificial-superintelligence-scenarios-may-2026-what-we-got-wrong-and-right-11d62fd8983c): the distance between what frontier AI systems can do and what our institutions, controls, and norms are prepared to handle — and it's widening from the wrong direction. Reasoning models and long-horizon agentic systems are already in enterprise production, running faster than the compliance frameworks meant to oversee them and faster than the interpretability research meant to understand them. You don't need ASI for that to bite. You need a capable agent and an oversight process that can't keep up. We have both." },
    { k: "h2", t: "Why “just build a smarter overseer” isn't the whole answer" },
    { k: "p", t: "The alignment research community frames the long-term version of this as superalignment — supervising and governing systems that may exceed human evaluative power, a problem [OpenAI stood up a dedicated team for in 2023](https://www.ibm.com/think/topics/superalignment) and one nobody claims to have solved. The leading technical direction, scalable oversight, uses weaker but trustworthy systems to constrain stronger ones; recent work like [Calibrated Collective Oversight](https://arxiv.org/html/2605.28807v1) even shows weaker overseers reining in an adversarially misaligned stronger agent on real benchmarks. Promising. Also unfinished, and largely about keeping the model's outputs in line." },
    { k: "p", t: "But here's the thing security people understand in their bones: you do not have to win the argument with a smarter system to contain it. A bank vault isn't smarter than a thief. A circuit breaker isn't smarter than a short. Control is not a debate you win on intelligence; it's a boundary you enforce on access. The smarter the agent, the more that distinction matters — because the one thing you can still guarantee about a system you can't fully predict is what it is physically permitted to reach." },
    { k: "h2", t: "Containment scales when persuasion doesn't" },
    { k: "p", t: "So the pragmatic posture, today, isn't to out-think the agent. It's to bound it and keep a receipt: enforce policy at the point where intent becomes action, stop an off-policy action before anything leaves, and write an immutable record of what was attempted and what was decided. That posture doesn't get harder as the model gets smarter — a dropped packet is dropped whether a toddler or a superintelligence sent it. The boundary holds regardless of who's pushing on it." },
    { k: "h2", t: "Where Vantio fits" },
    { k: "p", t: "Vantio is not an alignment solution and won't claim to be — we don't make a model want the right things. We're the other half: the control layer that bounds what an agent can do and proves what it did. Enforcement runs where the agent runs, off-policy egress is stopped before it leaves (in the kernel, for enrolled workloads, even if user-space is bypassed), and every decision is committed to a tamper-proof, metadata-only ledger you can verify without trusting us. Capability is going to keep climbing whether we're ready or not. Control is the part you actually get to decide — so decide it." },
  ],
  sources: [
    { label: "Medium (M. Bukhtoyarov) — Artificial Superintelligence Scenarios, May 2026 (the Capability Overhang)", url: "https://medium.com/@mikhailbukhtoyarov/artificial-superintelligence-scenarios-may-2026-what-we-got-wrong-and-right-11d62fd8983c" },
    { label: "IBM — What Is Superalignment?", url: "https://www.ibm.com/think/topics/superalignment" },
    { label: "arXiv — Calibrating Conservatism for Scalable Oversight (2605.28807)", url: "https://arxiv.org/html/2605.28807v1" },
    { label: "Help Net Security — Waiting for AI superintelligence? Don't hold your breath", url: "https://www.helpnetsecurity.com/2026/01/27/cybersecurity-superintelligence-ai-future/" },
  ],
};
