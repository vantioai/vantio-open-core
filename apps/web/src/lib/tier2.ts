/**
 * Tier 2 (Pro) public purchase flow is gated behind a waitlist until billing
 * is live.
 *
 * Waitlist mode is ON BY DEFAULT and is only disabled when the flag is exactly
 * the string "false". With no env var set, the site stays in waitlist mode and
 * no checkout can occur — safe by default. Flip to live with
 * `NEXT_PUBLIC_TIER2_WAITLIST=false` + redeploy.
 *
 * Read inside functions/components only (never at module load) so it works in
 * both server and client components and never throws. `NEXT_PUBLIC_*` is inlined
 * at build time, so this resolves correctly on the client too.
 */
export function isTier2Waitlist(): boolean {
  return process.env.NEXT_PUBLIC_TIER2_WAITLIST !== "false";
}
