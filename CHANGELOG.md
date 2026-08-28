# Changelog

All notable changes to this package are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-28

The first release with code in it. Every documented endpoint of the PlanVortex API has a method -
**112 of the 112 operations** - in two clients that cannot drift apart, the types come from the same
OpenAPI document the API publishes, the three test layers are in place (the third against a real
PlanVortex) and the reference is published. It is a `0.x` on purpose: the shape of the client is
settled and pinned by tests, but nobody outside has used it yet, so a break before `1.0.0` is
possible and would arrive written down in `MIGRATION.md`.

The `0.0.1` already on PyPI carries no code. It was published on 2026-08-26 to reserve the name and
to prove the release pipeline before there was anything to lose.

### Added

- The **types**, generated from the OpenAPI document PlanVortex publishes and exposed with readable
  names in `planvortex.types`: `Publication`, `Account`, `Upload`, `Comment`, `Message`, `Contact`
  and the rest of the API's shapes, as `TypedDict`. The API's field names survive untranslated, so
  it is `publication["_id"]` and not `publication.id`.
- The value lists, at the package root and at runtime: `SOCIAL_NETWORKS`, `PUBLICATION_STATES`,
  `PUBLICATION_TYPES`, `COMMENT_NETWORKS`, `CONTACT_CHANNELS`, `MESSAGE_TYPES`,
  `INTEGRATION_PROVIDERS` and `AI_PLAN_STATES`. Each one is derived from the same `Literal` the type
  checker reads, so the two cannot disagree. **The lists grow**: a value you do not recognise is one
  this release had not heard of, not an error.
- Helpers for the fields the API returns in two shapes: `account_id()`, `account()`,
  `publication_id()`, `publication()`, `message_direction()`, `message_contact_id()`,
  `message_contact()`, `message_files()` and `message_file_ids()`. `id_account` arrives resolved in
  some operations and as a string in others, and these cover it without an `isinstance` in every
  call site.
- The asynchronous and synchronous cores: HTTP with timeouts, backoff and retry rules, the
  `client_credentials` token with its cache and its lock, the error hierarchy, and the query encoder
  with the camelCase map.
- **The two clients**, `PlanVortex` and `AsyncPlanVortex`, with **fourteen resources covering the
  whole public API**: `catalog`, `clients`, `organizations`, `accounts`, `uploads`, `publications`,
  `comments`, `messages`, `contacts`, `products`, `integrations`, `ai_plans`, `dashboard` and
  `apps` — **112 of the 112 operations** the specification documents, everything except the 19
  routes of roles and invitations, which are out of scope. The synchronous client is generated from
  the asynchronous one, so they cannot drift apart, and `scripts/route_coverage.py` walks the
  OpenAPI bundle on every test run so that "no route is missing" keeps being true.
- Three things that **used to be documented as broken and work now**, fixed in the server on
  2026-08-24 and exposed here for the first time: filtering contacts by `social_network`, asking for
  one product by `product_id` (`products.get()`, which also tolerates the single-object shape the
  network answers with), and `in_response_external_id` in `messages.send()`, which is what makes
  `comment_message` and `publication_message` reachable from the public API.
- `contacts.merge()`, which reads the contact before updating it so that its `extra_data` is not
  wiped: it is the one field the server overwrites with whatever the body carries.
- `organizations.users()`, the one read of the roles section the library covers, because a custom
  panel needs to paint the team.
- `Page(data, total)` for every listing, with the API's envelope already opened, plus `iterate()` /
  `aiterate()` to chain pages — with a page cap so that a server ignoring the `offset` fails instead
  of hanging the process.
- Uploading from a path, `bytes`, an open binary file or an iterable of `bytes`. A path is the one
  that neither goes through memory nor asks you to close anything. A body that cannot be rewound
  forbids the retry outright, because a second attempt over a spent stream uploads zero bytes.
