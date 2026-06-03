import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

// PKCE callback for magic-link sign-in. The emailed link returns the user here
// with a `?code=...`. We exchange that code for a session and — crucially —
// write the resulting session cookies through the cookie adapter's `setAll`,
// then redirect into the app. Without this exchange the browser PKCE client
// never persists a session, so the server components on /dashboard see no user
// and bounce straight back to /login.
export async function GET(request: NextRequest): Promise<NextResponse> {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  // Only ever redirect to a same-origin path so the callback can't be used as
  // an open redirect.
  const nextParam = searchParams.get("next") ?? "/dashboard";
  const next = nextParam.startsWith("/") ? nextParam : "/dashboard";

  if (!code) {
    return NextResponse.redirect(`${origin}/login?error=auth`);
  }

  // Lazy-read env inside the handler — no module-level throws.
  const url     = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) {
    console.error("[vantio:auth] Missing Supabase env vars in callback.");
    return NextResponse.redirect(`${origin}/login?error=auth`);
  }

  // Next.js 15: cookies() is async. The adapter MUST implement setAll — that is
  // what writes the session cookies onto the response. getAll alone (as in the
  // read-only server routes) would exchange the code but never persist it.
  const cookieStore = await cookies();
  const supabase = createServerClient(url, anonKey, {
    cookies: {
      getAll: () => cookieStore.getAll(),
      setAll: (cookiesToSet) => {
        cookiesToSet.forEach(({ name, value, options }) =>
          cookieStore.set(name, value, options)
        );
      },
    },
  });

  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (error) {
    console.error("[vantio:auth] exchangeCodeForSession failed:", error.message);
    return NextResponse.redirect(`${origin}/login?error=auth`);
  }

  return NextResponse.redirect(`${origin}${next}`);
}
