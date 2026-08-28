"""The PUBLIC types of the package: the names you talk about the API with.

Underneath every one of them is ``planvortex._generated.models``, which comes out of the public
OpenAPI document and is never edited by hand. This file is the thin layer on top, and it does three
things a generator cannot:

1. **It gives them readable names.** In the generated module a schema is called
   ``PublicationsPublicationInput``, because the 16 documents of the specification are merged into
   one and a client's ``Plan`` is not an organization's ``Plan``. Here it is ``PublicationInput``.
   The ones describing *the same thing* across sections live in ``common.json`` and keep their bare
   name — ``Publication``, ``Account``, ``Upload``, ``Message``, ``Contact`` — which is what stops
   one server object from becoming two Python types.
2. **It publishes the value lists at runtime.** ``SOCIAL_NETWORKS`` is a real tuple you can iterate
   over and validate against, derived from the same ``Literal`` the type checker reads, so the two
   can never drift apart.
3. **It says what the type cannot say by itself**, such as that ``public_path`` expires.

**Everything here is a ``TypedDict``, so a resource is a plain ``dict``**: it is
``publication["_id"]`` and never ``publication.id``. That is deliberate, and it is the whole reason
this library does not use models — the primary key of every PlanVortex resource is called ``_id``,
and pydantic cannot have a field whose name starts with an underscore. The names of the API are not
translated either: ``_id`` is ``_id`` and ``id_organization`` is ``id_organization``, exactly as the
documentation you have open next to this says.

A NOTE ON THE ``Literal`` TYPES. ``SocialNetwork``, ``PublicationState`` and their friends are
closed unions, which is not what the Node library does — TypeScript can write an *open* enum
(``T | (string & {})``) and Python cannot: ``Literal[...] | str`` collapses to ``str`` and loses the
autocompletion, which is the worst of both worlds. So the closed one is what is published, and the
rule that follows from it is that **the arguments this library accepts are typed ``str``**, so a
network released after this version still works; only the fields it *returns* are narrowed. If you
compare one against a value this release does not know, the type checker will complain and the
runtime will not — the list grows, so ask ``pv.catalog.social_networks()`` instead of hardcoding it.
"""

from __future__ import annotations

from typing import Literal, TypeAlias, TypeGuard, cast, get_args

from planvortex import _shapes
from planvortex._generated import models as _models

# =================================================================================================
# Enumeraciones abiertas: el `Literal` para el comprobador y la tupla para el runtime
# =================================================================================================

SocialNetwork: TypeAlias = _models.SocialNetwork
"""A supported social network. The runtime list is :data:`SOCIAL_NETWORKS`."""

PublishableNetwork: TypeAlias = _shapes.PublishableNetwork
"""A network that accepts publications: nine of the ten. The runtime list is
:data:`PUBLISHABLE_NETWORKS`, and :func:`is_publishable_network` is what narrows a
:data:`SocialNetwork` down to it."""

CommentNetwork: TypeAlias = _models.CommentsCommentNetworkName
"""A network whose comments PlanVortex reads. The runtime list is :data:`COMMENT_NETWORKS`."""

ContactChannel: TypeAlias = _models.ContactChannel
"""Where a contact can be reached: any network with messaging, or ``email``."""

MessageType: TypeAlias = _models.MessageType
"""What kind of message it is. ``simple_message`` and ``file_message`` work on every network."""

IntegrationProviderName: TypeAlias = _models.IntegrationsIntegrationProviderName
"""A supported integration provider."""

MetricName: TypeAlias = _models.DashboardMetricName
"""A metric of the COMMON vocabulary — the one that can be added up across networks.

Closed on purpose, unlike :data:`SOCIAL_NETWORKS`: this is not a list that grows with every new
network, it is the translation that makes them comparable. A name that is not here is a network's
raw name and cannot be added to anything.
"""

# Estas cinco NO tienen un esquema propio en el spec: son enumeraciones declaradas en linea dentro
# de `Publication`, de `Upload` y de `AiPlan`, asi que el generador las emite como un `Literal`
# anonimo dentro del campo y no hay nada que importar. Se escriben aqui, y `tests/test_types.py`
# las compara contra el bundle: es la unica parte de este fichero que puede quedarse atras sola.

PublicationState: TypeAlias = Literal["ready", "withErrors", "sended", "draft", "publishing"]
"""The state of a publication.

``draft`` is never sent; ``ready`` is scheduled; ``publishing`` is in the network's hands right now;
``sended`` went out; ``withErrors`` failed and carries the reason in ``publication_errors``.
"""

PublicationType: TypeAlias = Literal["profile", "page", "group", "reels", "stories", "message"]
"""Where inside the network a publication goes: profile, page, group, reel, story or message."""

FileType: TypeAlias = Literal["video", "image"]
"""``image`` or ``video``."""

FileFormat: TypeAlias = Literal["mp4", "jpeg", "gif", "png", "jpg"]
"""The format of the STORED bytes.

``heic``/``heif`` get in through the door — that is what an iPhone produces — but never come back
out: they are converted to JPEG while being ingested.
"""

EngagementBase: TypeAlias = Literal["reach", "impressions", "followers"]
"""What a publication's engagement rate is divided by.

Not every network reports reach, so it falls back: ``reach``, else ``impressions``, else
``followers`` (which is all there is on Bluesky and on Discord). **Two rows with different bases are
not comparable**: if you put them in the same table, say which one it is.
"""

