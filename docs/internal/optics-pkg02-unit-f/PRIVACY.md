# PKG-02 Unit F privacy

PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

The mapper strips prohibited names. This reader does not echo the rejected value. Diagnostics keep the adapter's fixed note strings only. A note that is not on that list is dropped. The note that names a refused optics token is replaced with `optics token refused`, so the raw token is not copied into the explanation.

A payload name such as `prompt` drops that observation. The canary value is absent from the explanation JSON. Structural legacy names such as `plane`, `data_note`, `residual`, and `est_spend_usd` are not stored.

The absolute path is not copied into the result. `source_name` is the basename only when it matches a short safe grammar. A directory name that contains a canary does not appear in the explanation.

An own getter is not called. The reader does not import the live CLI or the live SDKs, so it does not log through those trees.

The application result is not copied into the explanation. A validator rejection does not replace the caller object and does not change the caller return value.
