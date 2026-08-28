"""Official Python client for the PlanVortex API.

Two clients, the same surface, and three differences between them and no more: ``PlanVortex`` and
``AsyncPlanVortex``, ``iterate`` and ``aiterate``, and an ``await``. The synchronous one is
GENERATED from the asynchronous one, so they cannot drift apart.

    from planvortex import PlanVortex

    pv = PlanVortex()                    # PLANVORTEX_CLIENT_ID / PLANVORTEX_CLIENT_SECRET
    upload = pv.uploads.create(org_id, "./hogaza.jpg")
    publication = pv.publications.create(org_id, account_id, {
        "social_network": "instagram",
        "text": "Nuevo horno, nuevas hogazas",
        "files": [upload["_id"]],
        "publish_date": datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
    })

**A publication that could not be built is NOT an exception**: it comes back saved, in state
``withErrors``, with the reason in ``publication_errors``. The content is validated against the
social network, and that is not a failure of your request. Look at ``state``.

Listing gives a page, and there is a chaining iterator for when you want them all:

    page = pv.accounts.list(org_id, limit=50)
    page.data, page.total

    for publication in pv.publications.iterate(org_id, state=["ready"]):
        ...

**The error hierarchy** is what you write ``except`` clauses against:

    from planvortex import PlanVortexError, PlanLimitError

    try:
        ...
    except PlanLimitError as error:      # codes 1300-1307 and 1400-1408
        ...                              # not fixed by retrying: fixed by changing plan
    except PlanVortexError as error:
        error.code, error.family, error.message, error.data, error.status

**Classify by ``code``, never by the HTTP status.** Every domain error in this API travels with a
400 — an expired token, a disconnected account, an exhausted quota and a text that is too long are
all four a 400. A code outside the known catalogue is not an error in this library either: it lands
on :class:`PlanVortexError` with its ``code`` and ``message`` intact, because the server's catalogue
grows every month.

**The types** live in :mod:`planvortex.types`: ``Publication``, ``Account``, ``Upload``, ``Comment``,
``Message`` and the rest of the API's shapes, generated from the same OpenAPI document PlanVortex
publishes. They are ``TypedDict``, so a resource is a plain ``dict`` and the API's own field names
survive untranslated — it is ``publication["_id"]``, not ``publication.id``.

    from planvortex import SOCIAL_NETWORKS        # the tuple, to iterate and validate at runtime
    from planvortex.types import SocialNetwork    # the Literal, for whoever wants to narrow

The value lists live at the root because they are what you check things against; the types live in
``planvortex.types`` because that is where you look for a name. **The lists grow** — the networks
have gone from six to ten in two years — so a value you do not recognise is a value this release
had not heard of, never an error.

**The webhooks live apart**, in :mod:`planvortex.webhooks`, because whoever receives a delivery is
almost never the process that publishes. Two things about them, and both are load-bearing: the body
is an **array** of changes, and the signature is computed over the **raw** bytes — a body re-encoded
by ``json.dumps`` never matches.

    from planvortex.webhooks import handle_webhook_request, is_comment_change

**This is a server-side package.** The ``client_credentials`` grant needs the ``client_secret``, and
a secret inside a front-end bundle is the whole account given away. To connect an account from a
browser there is the temporal token: ``organizations.create_connect_token`` and
``pv.as_temporal_token(...)``.

See https://github.com/taliasoftworks/PlanVortexPython
"""

from planvortex._client import AsyncPlanVortex
from planvortex._client_sync import PlanVortex
from planvortex._core.errors import (
    NO_ERROR_CODE,
    PLANVORTEX_ERROR_RANGES,
    TOKEN_ERROR_CODES,
    AccountError,
    AiPlanError,
    AuthError,
    ContactError,
    ErrorRange,
    FileError,
    IntegrationError,
    MessagingError,
    OrganizationError,
    PlanLimitError,
    PlanVortexAuthenticationError,
    PlanVortexConfigError,
    PlanVortexConnectionError,
    PlanVortexError,
    ProductError,
    PublicationError,
    UserError,
    is_token_error,
)
from planvortex._core.pagination import DEFAULT_PAGE_SIZE, MAX_PAGES, Page
from planvortex._core.transport import (
    DEFAULT_TIMEOUT_SECONDS,
    HttpHooks,
    HttpRequest,
    HttpResponse,
    RequestInfo,
    ResponseInfo,
    RetryConfig,
    RetryInfo,
)
from planvortex._version import PLANVORTEX_API_URL, VERSION
from planvortex.types import (
    AI_PLAN_STATES,
    COMMENT_NETWORKS,
    CONTACT_CHANNELS,
    INTEGRATION_PROVIDERS,
    MESSAGE_TYPES,
    PUBLICATION_STATES,
    PUBLICATION_TYPES,
    PUBLISHABLE_NETWORKS,
    SOCIAL_NETWORKS,
)

__version__ = VERSION

__all__ = [
    "AI_PLAN_STATES",
    "COMMENT_NETWORKS",
    "CONTACT_CHANNELS",
    "DEFAULT_PAGE_SIZE",
    "DEFAULT_TIMEOUT_SECONDS",
    "INTEGRATION_PROVIDERS",
    "MAX_PAGES",
    "MESSAGE_TYPES",
    "NO_ERROR_CODE",
    "PLANVORTEX_API_URL",
    "PLANVORTEX_ERROR_RANGES",
    "PUBLICATION_STATES",
    "PUBLICATION_TYPES",
    "PUBLISHABLE_NETWORKS",
    "SOCIAL_NETWORKS",
    "TOKEN_ERROR_CODES",
    "VERSION",
    "AccountError",
    "AiPlanError",
    "AsyncPlanVortex",
    "AuthError",
    "ContactError",
    "ErrorRange",
    "FileError",
    "HttpHooks",
    "HttpRequest",
    "HttpResponse",
    "IntegrationError",
    "MessagingError",
    "OrganizationError",
    "Page",
    "PlanLimitError",
    "PlanVortex",
    "PlanVortexAuthenticationError",
    "PlanVortexConfigError",
    "PlanVortexConnectionError",
    "PlanVortexError",
    "ProductError",
    "PublicationError",
    "RequestInfo",
    "ResponseInfo",
    "RetryConfig",
    "RetryInfo",
    "UserError",
    "__version__",
    "is_token_error",
]