AiPlanState: TypeAlias = Literal["pending", "generating", "generated", "validated", "failed", "cancelled"]
"""The state of an AI plan. ``pending`` and ``generating`` are the two you poll on."""

# --- las tuplas de runtime -----------------------------------------------------------------------
#
# Se derivan del propio `Literal` con `get_args` y no se copian a mano: son las dos caras de lo
# mismo, y una lista copiada se queda atras en la primera red nueva sin que nadie lo note — hasta
# que un `if red in SOCIAL_NETWORKS` empieza a decir que no a una red que si existe.

SOCIAL_NETWORKS: tuple[SocialNetwork, ...] = cast("tuple[SocialNetwork, ...]", get_args(SocialNetwork))
"""Every social network this release knows about, as a tuple you can iterate at runtime.

**The list grows** — it has gone from six to ten in two years — so treat a value you do not
recognise as a network you have not heard of yet, never as an error. What is authoritative at any
moment is ``GET /social_networks``; this tuple is what shipped with this version of the package.

They do not all do the same things, either: ``whatsapp`` is messaging with no feed and
``google_business`` is a business listing that receives reviews, so neither of them publishes. The
capabilities are published by ``GET /social_capabilities``.
"""

PUBLISHABLE_NETWORKS: tuple[PublishableNetwork, ...] = cast(
    "tuple[PublishableNetwork, ...]", get_args(PublishableNetwork)
)
"""The networks that accept publications, as a tuple you can iterate at runtime.

It is :data:`SOCIAL_NETWORKS` minus ``google_business``, and it grows the same way. Authoritative
at any moment is ``GET /allowed_social_publications``; this is what shipped with this version.
"""

COMMENT_NETWORKS: tuple[CommentNetwork, ...] = cast("tuple[CommentNetwork, ...]", get_args(CommentNetwork))
"""The networks whose comments PlanVortex reads. Also grows.

Knowing that a network has comments is not enough to know what you can do with them: Instagram, X
and Bluesky do not let you delete somebody else's, LinkedIn has no "hide", and Google Business only
lets you delete **your own** reply. That matrix is ``GET /social_comment_actions``.
"""

CONTACT_CHANNELS: tuple[ContactChannel, ...] = cast("tuple[ContactChannel, ...]", get_args(ContactChannel))
"""Every channel a contact can be reached on."""

MESSAGE_TYPES: tuple[MessageType, ...] = cast("tuple[MessageType, ...]", get_args(MessageType))
"""Every kind of message.

``comment_message`` and ``publication_message`` are in the list but **cannot be sent through the
public API**: both need the identifier of what they are answering and the endpoint does not read it
from the body, so the message would leave with no recipient.
"""

INTEGRATION_PROVIDERS: tuple[IntegrationProviderName, ...] = cast(
    "tuple[IntegrationProviderName, ...]", get_args(IntegrationProviderName)
)
"""The third-party tools an organization can pull material from. Grows too.

An **integration** is not an **app**: an app (:data:`ClientApp`) is API access to PlanVortex. Half
the marketing copy has called both the same thing; this library does not.
"""

PUBLICATION_STATES: tuple[PublicationState, ...] = cast(
    "tuple[PublicationState, ...]", get_args(PublicationState)
)
"""Every state a publication can be in."""

PUBLICATION_TYPES: tuple[PublicationType, ...] = cast(
    "tuple[PublicationType, ...]", get_args(PublicationType)
)
"""Everywhere inside a network a publication can go."""

AI_PLAN_STATES: tuple[AiPlanState, ...] = cast("tuple[AiPlanState, ...]", get_args(AiPlanState))
"""Every state an AI plan can be in."""

# =================================================================================================
# Catalogo
# =================================================================================================

SocialLimits: TypeAlias = _models.CatalogSocialLimits
"""The per-network limits: characters, images, video duration, file size.

Published by the server, which is who validates them — whoever enforces a limit is who gets to
announce it. Bluesky carries **two** different counts of the same text (300 graphemes in
``characters`` and 3.000 bytes in ``max_post_bytes``) because ``len()`` lies in both directions. A
``0`` in ``max_post_bytes``, ``comment_characters`` or ``title_characters`` means "this network does
not measure that", never "zero".
"""

SocialLimitsMap: TypeAlias = _models.CatalogSocialLimitsMap
"""One number per network, with EVERY network present."""

AspectRatios: TypeAlias = _models.CatalogAspectRatios
"""The crops a network accepts, as a number and as it is written. Parallel indices."""

SocialCapabilities: TypeAlias = _models.CommentsSocialCapabilities
"""What a network can do: publish, messages, products, webhooks, persistent menu, comments."""

PublicationLimits: TypeAlias = _shapes.PublicationLimits
"""The caps of a publication that do not depend on the network. Today, only its manual retries.

Written by hand because the specification declares it inline and the generator only emits
``components/schemas``; ``tests/test_shapes_parity.py`` is what keeps it honest.
"""

CommentActions: TypeAlias = _models.CommentsCommentActions
"""What can be done with a network's comments, one by one. It is what decides which buttons exist.

Published separately from :data:`SocialCapabilities` and on purpose: knowing that a network *has*
comments says nothing about whether you may hide one or delete somebody else's.
"""

