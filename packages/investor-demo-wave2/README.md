# Investor demo Wave 2

PRIVATE | INTERNAL_RESTRICTED | NOT SHIPPED

This package runs the internal investor-demo session. It does not modify `@vantio/cli` 0.3.24. It does not publish, announce, or assign `PROVED_EXTERNAL`.

Producer classification before council: `INVESTOR_DEMO_WAVE2_READY_FOR_COUNCIL`.

That classification is the producer handoff. It is not a council verdict.

```sh
node --test tests/investor-demo-wave2/*.test.cjs
```

From this package, after a checkout of the repository:

```sh
node bin/investor-demo.cjs run --offline --repo ../..
```

`--offline` uses the labeled fallback and does not spawn the CLI. Omit it to run the frozen CLI `0.3.24` against a temporary demo home.
