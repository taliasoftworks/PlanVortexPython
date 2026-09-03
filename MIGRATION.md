# Migration guide

Breaking changes, version by version, with what to do about each. The [CHANGELOG](CHANGELOG.md)
records *what* changed; this file records *what you have to do about it*.

## 0.5.0 → 0.6.0

The first breaking release, and it breaks in the type checker rather than at runtime: one key left a
`TypedDict`. Nothing changed on the wire — the server stopped charging for publications on
02-09-2026 and opened the public API to every plan, and this release is the types catching up.

### `PlanData` no longer has a `publications` key

**Publications are unlimited on every plan**, so there is no quota to describe. The count did not
disappear: it moved to the new `PlanUseData`, which is what `actual_use` has always been in
practice — a plan plus `publications`, `NotRequired` because a brand-new organization has spent
nothing.

```python
use = await pv.organizations.use(id_organization)

use["limits"]["publications"]  # ✗ mypy error now — and it already raised KeyError
use["actual_use"].get("publications", 0)  # ✓ the month's count, with no ceiling to compare it to
```

**What to do:** if you drew a progress bar for publications, delete it — there is no denominator.
Print the count on its own. What throttles publishing is **rate**, not the plan: a per-hour cap per
account and a per-network daily cap, both in `GET /social_limits`, arriving as errors 978 and 979.

The asymmetry is deliberate: `actual_use` is a `PlanUseData` and `actual_asigned` stays a
`PlanData`, because what a parent hands a child organization is a quota and cannot include a metric.

### The error ranges: three families are wider

| Family | Was | Now | What was falling through |
|---|---|---|---|
| `publication` | 900-960 | **900-979** | Bluesky, Discord, Telegram and Threads (961-977), plus the two rate brakes, **978** and **979** |
| `auth` | 500-544 | **500-546** | **545** (the plan's API rate limit, a `429` with `Retry-After`) and **546** (unverified email when creating an app) |
| `plan_limit` | 1300-1307 | **1300-1308** | **1308** (no more apps fit in this plan) |

Everything above each old ceiling was arriving as a bare `PlanVortexError`, so this only adds to
what an `except` clause sees. It is listed here because that is a change in which class an exception
*is*, not only in what the docs say.

**What to do:** nothing, if you let the library classify. If you copied the ranges, copy them again.
And if you catch `PublicationError` to decide whether to retry, look at the code: **978 and 979 are
transient** — waiting fixes them — while the rest of that family is not.