- `publish_date` accepts a `datetime` and is serialized with its offset. A naive one raises instead
  of guessing: assuming UTC publishes at the wrong time for whoever is in Madrid, and assuming the
  process's zone does it for whoever is in Docker.
- `as_temporal_token()`, for the account-connection flow: an app cannot connect an account, so it
  issues a temporal token and hands it to the person who can.
- `is_publishable_network()`, a `TypeGuard` narrowing a network down to the **nine** that accept
  publications, and `PUBLISHABLE_NETWORKS` beside it. An account's `social_network` is one of ten
  and a publication's is one of nine — `google_business` receives reviews, not posts — so handing
  one to the other was a type error with no way out that did not throw away a real guarantee.
- **Five runnable examples**, each with a test of its own: `publish.py` (credentials to a scheduled
  publication), `schedule.py` (the calendar, moving a post, rescuing a failed one), `comments.py`
  (inbox, actions matrix, live thread and replying — read-only unless `PLANVORTEX_ALLOW_REPLY=1`),
  `webhooks.py` (a receiver with no dependencies, and a `--self-test` that signs a delivery to
  itself) and `connect.py` (the connection flow, and what the browser has to do).
- **The published reference**, generated with `pdoc` from the docstrings and deployed to GitHub
  Pages on every push to `main`: <https://taliasoftworks.github.io/PlanVortexPython/>.
- **`planvortex.webhooks`**, in a module of its own because whoever receives deliveries is rarely
  the process that publishes: `verify_webhook_signature()` over the **raw** body with a constant-time
  comparison, `parse_webhook_body()` (the body is an **array** of changes), and
  `handle_webhook_request()`, which does both and finds the signature header whatever your framework
  calls it. No framework middleware is shipped: the README carries the Flask, FastAPI and Django
  recipes, each with the one line that gives you the raw body.
- The webhook event types, split by `field` so they can be narrowed — `AccountStateChange`,
  `MessageChange`, `CommentChange` and `IntegrationErrorChange` — with the predicates
  `is_comment_change()` and friends, and `UnknownWebhookChange` for the events a future server sends
  and this release has never heard of. `WebhookSignatureError` and `WebhookBodyError` are
  `PlanVortexError` of family `webhook`.

- **The live test suite** (`tests/live/`), which talks to a real PlanVortex and is the only layer
  that can notice the *server* changing under the library: a renamed list envelope, an error code
  that moved, a tenth social network. It ships in the sdist like the rest of the tests. It is not in
  `uv run pytest` — it carries the `live` marker and is asked for with `uv run pytest -m live` — it
  skips itself whole without `.env.live`, and everything that writes is behind `LIVE_ALLOW_PUBLISH`,
  `LIVE_ALLOW_SOCIAL_PUBLISH` and `LIVE_ALLOW_PRODUCTION`. See `.env.live.example`.

### Changed

- `PublicationInput["publish_date"]` now **accepts a `datetime` in the type**, not only at runtime.
  The generated type said `str`, so the usage the library documents did not type-check. It is the
  one shape written by hand on top of the generated one, and it has a parity test against the
  specification that allows exactly that one difference.
- `examples/` is inside mypy's scope. It was the only code in the repository nobody checked, and
  the two failures it turned up were holes in the library, not in the examples.
- `typing-extensions` is now a dependency on **Python 3.10 only** (`python_version < "3.11"`), where
  `NotRequired` is not yet in `typing`. Nothing is installed from 3.11 upwards.
- The coverage floor is now enforced (`fail_under = 97`), measured over layers 1 and 2 — the ones
  CI runs.

## [0.0.1] - 2026-08-26

Placeholder release. It reserves the `planvortex` name on PyPI and proves the trusted-publishing
pipeline end to end before there is anything to lose. It contains no client.

[0.1.0]: https://github.com/taliasoftworks/PlanVortexPython/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/taliasoftworks/PlanVortexPython/releases/tag/v0.0.1
