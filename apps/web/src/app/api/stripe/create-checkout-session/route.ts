import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";
import { isTier2Waitlist } from "@/lib/tier2";

function getStripe() {
  return new Stripe(process.env.STRIPE_SECRET_KEY!, {
    apiVersion: "2026-04-22.dahlia",
  });
}

export async function POST(req: NextRequest): Promise<NextResponse> {
  // SAFETY: while Tier 2 is waitlist-only, hard-disable checkout BEFORE creating
  // any Stripe session — so even a direct POST cannot start a charge. Waitlist
  // mode is on by default and only off when NEXT_PUBLIC_TIER2_WAITLIST==="false".
  if (isTier2Waitlist()) {
    return NextResponse.json(
      { error: "tier2_waitlist", message: "Tier 2 is currently waitlist-only." },
      { status: 403 }
    );
  }

  // Derive redirect URLs from a TRUSTED origin, never the request `origin`
  // header (attacker-controlled — would enable an open redirect that chains
  // with the /success API-key disclosure).
  const origin = process.env.NEXT_PUBLIC_APP_URL ?? "https://vantio.ai";

  let email: string | undefined;
  try {
    const body = await req.json() as { email?: string };
    email = typeof body.email === "string" && body.email.length > 0 ? body.email : undefined;
  } catch {
    // Empty or non-JSON body — email prefill is optional.
  }

  try {
    const session = await getStripe().checkout.sessions.create({
      mode: "subscription",
      payment_method_types: ["card"],
      line_items: [{ price: process.env.STRIPE_SMB_PRICE_ID!, quantity: 1 }],
      customer_email: email,
      success_url: `${origin}/success?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${origin}/pricing`,
      subscription_data: { trial_period_days: 14, metadata: { tier: "SMB_PRO" } },
      allow_promotion_codes: true,
    });
    return NextResponse.json({ url: session.url });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
