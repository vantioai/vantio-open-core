# PKG-02 Unit D known limitations

PRIVATE | FUTURE LINE | NOT PUBLISHED | NOT SEALED | NO UNIT E | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

- This line is not published and not sealed. `UNIT_D_PROVED_NOT_SHIPPED` is not a customer release.
- CLI `0.3.24` stderr still prints `Optics status: Successful` because that sentence is in the frozen interceptor. The canonical file does not store optics `SUCCESS`.
- `displayCall` still returns optics `SUCCESS`. The matrix cell `future_cli` / `cli_0_3_24` stays `UNSUPPORTED` for that reason.
- Fetch is the path with a content-length note. `http.request`, `https.request`, and curl do not fill that note. A missing note omits `response_bytes` rather than copying the frozen `0`.
- The contract still writes envelope `span_id` `null`, `parent_span_id` `null`, and `identity_conflict` `NONE`. Those are the validator's envelope fields. They are not a claim that a span or a parent run was observed.
- `ended_at` is the wrap exit instant, which is also when the file is written.
- Reusing `VANTIO_TRACE_ID` overwrites that one path. Other files stay.
- If canonical serialization throws and the error document also throws, the preload falls through to the frozen bytes so the exit handler does not change the workload status. The fault-injection proof does not take that branch. It writes `OPTICS_ERROR`.
- Unit E is not in this tree. Python `3.1.0` is unchanged. The launcher refuses a non-Node program.
- Windows, macOS, and a Kubernetes cluster were not part of this proof. The proofs ran on this Linux host.
- No council pass is recorded here.
