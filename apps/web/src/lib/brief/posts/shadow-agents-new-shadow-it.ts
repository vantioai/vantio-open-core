import type { Post } from "@/lib/brief";

export const post: Post = {
  slug: "shadow-agents-new-shadow-it",
  title: "Shadow agents are the new shadow IT",
  excerpt:
    "The old shadow-AI problem was an employee pasting data into a chatbot. The new one is an autonomous agent running with that employee's permissions — reading repos, calling APIs, moving data at machine speed. Same blind spot, much bigger teeth.",
  category: "Market",
  author: "Dani Brooks",
  authorRole: "Security & governance",
  date: "2026-05-24",
  cover: "red",
  tierCta: "pro",
  body: [
    { k: "p", t: "Two years ago, “shadow AI” meant something you could picture: an employee pasting a customer list into ChatGPT, a developer dropping proprietary code into a chat window. Real risk, but a familiar shape — data going out one window at a time." },
    { k: "p", t: "That shape changed. The same employees now point autonomous agents at folders, repositories, and internal systems and tell them to go do something. The agent reads files, runs commands, queries databases, calls other agents — and it does it with whatever permissions the person who launched it already had. The Cloud Security Alliance [put it about as sharply as you can](https://cloudsecurityalliance.org/blog/2026/05/26/shadow-ai-agents-the-insider-threat-you-re-not-monitoring-yet): the earlier risk was that shadow AI exposed your data; the risk now is that it operates on it." },
    { k: "h2", t: "How big is this, really?" },
    { k: "p", t: "Take the specific numbers as directional — they come from vendor and survey data, not a census — but the direction is not subtle. A widely-cited 2026 roundup reported a [466% year-over-year jump in AI agents operating inside enterprise environments](https://www.iprompt.com/p/the-agents-inside-the-walls-shadow-ai-security-in-2026), an average of dozens of deployed agents per organization, and — the stat that should keep you up — only about a quarter of organizations claiming full visibility into which agents are even talking to each other." },
    { k: "p", t: "In other words: most of the agents are unmanaged, and most teams can't list them. That's textbook shadow IT, except the “IT” can now act on its own." },
    { k: "h2", t: "Why agents leak in the first place" },
    { k: "p", t: "An agent is a near-perfect exfiltration channel by construction. It has read access to sensitive internal data, the ability to call tools that make outbound network requests, and a well-documented weakness to prompt injection. Put those together and you don't even need a malicious insider — you need a poisoned document. [Security researchers have been blunt about this](https://safeguard.sh/resources/blog/data-exfiltration-via-llm-agents-2026): instructions hidden in a support ticket, a GitHub issue, or a retrieved file can turn the model into an unwitting courier." },
    { k: "p", t: "It's not hypothetical. The Slack AI RAG incident in 2024 showed an attacker placing instructions in a public channel that caused the assistant to pull data from private channels it shouldn't have touched. And a financial-services incident documented in a 2026 zero-trust [research paper](https://www.cequence.ai/wp-content/uploads/2026/05/Agentic-Zero-Trust-Research-Paper-v3.pdf) describes an agent exfiltrating tens of thousands of customer records — not because it was hacked in the classic sense, but because the request looked like a reasonable business task." },
    { k: "h2", t: "Why your existing controls don't catch it" },
    { k: "ul", items: [
      "DLP was tuned to spot a human doing something unusual. An agent acting inside a sanctioned identity, over normal protocols, doesn't look unusual.",
      "The traffic is legitimate. The agent is using credentials it was given, hitting APIs it's allowed to hit. Nothing trips.",
      "There's no inventory. You can't govern, scope, or revoke an agent you don't know exists.",
    ] },
    { k: "h2", t: "What actually helps" },
    { k: "p", t: "The defenses that hold up share a theme: stop trusting the agent's intent and start constraining its reach. Inventory every agent and its grants. Scope tool permissions to the minimum. Gate outbound actions that could carry sensitive content. And — the one most teams skip — control where data is actually allowed to go, at the moment it tries to leave." },
    { k: "h2", t: "Where Vantio fits" },
    { k: "p", t: "This is the problem we were built for. Vantio redacts PII from a request before it ever leaves your environment, so a poisoned prompt can't turn a customer record into an outbound payload. Host allow/block rules mean an agent calling somewhere it has no business calling gets stopped client-side and logged — not discovered in a breach report. And because every decision is written to a metadata-only trail, you finally get the inventory: what your agents did, where they tried to send things, and what got blocked. For workloads where “stopped in user-space” isn't enough, Enterprise pushes that same enforcement into the kernel, so off-policy egress is dropped before it leaves the node even if the application layer is compromised." },
  ],
  sources: [
    { label: "Cloud Security Alliance — Shadow AI Agents: The Insider Threat You're Not Monitoring Yet", url: "https://cloudsecurityalliance.org/blog/2026/05/26/shadow-ai-agents-the-insider-threat-you-re-not-monitoring-yet" },
    { label: "iPrompt — Shadow AI Security in 2026", url: "https://www.iprompt.com/p/the-agents-inside-the-walls-shadow-ai-security-in-2026" },
    { label: "Safeguard — Data Exfiltration via LLM Agents in 2026", url: "https://safeguard.sh/resources/blog/data-exfiltration-via-llm-agents-2026" },
    { label: "Cequence — Agentic Zero Trust (research paper)", url: "https://www.cequence.ai/wp-content/uploads/2026/05/Agentic-Zero-Trust-Research-Paper-v3.pdf" },
  ],
};