# =================================================================================================
# Cliente, organizacion y plan
# =================================================================================================

Client: TypeAlias = _models.ClientsClient
"""A client: who contracts the plan, and who the organizations hang from."""

ClientPlan: TypeAlias = _models.ClientsPlan
"""A client's SUBSCRIPTION, which is not the same as the resources it hands out — those are in
``plan_data``.

Reading ``plan_identifier`` to work out the limits is the classic mistake: a ``custom`` plan carries
its own.
"""

PlanData: TypeAlias = _models.PlanData
"""The resources a plan hands out. On a client it is what was contracted; on an organization, the
share assigned to it.

CAREFUL WITH THE SUM: what is assigned to a client's organizations can never exceed what the client
has contracted — asking for more comes back as a 1400-1408.
"""

Organization: TypeAlias = _models.Organization
"""An organization: the container of accounts, publications and files. They nest.

``actual_plan`` is what was ASSIGNED, and **it is missing when nothing was assigned** — then the
organization shares the plan of the first parent that has one, or the client's unallocated
remainder. For the numbers that really apply, ask for :data:`Limit`.
"""

Limit: TypeAlias = _models.OrganizationsLimit
"""What actually applies to one organization, already resolved. This is the number to show."""

ClientUpdate: TypeAlias = _shapes.ClientUpdate
"""What a client lets you change: its name and its type. Anything else is ignored, not rejected."""

ClientWithOrganizations: TypeAlias = _shapes.ClientWithOrganizations
"""A client with its root organizations inside, as the shortcut listing returns them."""

OrganizationCreate: TypeAlias = _models.OrganizationsOrganizationCreate
"""What you send to create an organization, root or child. ``actual_plan`` is the quota it is given.

The specification declares the same shape twice, once per route; they are the same body and this is
the one type for both.
"""

OrganizationUpdate: TypeAlias = _models.OrganizationsOrganizationUpdate
"""What you send to change an organization: its quota, its statistics settings.

**The name is not in here and that is not an omission**: the server keeps the current one and
ignores whatever arrives, on both routes. An organization is named when it is created.
"""

OrganizationUse: TypeAlias = _shapes.OrganizationUse
"""What an organization spends and what it has already handed down. Both only travel when asked."""

OrganizationUser: TypeAlias = _models.OrganizationsUser
"""A person with a role in an organization. Their identifier is ``id``, Keycloak's, not an ``_id``:
these people do not live in PlanVortex's database.
"""

StatsSettings: TypeAlias = _models.StatsSettings
"""Whether the robot refreshes this organization's statistics by itself.

``auto_refresh_twitter`` is the one that spends real money: on X, measuring costs credits.
"""

AiContext: TypeAlias = _models.AiContext
"""The brand context the AI writes with for this organization."""

AiSettings: TypeAlias = _models.ClientsAiSettings
"""A client's AI provider configuration (BYOK), scope by scope.

A scope set to ``None`` deletes its configuration and returns that scope to PlanVortex's credits.
"""

SocialCredentials: TypeAlias = _models.SocialCredentials
"""An organization's own application credentials (BYOB). The secrets never come out."""

SocialCredentialsInput: TypeAlias = _models.OrganizationsSocialCredentialsInput
"""The credentials as they are SENT. Write-only: nothing that goes in here ever comes back.

All three are needed the first time; afterwards, whatever is omitted is kept.
"""

# =================================================================================================
# Conexion de cuentas
# =================================================================================================

ConnectLink: TypeAlias = _models.Link
"""How ONE network is connected.

Almost always it is a link: you send the user there and the network returns them to PlanVortex,
which completes the connection. **Almost — so look at ``authorization["type"]``, not at whether
``link`` is empty.** WhatsApp has no authorization URL: its sign-up is Meta's Embedded Signup, a
popup your own page raises with the Facebook JavaScript SDK, which answers over ``postMessage`` with
data (the ``waba_id``, the ``phone_number_id``) that does not fit in a query string. Its ``link`` is
the empty string and the popup's parameters travel in ``authorization``.
"""

ConnectToken: TypeAlias = _shapes.ConnectToken
"""The temporal token a PERSON connects an account with: the hosted ``url`` and the ``token`` itself.

Fifteen minutes, one organization, one connection, and it cannot issue another token.
"""

ConnectResult: TypeAlias = _shapes.ConnectResult
"""What completing a connection leaves: accounts, still DISABLED, and where to send the user next."""

EnableResult: TypeAlias = _shapes.EnableResult
"""What enabling an account leaves, which is only the place to send the user afterwards, if any."""

SocialAuthorizationMethod: TypeAlias = _models.AccountsSocialAuthorizationMethod
"""How a network is authorized: ``redirect`` (nine of them) or ``meta_embedded_signup`` (WhatsApp).

**It is a union pretending to be one type.** OpenAPI cannot say "these five fields only when ``type``
is ``meta_embedded_signup``", so the generated shape declares all of them optional — and reading
``authorization["app_id"]`` off it passes ``mypy --strict`` while raising ``KeyError`` against a
``redirect`` entry. :func:`is_redirect_authorization` and :func:`is_meta_embedded_signup` narrow it
to :data:`RedirectAuthorization` and :data:`MetaEmbeddedSignupAuthorization`, which do say it.
"""

RedirectAuthorization: TypeAlias = _shapes.RedirectAuthorization
"""``authorization`` when the network is authorized with a URL. Narrowed by
:func:`is_redirect_authorization`."""

