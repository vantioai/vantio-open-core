# Disclosure — public and private paths

Audience: INTERNAL_RESTRICTED

## Where this packet lives

The source is in the public `vantio-open-core` repository because that is where the other private internal packages live. The package is `private`, it is outside `pnpm-workspace.yaml`, and the npm promote list does not name it. The public README is unchanged. There is no public SKU.

Distribution of the reports is `INTERNAL_RESTRICTED`. The public disclosure object withholds control rows, evidence hashes, Wave 2 states, and procurement detail.

## What was kept generic

Framework rows use identifiers, dates, and source URLs. ISO/IEC 42001 clause text is `SOURCE_ACCESS_REQUIRED`. No clause number is invented. EU rows are a technical crosswalk and do not classify a system. Federal rows point at OMB memoranda and do not copy a procurement strategy.

Host-authority evidence cites the contract-only manifest already in this tree. It does not add loader behavior or enforcement parameters.

## Overlays

Customer-confidential material, government bid strategy, and proprietary enforcement detail are not in this packet. Those overlays are `OVERLAY_REQUIRED` and are not stored here. See `overlays/README.md`.

Proof class does not rise when an audience changes from internal to investor, customer, or assessor. Nothing in this packet is cleared for `PUBLIC` except the short disclosure object.
