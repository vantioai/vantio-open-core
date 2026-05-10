import NextAuth from "next-auth"
import Credentials from "next-auth/providers/credentials"
import { db } from "@/lib/db"

// PrismaAdapter is available via @auth/prisma-adapter for when OAuth providers
// are added. Omitted here because JWT strategy stores sessions in tokens, not
// the database, and the adapter requires a `User` model that differs from
// our EnterpriseUser schema.
export const { handlers, auth, signIn, signOut } = NextAuth({
  session: { strategy: "jwt" },
  providers: [
    Credentials({
      name: "Enterprise SAML Mock",
      credentials: {
        email: { label: "Enterprise Email", type: "email" },
        domain: { label: "Corporate Domain", type: "text" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.domain) return null

        // Deterministic mock user generation
        const user = await db.enterpriseUser.upsert({
          where: { email: credentials.email as string },
          update: {},
          create: {
            email: credentials.email as string,
            domain: credentials.domain as string,
            samlId: `mock-saml-${Date.now()}`,
          },
        })

        return { id: user.id, email: user.email, name: user.domain }
      },
    }),
  ],
  pages: {
    signIn: "/auth/enterprise",
  },
})
