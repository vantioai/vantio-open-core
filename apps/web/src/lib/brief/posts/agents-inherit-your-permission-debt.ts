import type { Post } from "@/lib/brief";

export const post: Post = {
  slug: "agents-inherit-your-permission-debt",
  title: "Your AI agent just inherited 96% of the access you never use",
  excerpt:
    "Research on 3.6 billion permissions found that humans exercise about 4% of the access they're granted. When an agent inherits a user account, it inherits the other 96% — and unlike the human, it will actually use it.",
  category: "Guide",
  author: "Priya Nadkarni",
  authorRole: "Dev-tools engineer, recovering SRE",
  date: "2026-06-14",
  cover: "blue",
  tierCta: "pro",
  body: [
    {
      k: "p",
      t: "Oso and Cyera analyzed 2.4 million workers and 3.6 billion application permissions and found that humans exercise roughly 4% of the access they're granted over any 90-day window. [InfoWorld's coverage of the research](https://www.infoworld.com/article/4148328/the-agent-security-mess.html) put it starkly: only 9% of sensitive data that workers can access is ever actually touched, and nearly a third of users have the power to modify or delete sensitive data they've never queried. Permission sprawl is an old problem. We've known about it for years and mostly not fixed it.",
    },
    {
      k: "p",
      t: "That statistic was already uncomfortable. Then enterprises started pointing agents at production systems using inherited human credentials, and it became urgent. A human with unused database-write access mostly doesn't write to the database. An agent told to 'clean up stale records' that happens to hold the dormant permission to modify the entire database will attempt to do exactly that. The distinction between 'has the permission' and 'would ever use it' evaporates.",
    },
    { k: "h2", t: "The numbers aren't theoretical" },
    {
      k: "p",
      t: "According to a [Cloud Security Alliance study published in April 2026](https://cloudsecurityalliance.org/press-releases/2026/04/16/more-than-half-of-organizations-experience-ai-agent-scope-violations-cloud-security-alliance-study-finds) — commissioned by Zenity and drawing on enterprise survey data — 53% of organizations have had AI agents exceed their intended permissions. Only 8% reported that agents never exceed their intended permissions. Just 16% said they have high confidence in their ability to detect agent-specific threats; 44% reported low or no confidence.",
    },
    {
      k: "p",
      t: "A separate report from the Cloud Security Alliance and Token Security, [covered by Kiteworks in April 2026](https://www.kiteworks.com/cybersecurity-risk-management/ai-agent-security-incidents-2026/), found that 65% of organizations experienced at least one security incident in the past year caused by an AI agent operating on their network. The incidents don't cluster around sophisticated attacks. They cluster around permissions doing exactly what they were granted to do.",
    },
    { k: "h2", t: "Why inheriting human credentials is structurally wrong" },
    {
      k: "ul",
      items: [
        "A human credential carries the entire historical permission surface — all the access accumulated, never cleaned up, never scoped down after a role change.",
        "Agents operate continuously, don't get tired, and chain actions across systems without the hesitation a human brings to 'this feels risky.'",
        "When something goes wrong, audit logs tied to a human credential can't tell you which agent, which session, which autonomous decision triggered the action.",
        "Revoking access for the agent means revoking it for the human whose credentials it inherited.",
      ],
    },
    { k: "h2", t: "What a better model looks like" },
    {
      k: "p",
      t: "The [Auth0 post on AI agent permissions](https://auth0.com/blog/why-ai-agents-need-their-own-permission-model/) articulates the target clearly: agents should request short-lived tokens tied to the specific execution plan, carrying only the capabilities that plan requires, expiring in minutes, discarded after use. The token shouldn't preauthorize everything the agent might conceivably need — it should encode the specific actions the current task calls for.",
    },
    {
      k: "ul",
      items: [
        "**Give agents their own identity.** Not a shared API key. Not a human credential. A distinct machine identity that can be inventoried, scoped, and revoked on its own without touching anyone's user account.",
        "**Task-scope the permissions.** An agent doing a code review doesn't need write access. An agent reading logs doesn't need production database credentials. Scope at task time, not at registration time, and let those permissions expire when the task ends.",
        "**Separate drafting from executing.** The ability to propose an action and the ability to carry it out are different permissions. Irreversible operations — deletions, payments, external requests, configuration changes — should require explicit authorization, not just an agent that decided to proceed.",
        "**Inventory what exists.** The CSA research found most organizations have no decommissioning strategy for agents. That's the foundational problem. Treat every agent as a governance artifact with a lifecycle — something that gets reviewed and retired, not just deployed.",
      ],
    },
    {
      k: "quote",
      t: "Agents require purpose-built identities with aggressively minimal permissions. If 96% of a human user's access goes unused anyway, we can't grant that excess access to a machine.",
      cite: "InfoWorld, citing Oso blind spot research",
    },
    { k: "h2", t: "Where Vantio fits" },
    {
      k: "p",
      t: "The scope-violation problem is partly a permission problem and partly a visibility problem — you can't govern what you can't see in motion. Vantio's metadata trail records every agent action: which agent, which tool, what the call looked like, and what the policy outcome was. That gives you the inventory in practice rather than on paper — not a list of what you think agents are authorized to do, but a record of what they actually did. Pair that with host allow/block policies that constrain egress regardless of what the inherited permission grant says, and you've closed the gap between 'the agent had access' and 'the agent could reach it.'",
    },
  ],
  sources: [
    {
      label:
        "InfoWorld — The agent security mess (citing Oso/Cyera blind spot research)",
      url: "https://www.infoworld.com/article/4148328/the-agent-security-mess.html",
    },
    {
      label:
        "Cloud Security Alliance — More Than Half of Organizations Experience AI Agent Scope Violations (April 2026)",
      url: "https://cloudsecurityalliance.org/press-releases/2026/04/16/more-than-half-of-organizations-experience-ai-agent-scope-violations-cloud-security-alliance-study-finds",
    },
    {
      label:
        "Kiteworks — AI Agent Security Incidents Hit 65% of Firms in 2026 (citing CSA/Token Security research)",
      url: "https://www.kiteworks.com/cybersecurity-risk-management/ai-agent-security-incidents-2026/",
    },
    {
      label: "Auth0 — Why AI Agents Need Their Own Permission Model",
      url: "https://auth0.com/blog/why-ai-agents-need-their-own-permission-model/",
    },
  ],
};
