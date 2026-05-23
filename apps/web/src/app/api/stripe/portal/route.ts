import { NextRequest, NextResponse } from "next/server";
import Stripe                        from "stripe";
import { createClient }              from "@supabase/supabase-js";
import { createServerClient }        from "@supabase/ssr";
import { cookies }                   from "next/headers";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: "2025-04-30.basil",
});

export async function POST(req: NextRequest): Promise<NextResponse> {
  // Auth gate — portal is only for authenticated users.
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

  // Look up the Stripe customer ID via the tenant's subscription.
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

  // Retrieve the customer ID from the subscription.
  const subscription  = await stripe.subscriptions.retrieve(subscriptionId);
  const customerId    = typeof subscription.customer === "string"
    ? subscription.customer
    : subscription.customer.id;

  const origin  = req.headers.get("origin") ?? process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
  const session = await stripe.billingPortal.sessions.create({
    customer:   customerId,
    return_url: `${origin}/dashboard`,
  });

  return NextResponse.json({ url: session.url });
}
