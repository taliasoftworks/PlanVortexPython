# Contributing

Thanks for taking the time. This is the official Python client for the PlanVortex API, and it is
developed in the open. Its sibling is [PlanVortexNode](https://github.com/taliasoftworks/PlanVortexNode),
the Node client — the two are deliberately the same library in two languages, so a change to one
usually belongs in both.

> **Status.** The package is being built. `0.0.1` on PyPI is a placeholder that reserves the name
> and proves the release pipeline; it contains no client. The first usable release is `0.1.0`.

## Before you start

- **Bugs and questions about the API itself** (an endpoint that answers something unexpected, a
  permission that does not behave) belong in PlanVortex support, not here. This repository is the
  client.
- **A new endpoint** normally does not start here either: the client's types are generated from the
  public OpenAPI specification at <https://planvortex.com/openapi.json>, so an endpoint missing
  here is usually missing from the specification too.

## Setting up

The project uses [uv](https://docs.astral.sh/uv/). Python 3.10 or newer.

```bash
uv sync
uv run pytest
```

The tests need no network and no credentials, on purpose.

## The rules that are not negotiable

These are design constraints, not preferences. Each one is here because breaking it produces a bug
that does not announce itself.

- **`httpx2` is the only runtime dependency.** Not `httpx` classic — a different package, so an
  integrator already using `httpx` has no version conflict with us. Anything else has to be argued
  for in the roadmap first.
- **The synchronous client is generated from the asynchronous one.** `_client_sync.py`,
  `_core/http_sync.py` and `resources_sync/` are written by `scripts/generate_sync.py` and carry a
  header saying so. Edit the async source and regenerate; CI runs the generator and fails on a
  diff. Wrapping the async client in `asyncio.run` is not an option — it raises `RuntimeError`
  inside FastAPI, inside a notebook, and inside any running loop.
- **Errors are classified by `code`, never by the HTTP status.** Every domain error arrives as an
  HTTP 400.
- **An unknown value is not an error.** The list of social networks, the publication states and the
  error catalogue all grow. A client that rejects a value it does not recognise breaks every
  integration the day PlanVortex adds a network. That is why `social_network` is typed `str`, with
  `SOCIAL_NETWORKS` and `SocialNetwork` published beside it for whoever wants to narrow.
- **No `POST` is ever retried once it reached the server.** Publishing twice is worse than failing,
  and the API has no idempotency key. A `ConnectError` proves the body never left; a `ReadTimeout`
  proves nothing.
- **API field names are not translated.** `_id` stays `_id` and `id_organization` stays
  `id_organization`, because the integrator reads them in the documentation. This is the reason the
  library returns `TypedDict` and not pydantic models: a leading underscore cannot be a pydantic
  field.
- **`src/planvortex/py.typed` is empty and must stay packaged.** Without that file, PEP 561 says the
  annotations are invisible to mypy and pyright once installed, and every generated type stops
  existing for whoever depends on us.

## Sending a change

1. A branch off `main`.
2. `uv run ruff check`, `uv run mypy` and `uv run pytest` in green.
3. A line in `CHANGELOG.md` under _Unreleased_.
4. A pull request describing what changes for whoever uses the package.
