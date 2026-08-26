# planvortex

The official Python client for the [PlanVortex](https://planvortex.com) API — connect social
accounts, schedule and publish posts, read comments and messages, and pull stats, from Python.

> ## ⚠️ Not released yet
>
> **`0.0.1` is a placeholder.** It reserves the name on PyPI and proves the release pipeline; it
> contains no client and there is nothing useful to install yet. The first usable release will be
> `0.1.0`.
>
> If you need a PlanVortex client today, the Node one is published and complete:
> [`npm i planvortex`](https://www.npmjs.com/package/planvortex).
>
> Watch this repository to hear about `0.1.0`.

## What it will be

- **Synchronous and asynchronous**, same surface: `PlanVortex` and `AsyncPlanVortex`.
- **Typed**, from the same OpenAPI specification the API publishes at
  <https://planvortex.com/openapi.json>. Returned shapes are `TypedDict`, so `_id` stays `_id`.
- **One runtime dependency**, `httpx2` — a different package from `httpx` classic, so it will not
  collide with whatever your project already uses.
- **Server-side.** The `client_credentials` flow needs your `client_secret`. Connecting an account
  from a browser is what the temporal connect token is for.
- Python 3.10 and newer.

```python
from planvortex import PlanVortex

pv = PlanVortex()  # reads PLANVORTEX_CLIENT_ID and PLANVORTEX_CLIENT_SECRET

upload = pv.uploads.create(org_id, file="./sourdough.jpg")
pv.publications.create(
    org_id,
    account_id,
    social_network="instagram",
    text="New oven, new loaves",
    files=[upload["_id"]],
)
```

## Links

- [API documentation](https://planvortex.com/documentation)
- [Developers](https://planvortex.com/developers)
- [Node client](https://github.com/taliasoftworks/PlanVortexNode)
- [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Changelog](CHANGELOG.md)

MIT © Talia Softworks
