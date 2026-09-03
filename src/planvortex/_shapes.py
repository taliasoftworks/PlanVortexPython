"""The shapes the specification declares INLINE, which the generator does not emit.

``datamodel-code-generator`` runs with its default scope, ``components/schemas``: a body or a
response written inline inside an operation — ``{max_retries}``, ``{url, token, expires_at}``,
``{cover_image, cover_offset}`` — has no schema of its own and therefore no generated type. There are
a dozen of them and they are all on the main path, so they are written here by hand and
``tests/test_shapes_parity.py`` walks the committed bundle to make sure each one still says what the
API says. That test is the whole point of the file: a hand-written type has no ``git diff`` guarding
it, so it gets a parity check instead, exactly like the camelCase map (§ Trampa P2) and the six
hand-written ``Literal`` of ``types.py``.

TWO THINGS ABOUT THE TOP OF THIS FILE ARE LOAD-BEARING, and neither one fails visibly (§ Trampa P13):

- **There is no ``from __future__ import annotations``**, and it is not an oversight. It would leave
  the annotations as strings, ``TypedDict`` cannot read a ``NotRequired`` that is text, and every key
  here would be reported as required at runtime while mypy carried on agreeing with the source. The
  parity test reads ``__optional_keys__``, so it is also the thing that would catch it.
- **``TypedDict`` and ``NotRequired`` come from the same place**, behind the version guard. Taking
  one from ``typing`` and the other from ``typing_extensions`` is precisely the mix that misreports
  on 3.10, and importing ``typing_extensions`` unguarded is what breaks the import on 3.13 and 3.14.
  It is the same guard the generated module carries, and for the same reasons.
"""

import sys
from datetime import datetime
from typing import Any, Literal, TypeAlias

from planvortex._generated.models import (
    Account,
    ClientsClient,
    DashboardPublicationsSummary,
    Organization,
    PlanData,
    PlanUseData,
    Publication,
    Upload,
)
from planvortex._generated.models import (
    CommentsComment as Comment,
)
from planvortex._generated.models import (
    DashboardDashboardRange as DashboardRange,
)
from planvortex._generated.models import (
    DashboardMetricRow as MetricRow,
)
from planvortex._generated.models import (
    DashboardTopPublication as TopPublication,
)
from planvortex._generated.models import (
    IntegrationsRssConfig as RssConfig,
)

if sys.version_info >= (3, 11):
    from typing import NotRequired, TypedDict
else:  # pragma: no cover - la rama la elige el interprete, no un test
    from typing_extensions import NotRequired, TypedDict


# =================================================================================================
# Catalogo
# =================================================================================================


class PublicationLimits(TypedDict):
    """The publication limits that do not depend on the network. Today, just the retry cap."""

    max_retries: int
    """Manual retries a failed publication accepts in total. Read it; do not hardcode a 3."""


# =================================================================================================
# Cliente y organizacion
# =================================================================================================


class ClientUpdate(TypedDict):
    """What a client lets you change. Anything else in the body is ignored, not rejected."""

    name: NotRequired[str]
    client_type: NotRequired[str]
    """``personal``, ``professional``, ``enterprise`` or ``agency``."""


class ClientWithOrganizations(ClientsClient):
    """A client with its ROOT organizations inside, as the shortcut listing returns them.

    It exists to save the ``1 + N`` requests that painting an organization picker would otherwise
    cost. ``total`` here is that client's organization count, not the number of clients.
    """

    organizations: list[Organization]
    total: int


class ConnectToken(TypedDict):
    """The temporal token a PERSON connects a social account with, in its two usable forms.

    ``url`` is the hosted path — send the user there and PlanVortex handles the network choice, the
    OAuth and the screen where they pick which accounts to keep. ``token`` is the credential on its
    own, for ``pv.as_temporal_token(...)`` when the interface is yours. **Do not parse the token out
    of the url**: they are both given so that neither has to be taken apart.

    It lasts fifteen minutes, works for ONE organization, connects ONE account and cannot issue
    another token.
    """

    url: str
    token: str
    expires_at: str
    """ISO-8601. Fifteen minutes after it was issued."""


class OrganizationUse(TypedDict):
    """What an organization spends and what it has already handed down to its children.

    Both are missing when the server was not asked for them, which is why they are optional here:
    the two figures come from an aggregation over every organization underneath, so they only travel
    with ``get_use=True``.
    """

    actual_use: NotRequired[PlanUseData]
    actual_asigned: NotRequired[PlanData]


# =================================================================================================
# Cuentas
# =================================================================================================


class AccountUpdate(TypedDict):
    """The only thing a connected account lets you change: the name it is shown under.

    It renames nothing on the social network.
    """

    name: NotRequired[str]