MetaEmbeddedSignupAuthorization: TypeAlias = _shapes.MetaEmbeddedSignupAuthorization
"""``authorization`` when the network is authorized with Meta's popup — WhatsApp, and nothing else.
Narrowed by :func:`is_meta_embedded_signup`."""

# =================================================================================================
# Recursos
# =================================================================================================

Account: TypeAlias = _models.Account
"""A social account connected to an organization.

On Discord an account is a **channel**, not a profile: publishing to two channels of the same server
spends two accounts of the plan. ``error_code`` other than ``0`` means the connection broke — expired
token, permission taken away — and it has to be connected again.
"""

AccountMetrics: TypeAlias = _models.AccountsMetricModel
"""The series of one account metric, already grouped.

``group`` says what each row covers: a range of 31 days or fewer is grouped by day, up to 720 by
month, and beyond that by year. The ``name`` values are the network's RAW names — the same ones the
metric list returns — and not the common vocabulary.
"""

AccountMetricNames: TypeAlias = _models.AccountsMetricList
"""The RAW metric names of one network, which is what the metrics endpoint takes and returns.

They are NOT the common vocabulary (:data:`MetricName`): here each network speaks its own language,
``page_impressions`` against ``total_interactions`` against ``allPageViews``, and two of them cannot
be added together.
"""

AccountUpdate: TypeAlias = _shapes.AccountUpdate
"""The only thing a connected account lets you change: the name it is shown under here."""

PersistentMenu: TypeAlias = _models.AccountsPersistentMenu
"""The chat's fixed menu, in Meta's format. Only the networks with messaging have one."""

Upload: TypeAlias = _models.Upload
"""A file in the organization's library.

CAREFUL WITH ``public_path``: it is a **signed, temporary** URL, not a permanent link. It stays
byte-identical within the same hour — so caching it that long is correct — and stops working after
that. Storing it in your database is the classic mistake: three days later every thumbnail is
broken. Ask for the upload again when you need it.
"""

UploadUpdate: TypeAlias = _shapes.UploadUpdate
"""A video's cover settings, which is all an upload lets you change.

``cover_offset`` is written unconditionally, so omitting it CLEARS the stored value.
"""

ImportFile: TypeAlias = _shapes.ImportFile
"""One file of an integration to bring into the library, as the provider's picker described it."""

ImportFileError: TypeAlias = _shapes.ImportFileError
"""One file that did not get in, and why. Not to be confused with the :class:`planvortex.FileError`
exception: this is data inside a **successful** response.
"""

ImportResult: TypeAlias = _shapes.ImportResult
"""The result of an import, which is PARTIAL on purpose: look at ``errors`` even when it worked."""

FileProperties: TypeAlias = _models.FileProperties
"""Width, height, duration and size of a file, plus which networks it fits in **by its crop**."""

Publication: TypeAlias = _models.Publication
"""A publication: scheduled, sent or failed.

TWO THINGS THAT SURPRISE PEOPLE, both checked against the server:

- **``files`` arrives POPULATED**: whole :data:`Upload` objects, not identifiers. Identifiers are
  what you SEND (see :data:`PublicationInput`).
- **``id_account`` changes shape depending on the operation**: the single-publication ones (create,
  read, retry) return it resolved, and the listing and the update return it as an identifier. Use
  :func:`account_id` or :func:`account` instead of assuming either.

If ``state`` is ``withErrors``, the reason is in ``publication_errors`` — which is a LIST — and its
``code`` is a PlanVortex catalogue code, never an HTTP status.
"""

PublicationInput: TypeAlias = _shapes.PublicationInput
"""What you send to create or update a publication. Here ``files`` ARE identifiers.

``publish_date`` accepts a ``datetime`` as well as an ISO-8601 string and the library serializes it
— but **it has to carry a timezone**. A naive ``datetime`` raises instead of guessing: assuming UTC
publishes at the wrong time for whoever is in Madrid, and assuming the process's local zone does it
for whoever is in Docker.

That ``datetime`` is why this is the one shape written by hand on top of the generated type: OpenAPI
has a ``string`` with ``format: date-time`` and no way to say "or the language's own date". Its
``social_network`` is :data:`PublishableNetwork`, which is **nine** networks and not ten.
"""

PublicationErrorDetail: TypeAlias = _models.PublicationError
"""One reason a publication failed, as it travels inside ``publication_errors``.

NOT to be confused with :class:`planvortex.PublicationError`, which is the EXCEPTION this library
raises when a request fails. This is data inside a **successful** response: the publication was
saved, and here is why it did not go out.
"""

PublicationRetryResult: TypeAlias = _models.PublicationsPublicationRetry
"""What retrying leaves: the publication as it ended up, plus the cap the server enforces.

Read ``max_retries`` from here instead of hardcoding a 3: it is the same number the server checks.
"""

PublicationStats: TypeAlias = _models.PublicationStats
"""The raw metric breakdown the network gives, which is not the same on any two networks."""

PublicationMetrics: TypeAlias = _models.NormalizedMetrics
"""The metrics that are comparable between networks: the ones you can add up in one chart."""

PublicationStatsHistory: TypeAlias = _models.PublicationsPublicationStatsHistory
"""The historical series of one publication, plus its last measurement."""

