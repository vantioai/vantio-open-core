"use client";

import * as Dialog from "@radix-ui/react-dialog";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Slot } from "@radix-ui/react-slot";
import { cn } from "@/lib/utils";

function PerimeterButton({
  asChild,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      className={cn(
        "inline-flex items-center justify-center rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-900 disabled:pointer-events-none disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export default function EnterpriseAuthPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gray-50 p-8">
      <div className="w-full max-w-md space-y-6 rounded-xl border border-gray-200 bg-white p-8 shadow-sm">
        {/* Header */}
        <div className="space-y-1 text-center">
          <p className="text-xs font-semibold uppercase tracking-widest text-gray-400">
            Vantio AI — Enterprise Perimeter
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">
            SAML / SSO Gateway
          </h1>
          <p className="text-sm text-gray-500">
            Cryptographically isolated single sign-on for verified institutional
            identities.
          </p>
        </div>

        {/* IdP selector */}
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <PerimeterButton className="w-full justify-between">
              <span>Select Identity Provider</span>
              <span aria-hidden>▾</span>
            </PerimeterButton>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              className="z-50 min-w-[16rem] overflow-hidden rounded-md border border-gray-200 bg-white p-1 shadow-md"
              sideOffset={4}
            >
              {["Okta", "Azure AD", "Google Workspace", "PingFederate"].map(
                (idp) => (
                  <DropdownMenu.Item
                    key={idp}
                    className="cursor-pointer select-none rounded px-3 py-2 text-sm text-gray-700 outline-none hover:bg-gray-100 focus:bg-gray-100"
                  >
                    {idp}
                  </DropdownMenu.Item>
                ),
              )}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        {/* Primary CTA */}
        <Dialog.Root>
          <Dialog.Trigger asChild>
            <PerimeterButton className="w-full">
              Authenticate via SAML
            </PerimeterButton>
          </Dialog.Trigger>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 bg-black/40 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
            <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-xl border border-gray-200 bg-white p-6 shadow-xl focus:outline-none">
              <Dialog.Title className="text-base font-semibold text-gray-900">
                SAML Handshake Initiated
              </Dialog.Title>
              <Dialog.Description className="mt-2 text-sm text-gray-500">
                Redirecting to your Identity Provider for assertion. This
                gateway enforces AES-256 transport encryption and validates
                signed SAML assertions before granting access.
              </Dialog.Description>
              <div className="mt-4 flex justify-end">
                <Dialog.Close asChild>
                  <PerimeterButton>Dismiss</PerimeterButton>
                </Dialog.Close>
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>

        <p className="text-center text-xs text-gray-400">
          Access restricted to credentialed enterprise accounts.
          <br />
          Contact{" "}
          <a
            href="mailto:security@vantio.ai"
            className="underline underline-offset-2 hover:text-gray-600"
          >
            security@vantio.ai
          </a>{" "}
          for provisioning.
        </p>
      </div>
    </main>
  );
}
