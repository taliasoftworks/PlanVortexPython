# Changelog

All notable changes to this package are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2026-09-04

**Users are unlimited on every plan**, so the quota that said otherwise is gone from the types —
the same correction 0.6.0 made for publications, one axis later.

It is the second half of a change the server made on 03-09-2026: users stopped being something a
plan grants and became something you simply count. `PlanData["users"]` was a **required** key, so
mypy accepted `limits["users"]` and the call raised `KeyError` at runtime, which is the same
failure mode 0.6.0 describes for publications.

### Changed

- **BREAKING (types only): `PlanData["users"]` no longer exists.** The count moved to
  `PlanUseData` as an optional key — how many users have access right now, with no limit to
  compare it against, because there is none. Nothing changes on the wire.
- **The `/apps` operations no longer claim the Custom plan.** Their docstrings still said the API
  needed it. That stopped being true on 02-09-2026, and the docstrings come straight from the
  OpenAPI document, so they were repeating a copy of the spec that had not been rebuilt since.

### Removed

- **`PlanData["artificial_inteligence"]`, `PlanData["stats"]` and `PlanData["whatsapp"]`.**
  Three optional keys describing a plan model that no longer exists: statistics and WhatsApp are on
  every plan, and what gates AI is `ai_credits` — a plan with credits has AI, and Free has zero.

## [0.6.0] - 2026-09-03

**Publications are unlimited on every plan**, so the quota that said otherwise is gone from the
types.

It was never a number this package invented: `PlanData["publications"]` came from the spec, and the
server stopped charging for it on 02-09-2026. What stayed behind was worse than a wrong number — it
was a key mypy kept promising, so `limits["publications"]` type-checked and raised `KeyError` at
runtime.

### Changed

- **BREAKING (types only): `PlanData` no longer has a `publications` key.** The count moved to the
  new `PlanUseData`, which is what `actual_use` has always been in practice: the same shape as a
  plan plus `publications`, and `NotRequired` because a brand-new organization has spent nothing.
  Nothing changes on the wire.
- `OrganizationUse["actual_use"]` is a `PlanUseData`; `actual_asigned` stays a `PlanData`, which is
  the real asymmetry: what a child organization was handed cannot include a metric.
- The `publish` example prints publications as what they are — a monthly count with no ceiling —
  instead of `12 de 100`. What throttles publishing is rate (per hour and account, and the
  per-network daily caps in `GET /social_limits`), not the plan.
- **The `publication` error family now reaches 979, not 960.** Everything above the old ceiling was
  falling outside every range and arriving as a bare `PlanVortexError`: the Bluesky, Discord,
  Telegram and Threads codes (961-977) and, more to the point, the two rate brakes that replaced the
  monthly quota — **978** (publishing too fast on this account) and **979** (that network's daily
  cap). `except PublicationError` now catches them.

### Added

**The public API is on every plan now, the free one included** — it used to be a Custom-plan
feature — and the types follow the three things that came with opening it.

- `PlanData["apps"]`: how many apps the plan allows (1 on Free, 2 on Basic, 5 on Pro, 10 on Custom).
  Each app is a `client_id` with a secret, so each one is a key to the whole API. Unlike accounts,
  users or storage it is **not** split between organizations — an app belongs to the client.
- Three error codes, and the two ranges that were hiding them: **545** (the plan's API rate limit,
  which arrives as a `429` with `Retry-After`) and **546** (the account's email must be verified to
  create an app) are `AuthError`, so that range now runs to 546; **1308** (no more apps fit in this
  plan) is a `PlanLimitError`, so that one runs to 1308.

## [0.5.0] - 2026-09-02

**Threads is the twelfth network**, and the types now know it.

Nothing here removes anything: `SocialNetwork` gains a value, `PublishableNetwork` gains another,
and everything that type-checked before type-checks now. What was wrong until today was quieter than
an error — the committed copy of the spec predated Threads, so an account coming back from a real
API arrived with a `social_network` no `Literal` had ever heard of, and the prose still counted
eleven networks where the API had twelve.

### Changed

- The OpenAPI copy and the generated models are rebuilt from the published document, so `threads`
  is a `SocialNetwork`, a `CommentNetwork` and a publishable network.
- `PublishableNetwork` — hand-maintained, because generating it is not possible — includes
  `threads`: **eleven of the twelve** networks have a feed, and `google_business` is still the one
  that does not.
- The prose that counts networks: a connection link is a `redirect` on **ten of the twelve**, not
  nine of eleven. WhatsApp and Telegram are still the two that are not.

## [0.4.0] - 2026-08-31

An AI plan can now be **archived**, and deleting one finally means what people thought it meant.

The two look alike on a screen and have nothing in common underneath: archiving takes the plan out
of the listing and touches nothing else, while deleting takes the publications that had not gone out
with it. Almost every time someone reaches for "remove" they wanted the first one.

Upgrading from `0.3.0` needs no changes and `MIGRATION.md` gains no entry — everything added here is
additive. **Read the note on `remove()` anyway**: what it deletes changed in the server, so it has
been happening to your `0.3.0` calls for a while and the docs that shipped with them say otherwise.

