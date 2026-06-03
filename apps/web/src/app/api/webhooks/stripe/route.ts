import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";
import { createClient } from "@supabase/supabase-js";

function getStripe() {
  return new Stripe(process.env.STRIPE_SECRET_KEY!, {
    apiVersion: "2026-04-22.dahlia",
  });
}

function getSupabaseAdmin() {
  const url        = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !serviceKey) throw new Error("Missing Supabase env vars");
  return createClient(url, serviceKey, { auth: { autoRefreshToken: false, persistSession: false } });
}

/**
 * Idempotency guard — returns true if this Stripe event ID was already processed.
 * Stripe guarantees at-least-once delivery; without this check a retried webhook
 * could double-provision a tenant or incorrectly re-downgrade an active account.
 */
async function markEventProcessed(supabase: ReturnType<typeof getSupabaseAdmin>, eventId: string): Promise<boolean> {
  const { error } = await supabase
    .from("stripe_processed_events")
    .insert({ event_id: eventId, processed_at: new Date().toISOString() });

  // Unique constraint violation (code 23505) means already processed — skip.
  if (error) {
    if (error.code === "23505") return true;
    // Any other error: log but continue (better to double-process than to drop).
    console.warn("[stripe-webhook] idempotency check failed:", error.message);
  }
  return false;
}

/**
 * Rollback the idempotency marker so Stripe's retry can reprocess the event.
 * Called when a handler fails AFTER the event was pre-marked as processed —
 * without this, the pre-mark would suppress every retry and the work (e.g.
 * provisioning a paid tenant) would be lost permanently.
 */
async function unmarkEvent(supabase: ReturnType<typeof getSupabaseAdmin>, eventId: string): Promise<void> {
  const { error } = await supabase
    .from("stripe_processed_events")
    .delete()
    .eq("event_id", eventId);
  if (error) {
    console.error("[stripe-webhook] failed to roll back idempotency marker:", error.message);
  }
}

async function resolveCustomerEmail(customerId: string | Stripe.Customer | Stripe.DeletedCustomer): Promise<string | null> {
  const id       = typeof customerId === "string" ? customerId : customerId.id;
  const customer = await getStripe().customers.retrieve(id);
  if (customer.deleted) return null;
  return (customer as Stripe.Customer).email ?? null;
}

/**
 * Map a Stripe subscription status to the tenant tier it implies.
 *   - active / trialing                                      → PRO
 *   - canceled / incomplete_expired / unpaid / past_due / paused → FREE
 *   - anything else (e.g. incomplete)                        → null (leave unchanged)
 */
function tierForStatus(status: Stripe.Subscription.Status): "PRO" | "FREE" | null {
  if (status === "active" || status === "trialing") return "PRO";
  if (
    status === "canceled" ||
    status === "incomplete_expired" ||
    status === "unpaid" ||
    status === "past_due" ||
    status === "paused"
  ) {
    return "FREE";
  }
  return null;
}

export async function POST(req: NextRequest): Promise<NextResponse> {
  const stripe = getStripe();
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

  // ── Idempotency check ─────────────────────────────────────────────────────
  const alreadyProcessed = await markEventProcessed(supabase, event.id);
  if (alreadyProcessed) {
    return NextResponse.json({ received: true, skipped: "duplicate" });
  }

  // ── checkout.session.completed ────────────────────────────────────────────
  if (event.type === "checkout.session.completed") {
    try {
      const session       = event.data.object as Stripe.Checkout.Session;
      const customerEmail = session.customer_details?.email ?? session.customer_email;
      const subscriptionId =
        typeof session.subscription === "string"
          ? session.subscription
          : session.subscription?.id ?? null;

      if (!customerEmail) {
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
          email:                      customerEmail,
          tier:                       "PRO",
          stripe_subscription_id:     subscriptionId,
          stripe_checkout_session_id: session.id,
          api_key:                    apiKey,
          updated_at:                 new Date().toISOString(),
        },
        { onConflict: "email", ignoreDuplicates: false }
      );

      console.log(`[stripe-webhook] Tenant provisioned (PRO): ${customerEmail}`);
    } catch (err) {
      console.error("[stripe-webhook] checkout.session.completed handler failed:", err);
      // Roll back the idempotency marker and signal failure so Stripe retries —
      // provisioning a paid tenant must not be silently dropped on a transient error.
      await unmarkEvent(supabase, event.id);
      return NextResponse.json({ error: "Processing failed; will retry." }, { status: 500 });
    }
    return NextResponse.json({ received: true });
  }

  // ── customer.subscription.updated / deleted ───────────────────────────────
  // Stripe does NOT guarantee event ordering, so a stale
  // `customer.subscription.updated(active)` can arrive AFTER a
  // `customer.subscription.deleted` and re-grant PRO to a cancelled tenant.
  // To make tier transitions authoritative we IGNORE the (possibly stale)
  // event payload status and re-`retrieve` the subscription's CURRENT status
  // from Stripe, deriving the tier from that. As a second out-of-order guard
  // we skip the write when the event predates the tenant's last update.
  if (event.type === "customer.subscription.updated" || event.type === "customer.subscription.deleted") {
    try {
      const subEvent = event.data.object as Stripe.Subscription;

      // Authoritative current state — not the event payload. Cancelled
      // subscriptions are retained by Stripe (status "canceled"), so retrieve
      // succeeds; only fall back to the event payload status if it fails.
      let status: Stripe.Subscription.Status = subEvent.status;
      try {
        const fresh = await stripe.subscriptions.retrieve(subEvent.id);
        status = fresh.status;
      } catch (retrieveErr) {
        console.warn(
          "[stripe-webhook] subscription re-retrieve failed; using event payload status:",
          retrieveErr
        );
      }

      const email = await resolveCustomerEmail(subEvent.customer);
      const tier  = tierForStatus(status);

      if (email && tier !== null) {
        // Out-of-order guard: ignore an event created before our last write so
        // a late-delivered stale event can't overwrite newer authoritative state.
        const { data: tenantRow } = await supabase
          .from("tenants")
          .select("updated_at")
          .eq("email", email)
          .single();
        const lastUpdatedMs = (tenantRow as { updated_at?: string } | null)?.updated_at
          ? Date.parse((tenantRow as { updated_at: string }).updated_at)
          : 0;
        const eventMs = event.created * 1000;

        if (Number.isFinite(lastUpdatedMs) && eventMs < lastUpdatedMs) {
          console.log(
            `[stripe-webhook] stale ${event.type} (event ${eventMs} < updated_at ${lastUpdatedMs}) — skipping: ${email}`
          );
        } else {
          const update: Record<string, unknown> = {
            tier,
            updated_at: new Date().toISOString(),
          };
          // Clear the stored subscription id once it's gone/cancelled.
          if (tier === "FREE" && (status === "canceled" || event.type === "customer.subscription.deleted")) {
            update.stripe_subscription_id = null;
          }
          await supabase.from("tenants").update(update).eq("email", email);
          console.log(`[stripe-webhook] ${event.type} → ${tier} (status=${status}): ${email}`);
        }
      }
    } catch (err) {
      console.error(`[stripe-webhook] ${event.type} handler failed:`, err);
      await unmarkEvent(supabase, event.id);
      return NextResponse.json({ error: "Processing failed; will retry." }, { status: 500 });
    }
    return NextResponse.json({ received: true });
  }

  return NextResponse.json({ received: true });
}
