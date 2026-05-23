import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: "2025-04-30.basil",
});

export async function POST(req: NextRequest): Promise<NextResponse> {
  const origin =
    req.headers.get("origin") ??
    process.env.NEXT_PUBLIC_APP_URL ??
    "http://localhost:3000";

  // Parse body first — req.json() can only be called once.
  let email: string | undefined;
  try {
    const body = await req.json() as { email?: string };
    email = typeof body.email === "string" && body.email.length > 0
      ? body.email
      : undefined;
  } catch {
    // Empty or non-JSON body is fine — email prefill is optional.
  }

  try {
    const session = await stripe.checkout.sessions.create({
      mode: "subscription",
      payment_method_types: ["card"],
      line_items: [{ price: process.env.STRIPE_SMB_PRICE_ID!, quantity: 1 }],
      customer_email: email,
      success_url: `${origin}/success?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${origin}/pricing`,
      subscription_data: { metadata: { tier: "SMB_PRO" } },
      allow_promotion_codes: true,
    });

    return NextResponse.json({ url: session.url });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error("[stripe] create-checkout-session failed:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