class RedirectAuthorization(TypedDict):
    """Send the person to the entry's ``link``. Ten of the twelve networks.

    One of the THREE halves of the ``authorization`` block of a connection link. The generated type
    is a single flat ``TypedDict`` with every field ``NotRequired``, because that is the only way
    OpenAPI can say "a union" here; these three say which fields go with which ``type``, and
    ``types.is_redirect_authorization`` / ``types.is_meta_embedded_signup`` /
    ``types.is_telegram_bot_authorization`` are what narrow to them.
    """

    type: Literal["redirect"]


class MetaEmbeddedSignupAuthorization(TypedDict):
    """Open Meta's *Embedded Signup* popup. **WhatsApp, and nothing else.**

    WhatsApp is not authorized with a URL: its sign-up is a popup your own page raises with the
    Facebook JavaScript SDK, which returns the session data — ``waba_id``, ``phone_number_id`` —
    over ``postMessage`` and in no query string. Its ``link`` is therefore the empty string, and
    walking the list redirecting to ``link`` sends your user to your own page.

    **The five fields are required here and optional in the generated type**, which is the point of
    splitting it: reading ``authorization["app_id"]`` off the flat type passes ``mypy --strict``
    and raises ``KeyError`` against a ``redirect`` entry.

    The library does not open the popup — that is browser work — so what it does is hand you every
    parameter it takes, which until now lived hardcoded in PlanVortex's own front end.
    """

    type: Literal["meta_embedded_signup"]
    app_id: str
    """``FB.init({appId})``. The same Meta app whose secret exchanges the code afterwards."""
    config_id: str
    """``FB.login(cb, {config_id})`` — the Embedded Signup configuration."""
    graph_version: str
    """``FB.init({version})``. It is the SDK's version, NOT the one the server calls Graph with."""
    feature_type: str
    """``extras.featureType``."""
    session_info_version: str
    """``extras.sessionInfoVersion``."""


class TelegramBotAuthorization(TypedDict):
    """Open a chat with the PlanVortex bot. **Telegram, and nothing else.**

    The third half, and the one that is genuinely new contract rather than one more network in a
    list. Telegram HAS a link and still is not a ``redirect``: there is no OAuth behind it — no
    consent screen, no ``code``, no account token and no ``redirect_uri``. That ``link`` opens a
    private chat with the bot, and nobody comes back from it. The account is created minutes later,
    when the person adds that bot to their channel, and it is announced over the WebSocket and the
    ``new_account`` webhook — never as the answer to a call of yours. Which is also why
    ``accounts.connect`` cannot finish it: for ``telegram`` that endpoint always answers 700.

    So: open ``link`` in ANOTHER TAB and keep listening. Redirect to it and there is nobody left to
    tell — no error, nothing broken to look at, which is exactly how WhatsApp's empty ``link`` cost
    the API a year.

    **The two fields are required here and optional in the generated type**, which is the whole
    point of splitting it, and the same reason the Meta half exists.
    """

    type: Literal["telegram_bot"]
    bot_username: str
    """The bot's ``@name``, **without the at sign**. It is what the person will see in Telegram and
    it changes with the deployment, so read it from here instead of writing it down."""
    add_to_group_link: str
    """The SECOND step, which does not follow from the first: ``link`` opens the list of channels
    and this one opens the list of groups. It adds the bot to the channel's linked discussion group,
    which is what turns comments on — a channel with no discussion group has no comment inbox at all
    (error 965). Optional for the user: publishing and statistics work without it."""


class AccountConnectResponse(TypedDict):
    """The RAW answer of the connection callback, which is not what the library returns.

    **The endpoint answers 200 even when it failed**, with the error inside the body, because the
    browser lands here from a redirect and a bare 400 would be a broken page. The library undoes
    that patch — it raises the error that corresponds to ``errorCode`` — so this shape is internal
    and what comes out is :class:`ConnectResult`.
    """

    accounts: NotRequired[list[Account]]
    # Los dos en camelCase porque es como los manda el servidor. `ruff` no exige snake_case en
    # un TypedDict, que es justamente por lo que estas clases tienen que venir de `typing`.
    errorCode: NotRequired[str]
    errorMsg: NotRequired[str]
    redirect_uri: NotRequired[str]


class ConnectResult(TypedDict):
    """What completing a connection leaves behind: accounts, and where to send the user next.

    **The accounts come back DISABLED**: they take no plan slot and publish nothing until
    ``accounts.enable`` is called on each. One authorization can leave several — a Facebook user
    with four pages is four of them — which is why there is a choosing step in the middle.
    """

    accounts: list[Account]
    redirect_uri: NotRequired[str]
    """Only when the call was made with a temporal token that carried one."""


class EnableResult(TypedDict):
    """What enabling an account leaves behind, which is almost nothing.

    ``success: true`` is not passed through: a failure arrives as an exception, so the only thing
    worth keeping is whether the temporal token carried somewhere to send the user afterwards.
    """

    redirect_uri: NotRequired[str]


