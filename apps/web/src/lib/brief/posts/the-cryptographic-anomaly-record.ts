import type { Post } from "@/lib/brief";

// Evergreen Deep Dive — repurposed from the original Research dossier
// "The Cryptographic Anomaly Record" with light human-voice polish.
export const post: Post = {
  slug: "the-cryptographic-anomaly-record",
  title: "The cryptographic anomaly record",
  excerpt:
    "A log you can edit is not evidence. The Anomaly Record is a metadata-only receipt — HMAC-signed, TrueTime-stamped, append-only — and it maps directly onto GDPR Article 30, SOC 2 CC7.2, and SEC cyber-disclosure expectations.",
  category: "Deep Dive",
  author: "Nina Alvarez",
  authorRole: "Compliance engineering, Vantio",
  date: "2026-05-10",
  cover: "violet",
  tierCta: "enterprise",
  body: [
    { k: "p", t: "A log you can quietly edit is not evidence — it's a story. The Anomaly Record exists to be the opposite: the smallest possible artifact that an auditor, a regulator, or a future version of you can verify without taking anyone's word for it." },
    { k: "p", t: "Concretely, each record is a structured row containing a `VANTIO_TRACE_ID` (UUID v4), execution metadata (PID, bytes severed, target host, action taken), an HMAC-SHA256 receipt over the event's trace ID, and a TrueTime commit timestamp from GCP Spanner. No prompts. No completions. Just what happened, when, and proof it wasn't tampered with." },
    { k: "h2", t: "Verifiable without trusting us" },
    { k: "p", t: "The HMAC receipt is computed with the tenant's API key as the signing secret and returned in the `x-vantio-signature` header on every ingest. That means anyone holding the tenant key can recompute the HMAC and confirm the receipt was issued for that exact trace ID. You don't have to trust the ledger; you can check it. That distinction is the whole point of a cryptographic record versus a database you're asked to believe." },
    { k: "h2", t: "The payload quarantine" },
    { k: "p", t: "Keeping content out isn't a policy promise; it's enforced in two places. Structurally, the ingest route whitelists only specific metadata fields — prompts and completions are architecturally excluded, so there's no column for them to land in. Contractually, the service-role key used for writes has no read access on raw input columns. The system is built so that the embarrassing data simply never exists to leak." },
    { k: "h2", t: "Mapping to the rules people actually get audited against" },
    { k: "p", t: "GDPR Article 30 asks for a “record of processing activities.” The ledger satisfies that natively: every agent action that touches personal data produces an immutable record with a globally consistent timestamp, a unique event ID, and a cryptographic integrity proof. The same primitive lines up with SOC 2 CC7.2 (detection and evidence of anomalies) and with the kind of defensible timeline SEC cyber-disclosure expectations increasingly assume you can produce on demand. Compliance teams don't want a dashboard screenshot; they want a record that holds up when someone hostile is looking at it. That's what this is." },
  ],
};
