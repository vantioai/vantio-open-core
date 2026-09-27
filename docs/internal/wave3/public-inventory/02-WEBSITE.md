# Website

Audience: INTERNAL_RESTRICTED

Host: `https://vantio.ai`. `www.vantio.ai` returns HTTP 308 to the apex. The server header is Vercel. HTML asset URLs carry deployment id `dpl_ixTfUX1NEHqyV1yrpSLTfzunR1Et`. The site source is not one of the four public GitHub repositories. Changing it is an external-account action. `vercel.json` in this repository only sets `installCommand`.

Disposition of every route: `UNREVIEWED`.

## Chrome

Nav: Optics, Phantom Engine, Enterprise, Pricing, Architecture, Security, Company, Docs, Talk to sales (`/contact?intent=sales`).

Footer adds Installation, Compatibility, Support, Assurance (`/trust`), Product evidence, Independent validation (`/docs/stranger-host`), Compliance, vulnerability disclosure, Privacy, Solutions, Design partners, Updates, Contact, Terms, and the open-core GitHub repository. The footer line is “Phantom Engine — patent pending.”

Shared metadata: viewport `width=device-width, initial-scale=1`, author Vantio AI, Inc., Twitter card `summary_large_image` with site `@vantioai`, Open Graph image `https://vantio.ai/opengraph-image` (HTTP 200, PNG, 76958 bytes, declared 1200×630). `/twitter-image` is HTTP 404. Homepage HTML has two `<svg>` tags, no `<img>`, no `<video>`, and no `<iframe>`. A help-assistant button is on the primary pages.

JSON-LD on the homepage names Vantio AI, Inc., address country US, and contact points `sales@`, `hello@`, and `security@vantio.ai`.

## What the site says it sells

`/llms.txt` (7478 bytes, also at `/.well-known/llms.txt`) states three products. Optics is free and local-first. Phantom Engine is $799 per enrolled node per month with a 14-day trial. Enterprise is talk to sales. The same file says Gate is not a current SKU.

`/pricing` repeats Free, $799 per enrolled node per month, 14-day trial, and talk to sales. `/start/design-partner` states a separate $600 per governed node per month, says outreach is paused, says no partners are enrolled, and says card checkout is not live.

`/compliance` says certifications are not held, naming SOC 2, ISO 42001, FedRAMP, StateRAMP, and CMMC. `/product-evidence` says no public evidence artifact currently meets the publication standard. `/company` says Vantio AI, Inc. is a Delaware C corporation founded in 2026 and based in Pittsburgh, and that the product system is separate from the company’s private operating system.

`/llms.txt` labels Necessity Objective as a strategic objective, Agent Capability Invariance and two-direction defence and lineage authority as target design, swarm-scale protection as no proof, stranger-host validation as not complete, and customer validation as none. Those are the site’s labels.

## Routes

Sitemap count: 59. Primary HTML routes, all HTTP 200, are the product, docs, solutions, company, legal, support, and evidence pages listed in the JSON `primary_routes` array. Twenty-nine update posts are in the sitemap. Four more update URLs returned HTTP 200 and are not in the sitemap:

- `/updates/agi-planning-horizon-host-control`
- `/updates/asi-superintelligence-host-floor`
- `/updates/show-hn-i-m-16-y-o-and-built-the-only-ai-agent-for-hardware-and-software`
- `/updates/vantio-runs-company-ops-on-optics-gate-phantom-engine`

The Show HN title is live public copy. This inventory does not treat the age in that title as a verified biographical fact.

## Redirects that still answer

| From | Lands on |
| --- | --- |
| `/install` | `/docs/install` |
| `/dashboard`, `/cli`, `/sdk` | `/docs` |
| `/gate`, `/pro` | `/phantom-engine#enforce` |
| `/phantom` | `/phantom-engine` |
| `/blog` | `/updates` |
| `/about` | `/company` |
| `/demo` | `/enterprise` |
| `/design-partners` | `/start/design-partner` |
| `/github` | `github.com/vantioai/vantio-open-core` |

`/install.sh` is HTTP 404. There is no `/download` page.

## Hidden and missing

`robots.txt` allows `/` and `/_next/static/`, and disallows `/api/`, `/portal/`, and `/gate/welcome`.

`/portal` is HTTP 200 with heading “Sign in with your invite.” Subpaths `/portal/evidence`, `/portal/exit`, `/portal/status`, and `/portal/support` also return the client-portal title. `/gate/welcome` is HTTP 200, title “Checkout return,” and says Gate is not a current SKU.

`/api/v1/config`, `/api/v1/ingest`, and `/api/v1/telemetry` return the HTML 404 page. Careers, jobs, press, media kit, investors, status, changelog, OpenAPI, preview, staging, and beta are HTTP 404.

These hostnames did not resolve: `staging`, `preview`, `dev`, `api`, `blog`, `trust`, `portal`, `app`, `docs`, and `m` under `vantio.ai`.

## Files a crawler is pointed at

`/llms.txt`, `/llms-full.txt`, `/robots.txt`, `/sitemap.xml`, `/security.txt` (contact `security@vantio.ai`, expires 2027-12-31), `/humans.txt` (Twitter `@vantioai`), and `/site.webmanifest`. The manifest description says infrastructure-level enforcement for autonomous AI and names Optics, Phantom Engine, and Enterprise.

## Forms

Contact, support, and the design-partner application render inputs. The static HTML form action was empty. The help assistant’s request host was not in the HTML. The portal form asks for an invite.
