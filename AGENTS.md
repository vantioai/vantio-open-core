# Agent notes

Engineering rules for this repo are in `.cursor/rules/vantio-engineering.mdc` with `alwaysApply: true`. Follow that file.

`node docs/scripts/check-docs-release.mjs` scans this markdown file. Do not add a retired product name. `.github/founder-approval-paths.txt` does not list this file or `.cursor/rules/`. The docs gate does not require the `founder-approved` label for either path. Do not apply that label and do not merge.
