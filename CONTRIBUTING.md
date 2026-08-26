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
- **`openapi/planvortex.openapi.json` is a committed copy of that specification**, byte for byte —
  the same copy [PlanVortexNode](https://github.com/taliasoftworks/PlanVortexNode) keeps. It is not
  edited here and it is not built here: it is written where the specification lives, and copied in.
  It is committed because CI clones only this repository, and without the copy the `git diff
  --exit-code` that guards the generated types would be guarding nothing.

## Setting up

The project uses [uv](https://docs.astral.sh/uv/). Python 3.10 or newer.

```bash
uv sync                 # environment from uv.lock, dev group included
uv run pytest           # tests
uv run ruff check .     # lint
uv run ruff format .    # format
uv run mypy             # types, --strict, analysed against the 3.10 floor
uv run python scripts/check_packaging.py   # builds the wheel and proves it carries its types
```

The tests need no network and no credentials, on purpose.

`.python-version` pins **3.13** for local work — it is only what `uv` picks for your virtualenv. The
floor is still 3.10 and three separate things hold it: `requires-python` in the metadata, ruff's
`target-version = "py310"` (so `UP` never suggests syntax 3.10 cannot parse), and mypy's
`python_version = "3.10"` (so a `X | Y` that only works from 3.11 is caught here rather than in
someone's production). CI runs the tests on all five: 3.10 through 3.14.

### Why `check_packaging.py` exists

Node has `publint` and `arethetypeswrong`, which open the built package and complain before a user
does. **Python has no equivalent**, and the failure they would catch here is invisible: a wheel
missing its `py.typed` marker builds, installs and imports exactly as well as a correct one. The
only difference is that every type in the package silently becomes `Any` for whoever installed it.

So the check is hand-rolled, and it runs as its own CI job. It builds for real, runs
`twine check --strict`, opens the `.whl` to confirm the marker is inside, installs into a clean
virtualenv outside the repository, and then runs `mypy --strict` **twice**: once on a correct
snippet, which must pass, and once on a snippet with a deliberate type error, which must fail.

That last pairing is the point. Checking only the broken snippet would go green on a wheel with no
`py.typed` at all — without the marker mypy does not say "fine", it says
`Skipping analyzing "planvortex": module is installed, but missing library stubs or py.typed marker`,
which is itself an error. The correct snippet is what actually proves the types arrived.

### The mock plugin: `httpx2-pytest`, and why not the other one

There are two young plugins for mocking `httpx2`, and the choice matters enough to write down.

- **`httpx2-pytest`** (chosen) depends on `httpx2` and `pytest` and nothing else. It is the
  `pytest_httpx` API carried over — one of its authors is `pytest_httpx`'s author — and it is
  published as Production/Stable.
- **`pytest-httpx2`** is built on `respx`, and **`respx` depends on `httpx` classic**. Choosing it
  would install both `httpx` and `httpx2` into the test environment of a library whose whole point
  is that it uses the one and not the other. Two HTTP clients one import away from each other, in
  the exact place where a wrong import produces a passing test that proves nothing.

If the plugin ever becomes a problem, the fallback is not dramatic: `httpx2` accepts a custom
`transport`, and a thirty-line `MockTransport` covers both test layers with no dependency at all.

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
