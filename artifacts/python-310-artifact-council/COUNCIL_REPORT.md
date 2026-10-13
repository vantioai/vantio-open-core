# Python SDK 3.1.0 independent exact-artifact council

Audience: INTERNAL_RESTRICTED

Council only. This review did not build the candidates. Builder agent: `bc-e89f892d-fdb6-5c0d-8e01-378389cfb821`.

Model: Grok 4.7. reasoning_effort: xhigh. context: 500k. fast: false.

Authorized source: `vantioai/vantio-open-core` `620c68fd6fb10960194bbefb25bbfb2036d6d435`.
Checkout at review time: that SHA, clean worktree before this report file.

No PyPI publish, no Twine upload, no rebuild of the sealed candidates, no source mutation, no tag, no GitHub Release, no announcement, no PKG-01 integration, and no PKG-02 work.

## Final classifications

- `PYTHON_310_ARTIFACTS_COUNCIL_PASSED`
- `TRUSTED_PUBLISHER_WORKFLOW_NEEDS_REVISION`

The artifact seats pass. The Trusted Publisher mismatch holds, so that classification stays beside the pass. It is a workflow finding. It does not change the sealed wheel or sdist bytes.

## Locked hash re-verification

| Artifact | Bytes | SHA-256 | Result |
|---|---:|---|---|
| `vantio_agent_sdk-3.1.0-py3-none-any.whl` | 39235 | `dcf84cb3c4f144ece21032001657bfd9c91067faeffbefd0fb2ae19d6109dbeb` | MATCH |
| `vantio_agent_sdk-3.1.0.tar.gz` | 59669 | `9f991291d5e44a23e17a9b0d7db24f6e7048d4c76cf0a9c37e35ccbcfe999c4f` | MATCH |

The wheel and sdist inside `python-310-rc-council-bundle.tar.gz` match the locked candidates. The sdist attached directly matches the bundle sdist byte for byte (same SHA-256). The same hashes were re-read after install and tests. The candidate files were not modified.

`BUILDER_REPORT.json`, `wheel-manifest.json`, and `sdist-manifest.json` in the bundle match the separately attached JSON files.

## Seat table

| # | Seat | Verdict |
|---|---|---|
| 1 | Python packaging | PASS_WITH_NONBLOCKING_NOTES |
| 2 | Artifact integrity | PASS |
| 3 | Python runtime compatibility | PASS |
| 4 | Observability semantics | PASS |
| 5 | Privacy and telemetry | PASS |
| 6 | Release engineering | PASS_WITH_NONBLOCKING_NOTES |
| 7 | PyPI Trusted Publishing | NEEDS_REVISION |
| 8 | License and metadata | PASS_WITH_NONBLOCKING_NOTES |
| 9 | Ordinary-client installation | PASS |
| 10 | Scope control | PASS_WITH_NONBLOCKING_NOTES |
| 11 | Evidence verification | PASS |
| 12 | Product-positioning accuracy | PASS_WITH_NONBLOCKING_NOTES |

## Required questions

**Are these artifacts built from the authorized source SHA?**
Yes. Every file tracked under `packages/vantio-agent-sdk-py/` at `620c68fd6fb10960194bbefb25bbfb2036d6d435` is byte-identical in the sdist. Every `vantio/*.py` file is byte-identical in the wheel. Generated `PKG-INFO` and wheel `METADATA` are identical to each other. `PKG-INFO` is a build product, not a source file.

**Is the version exactly 3.1.0?**
Yes. `pyproject.toml`, `vantio.__version__`, wheel `METADATA`, sdist `PKG-INFO`, and the installed distribution metadata all say `3.1.0`. Name is `vantio-agent-sdk`. Wheel tag is `py3-none-any`. Generator recorded in the wheel is `hatchling 1.32.4`.

**Does either artifact contain PKG-01?**
No. No `optics-evidence-contract` or PKG-01 module is packed, importable, or declared as a dependency. Installed file lists do not contain it.

**Does either artifact contain unrelated repository material?**
The wheel does not. The sdist contains one extra file: `vantio_agent_sdk-3.1.0/.gitignore`, 673 bytes, SHA-256 `9b954b3800e0cc9a18127c6c6c7a7378954d86c552be6bafd7dc9e8e2b00a271`. That digest is the repository-root `.gitignore`. It is not a file tracked under `packages/vantio-agent-sdk-py/`. Hatchling 1.32.4 force-includes the VCS exclusion file found by walking from the project directory up to `.git` (`hatchling/builders/sdist.py` `get_default_build_data`, via `vcs_exclusion_files`). The package directory has no local `.gitignore`, so the walk selects the monorepo ignore file and stores it as `.gitignore` in the sdist. The wheel target does not include it. It names ignore patterns (`.env`, `*.pem`, `passwd.txt`, `apps/web`, `apps/cli`). It does not contain secret values.

**Does either artifact contain credentials or internal documents?**
No private keys, API tokens, or `.env` files. Strings such as `api_key` and `secret` in the sdist tests are fixtures that assert those values are not stored. `CHANGELOG.md` mentions Gate only as a historical note that Gate is not a current standalone public SKU. Planning documents are absent.

