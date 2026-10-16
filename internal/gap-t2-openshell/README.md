# OpenShell rogue reconciliation (internal)

Audience: INTERNAL_RESTRICTED

This package joins a closed snapshot of Phantom Engine kernel observations with OpenShell OCSF rows and Gate rows. It is the Lab-only half of track T2. A live OpenShell sandbox with Phantom Engine loaded on an enrolled host is Roadmap.

The council verdict is **differentiate**. Read `COUNCIL.md` before changing the join. `POSITIONING.md` is an internal draft and is not for public use.

```bash
node --test internal/gap-t2-openshell/test/*.test.cjs
node internal/gap-t2-openshell/proof/prove-bypass.cjs
```

The proof reads the fixtures in this directory and writes `evidence/bypass-drill.json`. It does not enroll a host, load a kernel program, or open a socket.

`harness/live.cjs` is the Lab-only file tail. It joins local NDJSON the same way. A live OpenShell sandbox on an enrolled host stays Roadmap. Read `LIVE-JOIN.md`.

Public pricing stays Contact Vantio. This package is not part of the pnpm workspace and is not a published module.
