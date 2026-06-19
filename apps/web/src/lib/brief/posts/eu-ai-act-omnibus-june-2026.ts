import type { Post } from "@/lib/brief";

export const post: Post = {
  slug: "eu-ai-act-omnibus-june-2026",
  title: "The EU AI Act deadline you were building toward just moved. Here's what didn't.",
  excerpt:
    "On May 7, 2026, a provisional agreement reshuffled the high-risk AI deadlines most compliance teams had been targeting. Some things got delayed 16 months. Others are enforceable right now.",
  category: "Market",
  author: "Laila Osei",
  authorRole: "Policy & compliance",
  date: "2026-06-11",
  cover: "violet",
  tierCta: "enterprise",
  body: [
    {
      k: "p",
      t: "If your AI governance roadmap was built on compliance guides published before May 7, 2026, parts of it are wrong. On that date, the European Parliament and Council reached provisional political agreement on the Digital Omnibus amendments to the EU AI Act. The headline change: the August 2, 2026 deadline for high-risk Annex III AI systems — the one that's driven most enterprise compliance spending over the past year — has moved to December 2, 2027. Sixteen more months.",
    },
    {
      k: "p",
      t: "One critical caveat before anyone starts deprioritizing: the Digital Omnibus is still a provisional agreement. Parliamentary committee approval came through in early June 2026; the full plenary vote and Council formal adoption are expected before August 2. Until the text is published in the Official Journal of the EU, the original deadlines remain legally binding. As [Bits From Bytes noted](https://bitsfrombytes.com/eu-ai-act-phase-1-implementation-update/), organizations treating the postponement as already in force are taking a legal risk. Directionally, the delay is settled. Legally, it isn't yet.",
    },
    { k: "h2", t: "What got delayed" },
    {
      k: "ul",
      items: [
        "**Annex III high-risk systems** (recruitment tools, credit scoring, biometrics, law enforcement AI, education and border management): pushed from August 2, 2026 to December 2, 2027.",
        "**Annex I high-risk systems** (AI embedded in regulated products — medical devices, machinery, radio equipment): pushed from August 2, 2027 to August 2, 2028.",
        "**National AI regulatory sandboxes**: member states' deadline to establish these moves from August 2026 to August 2027.",
      ],
    },
    { k: "h2", t: "What didn't move" },
    {
      k: "p",
      t: "This is the half of the story getting less attention. Three obligations are in force now, not in 2027:",
    },
    {
      k: "ul",
      items: [
        "**Article 5 prohibited practices** have been live since February 2025. Banned uses — social scoring by public authorities, real-time remote biometric surveillance in public spaces, systems that manipulate vulnerable groups — are enforceable today.",
        "**GPAI model obligations** (Articles 51–56) activated in August 2025. Starting August 2, 2026, the EU AI Office gains direct enforcement authority to fine GPAI providers for noncompliance — up to 3% of global annual turnover. This is not delayed.",
        "**Article 50 transparency obligations** apply from August 2026. The watermarking requirement for AI-generated content has a grace period to December 2, 2026, but the core transparency duties are live.",
      ],
    },
    {
      k: "p",
      t: "A [post-Omnibus deployer obligations guide from Alatirok](https://alatirok.com/eu-ai-act-deployer-obligations-2026/) puts the fine exposure in plain terms: Article 26 deployer violations carry up to €15 million or 3% of worldwide annual turnover, whichever is higher. The Article 26 duties — log retention for at least six months, assignment of human oversight, operation monitoring, worker notification before workplace deployment — are what the Omnibus delayed on their full conformity clock, but the artifacts required to demonstrate them take real engineering time to build. The runway is for execution, not for waiting.",
    },
    { k: "h2", t: "What to actually do before August" },
    {
      k: "p",
      t: "[Axis Intelligence's post-Omnibus enforcement guide](https://axis-intelligence.com/eu-ai-act-enforcement-guide/) is the sharpest I've seen on this: 'The postponement applies to technical conformity deadlines, not to the underlying requirement for responsible AI governance.' The classification work — figuring out which of your AI deployments land in Annex III — can't wait for 2027. That mapping depends on supplier documentation you may not have and needs to stay current as your deployments evolve.",
    },
    {
      k: "ul",
      items: [
        "**Audit your AI inventory now.** You can't classify systems you haven't listed. This is the foundational work and it takes longer than expected.",
        "**Document Article 5 prohibitions.** These are already enforceable. If you're unclear whether any deployed systems touch the banned practices, resolve that first.",
        "**Start Article 26 infrastructure.** Log retention, human oversight assignment, and operation monitoring require engineering time. Use the 18-month window to build them, not as an excuse to start in 2027.",
        "**If you operate GPAI models: August 2026 is not theoretical.** That's when fines start. GPAI obligations are not delayed.",
      ],
    },
    { k: "h2", t: "Where Vantio fits" },
    {
      k: "p",
      t: "Article 26 requires deployers to retain automatically generated logs and demonstrate human oversight. The audit trail Vantio produces — metadata-only records of every agent action, what policy applied, what was allowed or blocked, with timestamps — is the kind of artifact Article 26 compliance depends on. It wasn't designed as a compliance product; it's infrastructure for governing agents that happens to produce exactly what a log-retention and oversight-documentation program needs. If you're building the evidence pipeline for your EU AI Act obligations, the agent event trail is a practical starting point.",
    },
  ],
  sources: [
    {
      label:
        "Axis Intelligence — EU AI Act Enforcement 2026: The Post-Omnibus Guide",
      url: "https://axis-intelligence.com/eu-ai-act-enforcement-guide/",
    },
    {
      label:
        "Bits From Bytes — EU AI Act Phase 1 Implementation Update (June 2026)",
      url: "https://bitsfrombytes.com/eu-ai-act-phase-1-implementation-update/",
    },
    {
      label:
        "Alatirok — EU AI Act Deployer Obligations After the Omnibus (2026)",
      url: "https://alatirok.com/eu-ai-act-deployer-obligations-2026/",
    },
    {
      label:
        "Usercentrics — EU AI Act Digital Omnibus: What It Means for Consent Infrastructure",
      url: "https://usercentrics.com/knowledge-hub/eu-ai-act-high-risk-delay-article-50-transparency-consent/",
    },
  ],
};