**Does the wheel install cleanly?**
Yes. A clean virtualenv install of only the wheel on Python 3.12.14 produced `vantio-agent-sdk` 3.1.0 from site-packages, with `Requires-Dist` absent. The same wheel installed on Python 3.10.21, 3.11.16, and 3.12.14.

**Does the source distribution install cleanly?**
Yes. A clean virtualenv install of only the sdist on Python 3.12.14 produced the same version from site-packages and no third-party requirements. The same sdist installed on 3.10.21, 3.11.16, and 3.12.14. Pip's isolated install build is ordinary installation. It did not replace the sealed candidates.

**Do supported Python versions pass?**
Yes for the declared range 3.10, 3.11, and 3.12. Each of the six installs (wheel and sdist, three interpreters) ran the sdist's own suite: 115 tests, 3 skipped, 0 failures.

Skips, identical on every cell:

- `InlineRedact310Tests.test_pycurl_redacts_and_blocks` — pycurl is not installed
- `OutcomeIntegrationTests.test_pycurl_success_path_does_not_invent_status` — pycurl is not installed
- `WheelSdistEquivalenceTests.test_wheel_and_sdist_runtime_sources_match` — the `build` module was not installed, because this council does not rebuild. The comparison that test would make was done directly: wheel and sdist `vantio/*.py` hashes match each other and match git.

Interpreters: CPython 3.10.21, 3.11.16, and 3.12.14.

**Does telemetry remain opt-in?**
Yes. With the three telemetry variables unset, `is_telemetry_disabled()` is true and no request is sent. `VANTIO_TELEMETRY=1` is the opt-in. An opted-in POST to a local sink carried only `anonymousId`, `runtime`, `runtimeVersion`, `os`, `event`, `hosts`, `callCount`, and `sdkVersion`. No `Authorization` header.

**Do disable overrides work?**
Yes. `VANTIO_TELEMETRY_DISABLED=1` and `DO_NOT_TRACK=1` each keep telemetry off when `VANTIO_TELEMETRY=1`.

**Are outcome semantics preserved?**
Yes. Independent checks and the package suite agree:

- HTTP 401 from urllib is raised, stored with `ok` false, `opticsStatus` `SUCCESS`, `applicationStatus` `APPLICATION_ERROR`, and is not `network_error`.
- HTTP 200 is `applicationStatus` `SUCCESS` with `opticsStatus` `SUCCESS`.
- DNS, connection refusal, and TLS classification do not invent an HTTP status and do not copy a secret from the exception message.
- A wrapped application exception stays `wrapped` and does not copy the message.
- An empty `shield()` writes no run log.
- The prompt body used in the 401 POST was absent from the run log.
- Package tests also cover requests, httpx (sync and async), aiohttp, urllib3, handled retry as the final response, and a final HTTP status winning over a nested transport error.

**Does metadata match the approved public product model?**
The packed metadata matches the authorized source and the three-product ladder written in that source: Optics, Phantom Engine, Enterprise. Project URLs are Homepage, Optics, Phantom Engine, Enterprise, Pricing, Repository, Issues, and Documentation. There is no Gate project URL. License expression is MIT. `Requires-Python` is `>=3.10`. Classifiers name Python 3.10, 3.11, and 3.12.

The one-line Summary is still `Vantio Optics Python SDK — shield() for Sight Loop observe. Metadata only; no prompts.` Keywords include `sight-loop`. That name is stale on other public surfaces in this repo. It is still the summary of the authorized `pyproject.toml`, so these exact artifacts carry it.

**Does the long description remove stale Sight Loop and enforcement confusion?**
The long-description body (the README after the metadata headers) contains no `Sight Loop`, `sight-loop`, or `sight_loop` string, and no `Gate` string. It states that Optics does not block, redact, or cap spend on its own; that Phantom Engine is the paid runtime-protection purchase; that Enterprise is talk-to-sales; and that Continuous Assurance is not a separate product. `fetch_policy` and `report_anomaly` are labeled as separately provisioned Phantom Engine / Enterprise APIs. The enforcement tutorial remains in that scoped section.

**Does the package remain Optics observational software rather than enforcement?**
The free path is observational. With no `VANTIO_API_KEY`, `_decide` returns `observe` for an in-scope host and `pass` for an out-of-scope host. Default policy sets `enforce` false. The same modules also contain Gate blocking, PII redaction, and spend-cap logic that run when a control-plane key is set and the fetched policy enables them. The run-log residual text states that. This is the authorized 3.1.0 source, not an extra file introduced by packaging.

**Does the Trusted Publisher workflow match the PyPI / documented GitHub path?**
No. See the Trusted Publisher section. Classification retained: `TRUSTED_PUBLISHER_WORKFLOW_NEEDS_REVISION`.

