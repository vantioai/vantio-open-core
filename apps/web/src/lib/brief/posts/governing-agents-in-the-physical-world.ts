import type { Post } from "@/lib/brief";

export const post: Post = {
  slug: "governing-agents-in-the-physical-world",
  title: "When the agent has hands",
  excerpt:
    "Software agents fail and you restore from backup. Embodied agents fail and something moves. Why governing agents that act in the physical world is a runtime problem — and where the digital boundary still does the heavy lifting.",
  category: "Deep Dive",
  author: "Theo Lindqvist",
  authorRole: "Robotics & physical-world safety",
  date: "2026-05-31",
  cover: "red",
  tierCta: "enterprise",
  body: [
    { k: "p", t: "There's a clean line between an agent that writes to a database and an agent that writes to the world. When the first one makes a mistake, you restore from backup. When the second one does, something has already moved — a forklift, a valve, a robot arm, a delivery drone. You can't roll back kinetic energy." },
    { k: "p", t: "Embodied agents — the LLM-driven kind now steering mobile robots, industrial machines, and vehicles — are pushing past passive reasoning into persistent execution in physical space. And the research consensus forming in 2026 is that the old playbook of test-it-before-you-ship-it doesn't hold for systems whose behavior depends on live data and adaptation. A [runtime governance framework for embodied agents](https://www.arxiv.org/pdf/2604.07833) makes the argument directly: governance has to be externalized into a dedicated layer that checks each proposed action — capability admission, policy checking, execution monitoring, rollback, human override — rather than trusted to live inside the agent that's also doing the planning." },
    { k: "h2", t: "It's a systems problem, not a model problem" },
    { k: "p", t: "The clearest statement of this came out of [SAE's 2026 World Congress](https://arxiv.org/html/2605.10653), where the embodied-AI panel landed on a theme worth tattooing somewhere: safe deployment depends on sensors, hardware robustness, operational design limits, cybersecurity, and organizational process — not just the algorithm. Treating an embodied agent as “software with a body” is exactly the mistake that gets someone hurt." },
    { k: "p", t: "On the controls side, runtime-governance proposals like the MI9 framework push for real-time mechanisms — semantic telemetry, conformance checking, dynamic authorization, graduated intervention — instead of a pre-deployment sign-off and a hope. And regulation is catching up: the EU's Machinery Regulation, expected to apply from 2027, treats AI acting as a safety component of a physical product as something requiring real conformity assessment. The recurring, unglamorous advice across all of it: keep granular audit trails, enforce least-privilege access to external systems, and put the emergency stop on a circuit that's physically independent of the agent's own logic." },
    { k: "h2", t: "Where the digital boundary still does the work" },
    { k: "p", t: "Here's the honest scoping, because it matters: a network policy does not stop a robot arm. Functional safety — e-stops, force limits, safety-rated controllers — is a hardware discipline, and nothing in software replaces it. But strip an embodied agent down and a huge fraction of what it does is still digital: it calls APIs, fetches instructions, reads and writes data, talks to other agents and cloud services. That digital surface is where a poisoned instruction enters, where data leaves, and where an off-policy command to some external system originates. It is governable, and most embodied stacks barely govern it." },
    { k: "h2", t: "Where Vantio fits" },
    { k: "p", t: "Vantio governs that digital half — and it does it where bypasses don't help, in the kernel. For the workloads you enroll, off-policy network egress is dropped in-kernel before it leaves the node, even if the user-space agent is compromised or confused; every action lands in a tamper-proof, metadata-only audit trail you can hand to a safety reviewer or a regulator. We're not your functional-safety controller, and we won't pretend to be — the e-stop is still yours to wire. But the instruction that tells the machine to do the wrong thing usually travels over a wire we can watch, and stopping it there, with a receipt, is the part most physical-AI deployments are missing." },
  ],
  sources: [
    { label: "arXiv — A Runtime Governance Framework for Embodied Agents (2604.07833)", url: "https://www.arxiv.org/pdf/2604.07833" },
    { label: "arXiv — Embodied AI in Action: Insights from SAE World Congress 2026 (2605.10653)", url: "https://arxiv.org/html/2605.10653" },
    { label: "Governance & Safety Frameworks: From MI9 to Misuse Reports", url: "https://www.linkedin.com/pulse/governance-safety-frameworks-from-mi9-misuse-reports-prasad-9cxqc" },
  ],
};