PublicationStatsPoint: TypeAlias = _models.PublicationsPublicationStatsPoint
"""One measurement of the series: the RUNNING TOTAL at that date, not the day's increment."""

PublicationsStatsResult: TypeAlias = _models.PublicationsPublicationsStatsList
"""The aggregates and the page returned by the publication stats listing."""

Comment: TypeAlias = _models.CommentsComment
"""A comment, or a Google Business review.

Only ``read`` and ``replied`` are ours. Everything else is what the network said, and a live read
overwrites what was stored. THREE THINGS SURPRISE PEOPLE:

- **``id_publication`` is missing** when the comment does not hang off a publication of ours, and
  that is not rare: a Google Business review hangs off the LISTING (there ``publication_external_id``
  is ``locations/{id}``), and a video uploaded by hand or a post older than PlanVortex also get
  comments. What always identifies the target is ``publication_external_id``.
- **``id_account`` and ``id_publication`` change shape depending on the operation**: the inbox
  returns them populated and everything else — the live threads, the reply, the update — returns
  them as strings. Same asymmetry as ``Publication["id_account"]`` and covered the same way, with
  :func:`account_id` / :func:`account` and :func:`publication_id` / :func:`publication`.
- **``text`` can be empty and that is not a failure**: a stars-only review carries no text at all,
  so render ``rating`` beside it instead of treating the row as broken.
"""

CommentAuthor: TypeAlias = _models.CommentsCommentAuthor
"""Who wrote a comment. ``is_own`` tells ours apart from a third party's."""

CommentThread: TypeAlias = _models.CommentsCommentThread
"""A thread read LIVE: what the network says right now, already reconciled with what was stored.

``credits_consumed`` is real money and only on X — one credit per reply returned, ``0`` on every
other network — and ``next_cursor`` is the network's opaque token, handed back AS IS as ``offset``
on the next call. Its absence means there are no more pages.
"""

CommentUpdate: TypeAlias = _shapes.CommentUpdate
"""What you send to change a comment: ``read`` (ours) and/or ``hidden`` (the network's)."""

CommentReplyResult: TypeAlias = _shapes.CommentReplyResult
"""What replying leaves: the comment answered, our reply, and what X charged.

``reply`` **can arrive without ``_id``**: the network publishes first and the row is written
afterwards, and that write is not allowed to fail the request. ``comment["our_reply_external_id"]``
always identifies it.
"""

Contact: TypeAlias = _models.Contact
"""A contact in the organization's address book."""

ContactCreate: TypeAlias = _models.ContactsContactCreate
"""What you send to create a contact.

``social_identifiers`` is NOT optional: a contact with no channel is a contact nobody can write to,
and the server rejects it with error 1601.
"""

ContactUpdate: TypeAlias = _models.ContactsContactUpdate
"""What you send to change a contact.

**``extra_data`` is destructive**: it is the one field the server writes with whatever arrives
instead of merging it, so omitting it DELETES the contact's own fields. The other three are kept
when they do not travel.
"""

ContactExtraData: TypeAlias = _models.ContactExtraData
"""A contact's own fields: the address block and the six free properties."""

SocialIdentifier: TypeAlias = _models.SocialIdentifier
"""The same contact, on one channel. Either a social network or ``email``."""

SocialIdentifierInput: TypeAlias = _models.ContactsSocialIdentifierInput
"""The same, as it is SENT: here ``_id`` is optional and the server assigns one.

Two types and not one because the one that comes back always carries ``_id`` and the one you send
almost never does; with a single type, either you demand an identifier that does not exist yet or
you stop guaranteeing the one that does.
"""

Message: TypeAlias = _models.Message
"""A message exchanged with a contact.

CAREFUL WITH THE THREE REFERENCE FIELDS. ``contact_id``, ``from_contact_id`` and
``message_options["files"]`` arrive **populated** — the whole object, not the identifier — in the
messages listing and in the webhook PlanVortex posts to your app, and as plain identifiers
everywhere else. Same asymmetry as ``Publication["id_account"]``, and covered the same way: with
:func:`message_contact`, :func:`message_contact_id` and :func:`message_files`.
"""

MessageOptions: TypeAlias = _models.MessageOptions
"""What a message carries besides its text: files, template, payload, Meta cards."""

MessageInput: TypeAlias = _models.MessagesMessageInput
"""What you send to write a message.

``comment_message`` and ``publication_message`` are in :data:`MessageType` but **cannot be sent
from here**: both need the identifier of what they answer and the endpoint does not read it from
the body, so the message would leave with no recipient.
"""

MessageTemplate: TypeAlias = dict[str, object]
"""A message template, **in the network's own format**: Meta's ``name``, ``status``, ``components``
and ``language``.

Deliberately not translated into a shape of ours. The template you have to name when sending
(``message_options["template_name"]``) is the network's, so inventing another one here would mean
translating back in the only place it is used. And it is WhatsApp's and nobody else's.
"""

Conversation: TypeAlias = _models.MessagesConversation
"""A conversation: a contact, when they last wrote, and how many of their messages are unread.

It has no ``_id`` of its own — it comes out of an aggregation that projects it away — because a
conversation is not an entity: what exists are the messages with that contact. The identifier that
opens the thread is ``conversation["contact"]["_id"]``.
"""