### Added

- **`ai_plans.archive()` and `ai_plans.unarchive()`**, in both clients. Archiving is **visibility
  only**: the plan leaves the listing and moves to the archived one, no publication is touched —
  anything scheduled keeps publishing — no credits come back, nothing is cancelled. It therefore
  works in **any state**, `generating` included, and it is undone. On the object it is
  `archived_date`: a field, **not** a value of `state`, so reading the state to find out whether a
  plan is archived will never work. Absent means active, which is how every plan created before the
  field existed comes back.
- **`archived` on `ai_plans.list()` and `ai_plans.aiterate()`/`iterate()`.** `True` returns the
  archived plans instead of the active ones, never both at once. A `False` is not sent: the server
  switches the filter on with the literal `"true"`, so it would be noise — and it would suggest a
  third mode with both cupboards open that does not exist.

### Changed

- **`ai_plans.remove()` deletes the plan's publications that have not gone out yet**, not only the
  drafts: if the plan had already been validated, whatever was still scheduled goes too. This is a
  change **in the server**, so it reached your existing calls the day it shipped — before it, a
  validated plan you deleted kept publishing by itself the following week. Two states are
  deliberately left alone: the already published one, because deleting it here would not take it off
  the network and would only lose its history, and the one being published at that very moment.
  If you wanted the plan out of the way without losing anything, that is `archive()`.

## [0.3.0] - 2026-08-31

The AI planner stops being one thing. A plan can now be generated from **your own photos**, from an
**article**, from the **products of a connected catalogue** or as a **countdown towards a date**, and
the package publishes the catalogue that says what each of those accepts and what each of them
costs.

Everything here is additive: `template` and `source` are optional, and a plan created without them
is a `standard` one — exactly what every plan was before templates existed. Upgrading from `0.2.0`
needs no changes and `MIGRATION.md` gains no entry.

**The headline is a price, and it is worth saying out loud before your user creates the plan.**
Images are 94 % of what a plan costs. A template whose pictures come from the source generates none,
so the same week — 7 publications with a picture on each, one account — goes from **519 credits to
48**. That is not a rounding: it is the difference between a feature a customer uses once a month
and one they use every week.

### Added

- **`catalog.planner_templates()`**, in both clients and cached like the rest of the catalogue. It
  answers what a plan can be generated FROM and what each source allows: `allows_shared`,
  `allows_gallery`, `generates_images`, the `regenerate` matrix, `orchestration_cost` and
  `orchestration_cost_per_source_item`, `max_source_items`, and the `source_fields` the source step
  is made of. **Read it, do not copy it** — it is the one catalogue entry that carries prices, and a
  table written by hand in your interface would show a cost the server no longer charges. It is also
  the only route of the catalogue that **wraps its answer** (`{"templates": [...]}`), which is the
  kind of thing that fails without an error: iterating the envelope gives you the string
  `"templates"` and nothing complains.
- **`template` and `source` on `ai_plans.create()`**, with the five templates: `standard`,
  `from_images`, `from_text`, `from_catalog` and `campaign`. A template is the **source** of the
  content and not a different flow — publish days, language, tone, `shared` and the images stay
  cross-cutting options, and each template declares which of them it accepts. Sending one it does
  not accept is a 2106, not a silent ignore.
- **`PlannerTemplateName` and `PLANNER_TEMPLATES`**, plus `PlannerTemplate`,
  `PlannerTemplateField`, `PlannerTemplateFieldType`, `AiPlanSourceInput`,
  `AiPlanSourceImageInput`, `AiPlanSource`, `AiPlanSourceProduct` and `AiPlanNotice`. The
  `Literal` is **closed**, unlike the Node library's open enumeration and for the same reason the
  networks are closed here: a template you have not heard of should go red where you branch on it
  rather than slip through. `AiPlan` now carries `template` — always, a plan created before
  templates existed reads `standard` — and `source`.
- **Errors 2111 to 2117 arrive as `AiPlanError`**, with nothing registered to make them: they fall
  in the 2100-2199 range on their own, and there is now a test that says so rather than assuming it.
  They come back from `create()`, which is the part that surprises: **the source is validated when
  the plan is created, not when it is generated.** The article is downloaded, the catalogue is read
  live and the product pictures are copied inside that call, so a source that does not work fails
  while your user is still in front of it. What gets stored is a snapshot — a `retry` three days
  later does not depend on the article still being online or the product still being in the
  catalogue.

### Changed

- `ai_plans.regenerate` documents that **`"image"` depends on the plan's template**, not only on
  whether the plan allowed images. The template that did not generate the picture cannot regenerate
  it: read `regenerate["image"]` from the catalogue before you draw that button, because on
  `from_images` it charges 70 credits to replace the user's own photo with an invented one.
