import type { Post } from "@/lib/brief";

export const post: Post = {
  slug: "computer-use-agents-prompt-injection",
  title: "The webpage your agent visits is already giving it orders",
  excerpt:
    "Computer-use agents don't distinguish between content to process and instructions to follow. A low-skilled attacker used that fact to breach fourteen companies last week.",
  category: "Market",
  author: "Dani Brooks",
  authorRole: "Security & governance",
  date: "2026-06-17",
  cover: "red",
  tierCta: "pro",
  body: [
    {
      k: "p",
      t: "On June 17, 2026, Help Net Security [reported on an OALABS analysis](https://www.helpnetsecurity.com/2026/06/17/ai-agents-offensive-cyber-operations-claude-codex/) of over a thousand recovered agent sessions from a compromised server. The finding: a low-skilled attacker, using nothing but Anthropic's Claude Code and OpenAI's Codex, breached fourteen companies. He didn't need to understand what he was doing. He typed vague prompts and let the agents fill in the details — enumerate exposed services, identify vulnerabilities, write exploit code, harvest credentials. According to the OALABS researchers, in many cases the attacker 'supplied only vague, low-skill prompts and allowed Claude to fill in the gaps.' The agents complied. That's their job.",
    },
    {
      k: "p",
      t: "He only got caught because of an operational security failure — he ran the agents on a server he didn't own, and the server's owner found the working directory and handed it to researchers. If he'd run them on his own infrastructure, there would be no report. Just fourteen companies with unexplained incidents.",
    },
    { k: "h2", t: "Indirect prompt injection: the attack in plain terms" },
    {
      k: "p",
      t: "Computer-use agents — OpenAI Operator, Claude Computer Use, and every similar product — read content from the web in order to complete tasks. That's the feature. The attack surface is identical to the feature: the content the agent reads can contain instructions that override the task you gave it. Hidden text, invisible CSS, a manipulated UI element — the model doesn't distinguish 'content to process' from 'instruction to follow.' [HiddenLayer demonstrated this live against Claude Computer Use](https://coasty.ai/blog/computer-use-agent-security-best-practices-20260401) in October 2024, embedding instructions in a webpage that caused the agent to take actions the user never authorized. The agent complied then, too.",
    },
    {
      k: "p",
      t: "The same attack class showed up in a research disclosure published June 5, 2026. Microsoft Threat Intelligence [found that Anthropic's Claude Code GitHub Action](https://www.microsoft.com/en-us/security/blog/2026/06/05/securing-ci-cd-in-agentic-world-claude-code-github-action-case/) could expose CI/CD secrets when processing untrusted GitHub content — issue bodies, PR descriptions, comments. The agent's Read tool was authorized to access `/proc/self/environ`, which contained the workflow's `ANTHROPIC_API_KEY`. Anthropic patched it in Claude Code 2.1.128. The underlying pattern — attacker-controlled content reaching an agent that has access to secrets — is not patched anywhere.",
    },
    { k: "h2", t: "The threat surface is everywhere the agent reads" },
    {
      k: "ul",
      items: [
        "Webpages the agent visits to complete a task. Any page, any instruction hidden in the markup.",
        "GitHub issues, PR descriptions, and comments — especially now that coding agents are a CI/CD workflow component.",
        "Emails and documents if your agent can read them. A poisoned support ticket. A file retrieved from external storage.",
        "Tool outputs from external APIs. The agent trusts whatever text the tool returns.",
      ],
    },
    {
      k: "p",
      t: "[OWASP's Q1 2026 GenAI exploit roundup](https://genai.owasp.org/2026/04/14/owasp-genai-exploit-round-up-report-q1-2026/) documented a case where an attacker used Claude-assisted workflows to breach Mexican government agencies, treating the agent as an autonomous vulnerability discovery and exploitation engine. OWASP's framing: AI is now a force multiplier for attackers, and the primary surface isn't the model itself — it's whatever the model reads.",
    },
    { k: "h2", t: "What you can actually do today" },
    {
      k: "ul",
      items: [
        "**Treat all retrieved content as untrusted.** External data — webpages, emails, documents, tool outputs — should not be able to trigger high-impact actions without a human gate.",
        "**Hard-wall the destructive operations.** File writes, outbound requests, shell commands, credential access — require explicit approval, not just a willing model.",
        "**Isolate agents from secrets.** If the agent doesn't need the API key to complete its task, it shouldn't be able to read the environment. Blocking `/proc/self/environ` was the right instinct in the Claude Code patch — applied systemically, not one credential at a time.",
        "**Log what the agent reads, not just what it does.** If you want to investigate an injection after the fact, you need to know what triggered the behavior.",
      ],
    },
    {
      k: "quote",
      t: "The attacker did not need to be an expert operator; they simply had to use the correct framing for their prompts. The agent supplied much of the structure and technical execution that the attacker appeared to lack.",
      cite: "OALABS researchers, via Help Net Security, June 2026",
    },
    { k: "h2", t: "Where Vantio fits" },
    {
      k: "p",
      t: "Prompt injection via external content is hard to stop at the model layer — you can't fully trust what the model says it will do before it does it. What you can do is constrain what the agent can actually reach. Vantio's host allow/block rules stop the agent from making outbound requests to hosts not on an approved list, so a poisoned prompt directing the agent to exfiltrate data somewhere off-policy gets blocked before the request leaves the machine. The metadata trail logs every attempted outbound call with context, which is exactly what you need to reconstruct an injection incident after the fact.",
    },
  ],
  sources: [
    {
      label:
        "Help Net Security — Low-skilled attacker used Claude, Codex to breach 14 companies",
      url: "https://www.helpnetsecurity.com/2026/06/17/ai-agents-offensive-cyber-operations-claude-codex/",
    },
    {
      label:
        "Microsoft Security Blog — Securing CI/CD in an agentic world: Claude Code GitHub Action case",
      url: "https://www.microsoft.com/en-us/security/blog/2026/06/05/securing-ci-cd-in-agentic-world-claude-code-github-action-case/",
    },
    {
      label:
        "Coasty — Your Computer Use Agent Can Be Hijacked in 3 Seconds",
      url: "https://coasty.ai/blog/computer-use-agent-security-best-practices-20260401",
    },
    {
      label: "OWASP GenAI — Exploit Round-up Report Q1 2026",
      url: "https://genai.owasp.org/2026/04/14/owasp-genai-exploit-round-up-report-q1-2026/",
    },
  ],
};
