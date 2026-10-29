# Research team answers (NOT Steve) 2026-10-29 23:09, PR #73

Frozen sha256 `cc904288bbab80c0e4115df39e3baa8587514d9567847e326cb401e3ea112b2d`.
Research team, **not** Steve.

1) Flatten-grace limit: APPROVE. 5s hard explicit timeout, fallback to separate stop or immediate flatten; document residual race (fill before ATM attached), not blocking; no open-ended grace.
2) Prolonged-disconnect flatten: APPROVE. Pre-registered threshold (e.g. 30-60s) without confirmed server-side stop -> Risk Core flatten; hard, enforced by Risk Core.
3) PC_Home ATM probe before merge: recommended/preferred, not strictly blocking if local tests + CI green and residual race documented.
Limited run may run in parallel.
