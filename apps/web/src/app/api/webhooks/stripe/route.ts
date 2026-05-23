import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";
import { createClient } from "@supabase/supabase-js";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: "2025-04-30.basil",
});

function getSupabaseAdmin() {
  const url        = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !serviceKey) throw new Error("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
  return createClient(url, serviceKey, { auth: { autoRefreshToken: false, persistSession: false } });
}

/** Resolve the customer email from a Stripe customer ID. */
async function resolveCustomerEmail(customerId: string | Stripe.Customer | Stripe.DeletedCustomer): Promise<string | null> {
  const id = typeof customerId === "string" ? customerId : customerId.id;
  const customer = await stripe.customers.retrieve(id);
  if (customer.deleted) return null;
  return (customer as Stripe.Customer).email ?? null;
}

export async function POST(req: NextRequest): Promise<NextResponse> {
  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!webhookSecret) {
    return NextResponse.json({ error: "Webhook secret not configured" }, { status: 500 });
  }

  const signature = req.headers.get("stripe-signature");
  if (!signature) {
    return NextResponse.json({ error: "Missing stripe-signature header" }, { status: 400 });
  }

  let event: Stripe.Event;
  try {
    const rawBody = await req.arrayBuffer();
    event = stripe.webhooks.constructEvent(Buffer.from(rawBody), signature, webhookSecret);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: `Signature verification failed: ${message}` }, { status: 400 });
  }

  const supabase = getSupabaseAdmin();

  // ── checkout.session.completed — provision tenant ──────────────────────────
  if (event.type === "checkout.session.completed") {
    const session       = event.data.object as Stripe.Checkout.Session;
    const customerEmail = session.customer_details?.email ?? session.customer_email;
    const subscriptionId =
      typeof session.subscription === "string"
        ? session.subscription
        : session.subscription?.id ?? null;

    if (!customerEmail) {
      console.error("[stripe-webhook] No customer email in session", session.id);
      return NextResponse.json({ error: "No customer email" }, { status: 400 });
    }

    const { data: existing } = await supabase
      .from("tenants")
      .select("api_key")
      .eq("email", customerEmail)
      .single();

    const apiKey =
      (existing as { api_key?: string } | null)?.api_key ??
      `vantio_${Buffer.from(crypto.randomUUID().replace(/-/g, ""), "hex").toString("base64url")}`;

    await supabase.from("tenants").upsert(
      {
        email:                       customerEmail,
        tier:                        "PRO",
        stripe_subscription_id:      subscriptionId,
        stripe_checkout_session_id:  session.id,
        api_key:                     apiKey,
        updated_at:                  new Date().toISOString(),
      },
      { onConflict: "email", ignoreDuplicates: false }
    );

    console.log(`[stripe-webhook] Tenant provisioned (PRO): ${customerEmail}`);
    return NextResponse.json({ received: true });
  }

  // ── customer.subscription.updated — handle status changes ──────────────────
  // Covers: trial_will_end → active, active → past_due, past_due → unpaid, etc.
  if (event.type === "customer.subscription.updated") {
    const sub    = event.data.object as Stripe.Subscription;
    const status = sub.status;

    if (status === "active" || status === "trialing") {
      // Subscription is healthy — ensure tier is PRO.
      const email = await resolveCustomerEmail(sub.customer);
      if (email) {
        await supabase.from("tenants")
          .update({ tier: "PRO", updated_at: new Date().toISOString() })
          .eq("email", email);
      }
    } else if (status === "past_due" || status === "unpaid" || status === "paused") {
      // Payment failed or subscription paused — downgrade access.
      const email = await resolveCustomerEmail(sub.customer);
      if (email) {
        await supabase.from("tenants")
          .update({ tier: "FREE", updated_at: new Date().toISOString() })
          .eq("email", email);
        console.log(`[stripe-webhook] Subscription ${status} — downgraded: ${email}`);
      }
    }

    return NextResponse.json({ received: true });
  }

  // ── customer.subscription.deleted — cancellation ───────────────────────────
  if (event.type === "customer.subscription.deleted") {
    const sub   = event.data.object as Stripe.Subscription;
    const email = await resolveCustomerEmail(sub.customer);
    if (email) {
      await supabase.from("tenants")
        .update({ tier: "FREE", stripe_subscription_id: null, updated_at: new Date().toISOString() })
        .eq("email", email);
      console.log(`[stripe-webhook] Subscription cancelled — downgraded to FREE: ${email}`);
    }
    return NextResponse.json({ received: true });
  }

  // All other events — acknowledge without action.
  return NextResponse.json({ received: true });
}
