# planvortex

[![PyPI](https://img.shields.io/pypi/v/planvortex.svg?color=2036d8&label=pypi)](https://pypi.org/project/planvortex/)
[![python](https://img.shields.io/pypi/pyversions/planvortex.svg?color=2036d8)](https://pypi.org/project/planvortex/)
[![CI](https://github.com/taliasoftworks/PlanVortexPython/actions/workflows/ci.yml/badge.svg)](https://github.com/taliasoftworks/PlanVortexPython/actions/workflows/ci.yml)
[![license](https://img.shields.io/pypi/l/planvortex.svg?color=2036d8)](./LICENSE)

The official Python client for the [PlanVortex](https://planvortex.com) API — connect social
accounts, schedule and publish posts, read comments and messages, and pull stats, from Python.

```bash
pip install planvortex
```

- **Synchronous and asynchronous**, same surface: `PlanVortex` and `AsyncPlanVortex`.
- **Typed**, from the same OpenAPI specification the API publishes at
  <https://planvortex.com/openapi.json>. Returned shapes are `TypedDict`, so `_id` stays `_id`.
- **One runtime dependency**, `httpx2` — a different package from `httpx` classic, so it will not
  collide with whatever your project already uses.
- **Server-side.** The `client_credentials` flow needs your `client_secret`, which must never reach
  a browser. Connecting an account from one is what the [temporal connect token](#connecting-an-account)
  is for.
- Python 3.10 and newer.

**Reference:** <https://taliasoftworks.github.io/PlanVortexPython/> · **Guides:**
[planvortex.com/en/developers](https://planvortex.com/en/developers)

## Authentication

Your credentials are a **client app**'s: you create one in the PlanVortex panel and it gives you a
`client_id` and a `client_secret`. They are read from the environment, so nothing is hardcoded:

```bash
export PLANVORTEX_CLIENT_ID=...
export PLANVORTEX_CLIENT_SECRET=...
# Only if you are not talking to production:
export PLANVORTEX_BASE_URL=http://localhost:3000/v1.0.0
```

```python
from planvortex import PlanVortex

pv = PlanVortex()  # from the environment
pv = PlanVortex(client_id="...", client_secret="...")  # or explicitly
```

The token is fetched on the first call, cached, and renewed before it expires — you never touch
`/oauth/token`. Use the client as a context manager (`with PlanVortex() as pv:`) so the connection
pool closes, and **keep one instance**: a new one per request throws away the cache and the pool.

An app sees **its own client** and that client's organizations, and nothing else.

## Publishing

```python
from datetime import datetime, timedelta, timezone

from planvortex import PlanVortex

pv = PlanVortex()

upload = pv.uploads.create(org_id, "./sourdough.jpg")
publication = pv.publications.create(
    org_id,
    account_id,
    {
        "social_network": "instagram",
        "text": "New oven, new loaves",
        "files": [upload["_id"]],
        "publish_date": datetime.now(timezone.utc) + timedelta(hours=1),
    },
)

# A publication that could not be built is NOT an exception: it comes back saved, in `withErrors`,
# with the reason inside. The content is validated against the network, and that is not a failure
# of your request.
if publication["state"] == "withErrors":
    for failure in publication["publication_errors"]:
        print(failure["code"], failure["message"])
```

`publish_date` takes a `datetime` as well as an ISO-8601 string, and **it has to carry a timezone**:
a naive one raises rather than being guessed at, because assuming UTC publishes at the wrong time
for whoever is in Madrid and assuming the process's zone does it for whoever is in Docker. With no
`publish_date` at all it goes out in that same request, and the answer already says whether it did.

A file can be a path, an open file, `bytes`, or a `(name, bytes)` pair. Per-network limits —
characters, images, video length, file size — come from `pv.catalog.social_limits()`, which is the
server's own copy: whoever enforces a limit is who gets to announce it.

Listing gives you a page, and there is a chaining iterator for when you want them all:

```python
page = pv.accounts.list(org_id, limit=50)
page.data, page.total

for publication in pv.publications.iterate(org_id, state=["ready"]):
    ...
```

The same code in async changes three things and no more — the class, an `await`, and `aiterate`:

```python
from planvortex import AsyncPlanVortex

async with AsyncPlanVortex() as pv:
    page = await pv.accounts.list(org_id, limit=50)
    async for publication in pv.publications.aiterate(org_id, state=["ready"]):
        ...
```

## Connecting an account

Connecting is the one flow the library **cannot finish on its own**: it ends with a person pressing
"allow" on Instagram's page. What the library does is hand you a URL to send them to.

```python
connection = pv.organizations.create_connect_token(org_id)
# connection["url"] is where the person goes. Never send them your client_secret.

person = pv.as_temporal_token(connection["token"])  # a client that can only do this
for link in person.accounts.connect_links(org_id):
    ...
```

Four things about that token, and each one bites separately: it lasts **fifteen minutes**, it is
**single-use**, it is tied to **one** organization, and it **cannot issue another one**. Saving it
for "next time" fails four different ways — issue a fresh one per connection, they are free.

And one that trips people without giving an error: branch on `link["authorization"]["type"]`, never
on the `link`. WhatsApp's is the empty string, because its sign-up is Meta's *Embedded Signup* popup
and not an OAuth redirect; walking the list redirecting to `link` sends your user to your own page.

Accounts come back **disabled** and take no plan slot until `pv.accounts.enable(...)`, and one
authorization can leave several — a Facebook user with four pages is four of them.

## Comments and messages

```python
# The comments inbox comes out of PlanVortex's database: free, fast, and a photograph of the last
# time the network was read. The thread asks the network right then, and on X that costs credits.
for comment in pv.comments.iterate(org_id, unread=True, rating=[1, 2]):
    print(comment["rating"], comment["text"])

thread = pv.comments.thread(org_id, publication_id)
thread["credits_consumed"]  # real money on X, 0 everywhere else

# Before painting a button, ask what the network allows: they are not all the same.
if (pv.comments.actions_for("linkedin") or {}).get("hide"):
    ...
```

## AI plans, and what they are generated from

A plan is a **week** of drafts written by a model: you queue it, a job generates it, and what comes
out are ordinary publications in `draft` that you edit and validate. `template` says what the
content is generated FROM, and it is the only thing that changes between one plan and another —
publish days, language, tone and images stay cross-cutting options, and each template declares which
of them it accepts.

```python
# The list, the prices and the fields of the source step. Cached, like the rest of the catalogue.
templates = pv.catalog.planner_templates()

# A week written from the customer's own photos, in the order that tells the story.
queued = pv.ai_plans.create(
    client_id,
    org_id,
    {
        "prompt": "Our autumn menu",
        "accounts": [account_id],
        "template": "from_images",
        "source": {
            "images": [
                {"id_upload": first, "description": "Dough resting on the bench"},
                {"id_upload": second, "description": "The loaf coming out of the oven"},
            ]
        },
    },
)
queued["estimate"]["images_target"]  # 0 — the pictures come from the source
```

Four things worth knowing before you build the screen:

- **The template that does not generate images does not spend image credits, and images are 94 % of
  a plan.** The same week — 7 publications with a picture on each, one account — costs 519 credits
  as `standard` and **48** as `from_images`. Say it before the plan is created, not after it is
  charged.
- **`regenerate(..., "image")` is per template**, not just per plan: the one that did not generate
  the picture cannot regenerate it. Read `regenerate["image"]` from the catalogue before you draw
  the button — on `from_images` it would charge 70 credits to replace the user's own photo with an
  invented one.
- **The source is validated when the plan is CREATED**, not when it is generated: the article is
  downloaded, the catalogue is read live and the product pictures are copied inside that call. So a
  broken source fails while your user is still there — errors 2111 to 2116, all of them
  `AiPlanError` — and what gets stored is a snapshot: a `retry` three days later does not depend on
  the article still being online.
- **A plan is weekly and the source does not extend it.** Twelve photos with six slots left publish
  six, and the plan carries warning **2117** in `ai_plan["warnings"]` — a notice on a plan that
  generated fine, not an error. The slots are your publish days times your accounts, so you can say
  it in advance.

Do not hardcode the list, the costs or the field limits: `GET /planner_templates` publishes them
because the server is what charges them.

## Errors

Errors are classified by `code`, **never by the HTTP status** — every domain error in this API
travels with a 400. Each range has its own exception class, so you can catch a family without
memorising numbers:

| Codes | Family | Exception |
|---|---|---|
| 500-546 | `auth` | `AuthError` |
| 601-612 | `user` | `UserError` |
| 700-715 | `account` | `AccountError` |
| 800-810 | `file` | `FileError` |
| 900-979 | `publication` | `PublicationError` |
| 1000-1003 | `general` | `PlanVortexError` |
| 1100-1111 | `organization` | `OrganizationError` |
| 1200-1207 | `role` | `PlanVortexError` |
| 1300-1308, 1400-1408 | `plan_limit` | `PlanLimitError` |
| 1500-1512 | `messaging` | `MessagingError` |
| 1600-1601 | `contact` | `ContactError` |
| 1900-1906 | `payment` | `PlanVortexError` |
| 2000-2099 | `product` | `ProductError` |
| 2100-2199 | `ai_plan` | `AiPlanError` |
| 2200-2299 | `integration` | `IntegrationError` |

```python
from planvortex import PlanLimitError, PlanVortexError

try:
    ...
except PlanLimitError as error:
    ...  # not fixed by retrying: fixed by changing plan
except PlanVortexError as error:
    error.code, error.family, error.message, error.data, error.status
```

The runtime list is `PLANVORTEX_ERROR_RANGES`. Two more that are not the API's answer:
`PlanVortexConnectionError` (it never got there — retried already, on the methods where retrying is
safe) and `PlanVortexConfigError` (something is wrong on this side, like a missing `client_secret`).

## Webhooks

PlanVortex `POST`s to your app when something happens: an account changed state, a message or a
comment came in, an integration stopped working. Two things trip up everybody, so they go first.

**The body is an array of changes**, not an object. And **the signature is computed over the raw
body** — if your framework already parsed the JSON and you serialise it again, the bytes are not the
same ones and the signature never matches. The line that gives you the raw body is the only line of
the recipe that changes:

```python
# Flask
import os

from flask import request

from planvortex.webhooks import handle_webhook_request, is_comment_change


@app.post("/webhooks/planvortex")
def planvortex_webhook():
    changes = handle_webhook_request(
        body=request.get_data(),  # raw! never request.json
        headers=request.headers,
        secret=os.environ["PLANVORTEX_CLIENT_SECRET"],
    )
    for change in changes:
        if is_comment_change(change):
            moderate(change.get("commentObj"))
    return "", 200
```

```python
# FastAPI
@app.post("/webhooks/planvortex")
async def planvortex_webhook(request: Request):
    changes = handle_webhook_request(
        body=await request.body(),  # raw! never the parsed model
        headers=request.headers,
        secret=os.environ["PLANVORTEX_CLIENT_SECRET"],
    )
    ...
```

```python
# Django
@csrf_exempt
def planvortex_webhook(request):
    changes = handle_webhook_request(
        body=request.body,  # raw! never request.POST
        headers=request.headers,
        secret=os.environ["PLANVORTEX_CLIENT_SECRET"],
    )
    ...
```

`handle_webhook_request` raises `WebhookSignatureError` if the signature is missing or does not
match (answer 401) and `WebhookBodyError` if the body is not what it has to be (answer 400). If you
would rather do it in two steps, `verify_webhook_signature(payload, signature, secret)` returns a
plain `True`/`False` and `parse_webhook_body(payload)` gives you the changes.

Narrow with the predicates — `is_account_state_change`, `is_message_change`, `is_comment_change`,
`is_integration_error_change` — and let anything else fall through: **the event list grows**, and a
`field` this release has never heard of is not an error.

**PlanVortex does not retry a failed delivery.** A 500 of yours loses the event, so if your work is
slow, queue it and answer — and use `pv.comments.list` / `pv.messages.list` to catch up on anything
you missed.

## The whole API, in fourteen resources

`pv.catalog` · `pv.clients` · `pv.organizations` · `pv.accounts` · `pv.uploads` · `pv.publications`
· `pv.comments` · `pv.messages` · `pv.contacts` · `pv.products` · `pv.integrations` · `pv.ai_plans`
· `pv.dashboard` · `pv.apps`

That is **113 of the 113 operations** the specification documents — everything except the 19 routes
of roles and invitations, which are out of scope. A script walks the OpenAPI bundle on every test
run and fails if a route is left without a method, so the sentence above stays true.

## Examples

Five runnable scripts, each one the whole of its path and with a test of its own:

| | |
|---|---|
| [`examples/publish.py`](https://github.com/taliasoftworks/PlanVortexPython/blob/main/examples/publish.py) | Credentials, quota, account, network limits, upload, scheduled publication. |
| [`examples/schedule.py`](https://github.com/taliasoftworks/PlanVortexPython/blob/main/examples/schedule.py) | The calendar: what is queued, moving it, and rescuing what failed. |
| [`examples/comments.py`](https://github.com/taliasoftworks/PlanVortexPython/blob/main/examples/comments.py) | The inbox, the actions matrix, the live thread, and replying. |
| [`examples/webhooks.py`](https://github.com/taliasoftworks/PlanVortexPython/blob/main/examples/webhooks.py) | A receiver with no dependencies. `--self-test` signs a delivery to itself. |
| [`examples/connect.py`](https://github.com/taliasoftworks/PlanVortexPython/blob/main/examples/connect.py) | The connection flow, and what the browser has to do. |

`comments.py` only reads unless you set `PLANVORTEX_ALLOW_REPLY=1`: replying is public, immediate,
and reaches a person.

## Links

- [Reference](https://taliasoftworks.github.io/PlanVortexPython/)
- [API documentation](https://planvortex.com/documentation)
- [Developers](https://planvortex.com/en/developers)
- [Node client](https://github.com/taliasoftworks/PlanVortexNode)
- [Contributing](https://github.com/taliasoftworks/PlanVortexPython/blob/main/CONTRIBUTING.md) · [Security](https://github.com/taliasoftworks/PlanVortexPython/blob/main/SECURITY.md) · [Changelog](https://github.com/taliasoftworks/PlanVortexPython/blob/main/CHANGELOG.md)

MIT © Talia Softworks