# =================================================================================================
# Publicaciones
# =================================================================================================

PublishableNetwork: TypeAlias = Literal[
    "facebook",
    "instagram",
    "threads",
    "twitter",
    "linkedin",
    "tiktok",
    "whatsapp",
    "youtube",
    "bluesky",
    "discord",
    "telegram",
]
"""A network that accepts publications: the eleven of the twelve that have a feed.

``google_business`` is the one missing, and it is not an oversight: a local listing receives
reviews, not posts. Sending it raises error 702. It is a **narrower** type than
``types.SocialNetwork`` and that is the whole point — an account's ``social_network`` is one of
twelve and this is one of eleven, so handing one straight to the other is a type error even when a
``capability="publications"`` filter has already made it impossible at runtime.
``types.is_publishable_network`` is what bridges it.

**The list grows**, like every other one here; what is authoritative at any moment is
``GET /allowed_social_publications``.
"""


class PublicationInput(TypedDict):
    """What you send to create or update a publication.

    THIS ONE IS WRITTEN BY HAND ON TOP OF THE GENERATED TYPE, which is the exception in this file
    and needs its reason stated. The generated ``PublicationsPublicationInput`` says
    ``publish_date: NotRequired[str]``, and the library accepts a ``datetime`` there — ``_serialize``
    turns it into ISO-8601 with its offset, the docstring of ``publications.create`` shows it that
    way, and ``publications.list`` already takes ``datetime | str`` in the query. OpenAPI has one
    ``string`` with ``format: date-time`` and no way to say "or the language's own date", so the
    widening cannot come out of the generator. The keys and what is required still come from the
    spec, and ``tests/test_shapes_parity.py`` checks it in both directions; what this class adds is
    the ``datetime``, and nothing else.
    """

    social_network: NotRequired[PublishableNetwork]
    """Network the publication targets. **Required when creating**: error 702 if it is missing or
    is not one of the ten. It has to match the network of the account in the path."""
    text: NotRequired[str]
    """Body text. Either this or one entry in ``files``; with neither, the publication is still
    created but lands in ``withErrors`` with code 915. On YouTube this is the video
    **description**."""
    title: NotRequired[str]
    """Only some networks use it: optional on LinkedIn, **required on YouTube** and 100 characters
    at most there (code 944)."""
    files: NotRequired[list[str]]
    """Identifiers of uploads already created. Here they ARE identifiers; what comes back is whole
    :data:`Upload` objects."""
    publish_date: NotRequired[datetime | str]
    """When it goes out. Omitted, it goes out in this same request.

    A ``datetime`` **has to carry a timezone**: a naive one raises instead of being guessed at,
    because assuming UTC publishes at the wrong time for whoever is in Madrid and assuming the
    process's zone does it for whoever is in Docker. A string travels untouched, so it is on you to
    make it ISO-8601 — an invalid date is error 938.
    """
    name: NotRequired[str]
    """Internal name, for grouping. Never shown on the network."""
    publication_type: NotRequired[Literal["profile", "page", "group", "reels", "stories"]]
    """Defaults to ``profile``. Not every network takes every type and a bad pair is error 923."""
    state: NotRequired[Literal["ready", "withErrors", "sended", "draft", "publishing"]]
    """Send ``draft`` to store it without publishing. Omitted, it is resolved automatically."""


# =================================================================================================
# Ficheros
# =================================================================================================


class UploadUpdate(TypedDict):
    """The cover settings of a video, which is all an upload lets you change."""

    cover_image: NotRequired[str]
    """Identifier of ANOTHER upload, which has to be an image. Replacing a cover deletes the old
    file. Error 810 if it does not exist or is not an image."""
    cover_offset: NotRequired[int]
    """Point of the video, in milliseconds, used as the cover frame.

    CAREFUL: **it is written unconditionally**, so omitting it clears the stored value. To change
    only ``cover_image``, send back the ``cover_offset`` the upload already had.
    """


class ImportFile(TypedDict):
    """One file of an integration, as the provider's picker described it."""

    external_id: str
    """The file's identifier at the provider — the Drive file id."""
    name: NotRequired[str]
    """What the picker showed. Used for the visible name and to say which file failed."""
    mime_type: NotRequired[str]
    """What the picker declared. Used to reject early; the real type of the body wins."""


class ImportFileError(TypedDict):
    """One file that did not get in, and why. The code is a PlanVortex code, never an HTTP status.

    ``800``/``801`` invalid format · ``802`` image over 5 MB · ``803`` video over 200 MB · ``804``
    the organization's storage quota is exhausted · ``805`` neither an image nor a video · ``2204``
    the provider has no bytes to give, which is what a native Google document is.
    """

    external_id: NotRequired[str]
    name: NotRequired[str]
    code: int
    message: str
    data: NotRequired[dict[str, Any]]


