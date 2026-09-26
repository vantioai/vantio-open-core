# Test and evidence strategy

Audience: INTERNAL_RESTRICTED

Evidence tiers used for a future claim are `UNIT_PROVED`, `INTEGRATION_PROVED`, `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, and `CUSTOMER_VALIDATED`.

Every requirement in the architecture matrix is `UNSET` on all of those tiers. This plan assigns the tier a future claim needs. It does not assign the tier as achieved. Producer tests, including tests a later implementation author runs, do not mark a package complete.

Independent verifier means a reviewer who did not write the change, on the exact source tip. Stranger-host means a host that is not the producer’s. Ordinary-client means a clean install path a customer can follow, which Slice 1 does not open because it does not publish. Customer validation means a customer workload and window, which no package has.

## 1. Applicable test classes

| Class | What it means here |
| --- | --- |
| Unit | One function, fixture in, result out |
| Integration | Two modules or both languages on one fixture |
| Adversity | Corrupt input, kill, disk refusal, symlink escape |
| Property | Invariants over generated records inside the allowlist |
| Fuzzing | Mutated bytes at the boundary. Out of scope to run in this plan |
| Privacy corpus | The canary list in `07-FIRST-SLICE-SPECIFICATION.md` |
| Crash | Process kill and torn write |
| Concurrency | Two writers, one file, after PKG-07 |
| Cross-version | Newer file, older reader, and the reverse |
| Windows, Linux, macOS, WSL, container | OS matrix. Not executed here |
| Offline | No network required for the asserted behavior |
| Stranger-host | Independent machine |
| Independent verifier | Other reviewer, exact tip |
| Ordinary-client | Published install. Not Slice 1 |
| Customer validation | Customer workload. Unset for every package |

## 2. Package matrix

`Y` means the class is a gate before an external claim for that package. `—` means it is not the closing gate. Slice 1’s subset is called out in section 3.

| Package | Unit | Integ | Adversity | Property | Fuzz | Privacy | Crash | Concurrency | Cross-version | OS matrix | Offline | Stranger | Verifier | Ordinary client | Customer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PKG-01 | Y | Y | Y | Y | later | Y | — | — | Y readers | Y before external | Y | Y | Y | — | Y before a customer claim |
| PKG-02 | Y | Y | Y | — | — | Y | — | — | Y | Y | Y | Y | Y | Y before a customer writer claim | Y |
| PKG-03 | Y | Y | Y | — | — | Y | — | — | — | Y | Y | Y | Y | — | — |
| PKG-04 | Y | Y | Y | Y | — | Y | — | — | Y proof bytes | Y byte identity | Y | Y | Y | — | Y before a customer export claim |
| PKG-05 | Y | Y | Y | — | — | Y | — | — | — | Y | Y | — | Y | — | — |
| PKG-06 | — | Y load | Y load fail | — | — | — | — | — | — | Y | Y | Y | Y | — | — |
| PKG-07 | Y | Y | Y | — | — | Y | Y | Y | Y | Y | Y | Y | Y | Y before a customer store claim | Y |
| PKG-08 | Y | Y | Y | — | — | Y | Y | — | Y | Y | Y | Y | Y | Y | Y before a preservation claim |
| PKG-09 | Y | Y | Y | — | — | Y | — | Y in-process | Y | Y | Y | Y | Y | — | Y before a correlation claim |
| PKG-10 | Y | Y | Y | Y | — | Y | — | — | Y | Y | Y | Y | Y | Y before a customer query claim | Y |
| PKG-11 | Y | Y | Y | — | — | Y | — | — | Y | Y | Y | Y | Y | Y | Y before a deletion claim |
| PKG-12 | Y | Y | Y | — | — | Y | Y | Y | Y | Y | Y | Y | Y | Y before a reliability claim | Y |
| PKG-13 | Y | Y | — | — | — | — | — | — | — | Y | Y | Y | Y | — | — |
| PKG-14 | — | Y | Y | — | — | Y | — | — | — | Y | Y | Y | Y | — | Y |
| PKG-15 | Y | Y | — | — | — | Y | — | — | — | Y | Y | Y | Y | — | Y before a trend claim |
| PKG-16 | — | Y | Y | — | — | Y | — | — | — | Y | depends on mode | Y | Y | — | Y |
| PKG-17 | — | Y | Y | — | — | Y | — | — | — | Y | local proof stays offline | Y | Y | — | Y |

Fuzzing is a later addition on PKG-01’s boundary. It is not a substitute for the named corpus. This plan does not set a fuzz budget.

## 3. Slice 1 gates and the tests that would satisfy them later

None of these gates are satisfied by this document.

| Gate | Test class |
| --- | --- |
| S1-G1 Source inventory and compatibility plan accepted | Review of the inventory against option B. Not a runtime test |
| S1-G2 Shared contract accepted | Unit tests of the catalog against A1 section 4 |
| S1-G3 Node implementation tests pass | Unit and property tests of the Node validator |
| S1-G4 Python implementation tests pass | Unit and property tests of the Python validator |
| S1-G5 Cross-package conformance passes | Integration: same fixtures, same outputs |
| S1-G6 Privacy corpus passes with zero prohibited persistence | Privacy corpus |
| S1-G7 Fail-open adversity tests pass | Adversity: application result unchanged |
| S1-G8 Independent council passes exact source tip | `PROVED_EXTERNAL` review, not producer tests |
| S1-G9 Sealed artifacts independently verified | Not Slice 1. Slice 1 does not seal |
| S1-G10 Ordinary-client proof passes | Not Slice 1. Slice 1 does not publish |

S1-G9 and S1-G10 stay on the list so a later release cannot skip them. They are not exit criteria for the option B library by itself. A customer claim about the live CLI or the live Python package needs PKG-02 plus those two gates.

## 4. Required tier before an external claim

| Package | Minimum tier before an external claim | Tier now |
| --- | --- | --- |
| PKG-01 | `UNIT_PROVED` for the library corpus. `INTEGRATION_PROVED` once writers are wired. `STRANGER_HOST_PROVED` and `PROVED_EXTERNAL` before the claim | `UNSET` |
| PKG-02 | `INTEGRATION_PROVED` on both writers, then `STRANGER_HOST_PROVED` | `UNSET` |
| PKG-03 | `INTEGRATION_PROVED` | `UNSET` |
| PKG-04 | `UNIT_PROVED` on the golden vector, then `INTEGRATION_PROVED` for both languages | `UNSET` |
| PKG-05 | `UNIT_PROVED` | `UNSET` |
| PKG-06 | `STRANGER_HOST_PROVED` load matrix before the binding is called shippable | `UNSET` |
| PKG-07 | `INTEGRATION_PROVED` on one file from both languages, then `STRANGER_HOST_PROVED` | `UNSET` |
| PKG-08 | `INTEGRATION_PROVED` | `UNSET` |
| PKG-09 | `INTEGRATION_PROVED` | `UNSET` |
| PKG-10 | `INTEGRATION_PROVED` | `UNSET` |
| PKG-11 | `INTEGRATION_PROVED` | `UNSET` |
| PKG-12 | `INTEGRATION_PROVED` including crash and fail-open | `UNSET` |
| PKG-13 | `INTEGRATION_PROVED` if OF-12 is built | `UNSET` |
| PKG-14 | `INTEGRATION_PROVED` after a charter | `UNSET` |
| PKG-15 | `INTEGRATION_PROVED` | `UNSET` |
| PKG-16 | `INTEGRATION_PROVED` after decision 3 | `UNSET` |
| PKG-17 | `INTEGRATION_PROVED` after decision 12 | `UNSET` |

`CUSTOMER_VALIDATED` is an additional tier. It is never implied by the tiers above. OF-52 stays deferred and unset.

## 5. Completeness of producer tests

A green producer run is an input to council review. It is not `PROVED_EXTERNAL`. The implementation author and the council reviewer are different agents. This planning producer is neither an implementer nor the planning council.
