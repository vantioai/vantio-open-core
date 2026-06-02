export interface FaqItem {
  question: string;
  answer: string;
}

// Shared between the visible FAQ sections and the FAQPage JSON-LD so the
// structured data always matches what's rendered on the page (a Google
// requirement for FAQ rich results).

export const HOME_FAQ: FaqItem[] = [
  {
    question: "What does Vantio do?",
    answer:
      "Vantio is a safety and compliance layer for AI agents. It makes sure your agents only do what they're allowed to, stops mistakes before they cause damage, and keeps an audit-ready record — so you can put agents into production with confidence.",
  },
  {
    question: "Do I need to change my code to use Vantio?",
    answer:
      "No. Vantio works with your agents as they already are — no code changes and no new infrastructure to stand up. Most teams are up and running in under an hour.",
  },
  {
    question: "Will Vantio slow my agents down?",
    answer:
      "No. Vantio runs quietly in the background with effectively zero lag, so your agents keep moving at full speed. You just get a safety net underneath them.",
  },
  {
    question: "Can Vantio see my data or prompts?",
    answer:
      "No. Vantio never reads the content of your prompts or your AI's responses. It sees what happened, not what was said — your data and your IP stay completely yours.",
  },
  {
    question: "Which AI tools does Vantio work with?",
    answer:
      "All the popular ones — OpenAI, Anthropic, LangChain, CrewAI, AWS Bedrock, Google Vertex, and more. If your agents use it, Vantio supports it.",
  },
];

// Mirrors the visible "Common questions" section on /pricing verbatim.
export const PRICING_FAQ: FaqItem[] = [
  {
    question: "Do I need to change my code?",
    answer:
      "No. The free plan and PRO plan require zero code changes. Run your agent through the Vantio CLI and it handles everything. Enterprise installs at the OS level — also no code changes.",
  },
  {
    question: "What happens after my 14-day trial?",
    answer:
      "Your card is charged $499 for the first month. You can cancel any time from your dashboard — no sales call required.",
  },
  {
    question: "Can Vantio read my AI prompts?",
    answer:
      "No. Vantio never sees the content of your prompts or your AI's responses — only that an action happened. Your sensitive inputs stay yours.",
  },
  {
    question: "What AI frameworks does this work with?",
    answer:
      "Any framework that makes HTTP calls: LangChain, AutoGen, CrewAI, OpenAI SDK, Anthropic SDK, Bedrock, Vertex, Cohere, and more.",
  },
  {
    question: "What's the difference between PRO and Enterprise?",
    answer:
      "PRO enforces inside your SDK/CLI — it redacts PII, caps spend, and blocks off-policy hosts locally, driven by a cloud-managed policy you control (fast, easy setup). Enterprise enforces at the operating system (kernel) level — your agents literally cannot make unauthorized calls, even if they try to bypass user-space controls.",
  },
  {
    question: "Is there a free trial for Enterprise?",
    answer:
      "Enterprise starts with a technical architecture review. Contact our sales team to schedule one.",
  },
];