ConversationTotals: TypeAlias = _models.MessagesConversationTotals
"""How many conversations there were in a range. TWO different responses, not one with extra fields:
without ``group_by`` you get ``{total}`` and with it you get ``{stats, group}``.

Careful with ``group_value``: it is the NUMBER that Mongo's ``$dayOfYear``, ``$month`` or ``$year``
produce — 240, 8, 2026 — and not a date. With ``group_by="day"``, two years of the same range fall
on the same value.
"""

Product: TypeAlias = _models.ProductsProduct
"""A product in a Meta Commerce catalog. Facebook and Instagram only.

It speaks Meta's vocabulary and not one of ours, unlike the statistics: what is here are the Graph
API's fields, with their names.
"""

ProductInput: TypeAlias = _models.ProductsProductInput
"""What you send to create a product. With ``id`` inside, it UPDATES the existing one."""

ProductCatalog: TypeAlias = _models.ProductsProductCatalog
"""A Meta Commerce catalog: what groups products and what everything else hangs from."""

ProductCatalogInput: TypeAlias = _models.ProductsProductCatalogInput
"""What you send to create a catalog."""

Integration: TypeAlias = _models.IntegrationsIntegration
"""An ORGANIZATION's connection to a tool it pulls material from: Google Drive, an RSS feed.

Not to be confused with an **app** (:data:`ClientApp`), which is access to PlanVortex's own API.
Credentials never come out: to know whether the connection is alive there is ``connected``, and the
reason when it is not, in ``error_code``.
"""

IntegrationProvider: TypeAlias = _models.IntegrationsIntegrationProvider
"""What a provider can do and what its form asks for. It is what decides how to connect."""

IntegrationConnectRequest: TypeAlias = (
    _models.IntegrationsGoogleDriveConnectRequest | _models.IntegrationsRssConnectRequest
)
"""What you send to connect or reconnect. Two shapes, told apart by ``provider``: with OAuth the
``code`` travels, and without it, the ``config_fields`` form.
"""

RssConfig: TypeAlias = _models.IntegrationsRssConfig
"""The configuration of an RSS feed. On Google Drive ``config`` is an empty object."""

IntegrationUpdate: TypeAlias = _shapes.IntegrationUpdate
"""What you send to change an integration: its name, its switch and, on RSS, its configuration."""

IntegrationPickerConfig: TypeAlias = _shapes.IntegrationPickerConfig
"""What the browser needs to open Google Drive's picker. It carries a LIVE, short-lived token: do
not store it and do not log it.
"""

AiPlan: TypeAlias = _models.AiPlansAiPlan
"""A publication plan generated with AI.

**``publications`` changes shape depending on the operation**, like ``Publication["id_account"]``:
reading one plan returns the whole publications with their files, and the LISTING returns their
identifiers. ``organization_context`` is a SNAPSHOT of the organization's brand context at the time
the plan was created, not today's — which is what makes a retry reproducible.
"""

AiPlanOptions: TypeAlias = _models.AiPlansAiPlanOptions
"""The options a plan was generated with, already normalized."""

AiPlanOptionsInput: TypeAlias = _models.AiPlansAiPlanOptionsInput
"""The options as they are SENT: all optional, the defaults are the server's."""

AiPlanCreateRequest: TypeAlias = _models.AiPlansAiPlanCreateRequest
"""What you send to queue a plan."""

AiPlanCostEstimate: TypeAlias = _models.AiPlansAiPlanCostEstimate
"""The DETERMINISTIC budget of a plan, computed by the server and never by the model.

``base_cost`` is the unavoidable part — orchestration and texts: if it does not fit in
``available_credits`` the plan is rejected instead of half-generated. ``estimated_cost`` also
includes the affordable images and is an upper bound.
"""

AiPlanCreateResult: TypeAlias = _models.AiPlansAiPlanCreateResponse
"""What queueing a plan returns: the plan in ``pending`` and what it was estimated to cost."""

AiPlanRegenerateResult: TypeAlias = _shapes.AiPlanRegenerateResult
"""What regenerating one publication leaves. ``credits_spent`` is the PLAN's total, not this call's."""

ClientApp: TypeAlias = _models.AppsClientApp
"""A client app: the credentials an integration authenticates with."""

ClientAppInput: TypeAlias = _models.AppsClientAppInput
"""What you send to create or update an app. On update, it REPLACES the five fields."""

# =================================================================================================
# Dashboard
# =================================================================================================

DashboardRange: TypeAlias = _models.DashboardDashboardRange
"""The range that was applied and the previous period it is compared against, of the SAME length.

It is not "last month": comparing 30 days against a calendar month would move the delta with the
calendar.
"""

MetricRow: TypeAlias = _models.DashboardMetricRow
"""One aggregated row of account metrics.

``group`` is the axis value — the day, the network, the account identifier — and it is **``None``
when the grouping was ``total``**: the field always travels, the value is not always a string.
"""

PublicationsSummary: TypeAlias = _models.DashboardPublicationsSummary
"""The publication counts of a range."""

PublicationsSummaryResult: TypeAlias = _shapes.PublicationsSummaryResult
"""The same counts, with the range they were computed over, as ``dashboard.publications`` returns
them. ``by_day`` counts what was CREATED and ``published_by_day`` what WENT OUT: two different
questions over two different sets.
"""

MetricsResult: TypeAlias = _shapes.MetricsResult
"""The aggregated account metrics of a range, plus the axis they were grouped on."""

