import { NextRequest, NextResponse } from "next/server";
import { createClient }             from "@supabase/supabase-js";

interface ContactPayload {
  name:    string;
  email:   string;
  company: string;
  size:    string;
  message: string;
}

function validate(raw: unknown): ContactPayload | null {
  if (typeof raw !== "object" || raw === null) return null;
  const b = raw as Record<string, unknown>;
  if (typeof b["name"]    !== "string" || b["name"].trim().length    === 0) return null;
  if (typeof b["email"]   !== "string" || !b["email"].includes("@"))        return null;
  if (typeof b["company"] !== "string" || b["company"].trim().length === 0) return null;
  return {
    name:    (b["name"]    as string).trim().slice(0, 128),
    email:   (b["email"]   as string).trim().slice(0, 256),
    company: (b["company"] as string).trim().slice(0, 128),
    size:    typeof b["size"]    === "string" ? (b["size"]    as string).trim().slice(0, 64)  : "",
    message: typeof b["message"] === "string" ? (b["message"] as string).trim().slice(0, 2000): "",
  };
}

export async function POST(req: NextRequest): Promise<NextResponse> {
  let raw: unknown;
  try {
    raw = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON." }, { status: 400 });
  }

  const payload = validate(raw);
  if (!payload) {
    return NextResponse.json(
      { error: "Required fields: name, email, company." },
      { status: 422 }
    );
  }

  try {
    const supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!,
      { auth: { autoRefreshToken: false, persistSession: false } }
    );

    await supabase.from("enterprise_leads").insert({
      name:       payload.name,
      email:      payload.email,
      company:    payload.company,
      team_size:  payload.size,
      message:    payload.message,
      created_at: new Date().toISOString(),
    });
  } catch (err) {
    console.error("[vantio:contact] Failed to store lead:", err);
  }

  // Notify internal Slack channel if configured
  const slackUrl = process.env.SLACK_WEBHOOK_URL;
  if (slackUrl) {
    void fetch(slackUrl, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        blocks: [
          {
            type: "header",
            text: { type: "plain_text", text: "🏢 New Enterprise Lead" },
          },
          {
            type: "section",
            fields: [
              { type: "mrkdwn", text: `*Name*\n${payload.name}` },
              { type: "mrkdwn", text: `*Email*\n${payload.email}` },
              { type: "mrkdwn", text: `*Company*\n${payload.company}` },
              { type: "mrkdwn", text: `*Team Size*\n${payload.size || "—"}` },
            ],
          },
          payload.message
            ? { type: "section", text: { type: "mrkdwn", text: `*Message*\n${payload.message}` } }
            : null,
        ].filter(Boolean),
      }),
    }).catch(() => {});
  }

  return NextResponse.json({ ok: true });
}
