"use server"

import { signIn } from "@/auth"

export async function authenticate(formData: FormData) {
  const email = formData.get("email") as string
  const domain = formData.get("domain") as string

  // Trigger the credentials bypass and redirect to the Oracle control plane
  await signIn("credentials", {
    email,
    domain,
    redirectTo: "/",
  })
}