class ImportResult(TypedDict):
    """The result of an import, which is PARTIAL on purpose.

    **Look at ``errors`` even when ``uploads`` brought something**: of six files chosen, four can get
    in. It is the only way to say which of them failed and why.
    """

    uploads: list[Upload]
    errors: list[ImportFileError]


# =================================================================================================
# Comentarios
# =================================================================================================


class CommentUpdate(TypedDict):
    """What a comment lets you change. Both fields can travel in the same call.

    They are not the same kind of thing, though: ``read`` is ours and never touches the network,
    while ``hidden`` goes out to it and is not allowed everywhere.
    """

    read: NotRequired[bool]
    """Our own state. It cannot fail because of what the network permits."""
    hidden: NotRequired[bool]
    """Hide or show **on the network**. LinkedIn has no such thing and answers 946; check
    ``comments.actions()`` before offering the button."""


class CommentReplyResult(TypedDict):
    """What replying leaves behind: the comment answered, our reply, and what X charged for it."""

    comment: Comment
    """The comment that was answered, now ``replied: true`` and ``read: true``."""
    reply: Comment
    """Our reply as it was stored. **It can arrive without ``_id``**: the network publishes first and
    the row is written afterwards, and that write is deliberately not allowed to fail the request.
    What always identifies it is ``comment["our_reply_external_id"]``."""
    credits_consumed: int
    """X credits this reply spent — 15, or 200 with a link in the text. ``0`` everywhere else."""


# =================================================================================================
# Integraciones
# =================================================================================================


class IntegrationUpdate(TypedDict):
    """What an integration lets you change once it is connected. Credentials are not in the list."""

    name: NotRequired[str]
    enabled: NotRequired[bool]
    """``False`` leaves it connected but out of play: the job skips it and **it stops taking up
    quota**. It is how you pause a feed instead of deleting it."""
    config: NotRequired[RssConfig]
    """RSS only. On Google Drive the configuration is the picker's and there is nothing to write."""


class IntegrationPickerConfig(TypedDict):
    """What the browser needs to open the provider's own file picker. **Google Drive only.**

    It carries a LIVE, short-lived ``access_token``: do not store it, do not log it, and do not send
    it anywhere that is not the Picker. Ask for it right before opening the picker.
    """

    access_token: str
    expires_in: str
    """Seconds left, as a string. It is what the provider answered, not a number of ours."""
    developer_key: str
    app_id: str
    """The Google Cloud project's NUMBER, not its text identifier: with the ``drive.file`` scope the
    permission over the chosen file is granted to the project that chose it, so it has to be the same
    one as the OAuth client."""


# =================================================================================================
# Planes de IA
# =================================================================================================


class AiPlanRegenerateResult(TypedDict):
    """What regenerating one publication of a plan leaves behind."""

    publication: Publication
    credits_spent: int
    """What the PLAN has spent in total, not what this call cost."""


# =================================================================================================
# Dashboard
# =================================================================================================


class MetricsResult(TypedDict):
    """The aggregated account metrics of a range, and the axis they were grouped on."""

    range: DashboardRange
    group_by: str
    """``day``, ``network``, ``account`` or ``total`` — the one that was applied, which is ``day``
    when nothing was asked for."""
    stats: list[MetricRow]


class TopPublicationsResult(TypedDict):
    """The ranking of a range by one metric, and the range it was computed over."""

    range: DashboardRange
    metric: str
    """The metric it is ordered by. ``engagement`` when nothing was asked for."""
    publications: list[TopPublication]


class PublicationsSummaryResult(DashboardPublicationsSummary):
    """The publication counts of a range, with the range itself attached.

    It is an ``allOf`` in the spec — the same counts block the dashboard carries, plus ``range`` —
    so it is written as inheritance for the same reason :class:`ClientWithOrganizations` is: what
    the generator already checks is not rewritten by hand here.
    """

    range: DashboardRange


__all__ = [
    "AccountConnectResponse",
    "AccountUpdate",
    "AiPlanRegenerateResult",
    "ClientUpdate",
    "ClientWithOrganizations",
    "CommentReplyResult",
    "CommentUpdate",
    "ConnectResult",
    "ConnectToken",
    "EnableResult",
    "ImportFile",
    "ImportFileError",
    "ImportResult",
    "IntegrationPickerConfig",
    "IntegrationUpdate",
    "MetaEmbeddedSignupAuthorization",
    "MetricsResult",
    "OrganizationUse",
    "PublicationInput",
    "PublicationLimits",
    "PublicationsSummaryResult",
    "PublishableNetwork",
    "RedirectAuthorization",
    "TelegramBotAuthorization",
    "TopPublicationsResult",
    "UploadUpdate",
]
