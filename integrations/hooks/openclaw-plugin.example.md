# OpenClaw plugin sketch — Vantio Optics

Vantio started by securing insecure runtimes like OpenClaw. Prefer the platform
path over a runtime-specific patch:

```bash
# Wrap the OpenClaw agent process
vantio run node openclaw-agent.js
```

Optional plugin hook (pseudocode for OpenClaw’s plugin API):

```js
export default {
  name: "vantio-optics",
  async onAgentStart(ctx) {
    ctx.env.NODE_OPTIONS = [
      ctx.env.NODE_OPTIONS,
      `--require=${require.resolve("@vantio/cli/interceptor")}`,
    ]
      .filter(Boolean)
      .join(" ");
    ctx.log.info("[vantio] Optics observe attached (Sight Loop)");
  },
};
```

Fence: observe only. Upgrade to Gate for Policy Latch; Phantom Engine for Absolute Control.
