import type { Post } from "@/lib/brief";

// Evergreen Deep Dive — repurposed from the original Research dossier
// "Linguistics Cannot Secure Compute" with light human-voice polish.
export const post: Post = {
  slug: "linguistics-cannot-secure-compute",
  title: "Linguistics cannot secure compute",
  excerpt:
    "A post-mortem on why semantic NLP firewalls fail against autonomous agents — infinite evasion, the wrong inspection point, and latency as an attack surface — and why syscall-level interception is the only verifiable containment primitive.",
  category: "Deep Dive",
  author: "Eli Cho",
  authorRole: "Founding engineer, Vantio",
  date: "2026-05-14",
  cover: "emerald",
  tierCta: "enterprise",
  body: [
    { k: "p", t: "Here's an uncomfortable thing to say out loud if you sell an AI firewall: you cannot read your way to safety. Every semantic guardrail system rests on the same assumption — that the dangerous part of an agent's action can be reliably detected by inspecting the text associated with it. Against autonomous agents, that assumption fails, and it fails for three compounding reasons." },
    { k: "h2", t: "1. Semantic evasion is infinite" },
    { k: "p", t: "Any NLP classifier with a finite parameter space can be bypassed by a sufficiently creative prompt — and an autonomous agent can iterate on prompt construction faster than any guardrail team can retrain. You are defending a bounded model against an unbounded search. That's not a fight you win on accuracy; it's a fight whose terms are wrong." },
    { k: "h2", t: "2. The inspection point is wrong" },
    { k: "p", t: "By the time a semantic guardrail reads the model's output, the action may already be in flight. A network call, a file write, a process spawn — these happen at the syscall layer, milliseconds before any application-layer reader can respond. Inspecting the words is inspecting a description of the action, not the action itself." },
    { k: "h2", t: "3. Latency is the real attack surface" },
    { k: "p", t: "Many “AI firewall” products add a synchronous LLM inference call to the critical path of every agent action. That's a 100–2000ms blocking penalty per step, and under load it becomes a denial-of-service vector you pointed at your own infrastructure. A safety control that scales cost with traffic is a liability wearing a safety badge." },
    { k: "h2", t: "The only primitive that actually holds" },
    { k: "p", t: "The most verifiable containment primitive is physics-based: intercept at the syscall layer, in the kernel (Ring-0), where the boundary between user-space intent and physical resource access is enforced by the operating system rather than inferred from text. The decision is binary and it happens before the bytes leave. This is exactly what the Vantio Phantom Engine does for the workloads you enroll — not by reading what the agent says it will do, but by governing what it can actually reach. Semantics describe; the kernel decides." },
  ],
};
