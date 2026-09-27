# Method

Audience: INTERNAL_RESTRICTED

Observation window: 2026-09-27T14:33:28Z through 2026-09-27T14:42:53Z.

## Website

`GET` of `https://vantio.ai/sitemap.xml` returned 59 URLs. Each sitemap URL was fetched, plus a probe list for legacy names (`/install`, `/dashboard`, `/gate`, `/pro`, `/blog`), portal paths, API paths, and hostnames that did not resolve. HTML was parsed for title, description, canonical, Open Graph, Twitter card, JSON-LD types, forms, and buttons. Nav and footer links were taken from the homepage `<nav>` and `<footer>`.

A second `GET` of `/pricing` used an iPhone Safari user agent. The response was HTTP 200, 59268 bytes, the same size as the desktop response. Breakpoints were not screenshotted.

## GitHub

The org `vantioai` listed `public_repos: 4`. Those four repositories were read for description, topics, root tree, releases, tags, branches, and issue titles. The `custody-py-3.1.0` release assets were downloaded and hashed with SHA-256. Named product repositories that are not in the public list were requested once. Each returned HTTP 404.

## Registries

npm search for `vantio` and for maintainer `vantioai` returned the same four `@vantio` packages. In-repo package names that are not published returned HTTP 404. PyPI JSON for `vantio-agent-sdk` was read at latest and at 1.0.0, 2.0.0, 3.0.0, 3.0.14, and 3.1.0. The PyPI HTML search page did not list projects, so name probes were used instead.

## Other surfaces

Public page titles and Open Graph descriptions were read for X and for three LinkedIn company URLs. Directory hosts were requested. Timeouts and HTTP 403 or 429 are recorded as not confirmed.

## Limits

Form and help-assistant backends were not in the static HTML. The official MCP registry host timed out. Code comments were counted, not quoted: 200 files in this checkout contain the phrase Phantom Engine.