- `ai_plans.get` documents **`warnings`**, which is a notice on a plan that generated **fine** and
  not an error of the response — the place nobody looks. Today it carries one: **2117**, part of the
  source did not fit in the plan week. A plan is weekly and the source does not extend it, so twelve
  photos with six slots left publish six; `data` brings `{"source_items": ..., "capacity": ...}`,
  and the slots are your publish days times your accounts, so it can be said before creating the
  plan rather than after charging for it.
- Two traps are now written on the types that carry them, because neither has an error code and both
  fail silently. **`source["text"]` wins over `source["url"]`** when both arrive — pasting the
  article is what a user does when the download did not work, so re-downloading to ignore what they
  wrote would take away their only way out. And **`event_date` is a calendar day, `YYYY-MM-DD`**,
  never an ISO instant: it is read in the plan's timezone, and `2026-09-15T00:00:00Z` is the 14th in
  the afternoon in New York — a whole day off in a countdown, for half of America.
- `AiPlanSourceProduct["price"]` says why the price is **never converted**: it comes exactly as the
  network returned it, the same field is a number elsewhere in Meta's API, and dividing by 100 "just
  in case" is precisely how a 10 EUR product gets advertised at 0,10 EUR.
- The route census is **113 of 113**. The new one is `GET /planner_templates`.

## [0.2.0] - 2026-08-30

Telegram, the eleventh network, reaches the package. No endpoint was added and no signature moved:
what changes is what the types know — and unlike in the Node library, where an open enumeration
absorbs an unknown network in silence, here the closed `Literal`s go red until somebody looks. Which
is the point of them.

Upgrading from `0.1.0` needs no changes, and `MIGRATION.md` gains no entry.

### Added

- **A third authorization shape: `TelegramBotAuthorization`, with its predicate
  `is_telegram_bot_authorization`.** This is the part that is genuinely new contract rather than one
  more name in a list. Telegram is the one entry that carries a `link` and still is not somewhere to
  redirect: it opens a private chat with the PlanVortex bot, with no OAuth behind it — no consent
  screen, no `code`, no `redirect_uri` — and the account is born minutes later, when the person
  drops that bot into their channel. It is announced over the WebSocket and the `new_account`
  webhook, never as the answer to a call of yours, and `accounts.connect` cannot finish it: for
  `telegram` that endpoint always answers 700. The block carries `bot_username` (the bot's `@name`,
  without the at sign) and `add_to_group_link`, the second step, which turns comments on by adding
  the bot to the channel's linked discussion group. **Branch on `authorization["type"]`, never on
  whether `link` is empty** — that test was already wrong for WhatsApp and it is worse here, because
  a filled-in `link` makes it look like it worked.
- **`"telegram"` in `PublishableNetwork`** — the one hand-written union in `_shapes.py` — and
  therefore in `PUBLISHABLE_NETWORKS`, `COMMENT_NETWORKS` and `SOCIAL_NETWORKS`, which derive from
  their `Literal` and needed no edit. It is deliberately **not** in `CONTACT_CHANNELS`: Telegram has
  no direct messages, and putting it there would promise a chat inbox that does not exist. That the
  contact channels are now a proper subset of the networks, rather than all of them plus `email`, is
  written down in the test that used to assert the equality.
- **`PublicationStats.reactions` and `reactions_by_emoji`**, which are Telegram's only publication
  metric — and neither of them is asked for. `reactions` is the COMPLETE STATE and not an increment,
  so it goes down when somebody takes theirs back.
- **`Publication.extra_data`**, for what one network has to remember about one publication and that
  has no common field. Today only `telegram_message_ids` writes there: on Telegram an album is one
  publication that is several messages, `external_identifier` holds the first and the rest live
  here, because deleting the album means deleting all of them.

### Changed

- The network-counting prose, which had quietly stopped being true and that no test watches:
  `accounts.connect_links`, `SocialAuthorizationMethod`, `ConnectLink`, `PublishableNetwork` and
  `is_publishable_network` all said "nine of the ten" or "one of ten and one of nine".
- Two warnings about this network are now on the methods that would otherwise surprise you, because
  neither has an error code to announce it. **The comment inbox starts the day the channel was
  connected** — the Bot API cannot read the past, so `comments.list` has nothing earlier and never
  will, and `comments.thread`, which is a live read on every other network, is not live here at all.
  And **there are no impressions and no reach**: engagement is computed over followers, the only
  audience figure the Bot API publishes being the channel's member count.
- `catalog.social_limits` explains Telegram's **two numbers for the same field** — 4.096 characters
  while the publication is text only and 1.024 the moment it carries an image or a video, because
  then the text is a media caption. The counter switches when the file is attached, not when publish
  is pressed.
- `publications.remove` documents Telegram's **48-hour window** (error 966, with `published_date`
  and `max_hours` in `data`), which is a button to grey out rather than to offer and fail.
- `examples/connect.py` grows the third branch, and its `else` — the one that skips an authorization
  method this version does not know — is no longer hypothetical: `telegram_bot` was exactly that.

### Fixed

- The synchronous twin of `products.get` had been left behind by the previous release: its docstring
  still said the Node library documented that endpoint as broken. Regenerating `resources_sync`
  brings it back in line.

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