TopPublicationsResult: TypeAlias = _shapes.TopPublicationsResult
"""The ranking of a range by one metric, plus the range and the metric that were applied."""

TopPublication: TypeAlias = _models.DashboardTopPublication
"""One row of the ranking. **It does not have the shape of a** :data:`Publication`: it comes out of
the stats aggregation, so there is no ``_id`` (the identifier is ``id_publication``) and the content
travels nested under ``publication``.
"""

PlanUse: TypeAlias = _models.DashboardPlanUse
"""What an organization spends, what it has handed down to its children, and what it has."""

AccountWithError: TypeAlias = _models.DashboardAccountWithError
"""A broken account: expired token or revoked permission. It neither publishes nor measures until it
is reconnected.
"""

DashboardPublicationRef: TypeAlias = _models.DashboardDashboardPublicationRef
"""A publication as the health block PROJECTS it: four fields, not a :data:`Publication`."""

DashboardAiPlanRef: TypeAlias = _models.DashboardDashboardAiPlanRef
"""The last AI plan, projected, as the plans block returns it."""

Dashboard: TypeAlias = _models.DashboardDashboard
"""The whole home screen.

**A missing block is not an error**: each one is checked against its own permission and skipped when
the caller cannot read it, instead of failing the request. ``available_blocks`` says which ones were
allowed; one that is ``True`` and does not arrive means there was no data.
"""

# =================================================================================================
# Los campos que la API devuelve de DOS formas
# =================================================================================================
#
# En TypeScript un `typeof value === "string"` estrecha la union sobre la marcha, y escribirlo en
# cada sitio es aceptable. Con TypedDict es un `isinstance` de tres lineas cada vez, asi que se
# escribe una sola vez aqui. No hacen E/S, asi que no tienen gemelo sincrono: los dos clientes las
# usan tal cual.


def is_redirect_authorization(
    authorization: SocialAuthorizationMethod,
) -> TypeGuard[RedirectAuthorization]:
    """The network is authorized with a URL: send the person to the entry's ``link``.

    **Do not narrow it with ``if authorization["type"] == "redirect"``**: the generated type is one
    flat ``TypedDict``, so no type checker can tell the two branches apart and you keep the five
    popup fields — all of them optional, all of them a ``KeyError`` waiting — inside the branch that
    has none of them.
    """
    return authorization["type"] == "redirect"


def is_meta_embedded_signup(
    authorization: SocialAuthorizationMethod,
) -> TypeGuard[MetaEmbeddedSignupAuthorization]:
    """The network is authorized with Meta's *Embedded Signup* popup. **WhatsApp, and nothing else.**

    Inside this branch the five fields the popup takes are required, so ``authorization["app_id"]``
    is a string and not a hope. Opening the popup is browser work the library does not do.
    """
    return authorization["type"] == "meta_embedded_signup"


def is_publishable_network(social_network: str) -> TypeGuard[PublishableNetwork]:
    """The network accepts publications, so it can go in a :data:`PublicationInput`.

    An account's ``social_network`` is one of **ten** and a publication's is one of **nine** —
    ``google_business`` is a business listing, it receives reviews and not posts — so handing one
    straight to the other is a type error even when you have already filtered the accounts with
    ``capability="publications"`` and it cannot happen at runtime. This is the bridge::

        red = cuenta["social_network"]
        if not is_publishable_network(red):
            continue
        pv.publications.create(org_id, cuenta["_id"], {"social_network": red, "text": texto})

    **Do not narrow it with ``if red != "google_business"``**: that reads as a negative comparison
    against a ten-value union and leaves the other nine plus itself, which is where it started.

    It takes a ``str`` on purpose, so a network released after this version can be checked without
    the checker objecting first — the same rule every argument in this library follows.
    """
    return social_network in PUBLISHABLE_NETWORKS


def account_id(resource: Publication | Comment) -> str:
    """The account identifier of a publication or a comment, populated or not.

    ``id_account`` arrives resolved in some operations and as a string in others — in publications,
    the single-resource ones against the listing; in comments, exactly the other way round — and
    this covers it without writing the ``isinstance`` in every place.
    """
    valor = resource["id_account"]
    return valor if isinstance(valor, str) else valor["_id"]


def account(resource: Publication | Comment) -> Account | None:
    """The account when it comes populated, and ``None`` when the API only sent the identifier.

    The counterpart of :func:`account_id`.
    """
    valor = resource["id_account"]
    return None if isinstance(valor, str) else valor


def publication_id(resource: Comment) -> str | None:
    """The publication identifier of a comment, populated or not.

    ``None`` in the two cases where there really is no publication behind it: the review that hangs
    off a Google Business listing, and the post that was not published from PlanVortex.
    """
    valor = resource.get("id_publication")
    if valor is None:
        return None
    return valor if isinstance(valor, str) else valor["_id"]


def publication(resource: Comment) -> Publication | None:
    """The publication when it comes populated — only the comments inbox resolves it — and ``None``
    when the API sent the identifier, or when there is no publication behind it.
    """
    valor = resource.get("id_publication")
    return None if valor is None or isinstance(valor, str) else valor


