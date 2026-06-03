import { NextResponse } from "next/server";
import Stripe from "stripe";
import { createClient } from "@supabase/supabase-js";
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

function getStripe() {
  return new Stripe(process.env.STRIPE_SECRET_KEY!, {
    apiVersion: "2026-04-22.dahlia",
  });
}

export async function POST(): Promise<NextResponse> {
  const cookieStore = await cookies();
  const authClient  = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { cookies: { getAll: () => cookieStore.getAll() } }
  );
  const { data: { user } } = await authClient.auth.getUser();
  if (!user?.email) {
    return NextResponse.json({ error: "Unauthenticated." }, { status: 401 });
  }

  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { autoRefreshToken: false, persistSession: false } }
  );
  const { data } = await supabase
    .from("tenants")
    .select("stripe_subscription_id")
    .eq("email", user.email)
    .single();

  const subscriptionId = (data as { stripe_subscription_id?: string } | null)?.stripe_subscription_id;
  if (!subscriptionId) {
    return NextResponse.json({ error: "No active subscription found." }, { status: 404 });
  }

  const stripe = getStripe();
  try {
    const subscription = await stripe.subscriptions.retrieve(subscriptionId);
    const customerId   = typeof subscription.customer === "string"
      ? subscription.customer
      : subscription.customer.id;

    // Trusted origin only — never the attacker-controlled `origin` header.
    const origin  = process.env.NEXT_PUBLIC_APP_URL ?? "https://vantio.ai";
    const session = await stripe.billingPortal.sessions.create({
      customer:   customerId,
      return_url: `${origin}/dashboard`,
    });

    return NextResponse.json({ url: session.url });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error("[stripe:portal] Stripe call failed:", message);
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
