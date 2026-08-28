# Contributing

Thanks for taking the time. This is the official Python client for the PlanVortex API, and it is
developed in the open. Its sibling is [PlanVortexNode](https://github.com/taliasoftworks/PlanVortexNode),
the Node client — the two are deliberately the same library in two languages, so a change to one
usually belongs in both.

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
uv run pytest           # tests (layers 1 and 2 — no network, no credentials)
uv run pytest -m live   # layer 3, against a REAL PlanVortex. Needs .env.live
uv run ruff check .     # lint
uv run ruff format .    # format
uv run mypy             # types, --strict, analysed against the 3.10 floor
uv run python scripts/generate_sync.py     # regenerates the synchronous twin
uv run python scripts/generate_models.py   # regenerates the types from the OpenAPI document
uv run python scripts/check_packaging.py   # builds the wheel and proves it carries its types
uv run python scripts/route_coverage.py    # which routes of the spec still have no method
```

`uv run pytest` needs no network and no credentials, on purpose — see *The three test layers* below
for the one that does.

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

### The generated types, and the two traps in them

`src/planvortex/_generated/models.py` is written by `scripts/generate_models.py` from
`openapi/planvortex.openapi.json`, which is a committed copy of what PlanVortexHome publishes at
<https://planvortex.com/openapi.json>. Both files are committed — installing `planvortex` must not
require generating anything — and CI regenerates and fails on a diff. With PlanVortexHome cloned
next door the copy is refreshed too; without it, the script says so and works from the copy. To
regenerate anywhere:

```bash
PLANVORTEX_OPENAPI=https://planvortex.com/openapi.json uv run python scripts/generate_models.py
```

Two options in that script are load-bearing, and neither failure announces itself:

- **`--special-field-name-prefix ""`.** `datamodel-code-generator` sanitises field names it cannot
  use as attributes, and the primary key of every PlanVortex resource is called `_id`. Without the
  option it emits `field_id` — a field that exists in no response at all — so mypy would approve
  `publication["field_id"]`, which explodes at runtime, and reject `publication["_id"]`, which is
  correct. The generator refuses to write a file where that happened, and `tests/test_models.py`
  checks it again on the committed one.
- **`--disable-future-imports`, plus the `sys.version_info` guard over `TypedDict` and
  `NotRequired`.** Both exist so that runtime introspection does not lie. With
  `from __future__ import annotations` the annotations stay *strings*, and `TypedDict` cannot read a
  `NotRequired` that is text: every key comes back required and `__optional_keys__` comes back
  empty. Taking `TypedDict` from `typing` and `NotRequired` from `typing_extensions` does exactly
  the same thing on 3.10. Type checkers get both cases right — they read PEP 655 directly — so mypy
  stays green either way and only `Publication.__optional_keys__` tells you.

That guard is also why `typing-extensions` appears in the dependencies with a
`python_version < "3.11"` marker: `NotRequired` is not in `typing` before 3.11, and `httpx2` only
pulls `typing_extensions` in below 3.13 — so relying on it would leave 3.10 broken the day `httpx2`
changed its mind, and importing it unconditionally would break 3.13 and 3.14, where nothing
installs it.

The public names live in `src/planvortex/types.py`, which is a thin hand-written layer on top:
readable names (`PublicationInput`, not `PublicationsPublicationInput`), the runtime tuples, and the
docstrings for what a type cannot say by itself — that `public_path` expires, that `id_account`
arrives populated in some operations and as a string in others.

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

One thing that will look like a mistake and is not: the distribution is called **`httpx2-pytest`**
but it imports as **`pytest_httpx2`**. The two names are crossed over. `pyproject.toml` names the
distribution, the test files name the module, and both are right.

### Why the tests run twice

Almost every test takes a `nucleo` fixture and runs once against the asynchronous core and once
against the generated synchronous one. The body is identical because `nucleo.esperar(...)` blocks in
both — it drives the coroutine in a loop of its own for the async variant, and returns the value
untouched for the other.

`nucleo.en_paralelo(...)` is what justifies the whole arrangement: `asyncio.gather` in one variant,
a `ThreadPoolExecutor` in the other. That is the only way to demonstrate that the twin's lock really
is a `threading.Lock`, because an `asyncio.Lock` across threads does not fail, does not warn, and
simply lets all ten through at once.

### The three test layers, and how to run the third

The same three layers the PlanVortex server and the Node library use, because they have already been
shown to work.

| Layer | What it proves | Where | Cost |
|---|---|---|---|
| **1 — core** | *Our* logic: token cache, backoff, pagination, error mapping, `multipart`, the `seek(0)` of a retry, the naive `datetime`. | `tests/test_core.py`, `test_files.py`, `test_pagination.py`, `test_webhooks.py` | free, no network |
| **2 — contract** | *Each resource's* HTTP contract: the request it builds and how it reads the answer. Real library code, the network mocked. | `tests/test_<domain>.py` | free, no network |
| **3 — live** | That the **server still answers what the library believes**. Talks to a real PlanVortex. | `tests/live/` | needs `.env.live` |

Layers 1 and 2 run against **both** variants (see *Why the tests run twice*). Layer 3 does not, and
that is a decision: every round of it is real traffic, so doubling it doubles the writes and doubles
the calls to `POST /oauth/token`, which the server throttles to 30 a minute per `client_id`. The
whole suite is synchronous and one smoke test in `tests/live/test_auth.py` covers the asynchronous
twin against a real server.

**Layer 3 is not in `uv run pytest`.** It carries the `live` marker and `addopts` carries
`-m "not live"`, so it is asked for out loud:

```bash
cp .env.live.example .env.live      # and fill in the two credentials
uv run pytest -m live               # read-only
LIVE_ALLOW_PUBLISH=1 uv run pytest -m live      # uploads, schedules a post, deletes both
```

Skipping it when `.env.live` is missing would not have been enough on its own: on the machine of
whoever *does* have the file, a plain `uv run pytest` would have gone out to the network without
anyone asking it to. The `-m` on the command line beats the one in `addopts` because it arrives
later.

Three switches guard the writing, all off by default and each one buying something different:
`LIVE_ALLOW_PUBLISH` (create and delete, scheduled a day out so nothing reaches a social network),
`LIVE_ALLOW_SOCIAL_PUBLISH` (send it to the network for real — public, immediate and irreversible,
which is why it does not share a switch with the previous one) and `LIVE_ALLOW_PRODUCTION` (writing
against `api.planvortex.com`, which **raises** rather than skipping: a dangerous configuration is
not the same thing as a missing one).

The credentials are prefixed `PLANVORTEX_LIVE_` and not `PLANVORTEX_CLIENT_ID`, which is what the
client reads from the environment on its own. That is deliberate: a `.env` holding production
credentials — the one `examples/` uses — must not arm this suite by accident.

`tests/live/test_read.py` is the boring one and the one that pays. Every list in this API arrives
wrapped under the name of its own resource and the library unwraps it by that exact name; layer 2
cannot catch a renamed envelope, because its mocks carry the old name — we wrote them.

### Adding a method to a resource

A resource is one module per domain in `src/planvortex/resources/`, written asynchronously; its twin
in `resources_sync/` is generated and must never be edited. To add a method:

1. Write it in the async module. Use the private helpers of `resources/base.py` — `_get`, `_post`,
   `_put`, `_delete`, `_list`, `_one`, `_post_one`, `_put_one` — and **declare a local with the
   return type** rather than returning the helper's value straight:

   ```python
   async def get(self, id_organization: str, id_account: str) -> Account:
       cuenta: Account = await self._one(self._path(id_organization, id_account), "account")
       return cuenta
   ```

   The extra line is not a style choice. The helpers return `Any`, and the obvious alternative — a
   `TypeVar` in their return type — **passes here and is rejected by mypy in the generated twin**,
   which is a file nobody is allowed to fix.
2. `uv run python scripts/generate_sync.py`. If the twin does not come out right, the substitution
   table is what is missing, not the code. Watch out for a name whose translated part has no word
   boundary after it: `aiterate_children` needed the rule to lose its trailing `\b`.
3. A contract test in `tests/test_<domain>.py`. The mock plugin already fails a test on an
   unmocked request **and** on a declared mock nobody asked for, which are the two halves that make
   the layer worth anything.

### The shapes the specification declares inline

`datamodel-code-generator` only emits `components/schemas`, and a dozen bodies and responses of this
API are written inline inside their operation — `{max_retries}`, `{url, token, expires_at}`,
`{cover_image, cover_offset}`. Those live by hand in `src/planvortex/_shapes.py`, and
`tests/test_shapes_parity.py` walks the committed bundle in both directions to keep them honest: a
hand-written type has no `git diff --exit-code` guarding it.

Two things about the top of that file are load-bearing and neither fails visibly: there is **no**
`from __future__ import annotations`, and `TypedDict` and `NotRequired` come from the same place
behind the version guard. Either mistake reports every key as required at runtime while mypy carries
on agreeing with the source. The parity test reads `__optional_keys__`, so it is also what catches
it.

## The rules that are not negotiable

These are design constraints, not preferences. Each one is here because breaking it produces a bug
that does not announce itself.

- **`httpx2` is the only unconditional runtime dependency.** Not `httpx` classic — a different
  package, so an integrator already using `httpx` has no version conflict with us. The one other
  entry, `typing-extensions`, carries a `python_version < "3.11"` marker and installs nowhere else.
  Anything more has to be argued for in the roadmap first, and `tests/test_packaging.py` is what
  forces the conversation.
- **The generated files are generated.** `_generated/models.py` and every `*_sync.py` carry a
  header saying so; editing one loses the change on the next run. Change the source — the OpenAPI
  document, or the async module — and regenerate.
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
- **What does no I/O is not generated.** `errors.py`, `query.py`, `transport.py`, `pagination.py`
  and `files.py` have no twin and will not get one. It is not tidiness: a `dataclass` declared in a
  generated source exists **twice** afterwards, and two classes with the same fields are two
  different types. Hand a `RetryConfig` built for one client to the other and it is a type error
  over a value that is identical field by field.
- **`src/planvortex/py.typed` is empty and must stay packaged.** Without that file, PEP 561 says the
  annotations are invisible to mypy and pyright once installed, and every generated type stops
  existing for whoever depends on us.

## Sending a change

1. A branch off `main`.
2. `uv run ruff check`, `uv run mypy` and `uv run pytest` in green.
3. A line in `CHANGELOG.md` under _Unreleased_.
4. A pull request describing what changes for whoever uses the package.