def message_direction(message: Message) -> Literal["incoming", "outgoing", "unknown"]:
    """Which way a message goes.

    It is not a field: it follows from WHICH of the two contacts it carries. ``from_contact_id`` is
    the contact writing to us and ``contact_id`` is us writing to them, and the server guarantees
    that exactly one arrives (``ERROR_CODE_1503`` if neither, ``1504`` if both). The ``"unknown"``
    is there for a message built by hand that has not been through the server yet.
    """
    if message.get("from_contact_id"):
        return "incoming"
    return "outgoing" if message.get("contact_id") else "unknown"


def message_contact_id(message: Message) -> str | None:
    """The contact identifier of a message, populated or not and whoever wrote it.

    For the direction there is :func:`message_direction`; what matters here is WHO is being talked
    to, which is the same person in both directions.
    """
    valor = message.get("from_contact_id") or message.get("contact_id")
    if valor is None:
        return None
    return valor if isinstance(valor, str) else valor["_id"]


def message_contact(message: Message) -> Contact | None:
    """The contact of a message when it comes populated — the listing and the webhook — and ``None``
    when the API only sent the identifier. The counterpart of :func:`message_contact_id`.
    """
    valor = message.get("from_contact_id") or message.get("contact_id")
    return None if valor is None or isinstance(valor, str) else valor


def message_files(message: Message) -> list[Upload]:
    """The attached files of a message that came populated.

    The ones that arrived as identifiers do NOT come out here: for those there is
    :func:`message_file_ids`.
    """
    adjuntos = message["message_options"].get("files", [])
    return [fichero for fichero in adjuntos if not isinstance(fichero, str)]


def message_file_ids(message: Message) -> list[str]:
    """The identifiers of a message's attached files, populated or not."""
    adjuntos = message["message_options"].get("files", [])
    return [fichero if isinstance(fichero, str) else fichero["_id"] for fichero in adjuntos]


__all__ = [
    "AI_PLAN_STATES",
    "COMMENT_NETWORKS",
    "CONTACT_CHANNELS",
    "INTEGRATION_PROVIDERS",
    "MESSAGE_TYPES",
    "PUBLICATION_STATES",
    "PUBLICATION_TYPES",
    "PUBLISHABLE_NETWORKS",
    "SOCIAL_NETWORKS",
    "Account",
    "AccountMetricNames",
    "AccountMetrics",
    "AccountUpdate",
    "AccountWithError",
    "AiContext",
    "AiPlan",
    "AiPlanCostEstimate",
    "AiPlanCreateRequest",
    "AiPlanCreateResult",
    "AiPlanOptions",
    "AiPlanOptionsInput",
    "AiPlanRegenerateResult",
    "AiPlanState",
    "AiSettings",
    "AspectRatios",
    "Client",
    "ClientApp",
    "ClientAppInput",
    "ClientPlan",
    "ClientUpdate",
    "ClientWithOrganizations",
    "Comment",
    "CommentActions",
    "CommentAuthor",
    "CommentNetwork",
    "CommentReplyResult",
    "CommentThread",
    "CommentUpdate",
    "ConnectLink",
    "ConnectResult",
    "ConnectToken",
    "Contact",
    "ContactChannel",
    "ContactCreate",
    "ContactExtraData",
    "ContactUpdate",
    "Conversation",
    "ConversationTotals",
    "Dashboard",
    "DashboardAiPlanRef",
    "DashboardPublicationRef",
    "DashboardRange",
    "EnableResult",
    "EngagementBase",
    "FileFormat",
    "FileProperties",
    "FileType",
    "ImportFile",
    "ImportFileError",
    "ImportResult",
    "Integration",
    "IntegrationConnectRequest",
    "IntegrationPickerConfig",
    "IntegrationProvider",
    "IntegrationProviderName",
    "IntegrationUpdate",
    "Limit",
    "Message",
    "MessageInput",
    "MessageOptions",
    "MessageTemplate",
    "MessageType",
    "MetaEmbeddedSignupAuthorization",
    "MetricName",
    "MetricRow",
    "MetricsResult",
    "Organization",
    "OrganizationCreate",
    "OrganizationUpdate",
    "OrganizationUse",
    "OrganizationUser",
    "PersistentMenu",
    "PlanData",
    "PlanUse",
    "Product",
    "ProductCatalog",
    "ProductCatalogInput",
    "ProductInput",
    "Publication",
    "PublicationErrorDetail",
    "PublicationInput",
    "PublicationLimits",
    "PublicationMetrics",
    "PublicationRetryResult",
    "PublicationState",
    "PublicationStats",
    "PublicationStatsHistory",
    "PublicationStatsPoint",
    "PublicationType",
    "PublicationsStatsResult",
    "PublicationsSummary",
    "PublicationsSummaryResult",
    "PublishableNetwork",
    "RedirectAuthorization",
    "RssConfig",
    "SocialAuthorizationMethod",
    "SocialCapabilities",
    "SocialCredentials",
    "SocialCredentialsInput",
    "SocialIdentifier",
    "SocialIdentifierInput",
    "SocialLimits",
    "SocialLimitsMap",
    "SocialNetwork",
    "StatsSettings",
    "TopPublication",
    "TopPublicationsResult",
    "Upload",
    "UploadUpdate",
    "account",
    "account_id",
    "is_meta_embedded_signup",
    "is_publishable_network",
    "is_redirect_authorization",
    "message_contact",
    "message_contact_id",
    "message_direction",
    "message_file_ids",
    "message_files",
    "publication",
    "publication_id",
]