**Can publication occur without rebuilding?**
The workflow is built to do that. `pypi-publish.yml` is `workflow_dispatch` only. The promote job downloads the named sealed wheel and sdist from a custody tag and passes those paths to `promote_pypi.py --publish`. It does not run `python -m build`. This council did not create a custody tag and did not publish, so that path was read and not executed.

**Can the exact registry hashes be compared after upload?**
The promote script does that after a successful upload: it compares the PyPI `digests.sha256` for the wheel and the sdist with the sealed hashes, then downloads each file from `files.pythonhosted.org` and compares SHA-256 and size. A mismatch stops without a second upload. This council did not upload, so that comparison was not observed live.

A read-only PyPI lookup during this review: project `vantio-agent-sdk` exists, `info.version` is `3.0.14`, and release `3.1.0` is absent (as is `3.0.15`). Seventeen versions are present, `1.0.0` through `3.0.14`.

## Trusted Publisher verdict

Builder claim: `.github/workflows/pypi-publish.yml` uploads with Twine through `scripts/release/promote_pypi.py` rather than `pypa/gh-action-pypi-publish`.

That claim is true on this SHA.

Evidence in `.github/workflows/pypi-publish.yml`:

- The promote job sets `environment: pypi` and `permissions: id-token: write`.
- It installs Twine with `python3 -m pip install --disable-pip-version-check twine` (unpinned).
- It publishes with `python3 scripts/release/promote_pypi.py --publish` and the sealed file paths plus the approved SHA-256 values.
- The file contains no `uses: pypa/gh-action-pypi-publish`.

Evidence in `scripts/release/promote_pypi.py`: the upload command is `twine upload --non-interactive` of the sealed wheel and sdist, with the ambient environment. The script does not mint an OIDC token, does not set `TWINE_USERNAME` or `TWINE_PASSWORD`, and does not invoke the PyPA action.

Documented GitHub path, fetched from <https://docs.pypi.org/trusted-publishers/using-a-publisher/> during this review:

- The documented easy path is `uses: pypa/gh-action-pypi-publish@release/v1` with `id-token: write`.
- The manual OIDC section is marked as something ordinary users should not use. It says a stable public interface requires the `pypi-publish` action, and that the manual details may change.
- The GitLab example is the one that documents bare `twine upload` with no token. That is not the GitHub example.

What this workflow still has: OIDC-shaped job permissions and a GitHub environment named `pypi`. No long-lived PyPI token is referenced.

What Twine 7.0.0 actually does, inspected locally (`twine version 7.0.0`, `id` 1.6.1) and not used to upload: if no password is provided and the username is the PyPI token username, `password_from_keyring_or_trusted_publishing_or_prompt` calls `detect_credential` and `POST /_/oidc/mint-token` before any interactive prompt. `--non-interactive` still reaches that attempt; `Private.prompt` raises only if minting does not yield a token. On a GitHub Actions runner with `id-token: write`, current Twine can therefore exchange an OIDC token by itself. That behavior is unpinned (`pip install twine`) and is not the documented stable GitHub path.

`twine check --strict` on both sealed files returned PASSED. That command does not upload.

## Nonblocking notes

- Sdist `.gitignore` is the monorepo ignore file, force-included by hatchling 1.32.4. Removing it changes the sdist bytes and requires a new build. These locked hashes include it. The installed wheel does not.
- Summary and Keywords still say Sight Loop / `sight-loop`. The long-description body does not. Run logs written by this source still set `workflow` to `sight_loop`. That field is in the authorized 3.1.0 modules.
- `test_version.py` inside the sdist compares `LICENSE` with `extensions/vantio-optics/LICENSE.txt` two directories above the package. Those bytes match in this monorepo (SHA-256 `f41a838e502baec9034ac2011f6c8848be21ff18f2003fa22bc416a79df9bf11`). The license text starts `MIT License` and does not contain the word patent. The test is coupled to the monorepo layout.
- Builder wheel-manifest `unix_mode` values are the permission bits (`0o755` / `0o644`). The ZIP external attribute also carries the regular-file type bit, so the full mode is `0o100755` / `0o100644`. Permission bits match. PEP 376 `RECORD` hashes (URL-safe base64 SHA-256, no padding) match all nine content files. The `RECORD` row itself has an empty hash and size.
- Reproducibility of a second `python -m build` was reported by the builder and was not repeated here.
- pycurl tests were skipped because pycurl is not installed in the review venvs.

## Limitations

- No upload occurred, so registry hash equality after publication was not observed.
- No custody tag or GitHub Release was created. The promote job's download step was not run.
- PyPI trusted-publisher registration for this repository and workflow filename was not visible from the public project JSON. This review did not open PyPI account settings.
- The `$799/node/mo` figure is text inside the artifact's long description. `vantio-phantom-engine/docs/product-spec.md` is not in this checkout, so this council does not treat that sentence as an independently re-measured price.
- Python 3.9 and 3.13 were not in the declared classifier set and were not tested.

## Publication confirmation

No publication occurred. `twine upload` was not run. Workflow dispatch was not run. The sealed files still hash to the locked candidates.
