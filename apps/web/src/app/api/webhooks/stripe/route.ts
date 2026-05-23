import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";
import { createClient } from "@supabase/supabase-js";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: "2025-04-30.basil",
});

// Supabase admin client bypasses RLS using the service role key.
function getSupabaseAdmin() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!url || !serviceKey) {
    throw new Error(
      "Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY"
    );
  }

  return createClient(url, serviceKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });
}

// Next.js 15 App Router requires the raw body as a Buffer for Stripe
// signature verification — the default JSON body parser must not run first.
export async function POST(req: NextRequest): Promise<NextResponse> {
  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!webhookSecret) {
    console.error("[stripe-webhook] STRIPE_WEBHOOK_SECRET is not set");
    return NextResponse.json(
      { error: "Webhook secret not configured" },
      { status: 500 }
    );
  }

  const signature = req.headers.get("stripe-signature");
  if (!signature) {
    return NextResponse.json(
      { error: "Missing stripe-signature header" },
      { status: 400 }
    );
  }

  let event: Stripe.Event;

  try {
    const rawBody = await req.arrayBuffer();
    event = stripe.webhooks.constructEvent(
      Buffer.from(rawBody),
      signature,
      webhookSecret
    );
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error(`[stripe-webhook] Signature verification failed: ${message}`);
    return NextResponse.json(
      { error: `Webhook signature verification failed: ${message}` },
      { status: 400 }
    );
  }

  // Strictly handle checkout.session.completed only.
  if (event.type !== "checkout.session.completed") {
    return NextResponse.json({ received: true }, { status: 200 });
  }

  const session = event.data.object as Stripe.Checkout.Session;

  const customerEmail = session.customer_details?.email ?? session.customer_email;
  const subscriptionId =
    typeof session.subscription === "string"
      ? session.subscription
      : session.subscription?.id ?? null;

  if (!customerEmail) {
    console.error("[stripe-webhook] No customer email found in session", session.id);
    return NextResponse.json(
      { error: "No customer email in session" },
      { status: 400 }
    );
  }

  if (!subscriptionId) {
    console.error("[stripe-webhook] No subscription_id found in session", session.id);
    return NextResponse.json(
      { error: "No subscription_id in session" },
      { status: 400 }
    );
  }

  try {
    const supabase = getSupabaseAdmin();

    // Check if tenant already has an API key so we never regenerate it
    // on re-subscribe (which would break existing integrations).
    const { data: existing } = await supabase
      .from("tenants")
      .select("api_key")
      .eq("email", customerEmail)
      .single();

    const apiKey =
      (existing as { api_key?: string } | null)?.api_key ??
      `vantio_${Buffer.from(crypto.randomUUID().replace(/-/g, ""), "hex").toString("base64url")}`;

    const { error } = await supabase
      .from("tenants")
      .upsert(
        {
          email: customerEmail,
          tier: "PRO",
          stripe_subscription_id: subscriptionId,
          stripe_checkout_session_id: session.id,
          api_key: apiKey,
          updated_at: new Date().toISOString(),
        },
        { onConflict: "email", ignoreDuplicates: false }
      );

    if (error) {
      console.error("[stripe-webhook] Supabase upsert failed:", error.message);
      return NextResponse.json(
        { error: "Database update failed" },
        { status: 500 }
      );
    }

    console.log(
      `[stripe-webhook] Tenant upgraded to PRO: ${customerEmail} (sub: ${subscriptionId})`
    );

    return NextResponse.json({ received: true }, { status: 200 });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error(`[stripe-webhook] Unexpected error: ${message}`);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
