"""GENERADO POR `scripts/generate_models.py`. NO SE EDITA A MANO.

Sale de `openapi/planvortex.openapi.json`, que a su vez sale de los `swagger/*-swagger.json` de
PlanVortexHome. Si algo de aqui no cuadra con la API, lo que hay que arreglar es el spec.

Estos tipos son un DETALLE INTERNO: los nombres van prefijados por dominio para que el `Plan` de un
cliente y el de una organizacion no se pisen, y los objetos declarados en linea reciben el nombre
que el generador se inventa. La superficie publica del paquete son los tipos con nombre legible de
`planvortex/types.py`, que se construyen encima de estos.
"""

import sys
from typing import Any, Literal, TypeAlias

if sys.version_info >= (3, 11):
    from typing import NotRequired, TypedDict
else:  # pragma: no cover - la rama la elige el interprete, no un test
    from typing_extensions import NotRequired, TypedDict

AccountsMetricList: TypeAlias = list[
    Literal[
        "page_total_actions",
        "page_call_phone_clicks_logged_in_unique",
        "page_get_directions_clicks_logged_in_unique",
        "page_website_clicks_logged_in_unique",
        "page_post_engagements",
        "page_consumptions_unique",
        "page_negative_feedback",
        "page_negative_feedback_unique",
        "page_fans_online_per_day",
        "page_impressions",
        "page_impressions_unique",
        "page_impressions_paid",
        "page_impressions_paid_unique",
        "page_impressions_organic_v2",
        "page_impressions_organic_unique_v2",
        "page_impressions_viral",
        "page_impressions_viral_unique",
        "page_impressions_nonviral",
        "page_impressions_nonviral_unique",
        "page_posts_impressions",
        "page_posts_impressions_unique",
        "page_posts_impressions_paid",
        "page_posts_impressions_paid_unique",
        "page_posts_impressions_organic",
        "page_posts_impressions_organic_unique",
        "page_posts_served_impressions_organic_unique",
        "page_posts_impressions_viral",
        "page_posts_impressions_viral_unique",
        "page_posts_impressions_nonviral",
        "page_posts_impressions_nonviral_unique",
        "impressions",
        "reach",
        "total_interactions",
        "accounts_engaged",
        "likes",
        "comments",
        "saves",
        "shares",
        "replies",
        "follows_and_unfollows",
        "profile_links_taps",
        "website_clicks",
        "profile_views",
        "paidFollowers",
        "organicFollowerGain",
        "careersPageBannerPromoClicks",
        "careersPagePromoLinksClicks",
        "careersPageEmployeesClicks",
        "careersPageJobsClicks",
        "careersPageViewsUnique",
        "careersPageViews",
        "overviewPageViewsUnique",
        "overviewPageViews",
        "allPageViews",
        "follows",
        "share",
        "views",
    ]
]


class Stat(TypedDict):
    date: str
    """
    First measurement of the group, which is what dates the row.
    """
    name: str
    """
    The metric's RAW name, the one the network publishes — the same names `GET .../metric_list` returns.
    """
    group_value: int
    """
    The group's ordinal: day of the year, month, or year, matching `group`.
    """
    group: Literal["day", "month", "year"]
    value: float
    """
    Sum of the measurements in the group.
    """


class AccountsMetricModel(TypedDict):
    """
    A metric series for one account, already grouped. `group` says what each row covers: a range of 31 days or less is grouped by day, up to 720 by month, and beyond that by year.
    """

    stats: list[Stat]
    """
    One row per metric and per group. Empty when nothing was measured in the range.
    """
    group: Literal["day", "month", "year"]


class AccountsPersistentMenuItem(TypedDict):
    locale: NotRequired[str]
    """
    `default`, or a locale such as `es_ES`.
    """
    composer_input_disabled: NotRequired[bool]
    """
    `true` hides the text box, leaving the menu as the only way to answer.
    """
    call_to_actions: NotRequired[list[dict[str, Any]]]
    """
    The buttons. A `postback` sends you its `payload` as a message; a `web_url` opens a page; a `nested` holds more buttons.
    """


AccountsPersistentMenu: TypeAlias = list[AccountsPersistentMenuItem]
"""
The chat's fixed menu, one entry per locale, in Meta's own format. The entry with `locale: "default"` is required and is what is shown when no other locale matches.
"""


class AccountsSocialAuthorizationMethod(TypedDict):
    """
    **How** an account of this network is authorized, which is not always "send the user to this URL".

    Nine of the eleven networks are `redirect`: open `link` and the network sends the person back to PlanVortex with a code. Two are not:

    • **WhatsApp.** Its sign-up is Meta's *Embedded Signup*: a popup raised by the Facebook JavaScript SDK from your own page, which returns — over `postMessage` — session data (`waba_id`, `phone_number_id`) that no query string carries. Its `link` is therefore an empty string.
    • **Telegram.** There is no OAuth here: no consent screen, no `code`, no account token. `link` opens a private chat with the PlanVortex bot, the person then adds that bot to their channel, and **the account is created from that event**, not from any request of yours. Which means the connection cannot be finished by calling `GET /organizations/{id_organization}/account-connect/telegram` — see that endpoint.

    Branch on `authorization.type`, never on whether `link` is empty.
    """

    type: Literal["redirect", "meta_embedded_signup", "telegram_bot"]
    """
    `redirect`: send the user to `link`. `meta_embedded_signup`: open the Meta popup with the fields below. `telegram_bot`: open `link` in another tab and wait for the account to show up.
    """
    app_id: NotRequired[str]
    """
    `meta_embedded_signup` only. Goes to `FB.init({appId})`. It is the same Meta app whose secret PlanVortex uses to exchange the code afterwards.
    """
    config_id: NotRequired[str]
    """
    `meta_embedded_signup` only. Goes to `FB.login(cb, {config_id})` — the Embedded Signup configuration.
    """
    graph_version: NotRequired[str]
    """
    `meta_embedded_signup` only. Goes to `FB.init({version})`. This is the JavaScript SDK version, not the Graph version PlanVortex calls server-side: they move independently.
    """
    feature_type: NotRequired[str]
    """
    `meta_embedded_signup` only. Goes to `extras.featureType`.
    """
    session_info_version: NotRequired[str]
    """
    `meta_embedded_signup` only. Goes to `extras.sessionInfoVersion`.
    """
    bot_username: NotRequired[str]
    """
    `telegram_bot` only. The bot's `@name`, **without the at sign**. Published here so you never have to write it by hand: it is the name the person will see in Telegram, and it changes with the deployment.
    """
    add_to_group_link: NotRequired[str]
    """
    `telegram_bot` only. The **second** step, and it does not follow from the first: `link` opens the list of channels and this one opens the list of groups. It adds the bot to the channel's linked discussion group, which is what turns comments on — a Telegram channel with no discussion group has no comment inbox at all (error 965). Optional for the user: publishing and statistics work without it.
    """


class AiContext(TypedDict):
    """
    Brand context for AI generation. Every field is optional; the ones you fill in are what the model is told about the business.
    """

    brand_name: NotRequired[str]
    """
    Commercial name, when it differs from the organization's.
    """
    description: NotRequired[str]
    """
    What the organization does.
    """
    sector: NotRequired[str]
    audience: NotRequired[str]
    """
    Who the content is aimed at.
    """
    value_proposition: NotRequired[str]
    website: NotRequired[str]
    shop_url: NotRequired[str]
    blog_url: NotRequired[str]
    social_urls: NotRequired[list[str]]
    """
    Social profiles or other reference links.
    """
    default_tone: NotRequired[str]
    """
    Default tone. A tone set on the plan itself wins over this one.
    """
    keywords: NotRequired[list[str]]
    """
    Recurring keywords and hashtags.
    """
    products: NotRequired[str]
    """
    Products or services that may be promoted.
    """
    avoid: NotRequired[str]
    """
    Topics, expressions or competitors that must never appear.
    """
    notes: NotRequired[str]
    """
    Anything else the model should know.
    """


class AiPlansAiPlanCostEstimate(TypedDict):
    """
    Deterministic cost estimate computed by the backend (never by the model). BYOK scopes cost 0 credits.
    """

    base_cost: int
    """
    Mandatory cost (orchestration + target texts). The orchestration half depends on the TEMPLATE and on the size of its source: `orchestration_cost` + `orchestration_cost_per_source_item` x units, both published in `GET /planner_templates`. The plan is rejected if this exceeds the available credits.
    """
    estimated_cost: int
    """
    Total estimated cost including the financeable images (upper bound).
    """
    texts_target: int
    images_target: int
    """
    How many images the plan will generate. **0 when the template does not generate them** (`from_images`, `from_catalog`): the pictures come from the source, so the plan spends no image credits at all — a week of 7 publications with a picture on each goes from 519 credits to 48. That is worth saying out loud before the plan is created.
    """
    available_credits: int


class AiPlansAiPlanNotice(TypedDict):
    """
    Something the plan has to say about itself, in the same shape as an API error.
    """

    code: int
    message: str
    data: NotRequired[dict[str, Any]]


class AiPlansAiPlanOptions(TypedDict):
    """
    Generation options as they were STORED, already normalised: `publish_days` comes sorted and deduplicated, and every default has been resolved.
    """

    timezone: str
    """
    IANA timezone for the optimal publish slots (typically the user's browser timezone). publish_date is stored in UTC.
    """
    week_start: str
    """
    Start of the week to plan (slots are generated between this date and +7 days). Defaults to now.
    """
    publish_days: list[int]
    """
    Days of the week the plan publishes on, in ISO 8601 numbering (1 = Monday ... 7 = Sunday). Defaults to the whole week. There is still at most ONE publication per day and account, so this is what bounds the size and the cost of the plan: the number of generated posts is (selected days x accounts). Must be a non-empty array of unique integers between 1 and 7, or the request is rejected with 2106. The 7-day window starts at week_start, so each ISO day appears exactly once: with a week_start in mid-week, day 1 (Monday) is the FOLLOWING Monday. If the selected days leave no future slot at all, the request is rejected with 2108.
    """
    language: str
    """
    Language of the generated texts.
    """
    tone: NotRequired[str]
    """
    Optional tone (e.g. 'cercano', 'profesional') passed to the prompt.
    """
    allow_images: bool
    """
    Whether images may be generated. Each image costs 70 AI credits.
    """
    max_images: NotRequired[int]
    """
    Optional cap on the number of images; the credit budget may reduce it further.
    """
    gallery_uploads: list[str]
    """
    Upload ids from the organization's gallery used as visual reference for the generated images.
    """
    shared: bool
    """
    Generate ONE piece of content per day and replicate it across every account, each scheduled at the best hour for ITS network, instead of one publication per account and day. Cheaper — one text and one image per day — and it caps images at 7.
    """
    use_organization_context: bool
    """
    Use the organization's brand context in the prompts. It is copied into the plan as a SNAPSHOT when the plan is created, so a retry or a regeneration uses the context the plan was asked with even if the configuration changed meanwhile.
    """


class AiPlansAiPlanOptionsInput(TypedDict):
    """
    Generation options, as you SEND them: every one is optional and the server fills in its default. Optimal publish slots are chosen deterministically by the backend from a fixed table per network, converted to this timezone; the model never invents times.
    """

    timezone: NotRequired[str]
    """
    IANA timezone for the optimal publish slots (typically the user's browser timezone). publish_date is stored in UTC. Optional; defaults to `"Europe/Madrid"`.
    """
    week_start: NotRequired[str]
    """
    Start of the week to plan (slots are generated between this date and +7 days). Defaults to now.
    """
    publish_days: NotRequired[list[int]]
    """
    Days of the week the plan publishes on, in ISO 8601 numbering (1 = Monday ... 7 = Sunday). Defaults to the whole week. There is still at most ONE publication per day and account, so this is what bounds the size and the cost of the plan: the number of generated posts is (selected days x accounts). Must be a non-empty array of unique integers between 1 and 7, or the request is rejected with 2106. The 7-day window starts at week_start, so each ISO day appears exactly once: with a week_start in mid-week, day 1 (Monday) is the FOLLOWING Monday. If the selected days leave no future slot at all, the request is rejected with 2108. Optional; defaults to `[1,2,3,4,5,6,7]`.
    """
    language: NotRequired[str]
    """
    Language of the generated texts. Optional; defaults to `"es"`.
    """
    tone: NotRequired[str]
    """
    Optional tone (e.g. 'cercano', 'profesional') passed to the prompt.
    """
    allow_images: NotRequired[bool]
    """
    Whether images may be generated. Each image costs 70 AI credits. Optional; defaults to `true`. Forced to `false` when the template does not generate images (`generates_images: false`), where the picture comes from the source and costs nothing.
    """
    max_images: NotRequired[int]
    """
    Optional cap on the number of images; the credit budget may reduce it further.
    """
    gallery_uploads: NotRequired[list[str]]
    """
    Upload ids from the organization's gallery used as visual reference for the generated images. They are references for the images the model GENERATES, so a template that does not generate them does not accept them either (`allows_gallery`): sending them to `from_images` or `from_catalog` is a 2106.
    """
    shared: NotRequired[bool]
    """
    Generate ONE piece of content per day and replicate it across every account, each scheduled at the best hour for ITS network, instead of one publication per account and day. Cheaper — one text and one image per day — and it caps images at 7. Optional; defaults to `false`. **Not every template accepts it** (`allows_shared` in `GET /planner_templates`): `from_images` and `from_catalog` do not, because each of their publications carries a photo of its own, and sending `true` to them is rejected with 2106.
    """
    use_organization_context: NotRequired[bool]
    """
    Use the organization's brand context in the prompts. It is copied into the plan as a SNAPSHOT when the plan is created, so a retry or a regeneration uses the context the plan was asked with even if the configuration changed meanwhile. Optional; defaults to `true`.
    """


class Image(TypedDict):
    id_upload: NotRequired[str]
    description: NotRequired[str]


class Event(TypedDict):
    """
    `campaign`. The event and its date, already normalised to the start of ITS day in the plan timezone.
    """

    name: NotRequired[str]
    date: NotRequired[str]


class AiPlansAiPlanSourceImageInput(TypedDict):
    """
    One photo of `from_images`.
    """

    id_upload: str
    """
    An upload of the organization. It has to be an image: a video or an audio is rejected here, not later at publish time.
    """
    description: str
    """
    What is in the photo. **Mandatory on purpose**: without it the model writes about what it believes it sees, and with a product photo it gets the product wrong about half the time.
    """


class AiPlansAiPlanSourceInput(TypedDict):
    """
    The plan's source, as you SEND it. **One shape per template**: send only the fields of the template you chose — what it does not read is ignored, and what it needs and does not get is a 2112.

    It is validated when the plan is **created**, not when it is generated: the article is downloaded, the catalogue is read live and the product pictures are copied. So a source that does not work fails while the user is still there and can fix it, and what gets stored is a SNAPSHOT — a retry three days later does not depend on the article still being online or the product still being in the catalogue.

    | Template | Fields |
    | --- | --- |
    | `standard` | none — no source |
    | `from_images` | `images` |
    | `from_text` | `url` **or** `text` |
    | `from_catalog` | `id_account_catalog`, `product_catalog_id`, `products` |
    | `campaign` | `event_name`, `event_date` |
    """

    images: NotRequired[list[AiPlansAiPlanSourceImageInput]]
    """
    `from_images`. Your own photos, each with its own description, **in the order that tells the story**: the orchestrator picks one per publication and keeps its position in `source_index`, so photo 3 can be the "before" and photo 7 the "after". Up to 20 (`max_source_items`), and each one has to be an image upload of this organization (806 otherwise).
    """
    url: NotRequired[str]
    """
    `from_text`. The article the plan is written from. It is downloaded at creation, and only `http`/`https` addresses that resolve to a **public** IP are accepted — checked again before every redirect (2114). A page that answers something that is not text or HTML, or that carries no usable text once stripped, is a 2113: paste the text in `text` instead.
    """
    text: NotRequired[str]
    """
    `from_text`. The article pasted by hand. **It wins over `url`** when both come: pasting is what a user does when the download did not work (a paywall, a page that needs JavaScript), so re-downloading to ignore what they wrote would take away their only way out. Truncated to 12.000 characters — the cap is what keeps the estimate honest, since the real charge is per use. Under 200 characters it is not an article, it is the theme, which is `prompt` and another field (2116).
    """
    id_account_catalog: NotRequired[str]
    """
    `from_catalog`. Which account's catalogue the products come from. It has to belong to the organization (2103) and be on a network that supports products (2115). It only chooses the catalogue: the publications still go to every account in `accounts` — a LinkedIn account can publish a product from a Facebook catalogue.
    """
    product_catalog_id: NotRequired[str]
    """
    `from_catalog`. The catalogue itself, as the network identifies it.
    """
    products: NotRequired[list[str]]
    """
    `from_catalog`. Ids of the chosen products, **in the order they should tell the week**. Up to 12 — a unit here is not an id already in the database: it is a live read plus a real download inside this request, with the user waiting. Repeated ids are deduplicated. They are ALL checked against the catalogue before a single picture is downloaded (2112 naming the missing one), and each picture is copied into an upload of the organization: the network CDN URL expires, and a plan published weeks later would carry a broken file. Those uploads count against the storage quota.
    """
    event_name: NotRequired[str]
    """
    `campaign`. What the countdown is towards ("Rebajas de verano", "Apertura del local"). Over 120 characters it is **rejected, not truncated**: a name cut mid-word would come out that way in all seven publications, and whatever else needs saying goes in `prompt`.
    """
    event_date: NotRequired[str]
    """
    `campaign`. The day of the event. **Send a calendar day, `YYYY-MM-DD` — never an ISO instant.** A bare date is read in the plan's `options.timezone`, which is the whole point: `2026-09-15T00:00:00Z` is midnight UTC, that is the 14th in the afternoon in New York — a whole day off in a countdown, for half of America, with no error anywhere. It cannot fall before the plan week (`options.week_start`) nor more than 60 days after it (2112). And it does **not** move `publish_days`: if the event lands on a day you did not choose, the plan respects your choice and it is up to you to say so.
    """


class AiPlansAiPlanSourceProduct(TypedDict):
    """
    A product of the catalogue, copied when the plan was created.
    """

    external_id: NotRequired[str]
    """
    The id it has in the network catalogue.
    """
    name: NotRequired[str]
    description: NotRequired[str]
    price: NotRequired[str]
    """
    The price **exactly as the network returned it** ("9,99 €"). It is never converted: the same field is a number in other paths of Meta's API and there is no way to tell units from cents, and dividing by 100 "just in case" is precisely how a 10 € product gets advertised at 0,10 €. The prompt is told to copy it verbatim or to say nothing.
    """
    id_upload: NotRequired[str]
    """
    The product picture, copied into an upload of the organization. The network CDN URL expires; this one does not.
    """


class AppsClientApp(TypedDict):
    """
    An app: the credentials a third-party integration authenticates with.

    **The secret is not here.** It lives in Keycloak and is read with `GET /clients/{id_client}/apps/{id_app}/secret`, which needs a user token.
    """

    _id: str
    id_client: str
    id_user: NotRequired[str]
    """
    The user who created the app, when it was created from the panel.
    """
    name: str
    keycloak_client_idenfifier: str
    """
    The app's `client_id`.
    """
    allowed_domains: list[str]
    redirect_urls: list[str]
    webhook_url: NotRequired[str]
    """
    Where PlanVortex posts events, when one is configured.

    **The body is an array of changes, not a single object**, and it carries two signature headers computed with this app's secret over the **raw** body: `x-hub-signature` (`sha1=<hex>`) and `x-hub-signature-256` (`sha256=<hex>`). Verify against the bytes you received — parsing the JSON and re-serialising it changes them and the signature will not match.

    The events delivered today are `new_account`, `change_state_account`, `messages`, `messaging_postbacks`, `messaging_seen`, `messaging_error`, `comments` and `integration_error`. The payload is documented in the `comments` specification. Delivery is best effort: PlanVortex does not retry a webhook that fails.
    """
    creation_date: str
    deleted: bool
    """
    Deleting an app marks it instead of removing it — the Keycloak client is gone, so it can no longer get a token — and the listing filters those out.
    """
    deleted_date: NotRequired[str]


class AppsClientAppInput(TypedDict):
    name: str
    """
    A name for the app. Cannot be blank (error 525).
    """
    keycloak_client_idenfifier: str
    """
    The app's `client_id`, which is what you send to `POST /oauth/token`. It has to be unique across PlanVortex (error 534). The spelling of the field is historical and kept for compatibility.
    """
    allowed_domains: NotRequired[list[str]]
    """
    Origins allowed to call the API with this app's identity. Every entry has to be a valid URL (error 531).
    """
    redirect_urls: NotRequired[list[str]]
    """
    URLs the connect flow is allowed to come back to. A `redirect_uri` that is not in this list is refused when issuing a temporal connect token (error 532).
    """
    webhook_url: NotRequired[str]
    """
    Where PlanVortex posts events. Has to be a valid URL (error 535). See `ClientApp.webhook_url` for what arrives and how it is signed.
    """


class AppsOAuthError(TypedDict):
    """
    The error shape of the token endpoint, and **only** of the token endpoint. Every other endpoint in the API answers with `Error` instead.
    """

    error: Literal["invalid_request", "invalid_client", "unsupported_grant_type", "slow_down", "server_error"]
    error_description: NotRequired[str]


class AppsTokenRequest(TypedDict):
    grant_type: Literal["client_credentials"]
    """
    Only `client_credentials` is supported.
    """
    client_id: NotRequired[str]
    """
    The app's identifier. Can travel here or in `Authorization: Basic`.
    """
    client_secret: NotRequired[str]
    """
    The app's secret. Can travel here or in `Authorization: Basic`.
    """
    scope: NotRequired[str]
    """
    Optional. Passed through to the identity provider; there are no PlanVortex-defined scopes today.
    """


class AppsTokenResponse(TypedDict):
    access_token: str
    """
    Send it as `Authorization: Bearer <access_token>`.
    """
    token_type: str
    """
    Always `Bearer`.
    """
    expires_in: int
    """
    Seconds the token is valid for. Refresh shortly before it runs out; there is no refresh token.
    """
    scope: NotRequired[str]


class CatalogAspectRatios(TypedDict):
    """
    Accepted crops. `values` and `text` are parallel arrays: same index, same ratio.
    """

    values: list[float]
    """
    The ratio as a number (width divided by height), which is what validation compares against.
    """
    text: list[str]
    """
    The same ratio written the way a person reads it.
    """


class Regenerate(TypedDict):
    """
    What can be regenerated on a publication of this plan.
    """

    text: NotRequired[bool]
    image: NotRequired[bool]


class CatalogPlannerTemplateField(TypedDict):
    """
    One field of the source step. `uploads_with_description` (photos, each with its own description) and `catalog_products` (products read live from a connected catalogue) need a dedicated component; the rest are ordinary controls.
    """

    name: NotRequired[str]
    type: NotRequired[
        Literal[
            "text",
            "textarea",
            "url",
            "boolean",
            "select",
            "date",
            "uploads_with_description",
            "catalog_products",
        ]
    ]
    required: NotRequired[bool]
    default: NotRequired[Any]
    options: NotRequired[list[str]]
    max: NotRequired[int]
    """
    Cap in the field's **own units**: characters of a text, items of a list, and **days** of a `date` — the `event_date` of `campaign` carries 60, which is how far ahead of the plan week the countdown may point.
    """
    min: NotRequired[int]
    """
    Floor in the field's own units. Today only `from_text`: under 200 characters it is not an article, it is the theme, which is `prompt` and another field. Published for the same reason as `max` — without it your UI hardcodes the 200 and the user gets a 2116 AFTER pasting the text instead of while pasting it.
    """


CatalogSocialLimitsMap: TypeAlias = dict[str, int]
"""
One number per network. Every network in `/social_networks` is present.

**And a few keys are not a network.** Some limits depend on the *kind* of publication rather than on the network alone, and those get a compound key next to the plain one: `instagram_story`, `facebook_reel`, `telegram_media`. Read the plain key by default and the compound one when it applies.
"""


class ClientsAiScopeSetting(TypedDict):
    """
    AI provider configuration for a single scope (BYOK). On write, api_key is required the first time and is stored encrypted; on subsequent writes it can be omitted to keep the existing key (send only provider/model). On read, the api_key is NEVER returned — only has_api_key is exposed.
    """

    provider: Literal["openrouter", "openai", "google", "anthropic"]
    """
    Fixed catalogue of allowed providers. The provider must support the capability of the scope (text for orchestrator/text, image for image).
    """
    model: str
    """
    Model identifier at the chosen provider (e.g. google/gemini-3-flash).
    """
    api_key: NotRequired[str]
    """
    Provider API key. Write-only: accepted on PUT, stored encrypted (AES-256-GCM), never returned.
    """
    has_api_key: NotRequired[bool]
    """
    Read-only. True when an encrypted API key is stored for this scope.
    """


class ClientsAiSettings(TypedDict):
    """
    Per-scope AI provider configuration (BYOK). Only the scopes you send are touched; a scope set to `null` clears its configuration and returns that scope to PlanVortex credits. `orchestrator` and `text` need a text-capable provider, `image` needs an image-capable one. `video` is reserved for a later phase.
    """

    orchestrator: NotRequired[ClientsAiScopeSetting | None]
    """
    Configuration of the `orchestrator` scope. **`null` clears it** and returns the scope to PlanVortex credits.
    """
    text: NotRequired[ClientsAiScopeSetting | None]
    """
    Configuration of the `text` scope. **`null` clears it** and returns the scope to PlanVortex credits.
    """
    image: NotRequired[ClientsAiScopeSetting | None]
    """
    Configuration of the `image` scope. **`null` clears it** and returns the scope to PlanVortex credits.
    """


ClientsRolesClientPermissions: TypeAlias = Literal[
    "client:update",
    "client:read",
    "client:delete",
    "client_app:create",
    "client_app:update",
    "client_app:read",
    "client_app:delete",
    "client_roles:create",
    "client_roles:update",
    "client_roles:read",
    "client_roles:delete",
    "client_roles_users:read",
    "client_roles_users:create",
    "client_roles_users:delete",
    "client_organization:create",
    "client_organization:update",
    "client_organization:read",
    "client_organization:delete",
    "client_organization_roles:read",
    "client_organization_roles:create",
    "client_organization_roles:update",
    "client_organization_roles:delete",
    "client_organization_users_roles:read",
    "client_organization_users_roles:create",
    "client_organization_users_roles:delete",
    "client_organization_accounts:read",
    "client_organization_accounts:create",
    "client_organization_accounts:update",
    "client_organization_accounts:delete",
    "client_organization_files:read",
    "client_organization_files:create",
    "client_organization_files:update",
    "client_organization_files:delete",
    "client_organization_publications:read",
    "client_organization_publications:create",
    "client_organization_publications:update",
    "client_organization_publications:delete",
    "client_organization_publications_stats:read",
    "client_organization_account_stats:read",
]


ClientsRolesClientPermissionsList: TypeAlias = list[ClientsRolesClientPermissions]


class ClientsRolesClientPermissionsOne(TypedDict):
    permissions: NotRequired[ClientsRolesClientPermissionsList]


class ClientsRolesRole(TypedDict):
    name: NotRequired[str]
    permissions: NotRequired[ClientsRolesClientPermissionsList]


class ClientsRolesRoleInput(TypedDict):
    """
    Name and permission list of a role.
    """

    name: str
    """
    Role name, shown when inviting a user.
    """
    permissions: list[
        Literal[
            "client:update",
            "client:read",
            "client:delete",
            "client_app:create",
            "client_app:update",
            "client_app:read",
            "client_app:delete",
            "client_roles:create",
            "client_roles:update",
            "client_roles:read",
            "client_roles:delete",
            "client_roles_users:read",
            "client_roles_users:create",
            "client_roles_users:delete",
            "client_organization:create",
            "client_organization:update",
            "client_organization:read",
            "client_organization:delete",
            "client_organization_roles:read",
            "client_organization_roles:create",
            "client_organization_roles:update",
            "client_organization_roles:delete",
            "client_organization_users_roles:read",
            "client_organization_users_roles:create",
            "client_organization_users_roles:delete",
            "client_organization_accounts:read",
            "client_organization_accounts:create",
            "client_organization_accounts:update",
            "client_organization_accounts:delete",
            "client_organization_products:create",
            "client_organization_products:update",
            "client_organization_products:read",
            "client_organization_products:delete",
            "client_organization_files:read",
            "client_organization_files:create",
            "client_organization_files:update",
            "client_organization_files:delete",
            "client_organization_publications:read",
            "client_organization_publications:create",
            "client_organization_publications:update",
            "client_organization_publications:delete",
            "client_organization_publications_stats:read",
            "client_organization_account_stats:read",
            "client_organization_messages:create",
            "client_organization_messages:read",
            "client_organization_messages:delete",
            "client_organization_contacts:create",
            "client_organization_contacts:read",
            "client_organization_contacts:update",
            "client_organization_contacts:delete",
            "client_organization_ai_plans:create",
            "client_organization_ai_plans:read",
            "client_organization_ai_plans:update",
            "client_organization_ai_plans:delete",
        ]
    ]
    """
    Permissions granted by this role.
    """


class ClientsRolesRoleList(TypedDict):
    roles: NotRequired[list[ClientsRolesRole]]
    total: NotRequired[int]


class ClientsRolesRoleOne(TypedDict):
    rol: NotRequired[ClientsRolesRole]


class ClientsRolesUser(TypedDict):
    id: NotRequired[str]
    username: NotRequired[str]
    email: NotRequired[str]
    firstname: NotRequired[str]
    lastname: NotRequired[str]


class ClientsRolesUserList(TypedDict):
    users: NotRequired[list[ClientsRolesUser]]
    total: NotRequired[int]


class CommentsCommentActions(TypedDict):
    """
    What one network lets you do to a comment. Four booleans and never fewer: an absent key would be indistinguishable from an oversight.
    """

    reply: bool
    hide: bool
    delete_own: bool
    """
    Delete a comment **you** wrote. On Google Business this means your reply to a review — the review itself is never deletable.
    """
    delete_others: bool
    """
    Delete somebody else's comment
    """


class CommentsCommentAuthor(TypedDict):
    """
    Who wrote it. Embedded in the comment and **not** a contact: a YouTube commenter has no private inbox you could ever write to, so they get no contact record.
    """

    external_id: str
    """
    The author's id on the network. When the network gives none — Google Business publishes no identifier for a reviewer — this falls back to the review's own id, which means two reviews by the same person look like two different authors. There is no way around it from the API.
    """
    name: NotRequired[str]
    """
    Display name. Always present for a review, including anonymous ones, which get a placeholder rather than an empty string.
    """
    profile_pic: NotRequired[str]
    is_own: bool
    """
    Whether the connected account wrote it. This is what separates "delete mine" from "delete theirs", and what keeps your own replies out of the inbox.
    """


CommentsCommentNetworkName: TypeAlias = Literal[
    "facebook",
    "instagram",
    "twitter",
    "linkedin",
    "youtube",
    "google_business",
    "bluesky",
    "discord",
    "telegram",
]
"""
A network that has comments. Treat it as an open list: a new one is added before your integration hears about it.
"""


class CommentsIntegrationWebhookChange(TypedDict):
    """
    One change in the array PlanVortex posts to your app's `webhook_url`, when an **integration** stopped working: a revoked Google Drive token, a feed that no longer answers, a publication quota that ran out.

    It carries neither `id_account` nor `social_network`, because an integration hangs off the organization and not off any account — which is exactly why it is a type of its own. A consumer that only understands account changes sees a `field` it does not know and ignores it, which is what should happen.
    """

    field: Literal["integration_error"]
    id_integration: str
    id_organization: str
    provider: str
    """
    `google_drive` or `rss` today. **This list grows**: treat it as an open enumeration.
    """
    error_code: int
    """
    PlanVortex error code saying what went wrong. Integration codes live in the 2200-2299 range.
    """


class CommentsSocialCapabilities(TypedDict):
    """
    The coarse gates of one network
    """

    publications: bool
    messages: bool
    products: bool
    webhooks: bool
    persistent_menu: bool
    comments: bool


ContactChannel: TypeAlias = Literal[
    "facebook",
    "instagram",
    "linkedin",
    "tiktok",
    "twitter",
    "whatsapp",
    "youtube",
    "google_business",
    "bluesky",
    "discord",
    "email",
]
"""
Where a contact can be reached. Every social network that has messaging, plus `email` for a contact created by hand instead of arriving from a network.

**This list grows** with the networks: treat it as an open enumeration.
"""


class ContactExtraData(TypedDict):
    """
    Your own fields on the contact. The address block is known to PlanVortex; the six generic properties are yours to use, and they are what `extra_data` filters on.
    """

    place_id: NotRequired[str]
    address: NotRequired[str]
    city: NotRequired[str]
    state: NotRequired[str]
    country: NotRequired[str]
    country_code: NotRequired[str]
    zip_code: NotRequired[str | float]
    number: NotRequired[str | float]
    building: NotRequired[str | float]
    floor: NotRequired[str | float]
    door: NotRequired[str | float]
    coords: NotRequired[list[float]]
    """
    Longitude and latitude, in that order.
    """
    string_property: NotRequired[str]
    string_property2: NotRequired[str]
    boolean_property: NotRequired[bool]
    boolean_property2: NotRequired[bool]
    number_property: NotRequired[float]
    number_property2: NotRequired[float]


class ContactsSocialIdentifierInput(TypedDict):
    """
    The same person on one channel, as you SEND it. `_id` is optional here and PlanVortex mints one when it is missing — which is the difference with `SocialIdentifier`, where it always travels back.
    """

    _id: NotRequired[str]
    """
    Only when you are keeping an identifier the API already gave you.
    """
    external_identifier: NotRequired[str]
    """
    The contact id on that channel — the phone number on WhatsApp, the PSID on Messenger. Optional in the model, but a contact without it cannot be written to, and it is what deduplicates on create.
    """
    social_network: ContactChannel


class AvailableBlocks(TypedDict):
    """
    Which blocks the caller was allowed to see. A `false` here is a permission (or plan) answer; a block that is `true` but empty means there is no data.
    """

    health: bool
    publications: bool
    publication_metrics: bool
    account_metrics: bool
    plan_use: bool
    ai_plans: bool
    messages: bool


class ByStateItem(TypedDict):
    state: NotRequired[str]
    total: NotRequired[int]


class Messages(TypedDict):
    unread: int


class Error(TypedDict):
    code: int
    message: str
    data: NotRequired[dict[str, Any]]


class DashboardDashboardAiPlanRef(TypedDict):
    """
    The most recent AI plan, projected: enough to tell at a glance whether one is still generating, failed, or is waiting to be validated. `publications` are identifiers here.
    """

    _id: str
    state: Literal["pending", "generating", "generated", "validated", "failed", "cancelled"]
    prompt: NotRequired[str]
    credits_spent: NotRequired[int]
    publications: NotRequired[list[str]]
    creation_date: str
    generation_end_date: NotRequired[str]
    error: NotRequired[Error]


class PublicationError(TypedDict):
    code: int
    message: str
    data: NotRequired[dict[str, Any]]


class DashboardDashboardRange(TypedDict):
    """
    The range that was actually used, plus the previous period of exactly the same length. The previous one is not "last month": comparing 30 days against a calendar month would move the delta with the calendar.
    """

    from_date: str
    to_date: str
    previous_from_date: str
    previous_to_date: str


DashboardMetricName: TypeAlias = Literal[
    "impressions",
    "reach",
    "engagement",
    "likes",
    "comments",
    "shares",
    "saves",
    "clicks",
    "video_views",
    "profile_views",
    "followers",
    "followers_gained",
]
"""
A metric in PlanVortex's common vocabulary. Each network reports what it reports and PlanVortex translates it; a metric a network does not publish is absent, never zero.
"""


class DashboardMetricRow(TypedDict):
    group: str | None
    """
    The value of the axis: the day, the network or the account identifier. **`null` when `group_by` was `total`** — the field is always there, the value is not always a string.
    """
    name: DashboardMetricName
    value: float


class ByDayItem(TypedDict):
    day: NotRequired[str]
    """
    `YYYY-MM-DD`, in UTC.
    """
    state: NotRequired[str]
    total: NotRequired[int]


class Error1(TypedDict):
    """
    Error payload returned by every failing request.

    **Classify by `code`, never by the HTTP status.** Every domain error travels with HTTP 400 — an expired token, a disconnected account, an exhausted plan quota and a text that is too long are all 400. Only error 520 (permissions) answers 401, and an unexpected failure answers 500.

    The catalogue grows with the product, so treat an unknown `code` as a generic failure instead of rejecting it.
    """

    message: str
    """
    Human readable description of the error.
    """
    code: int
    """
    PlanVortex error code. Ranges: 500-544 auth, tokens and client apps · 601-612 user · 700-715 social accounts · 800-810 files · 900-960 publications · 1000-1003 general · 1100-1111 organizations · 1200-1207 roles · 1300-1307 client plan · 1400-1408 organization plan · 1500-1512 messaging · 1600-1601 contacts · 1900-1906 payments · 2000-2099 products · 2100-2199 AI plans · 2200-2299 integrations.
    """
    data: NotRequired[dict[str, Any]]
    """
    Extra context attached to the error, when there is any.
    """


class AspectRatio(TypedDict):
    """
    Width divided by height, as a number and as a person writes it.
    """

    value: float
    text: str


class FileProperties(TypedDict):
    """
    Measurements taken when the file was ingested. Always present on an upload.
    """

    width: int
    """
    `0` on a file whose dimensions could not be read.
    """
    height: int
    duration: int
    """
    Seconds. `0` on an image.
    """
    size_in_bytes: int
    aspect_ratio: AspectRatio
    """
    Width divided by height, as a number and as a person writes it.
    """
    allowed_social_networks: list[str]
    """
    The networks whose accepted crops this file's ratio matches, with a 0.1 margin. It is about the RATIO only: a network listed here can still reject the file for its duration or its weight (see `GET /social_limits`).
    """


class IntegrationsGoogleDriveConnectRequest(TypedDict):
    provider: Literal["google_drive"]
    code: str
    """
    OAuth code returned to the redirect of connect_link. Single-use.
    """


class ConfigField(TypedDict):
    name: str
    type: Literal["url", "text", "textarea", "boolean", "accounts", "select"]
    required: NotRequired[bool]
    default: NotRequired[Any]
    options: NotRequired[list[str]]


IntegrationsIntegrationProviderName: TypeAlias = Literal["google_drive", "rss"]


class IntegrationsRssConfig(TypedDict):
    """
    Provider-specific configuration. Empty for google_drive.
    """

    url: NotRequired[str]
    id_accounts: NotRequired[list[str]]
    publication_type: NotRequired[str]
    template: NotRequired[str]
    auto_publish: NotRequired[bool]
    import_image: NotRequired[bool]
    seen_guids: NotRequired[list[str]]
    """
    Entries already processed (last 200, FIFO). Owned by the job: filled at connection time with everything the feed already had, so the back catalogue is never published.
    """
    last_checked: NotRequired[str]


class IntegrationsRssConnectRequest(TypedDict):
    provider: Literal["rss"]
    url: str
    """
    Public feed URL (RSS 2.0 or Atom). Private or authenticated feeds are not supported.
    """
    id_accounts: list[str]
    """
    Accounts of this organization the entries will be published to. At least one, otherwise 2206.
    """
    publication_type: NotRequired[str]
    """
    Optional; defaults to `"profile"`.
    """
    template: NotRequired[str]
    """
    Text template. Placeholders: {{title}}, {{link}}, {{summary}}. The result is truncated to the character limit of each network, taken from GET /social_limits. Optional; defaults to `"{{title}}\\n\\n{{link}}"`.
    """
    auto_publish: NotRequired[bool]
    """
    false (the default) creates each entry as a draft for review. true schedules it a few minutes out, so there is a window to catch it before it goes out on the client's networks. Optional; defaults to `false`.
    """
    import_image: NotRequired[bool]
    """
    Import the entry's featured image (enclosure, media:content or the first <img> of the content) into the library and attach it. Optional; defaults to `true`.
    """


class FilesUrl(TypedDict):
    url: NotRequired[str]
    mime_type: NotRequired[str]


MessageType: TypeAlias = Literal[
    "simple_message",
    "file_message",
    "comment_message",
    "publication_message",
    "quick_reply_message",
    "button_message",
    "elements_message",
    "postback_message",
    "template_message",
    "interactive_message",
]
"""
What kind of message this is. `simple_message` and `file_message` work everywhere; the rest are network-specific shapes.
"""


class MessagesConversationTotals1(TypedDict):
    """
    Two different answers, not one with optional fields: **without** `group_by` you get `{total}`, **with** it you get `{stats, group}`. Never both.
    """

    total: int
    """
    Conversations in the range. A conversation is one contact on one day, so the same person writing on Monday and on Tuesday counts twice.
    """


class Stat1(TypedDict):
    groupValue: int
    """
    The **number** Mongo's `$dayOfYear` / `$month` / `$year` gives, not a date: 240 for day, 8 for month, 2026 for year. Two years in the same `day` series collide on the same value — narrow the range instead.
    """
    totalConversations: int


class MessagesConversationTotals2(TypedDict):
    """
    Two different answers, not one with optional fields: **without** `group_by` you get `{total}`, **with** it you get `{stats, group}`. Never both.
    """

    group: Literal["day", "month", "year"]
    """
    The grouping that was applied.
    """
    stats: list[Stat1]
    """
    The series, sorted ascending. Empty when the range has no conversations.
    """


MessagesConversationTotals: TypeAlias = MessagesConversationTotals1 | MessagesConversationTotals2
"""
Two different answers, not one with optional fields: **without** `group_by` you get `{total}`, **with** it you get `{stats, group}`. Never both.
"""


class NormalizedMetrics(TypedDict):
    """
    Metrics translated to a **common vocabulary** shared by every network, which is what makes two networks comparable and summable (each network names them differently: `page_post_engagements`, `total_interactions`, `views`…).

    **A missing key means the network does not publish that metric** — it is never an implicit zero. A key present with value `0` means it was measured and came out zero. Never default a missing key to 0 when displaying it.

    `engagement` is the network's own total when it provides one, and otherwise the sum of likes, comments, shares, saves and clicks. Video views are deliberately excluded from it: a view is not an interaction.
    """

    impressions: NotRequired[int]
    """
    Times the content was shown (not unique)
    """
    reach: NotRequired[int]
    """
    Unique users reached
    """
    engagement: NotRequired[int]
    """
    Total interactions
    """
    likes: NotRequired[int]
    comments: NotRequired[int]
    shares: NotRequired[int]
    saves: NotRequired[int]
    clicks: NotRequired[int]
    video_views: NotRequired[int]
    profile_views: NotRequired[int]
    followers: NotRequired[int]
    """
    Followers accumulated at that date, not the day's gain.
    """
    followers_gained: NotRequired[int]
    """
    Followers gained that day.
    """


class OrganizationsRolesOrganizationRole(TypedDict):
    """
    An organization role as the API returns it. Note it exposes `total_users` and never the list of user identifiers.
    """

    _id: NotRequired[str]
    """
    Role identifier.
    """
    id_organization: NotRequired[str]
    """
    Organization the role belongs to.
    """
    name: NotRequired[str]
    """
    Role name.
    """
    default: NotRequired[bool]
    """
    Whether this is a default role. Default roles cannot be updated or deleted, and their last user cannot be removed.
    """
    permissions: NotRequired[
        list[
            Literal[
                "organization:create",
                "organization:update",
                "organization:read",
                "organization:delete",
                "organization_roles:create",
                "organization_roles:update",
                "organization_roles:read",
                "organization_roles:delete",
                "organization_users_roles:read",
                "organization_users_roles:create",
                "organization_users_roles:delete",
                "accounts:create",
                "accounts:update",
                "accounts:read",
                "accounts:delete",
                "products:create",
                "products:update",
                "products:read",
                "products:delete",
                "files:create",
                "files:update",
                "files:read",
                "files:delete",
                "publications:create",
                "publications:update",
                "publications:read",
                "publications:delete",
                "account_stats:read",
                "publication_stats:read",
                "messages:create",
                "messages:read",
                "messages:delete",
                "contacts:create",
                "contacts:read",
                "contacts:update",
                "contacts:delete",
                "ai_plans:create",
                "ai_plans:read",
                "ai_plans:update",
                "ai_plans:delete",
            ]
        ]
    ]
    """
    Organization permissions granted by this role.
    """
    total_users: NotRequired[int]
    """
    Number of users in the role.
    """
    creation_date: NotRequired[str]
    """
    When the role was created.
    """


class OrganizationsRolesOrganizationRoleInput(TypedDict):
    """
    Name and permission list of an organization role. Both properties overwrite the stored value.
    """

    name: str
    """
    Role name. Must be unique inside the organization.
    """
    permissions: list[
        Literal[
            "organization:create",
            "organization:update",
            "organization:read",
            "organization:delete",
            "organization_roles:create",
            "organization_roles:update",
            "organization_roles:read",
            "organization_roles:delete",
            "organization_users_roles:read",
            "organization_users_roles:create",
            "organization_users_roles:delete",
            "accounts:create",
            "accounts:update",
            "accounts:read",
            "accounts:delete",
            "products:create",
            "products:update",
            "products:read",
            "products:delete",
            "files:create",
            "files:update",
            "files:read",
            "files:delete",
            "publications:create",
            "publications:update",
            "publications:read",
            "publications:delete",
            "account_stats:read",
            "publication_stats:read",
            "messages:create",
            "messages:read",
            "messages:delete",
            "contacts:create",
            "contacts:read",
            "contacts:update",
            "contacts:delete",
            "ai_plans:create",
            "ai_plans:read",
            "ai_plans:update",
            "ai_plans:delete",
        ]
    ]
    """
    Complete list of organization permissions granted by this role.
    """


class OrganizationsRolesOrganizationRoleList(TypedDict):
    roles: NotRequired[list[OrganizationsRolesOrganizationRole]]
    total: NotRequired[int]
    """
    Total number of roles in the organization, ignoring pagination.
    """


class OrganizationsRolesOrganizationRoleOne(TypedDict):
    rol: NotRequired[OrganizationsRolesOrganizationRole]


class OrganizationsRolesPermissionList(TypedDict):
    permissions: NotRequired[
        list[
            Literal[
                "organization:create",
                "organization:update",
                "organization:read",
                "organization:delete",
                "organization_roles:create",
                "organization_roles:update",
                "organization_roles:read",
                "organization_roles:delete",
                "organization_users_roles:read",
                "organization_users_roles:create",
                "organization_users_roles:delete",
                "accounts:create",
                "accounts:update",
                "accounts:read",
                "accounts:delete",
                "products:create",
                "products:update",
                "products:read",
                "products:delete",
                "files:create",
                "files:update",
                "files:read",
                "files:delete",
                "publications:create",
                "publications:update",
                "publications:read",
                "publications:delete",
                "account_stats:read",
                "publication_stats:read",
                "messages:create",
                "messages:read",
                "messages:delete",
                "contacts:create",
                "contacts:read",
                "contacts:update",
                "contacts:delete",
                "ai_plans:create",
                "ai_plans:read",
                "ai_plans:update",
                "ai_plans:delete",
            ]
        ]
    ]


class Role(TypedDict):
    _id: NotRequired[str]
    name: NotRequired[str]


class OrganizationsRolesUserInOrganization(TypedDict):
    id: NotRequired[str]
    """
    User identifier.
    """
    username: NotRequired[str]
    email: NotRequired[str]
    enabled: NotRequired[bool]
    """
    `false` while an invitation is still pending acceptance.
    """
    firstname: NotRequired[str]
    lastname: NotRequired[str]
    roles: NotRequired[list[Role]]
    """
    Roles this user holds in the organization.
    """


class OrganizationsRolesUserInOrganizationList(TypedDict):
    users: NotRequired[list[OrganizationsRolesUserInOrganization]]
    total: NotRequired[int]
    """
    Total number of users, ignoring pagination. May be higher than the length of `users` if some user no longer exists in the identity provider.
    """


class OrganizationsSocialCredentialsInput(TypedDict):
    """
    Credentials of the organization's own Discord application. **Write-only**: nothing sent here ever comes back.

    All three are required the first time. Afterwards, what you leave out is kept — so the `client_id` can be fixed without resending the secrets.
    """

    client_id: NotRequired[str]
    """
    The Discord application's id (its *Application ID*, which is also its client id).
    """
    client_secret: NotRequired[str]
    """
    The application's OAuth2 secret. Stored encrypted.
    """
    bot_token: NotRequired[str]
    """
    The bot's token. Stored encrypted, and validated against Discord before anything is saved.
    """


class OrganizationsUser(TypedDict):
    id: NotRequired[str]
    username: NotRequired[str]
    email: NotRequired[str]
    firstname: NotRequired[str]
    lastname: NotRequired[str]


class OrganizationsUserList(TypedDict):
    users: NotRequired[list[OrganizationsUser]]
    total: NotRequired[int]


class PlanData(TypedDict):
    """
    The resources a plan grants. On a client it is what was contracted; on an organization, the slice of it that was assigned. The sum across all the organizations of a client can never exceed what the client has contracted.
    """

    accounts: int
    """
    Social accounts that may be connected.
    """
    publications: int
    """
    Publications that may be sent per month.
    """
    users: int
    """
    Users with access.
    """
    space: float
    """
    Storage, in GB.
    """
    integrations: int
    """
    Connections to a third-party tool material is pulled from (Google Drive, an RSS feed). Not the same thing as an app: an app is API access, and it is a Custom-plan feature of its own.
    """
    twitter_credits: NotRequired[int]
    """
    Monthly X (Twitter) credits. X bills per use: 15 per post, 200 if the text contains a link, 15 per deletion, 1 per stat read, 1 per timeline item. The pool resets on the 1st of each calendar month and does not roll over.
    """
    ai_credits: NotRequired[int]
    """
    Monthly AI credits (1 credit = $0.001 of provider cost): 15 per plan orchestration pass, 2 per generated text, 70 per generated image. Resets monthly and does not roll over. A client using its own provider key (BYOK) does not consume them in that scope.
    """
    artificial_inteligence: NotRequired[bool]
    """
    Whether AI generation is enabled.
    """
    whatsapp: NotRequired[bool]
    """
    Whether WhatsApp may be connected.
    """
    stats: NotRequired[bool]
    """
    Whether statistics collection is enabled.
    """


class ProductsProductCatalog(TypedDict):
    """
    A Meta commerce catalogue, as the network returns it.
    """

    id: NotRequired[str]
    name: NotRequired[str]
    product_count: NotRequired[int]
    feed_count: NotRequired[int]
    default_image_url: NotRequired[str]
    is_local_catalog: NotRequired[bool]
    is_catalog_segment: NotRequired[bool]


class ProductsProductCatalogInput(TypedDict):
    name: str


class ProductsProductInput(TypedDict):
    """
    A product in Meta's Commerce vocabulary. Only the fields PlanVortex depends on are listed; anything else Meta accepts travels through untouched.
    """

    id: NotRequired[str]
    """
    Send it to update an existing product. Leave it out to create one.
    """
    retailer_id: str
    """
    **Your** identifier for the product. It is what ties the Meta catalogue to your system.
    """
    name: str
    description: NotRequired[str]
    price: int
    """
    In **cents** of `currency`. 1250 is 12,50.
    """
    currency: str
    """
    ISO 4217 code, for example `EUR`.
    """
    image_url: str
    additional_image_urls: NotRequired[list[str]]
    url: NotRequired[str]
    """
    The product's page on your site.
    """
    availability: NotRequired[
        Literal[
            "in stock",
            "out of stock",
            "preorder",
            "available for order",
            "discontinued",
            "pending",
            "mark_as_sold",
        ]
    ]
    condition: NotRequired[
        Literal[
            "new", "refurbished", "used", "used_like_new", "used_good", "used_fair", "cpo", "open_box_new"
        ]
    ]
    brand: NotRequired[str]
    category: NotRequired[str]
    color: NotRequired[str]


class PublicationStats(TypedDict):
    """
    Raw, per-network metrics for a publication. Only the fields that belong to the publication's own social network are returned.

    **An absent field is not a zero.** A field is present only when the network actually reported it; `0` means the network measured zero. This matters most on X (Twitter), where metrics are split into groups with different access levels: `public_metrics` (likes, replys, retwets, quotes, bookmarks, impressions) is always available, while clicks, the pre-computed `engagement` and the video playback quartiles come from X's non-public metrics — only for your own posts, within 30 days of publishing, and only if the app is entitled to them. When they are unavailable they are omitted rather than returned as `0`. Do not default missing fields to zero when displaying them.

    On `discord` there are only two: `likes` (the reactions on the message) and `comments` (the messages in its thread). There is no impressions figure anywhere in Discord's API, so engagement is computed over the server's member count.

    On `bluesky` there are no impressions and no reach either — only the public counters — so engagement is computed over followers.

    On `telegram` there are two as well, and **neither of them is asked for**: the Bot API has no method that returns a message's metrics, so `reactions` arrives on its own through the bot and `comments` is counted in PlanVortex's own inbox. There are no impressions, no reach, no views and no forwards to be had anywhere in it, so engagement is computed over followers.
    """

    likes: NotRequired[int]
    loves: NotRequired[int]
    wows: NotRequired[int]
    hahas: NotRequired[int]
    sorrys: NotRequired[int]
    angers: NotRequired[int]
    impressions: NotRequired[int]
    negative_feedback: NotRequired[int]
    clicks: NotRequired[int]
    page_likes: NotRequired[int]
    video_views: NotRequired[int]
    comments: NotRequired[int]
    follows: NotRequired[int]
    profile_activity: NotRequired[int]
    profile_visits: NotRequired[int]
    shares: NotRequired[int]
    reach: NotRequired[int]
    saved: NotRequired[int]
    retwets: NotRequired[int]
    replys: NotRequired[int]
    quotes: NotRequired[int]
    url_link_clicks: NotRequired[int]
    """
    X (Twitter). Clicks on links in the post. Comes from X's non-public metrics: omitted when unavailable.
    """
    user_profile_clicks: NotRequired[int]
    """
    X (Twitter). Clicks on the author's profile from the post. Comes from X's non-public metrics: omitted when unavailable.
    """
    bookmarks: NotRequired[int]
    """
    X (Twitter). Times the post was saved to bookmarks. Always available (`public_metrics`). Normalised as `saves` and counted towards engagement.
    """
    engagement: NotRequired[int]
    """
    Total interactions. LinkedIn reports it directly. On X it comes from the non-public metrics and, when present, takes precedence over the sum of the individual interactions — it includes interactions the API does not break down.
    """
    playback_0_count: NotRequired[int]
    """
    X (Twitter). Video playbacks that reached 0% — i.e. started. Comes from X's non-public metrics: omitted when unavailable.
    """
    playback_25_count: NotRequired[int]
    """
    X (Twitter). Video playbacks that reached 25%. Comes from X's non-public metrics: omitted when unavailable.
    """
    playback_50_count: NotRequired[int]
    """
    X (Twitter). Video playbacks that reached 50%. Comes from X's non-public metrics: omitted when unavailable.
    """
    playback_75_count: NotRequired[int]
    """
    X (Twitter). Video playbacks that reached 75%. Comes from X's non-public metrics: omitted when unavailable.
    """
    playback_100_count: NotRequired[int]
    """
    X (Twitter). Video playbacks that reached 100%. Comes from X's non-public metrics: omitted when unavailable.
    """
    share: NotRequired[int]
    shareMentions: NotRequired[int]
    views: NotRequired[int]
    reactions: NotRequired[int]
    """
    Telegram. Every reaction on the post, all emoji together. It is the **complete state and not an increment**: it goes down when somebody takes theirs back. Normalised as `likes`.
    """
    reactions_by_emoji: NotRequired[dict[str, int]]
    """
    Telegram. The same total broken down by emoji. Reactions with a custom emoji are grouped under a single key: their identifier means nothing outside the server that created it.
    """


class PublicationsPublicationInput(TypedDict):
    """
    Body accepted when creating or updating a publication. Only these properties are read; anything else in the payload is ignored.
    """

    social_network: NotRequired[
        Literal[
            "facebook",
            "instagram",
            "twitter",
            "linkedin",
            "tiktok",
            "whatsapp",
            "youtube",
            "bluesky",
            "discord",
            "telegram",
        ]
    ]
    """
    Network the publication targets. **Required when creating**: the request fails with error 702 if it is missing or not one of these values. It must match the network of the account in the path.

    Not every connectable network publishes — a local business listing receives reviews, not posts — so this list is shorter than the one in `GET /social_networks`. Ask `GET /allowed_social_publications` rather than hardcoding it, because it grows.
    """
    text: NotRequired[str]
    """
    Body text of the publication. Either `text` or at least one entry in `files` is required: if both are empty the publication is still created, but in state `withErrors` with `publication_errors[].code = 915`. Maximum length depends on the network. On YouTube this is the video **description** (5,000 characters), and the publication must carry exactly one video file and no images — otherwise it is created in state `withErrors` with `publication_errors[].code = 943`. For X (Twitter), a text containing a link costs 200 credits instead of 15.

    **On Telegram the limit depends on what else the publication carries**: 4.096 characters while it is text only, and **1.024** the moment it has an image or a video, because then the text is the caption of a photo, a video or an album and no longer a message. Over the limit it is created in state `withErrors` with `publication_errors[].code = 967`, whose `data` carries `characters`, `max_characters` and `has_media`. Both numbers are published, as `characters.telegram` and `characters.telegram_media` in `GET /social_limits`.
    """
    title: NotRequired[str]
    """
    Title for the publication. Only some networks use it: optional on LinkedIn, and **required on YouTube**, where it is the video title and must be 100 characters or fewer — a publication without it, or with a longer one, is created in state `withErrors` with `publication_errors[].code = 944`.
    """
    files: NotRequired[list[str]]
    """
    Identifiers of uploads previously created through the uploads endpoints, attached to this publication.
    """
    publish_date: NotRequired[str]
    """
    When the publication must go out. If omitted, it is published immediately. An invalid date returns error 938.
    """
    name: NotRequired[str]
    """
    Internal name for the publication. Useful for grouping; never shown on the social network.
    """
    publication_type: NotRequired[Literal["profile", "page", "group", "reels", "stories"]]
    """
    Defaults to `profile`. Not every network accepts every type, and an unsupported combination returns error 923. Allowed values are: facebook and instagram -> profile, reels, stories; twitter, linkedin, tiktok and youtube -> profile; whatsapp -> stories. YouTube has no separate type for Shorts: any vertical video of 3 minutes or less is classified as one automatically.
    """
    state: NotRequired[Literal["ready", "withErrors", "sended", "draft", "publishing"]]
    """
    Send `draft` to store the publication without publishing it. If omitted, the state is resolved automatically: `ready` when everything validates, `withErrors` otherwise. Forcing `sended` marks it as published without actually sending it.
    """


class Latest(TypedDict):
    """
    The most recent row of the series, with the network's raw payload attached. Absent when the series is empty.
    """

    collected_date: str
    metrics: NormalizedMetrics
    engagement_base: NotRequired[Literal["reach", "impressions", "followers"]]
    raw: NotRequired[PublicationStats]
    """
    What the network answered, unprocessed.
    """


class PublicationsPublicationStatsPoint(TypedDict):
    """
    One measurement of a publication. `metrics` is the **running total** at `collected_date`, not that day's increment.
    """

    collected_date: str
    """
    Day of the measurement, normalized to 00:00
    """
    metrics: NormalizedMetrics
    engagement_base: NotRequired[Literal["reach", "impressions", "followers"]]
    """
    What the engagement rate is divided by. Two rows with different bases are not comparable: state the base whenever you put them in the same table.
    """


class Range(TypedDict):
    """
    The resolved range and the immediately preceding period of the same length, which is what `summary.previous_total` covers.
    """

    from_date: NotRequired[str]
    to_date: NotRequired[str]
    previous_from_date: NotRequired[str]
    previous_to_date: NotRequired[str]


class ByNetworkItem2(TypedDict):
    social_network: NotRequired[str]
    publications: NotRequired[int]
    metrics: NotRequired[NormalizedMetrics]


class Summary(TypedDict):
    """
    Aggregates for the whole organization in the range. Omitted when `summary=false`.
    """

    total: NotRequired[NormalizedMetrics]
    previous_total: NotRequired[NormalizedMetrics]
    by_network: NotRequired[list[ByNetworkItem2]]


class SocialCredentials(TypedDict):
    """
    What can be read back about an organization's own application. The secrets are not here and never will be.
    """

    client_id: NotRequired[str]
    application_name: NotRequired[str]
    """
    The application's name, as Discord returned it when the credentials were validated.
    """
    verified_date: NotRequired[str]
    """
    When the credentials were last validated against Discord.
    """
    has_client_secret: NotRequired[bool]
    """
    Whether a secret is stored. Never the secret.
    """
    has_bot_token: NotRequired[bool]
    """
    Whether a bot token is stored. Never the token.
    """


class SocialIdentifier(TypedDict):
    """
    The same person, on one channel.
    """

    _id: str
    external_identifier: NotRequired[str]
    """
    Identifier of the contact on that channel.
    """
    social_network: ContactChannel
    last_send_date: NotRequired[str]
    """
    Last message received from the contact. On WhatsApp it is what opens the 24-hour window in which a free-form message is allowed.
    """


SocialNetwork: TypeAlias = Literal[
    "facebook",
    "instagram",
    "linkedin",
    "tiktok",
    "twitter",
    "whatsapp",
    "youtube",
    "google_business",
    "bluesky",
    "discord",
    "telegram",
]
"""
A social network supported by PlanVortex.

**This list grows.** Treat it as an open enumeration: a client that rejects an unknown value breaks the day a network is added, which happens several times a year. Not every network does everything — ask `GET /social_capabilities`.
"""


class StatsSettings(TypedDict):
    """
    Statistics collection settings. Only `auto_refresh_twitter` is read; any other key is ignored.
    """

    auto_refresh_twitter: NotRequired[bool]
    """
    Whether the background job refreshes X (Twitter) statistics automatically. Every other network is free and always refreshed; X charges 1 credit per read, so this is the one setting that makes the robot spend the client's credits. Anything other than an explicit `false` is treated as `true`.
    """


class Success(TypedDict):
    """
    What an operation with nothing to return answers. A failure never looks like this: it comes back as an `Error` with HTTP 400.
    """

    success: bool


class FileExternal(TypedDict):
    social_network: SocialNetwork
    external_identifier: str
    external_url: str


class Upload(TypedDict):
    """
    A file in the organization's library.

    **`public_path` is a signed, temporary URL, not a permanent link.** Do not store it: it expires. Ask for the upload again when you need it.
    """

    _id: str
    id_organization: str
    name: str
    file_type: Literal["video", "image"]
    file_format: Literal["mp4", "jpeg", "gif", "png", "jpg"]
    """
    The format of the stored bytes. `heic`/`heif` are accepted at the door — that is what an iPhone produces — but never stored: they are converted to JPEG while being ingested, so an upload never comes back with one.
    """
    file_properties: FileProperties
    file_externals: list[FileExternal]
    """
    Where this file ended up on each network it has been published to. Some networks keep their own copy and give it an identifier that is reused instead of uploading the bytes again.
    """
    cover_image: NotRequired["Upload"]
    """
    Cover of a video, which is another upload of its own and comes back already resolved. It never appears on its own in the library listing.
    """
    cover_offset: NotRequired[int]
    """
    Point of the video, in milliseconds, used as the cover frame.
    """
    is_temporal: bool
    """
    `true` on a file the platform created for itself — a crop made to fit a network's aspect ratio. Temporary files are not part of the library listing.
    """
    public_path: str
    """
    Download URL. IMPORTANT: it is a TEMPORARY, signed URL, not a permanent link. It expires (24 hours by default) and must not be stored or shared: ask for the upload again to get a valid one. The URL stays byte-identical within the same hour, so it can be cached for that long.
    """
    creation_date: str


class UploadsUploadList(TypedDict):
    uploads: list[Upload]
    total: int


class UploadsUploadOne(TypedDict):
    upload: Upload


class Account(TypedDict):
    """
    A social account connected to an organization.

    On `discord` and on `telegram` an account is a **channel**, not a profile: publishing to two Discord channels of the same server — or to two Telegram channels of the same brand — costs two accounts of the plan.

    `error_code` other than `0` means the connection is broken — an expired token, a permission taken away — and the account has to be connected again. On `telegram` nothing expires, because there is no account token: what breaks the connection is the bot being removed from the channel or losing its permission to post there (error 968).
    """

    _id: str
    id_organization: str
    id_client: str
    """
    The client the organization hangs from. Denormalized here for the plan checks.
    """
    name: str
    """
    Display name of the profile, page or channel.
    """
    username: NotRequired[str]
    """
    The handle, when the network has one. Absent on the networks that do not (a Discord channel, a WhatsApp number, a Google Business listing) and on a **private** Telegram channel, which has no `@name` at all — only public ones do. That is also why a private channel's publications come back with no `url`.
    """
    social_network: SocialNetwork
    """
    Network this account belongs to. **Not every network publishes**: `whatsapp` is a messaging channel with no feed, and `google_business` is a local business listing that receives reviews — both can be connected and both appear here, but neither accepts publications (see `GET /social_capabilities`).
    """
    creation_date: str
    error_code: int
    """
    `0` is a healthy account. Anything else is a PlanVortex error code explaining why the connection stopped working; the account keeps its data but cannot be used until it is reconnected.
    """
    image: NotRequired[str]
    """
    Avatar URL as the network publishes it. Empty string when there is none.
    """
    followers_count: NotRequired[int]
    """
    Followers the network reports. Absent on an account that has never been measured. On `telegram` it is the channel's member count, and it is the **only** audience figure that network publishes: there are no views, no impressions and no reach anywhere in the Bot API.
    """
    next_stats_update: NotRequired[str]
    """
    When the collector will ask the network for this account's stats again.
    """
    next_comments_update: NotRequired[str]
    """
    When the collector will read this account's comments again. Only on the networks whose comments hang off the account and not off a publication — today, `google_business`, whose reviews belong to the listing.
    """
    private_message_link: NotRequired[str]
    """
    A link that opens a private chat with this account (`m.me`, `ig.me`, `wa.me`). Absent on every other network.
    """


class AccountsAccountList(TypedDict):
    accounts: list[Account]
    total: int


class AccountsAccountOne(TypedDict):
    account: Account


class Link(TypedDict):
    social_network: SocialNetwork
    link: str
    """
    The network's authorization URL. Send the user there. **Empty when `authorization.type` is `meta_embedded_signup`** — WhatsApp has no URL to give at all.

    On `telegram_bot` it is filled in, and it still is not somewhere to redirect: it opens a Telegram chat, not an authorization screen. Open it in another tab.
    """
    authorization: AccountsSocialAuthorizationMethod


class AccountsSocialLinksList(TypedDict):
    links: list[Link]
    """
    One entry per network that can be connected right now.
    """


class AiPlansAiPlanCreateRequest(TypedDict):
    prompt: str
    """
    Theme prompt written by the user.
    """
    template: NotRequired[Literal["standard", "from_images", "from_text", "from_catalog", "campaign"]]
    """
    What the plan is generated FROM. Optional; defaults to `standard`, which is exactly what every plan did before templates existed — send nothing and nothing changes.

    A template is the **source** of the content, not a different flow: `shared`, `publish_days`, `language`, `tone` and the images stay cross-cutting options, and each template declares which of them it accepts. Sending one it does not accept is a 2106, not a silent ignore.

    Read the list, the costs and the fields from `GET /planner_templates`; do not hardcode them.
    """
    source: NotRequired[AiPlansAiPlanSourceInput]
    """
    The source itself. Which fields it carries depends on `template`. Required for every template except `standard`, and validated at creation — 2112, 2113, 2114, 2115 or 2116 come back while the user is still there.
    """
    accounts: list[str]
    """
    Account ids (belonging to the organization) to generate the plan for.
    """
    options: NotRequired[AiPlansAiPlanOptionsInput]


class AiPlansAiPlanSource(TypedDict):
    """
    The plan source as it was STORED: a snapshot taken when the plan was created, not a live reference. It is what makes a retry reproduce the same plan even if the article went offline or the product left the catalogue — same reason as `organization_context`.
    """

    text: NotRequired[str]
    """
    `from_text`. The article, already downloaded and truncated. It is never downloaded again.
    """
    url: NotRequired[str]
    """
    `from_text`. The original address, kept for the record and to show where the plan came from.
    """
    images: NotRequired[list[Image]]
    """
    `from_images`. The chosen photos with their descriptions, in the order they were sent — the position IS the `source_index` of the publication that uses it.
    """
    id_account_catalog: NotRequired[str]
    """
    `from_catalog`. The account whose catalogue was read.
    """
    products: NotRequired[list[AiPlansAiPlanSourceProduct]]
    """
    `from_catalog`. Snapshot of the chosen products.
    """
    event: NotRequired[Event]
    """
    `campaign`. The event and its date, already normalised to the start of ITS day in the plan timezone.
    """


class CatalogPlannerTemplate(TypedDict):
    template: NotRequired[Literal["standard", "from_images", "from_text", "from_catalog", "campaign"]]
    """
    What the plan is generated FROM, and what you send as `template` when creating it:

    • **`standard`** — a theme prompt, images generated by the model. What every plan was before templates existed.
    • **`from_images`** — the user's own photos, each with its own description. One vision pass over ALL of them at once, so the model can sequence a narrative (photo 3 the "before", photo 7 the "after") instead of writing seven independent posts. It generates no images.
    • **`from_text`** — an article: a URL that is downloaded at creation, or the text pasted by hand.
    • **`from_catalog`** — products read LIVE from a connected catalogue, with their name, their price and their picture. The one template that cannot be copied by a generic AI tool, because it needs the catalogue connection.
    • **`campaign`** — a countdown towards a date, with a narrative arc: teaser, announcement, reminder, today, thank you. The only plan that is a story instead of seven loose posts.
    """
    allows_shared: NotRequired[bool]
    """
    Does it accept `options.shared` (one content replicated across every account)?
    """
    allows_gallery: NotRequired[bool]
    """
    Does it accept `options.gallery_uploads` (visual references for the generated images)?
    """
    generates_images: NotRequired[bool]
    """
    false = the pictures come from the source, and the plan spends no image credits.
    """
    regenerate: NotRequired[Regenerate]
    """
    What can be regenerated on a publication of this plan.
    """
    orchestration_cost: NotRequired[int]
    """
    Estimated credits for this template's orchestration pass. The real charge is per use.
    """
    orchestration_cost_per_source_item: NotRequired[int]
    """
    Extra estimated credits per unit of source (per image, in `from_images`). 0 when the source does not scale the prompt.
    """
    max_source_items: NotRequired[int]
    """
    Hard cap of source units accepted. 0 = this template has no unit-based source.
    """
    source_fields: NotRequired[list[CatalogPlannerTemplateField]]
    source_requires_any: NotRequired[list[str]]
    """
    Fields of which AT LEAST ONE is needed, even though none of them is required on its own. Today it is `from_text`: either the URL or the pasted text, never both empty (2116).

    It exists because a field's `required` cannot say "one or the other", and without it your UI would have to hardcode that rule — exactly the copy this catalogue exists to avoid. Absent = there is nothing of the sort to resolve.
    """


class CatalogSocialLimits(TypedDict):
    characters: CatalogSocialLimitsMap
    """
    Maximum length of a publication's text. Bluesky counts graphemes, everyone else counts characters — Telegram included, where `String.length` is exactly the right unit.

    On Telegram there are **two numbers for the same field**: `telegram` (4.096) while the publication is text only, and `telegram_media` (1.024) the moment it carries an image or a video, because then the text is a media caption and not a message. Switch the counter when the file is attached, not when publish is pressed.
    """
    max_post_bytes: CatalogSocialLimitsMap
    """
    Second text limit, in UTF-8 bytes. `0` means the network does not measure text in bytes; only Bluesky does, at 3.000.
    """
    comment_characters: CatalogSocialLimitsMap
    """
    Maximum length of a reply to a comment. `0` means the network has no comments.
    """
    title_characters: CatalogSocialLimitsMap
    """
    Maximum length of the title. `0` means the network has no title field at all.
    """
    total_images: CatalogSocialLimitsMap
    """
    How many images one publication accepts. `0` means images are not a publication on that network.
    """
    video_duration_in_seconds: CatalogSocialLimitsMap
    """
    Maximum video duration. A network that limits weight instead of duration is not here but in `max_file_size_mb`.
    """
    max_file_size_mb: CatalogSocialLimitsMap
    """
    Maximum size of one file, in megabytes.
    """


class ClientsOrganizationCreate(TypedDict):
    """
    Body accepted when creating an organization. Only these properties are read.
    """

    name: str
    """
    Organization name.
    """
    actual_plan: NotRequired[PlanData]
    """
    Resources assigned to this organization, taken from what the client has contracted.
    """


class ClientsOrganizationUpdate(TypedDict):
    """
    Body accepted when updating an organization. NOTE: `name` and `parent_organization` are NOT updatable through this endpoint - the server keeps their current value and silently ignores them.
    """

    actual_plan: NotRequired[PlanData]
    """
    New resource assignment. Validated against what is left of the client's contracted plan; lowering it below what the organization already uses is rejected.
    """
    stats_settings: NotRequired[StatsSettings]
    """
    Statistics collection settings.
    """


class ClientsPlan(TypedDict):
    """
    The client's SUBSCRIPTION, which is not the same thing as the resources it grants: the numbers live in `plan_data`.
    """

    enabled: bool
    """
    Whether the plan is usable. A disabled client cannot connect accounts or publish.
    """
    status: str
    """
    The subscription's state at the payment provider (`active`, `past_due`, `canceled`, `trialing`, `unpaid`...). A cancelled subscription still works until `current_period_end`.
    """
    isEnabled: bool
    """
    The same thing as `enabled`, recomputed on read rather than stored. Read either; they only disagree if the plan was never saved after changing.
    """
    require_action: NotRequired[bool]
    """
    The payment needs the customer to do something (3-D Secure, a new card).
    """
    plan_identifier: Literal["free", "basic", "pro", "custom"]
    """
    Which plan was contracted. `custom` carries its own numbers in `plan_data`.
    """
    plan_data: PlanData
    """
    **The client's actual limits**, resolved: the named plan's table, or the agreed numbers when `plan_identifier` is `custom`. This is what to read, not the plan's name.
    """
    current_period_start: NotRequired[str]
    current_period_end: NotRequired[str]
    """
    When the current billing period ends. A cancelled plan keeps working until then.
    """
    stripe_customer_id: NotRequired[str]


class Contact(TypedDict):
    """
    A person the organization exchanges messages with. The same contact can be reachable on several channels — that is what `social_identifiers` is.
    """

    _id: str
    id_organization: str
    name: NotRequired[str]
    profile_image: NotRequired[str]
    """
    URL of the contact's avatar on the network. It belongs to the network and it can stop working.
    """
    social_identifiers: list[SocialIdentifier]
    extra_data: NotRequired[ContactExtraData]
    creator_keycloak_identifier: NotRequired[str]
    """
    The user who created the contact, when it was created from the panel instead of arriving from a network.
    """
    creation_date: str
    last_contact_update: str
    """
    Last time the contact's profile was refreshed from the network.
    """


class ContactsContactCreate(TypedDict):
    """
    A new contact. **At least one identifier is mandatory** (`ERROR_CODE_1601` otherwise): a contact with no channel is a contact nobody can write to.

    Creating is idempotent on the FIRST identifier: if the organization already has a contact with that channel and that `external_identifier`, you get the existing one back untouched — `name`, `profile_image` and `extra_data` of the request are ignored. There is no "already exists" error.
    """

    name: NotRequired[str]
    profile_image: NotRequired[str]
    social_identifiers: list[ContactsSocialIdentifierInput]
    extra_data: NotRequired[ContactExtraData]


class ContactsContactUpdate(TypedDict):
    """
    Changes to a contact. `name`, `profile_image` and `social_identifiers` are left alone when you omit them.

    **`extra_data` is the exception and it is destructive**: it is written with whatever the body carries, so omitting it ERASES every custom field on the contact. Read the contact, change what you need and send the whole block back.
    """

    name: NotRequired[str]
    profile_image: NotRequired[str]
    social_identifiers: NotRequired[list[ContactsSocialIdentifierInput]]
    """
    Replaces the whole list, it does not merge into it. Omit it to keep the current one.
    """
    extra_data: NotRequired[ContactExtraData]
    """
    Written as sent. **Omitting it erases the contact's custom fields.**
    """


class DashboardAccountWithError(TypedDict):
    """
    A connected account that has stopped working: an expired token or a revoked permission. Until it is reconnected it neither publishes nor measures.
    """

    _id: str
    name: str
    username: NotRequired[str]
    social_network: SocialNetwork
    image: NotRequired[str]
    error_code: int
    """
    PlanVortex error code that broke it. `0` means healthy, so anything here is non-zero.
    """


class ByNetworkItem(TypedDict):
    social_network: NotRequired[SocialNetwork]
    publications: NotRequired[int]
    metrics: NotRequired[NormalizedMetrics]


class AccountMetrics(TypedDict):
    total: NormalizedMetrics
    previous_total: NormalizedMetrics
    by_day: list[DashboardMetricRow]
    by_network: list[DashboardMetricRow]


class AiPlans(TypedDict):
    total: int
    credits_spent: int
    by_state: list[ByStateItem]
    last_plan: NotRequired[DashboardDashboardAiPlanRef]
    """
    The most recent plan of the organization, **whatever the range**. Absent when there has never been one.
    """
    generated_publications: int
    """
    Publications generated by the plans of the range.
    """
    pending_validation: int
    """
    Plans already generated and **waiting for someone to validate them**: work paid for that is not publishing anything yet.
    """


class DashboardDashboardPublicationRef(TypedDict):
    """
    A publication as the health block projects it: a handful of fields, not a whole `Publication`. `state` is not among them — the list it came from already says what state it is in.
    """

    _id: str
    name: NotRequired[str]
    text: NotRequired[str]
    social_network: SocialNetwork
    publish_date: NotRequired[str]
    creation_date: NotRequired[str]
    publication_errors: NotRequired[list[PublicationError]]
    """
    Only on the failed ones. Same shape as in a full `Publication`.
    """


class DashboardPlanUse(TypedDict):
    actual_use: PlanData
    """
    What the organization and its children are consuming right now.
    """
    actual_asigned: PlanData
    """
    What has been handed down to child organizations out of this organization's plan.
    """
    limits: PlanData
    """
    The plan in force. An organization with no plan of its own inherits the closest parent that has one.
    """


class ByNetworkItem1(TypedDict):
    social_network: NotRequired[SocialNetwork]
    total: NotRequired[int]


class PublishedByDayItem(TypedDict):
    day: NotRequired[str]
    """
    `YYYY-MM-DD`, in UTC.
    """
    social_network: NotRequired[SocialNetwork]
    total: NotRequired[int]


class DashboardPublicationsSummary(TypedDict):
    total: int
    """
    Publications created in the range.
    """
    by_state: list[ByStateItem]
    by_network: list[ByNetworkItem1]
    by_day: list[ByDayItem]
    """
    Publications **created** each day, split by state.
    """
    published_by_day: list[PublishedByDayItem]
    """
    Publications that actually **went out** each day, split by network. Only the ones in state `sended`.
    """


class Publication1(TypedDict):
    """
    The bit of the publication needed to render the row. Nothing else is projected.
    """

    text: NotRequired[str]
    title: NotRequired[str]
    files: NotRequired[list[Upload]]
    publication_type: NotRequired[str]
    url: NotRequired[str]
    external_identifier: NotRequired[str]


class DashboardTopPublication(TypedDict):
    """
    One row of the ranking. It comes out of the stats aggregation, not out of the publications collection, so it does **not** have the shape of a `Publication`: there is no `_id` (the identifier is `id_publication`) and the content travels nested under `publication`.

    Only publications that have already been measured can appear here. For a listing that includes the unmeasured ones, use `GET /organizations/{id}/publications/stats`.
    """

    id_publication: str
    social_network: SocialNetwork
    publish_date: NotRequired[str]
    collected_date: NotRequired[str]
    """
    When this measurement was taken.
    """
    metrics: NormalizedMetrics
    engagement_base: NotRequired[Literal["reach", "impressions", "followers"]]
    """
    What this row's engagement rate is divided by. **Two rows with different bases are not comparable**, so say which one it is when you put them in the same table.
    """
    publication: Publication1
    """
    The bit of the publication needed to render the row. Nothing else is projected.
    """


class IntegrationsIntegration(TypedDict):
    """
    Credentials are never returned. `connected` is the summary the panel paints: false means the connection failed and needs attention.
    """

    _id: str
    id_organization: str
    id_client: str
    provider: IntegrationsIntegrationProviderName
    name: str
    external_identifier: NotRequired[str]
    """
    The Google account email, or the feed URL.
    """
    config: IntegrationsRssConfig
    """
    Provider-specific configuration. **Empty object for `google_drive`** — the Picker supplies everything — so every field here is optional and only an `rss` integration fills them in.
    """
    enabled: bool
    """
    Only enabled integrations consume plan allowance.
    """
    connected: bool
    """
    `error_code` is empty. It is computed on the way out, not stored: the panel needs to know whether the connection is alive, not with which credentials.
    """
    error_code: NotRequired[int | None]
    """
    PlanVortex error code of the last failure (2203 token revoked, 2205 feed unreachable, 924 no publication allowance left…).
    """
    last_used_date: NotRequired[str]
    creation_date: str


class IntegrationsIntegrationProvider(TypedDict):
    provider: IntegrationsIntegrationProviderName
    requires_oauth: bool
    """
    true = connect with connect_link + code. false = connect with a form built from config_fields.
    """
    file_import: bool
    """
    Contributes files to the library through POST /uploads/import.
    """
    content_feed: bool
    """
    Polled by the poll-feeds job, which turns new entries into publications.
    """
    accepted_formats: list[str]
    """
    File formats accepted at the door. **Empty when `file_import` is false** — that is what `rss` returns, and it does not mean "anything goes". heic/heif are accepted and converted to JPEG on ingestion, so what ends up stored is always jpeg.
    """
    config_fields: list[ConfigField]


class MessageOptions(TypedDict):
    """
    Everything a message can carry besides its text. Which block is required depends on `message_type`.
    """

    files: list[str | Upload]
    """
    The uploads attached to the message. **Populated** wherever the message itself is: the messages list and webhook deliveries carry whole uploads, everything else carries their identifiers. Handle both.
    """
    files_urls: list[FilesUrl]
    """
    Files already hosted somewhere else. Filled in by PlanVortex when a message arrives from the network.
    """
    template_name: NotRequired[str]
    """
    Required for `template_message`.
    """
    template_language: NotRequired[str]
    """
    Required for `template_message`, as the network's language code.
    """
    payload: NotRequired[str]
    """
    Payload of a Meta postback.
    """
    metaElements: NotRequired[list[dict[str, Any]]]
    """
    Meta cards, for `elements_message` and `button_message`.
    """
    metaQuickReplies: NotRequired[list[dict[str, Any]]]
    """
    Meta quick replies, for `quick_reply_message`.
    """
    whatsappInteractive: NotRequired[dict[str, Any]]
    """
    WhatsApp interactive list, for `interactive_message`. It needs at least one section.
    """


class MessagesConversation(TypedDict):
    """
    One contact's thread, as it looks in an inbox list.
    """

    contact: Contact
    date: str
    """
    When the last message of the thread was written, which is what the list is sorted by.
    """
    unread_messages: int
    """
    Unread messages **from the contact**. Ours never count.
    """


class MessagesMessageInput(TypedDict):
    """
    What you send to write a message.

    `comment_message` and `publication_message` need `in_response_external_id`, the identifier of the comment or the publication being answered ON THE NETWORK. The endpoint did not read it from the body until 2026-08-24, which left both types unreachable from the public API; it does now.
    """

    message_type: MessageType
    text: NotRequired[str]
    """
    Required for the text-based types. Validated against `characters` in `GET /social_limits`.
    """
    message_options: NotRequired[MessageOptions]
    in_response_external_id: NotRequired[str]
    """
    Required by `comment_message` and `publication_message`, and ignored by every other type (error `1510` when it is missing). It is the identifier the NETWORK gives: a comment's `external_id` or a publication's `external_identifier`, never a PlanVortex `_id`.

    Only Facebook and Instagram do anything with it: `comment_message` sends a private reply to a public comment (Meta's `recipient.comment_id`) and `publication_message` attaches the post as a `MEDIA_SHARE`.
    """


class SocialCredentialsModel(TypedDict):
    """
    The organization's own application credentials, by network. A network that is absent is not configured, and then it does not even appear as connectable.
    """

    discord: NotRequired[SocialCredentials]


class Organization(TypedDict):
    """
    The container of accounts, publications and files. Organizations can nest.
    """

    _id: str
    id_client: str
    """
    The client this organization belongs to.
    """
    name: str
    parent_organization: NotRequired[str]
    """
    The organization this one hangs from. Absent on a root organization.
    """
    creation_date: str
    actual_plan: NotRequired[PlanData]
    """
    The slice of the client's plan assigned to this organization. **Absent when nothing was assigned**, and then the organization shares whatever its nearest parent with a plan has — or, failing that, the client's unassigned remainder. Ask `GET /organizations/{id_organization}/limits` for the effective numbers instead of reading this.
    """
    actual_use: NotRequired[PlanData]
    """
    Current consumption. **Only present with `getUse=true`.** `twitter_credits` and `ai_credits` are what has been spent in the current calendar month; the rest is what exists right now.
    """
    actual_asigned: NotRequired[PlanData]
    """
    What is already handed out to the organizations sharing this plan, which is what is left to assign. **Only present with `getUse=true`.**
    """
    ai_context: NotRequired[AiContext]
    stats_settings: NotRequired[StatsSettings]
    social_credentials: NotRequired[SocialCredentialsModel]
    """
    The organization's own application credentials, by network. A network that is absent is not configured, and then it does not even appear as connectable.
    """


class OrganizationsLimit(PlanData):
    """
    What this organization may actually use. An organization with no plan of its own inherits the nearest parent's, and failing that the share of the client's plan that is not assigned to anyone.
    """


class OrganizationsOrganizationCreate(TypedDict):
    """
    Body accepted when creating an organization. Only these properties are read.
    """

    name: str
    """
    Organization name.
    """
    actual_plan: NotRequired[PlanData]
    """
    Resources assigned to this organization, taken from what the client has contracted.
    """


class OrganizationsOrganizationList(TypedDict):
    organizations: list[Organization]
    total: int


class OrganizationsOrganizationOne(TypedDict):
    organization: Organization


class OrganizationsOrganizationUpdate(TypedDict):
    """
    Body accepted when updating an organization. NOTE: `name` and `parent_organization` are NOT updatable through this endpoint - the server keeps their current value and silently ignores them.
    """

    actual_plan: NotRequired[PlanData]
    """
    New resource assignment. Validated against what is left of the client's contracted plan; lowering it below what the organization already uses is rejected.
    """
    stats_settings: NotRequired[StatsSettings]
    """
    Statistics collection settings.
    """


class ProductsProduct(ProductsProductInput):
    """
    A product as the network returns it. `id` is always present here.
    """


class Publication(TypedDict):
    _id: str
    id_organization: str
    id_account: str | Account
    """
    The account the publication goes out through.

    **It is not always the same shape.** The single-publication operations (create, read, retry) return the account already resolved; the listing and the update return its identifier as a string. Check before using it.
    """
    social_network: SocialNetwork
    """
    Always the network of the account in `id_account`.
    """
    name: NotRequired[str]
    """
    Internal name. Never shown on the social network.
    """
    text: NotRequired[str]
    title: NotRequired[str]
    """
    Only the networks that have a title field use it.
    """
    publication_type: Literal["profile", "page", "group", "reels", "stories", "message"]
    state: Literal["ready", "withErrors", "sended", "draft", "publishing"]
    """
    `draft` is never sent; `ready` is scheduled; `publishing` is in the network's hands right now; `sended` went out; `withErrors` failed and carries the reason in `publication_errors`.
    """
    files: list[Upload]
    """
    The attached files, **already resolved**: every read and write path returns full uploads, not identifiers. Identifiers are what you SEND (see `PublicationInput.files`).
    """
    publish_date: NotRequired[str]
    creation_date: str
    publication_errors: list[PublicationError]
    """
    Why the publication failed, one entry per problem. **It is an array**, and it is empty on a publication that has not failed.

    For a scheduled X (Twitter) publication that runs out of credits at publish time, `code` is 940 and `data` is `{ used, limit }`; the publication stays in state `withErrors` and the client-app webhook is fired.
    """
    retries: int
    """
    Manual retries already spent on a failed publication, against the `max_retries` published by `GET /publication_limits`. Only `POST .../retry` increases it; updating the publication resets it to 0.
    """
    extra_data: NotRequired[dict[str, Any]]
    """
    What one network needs to remember about **this** publication and that has no common field. Absent on a publication whose network needs nothing, which is almost all of them.

    Today only `telegram` writes here, and only `telegram_message_ids`: the ids of every message an album turned into, because deleting the album means deleting all of them.
    """
    external_identifier: NotRequired[str]
    """
    The network's own identifier, once published. On `telegram` an album is one publication that is **several messages**, and this holds the first one; the rest travel in `extra_data.telegram_message_ids`.
    """
    url: NotRequired[str]
    """
    Link to the publication on the network, when there is one. A **private** Telegram channel has no public URL, so it comes back empty even though the post went out.
    """
    statistics: NotRequired[PublicationStats]
    metrics: NotRequired[NormalizedMetrics]
    """
    Last known measurement, in the common vocabulary. Absent until it is measured.
    """
    engagement_base: NotRequired[Literal["reach", "impressions", "followers"]]
    """
    What this publication's engagement rate is divided by.
    """
    stats_updated_date: NotRequired[str]
    next_stats_update: NotRequired[str]
    id_integration: NotRequired[str]
    """
    The integration this publication came from — an RSS feed, for instance. Set when it is created and never changed afterwards.
    """


class PublicationsPublicationList(TypedDict):
    publications: list[Publication]
    total: int


class PublicationsPublicationOne(TypedDict):
    publication: Publication


class PublicationsPublicationRetry(TypedDict):
    publication: Publication
    max_retries: int
    """
    Retries a failed publication accepts in total. Read it from here instead of hardcoding it: it is the same number the server enforces.
    """


class PublicationsPublicationStatsHistory(TypedDict):
    """
    A publication's measured history plus its last known values.
    """

    id_publication: str
    social_network: SocialNetwork
    publish_date: NotRequired[str]
    stats_updated_date: NotRequired[str]
    """
    Last time it was measured. Absent means never
    """
    next_stats_update: NotRequired[str]
    """
    When the collector will look again. Absent means the 30-day window is over
    """
    metrics: NotRequired[NormalizedMetrics]
    engagement_base: NotRequired[Literal["reach", "impressions", "followers"]]
    statistics: NotRequired[PublicationStats]
    series: list[PublicationsPublicationStatsPoint]
    """
    One row per measured day, oldest first. Empty is valid: nothing has been measured yet.
    """
    latest: NotRequired[Latest]
    """
    The most recent row of the series, with the network's raw payload attached. Absent when the series is empty.
    """


class PublicationsPublicationsStatsList(TypedDict):
    range: NotRequired[Range]
    """
    The resolved range and the immediately preceding period of the same length, which is what `summary.previous_total` covers.
    """
    metric: NotRequired[str]
    """
    Metric the listing is ordered by
    """
    summary: NotRequired[Summary]
    """
    Aggregates for the whole organization in the range. Omitted when `summary=false`.
    """
    publications: NotRequired[list[Publication]]
    """
    The requested page. Each publication carries its last known `metrics`, `engagement_base` and `stats_updated_date`; a publication that has not been measured yet has none of them.
    """
    total: NotRequired[int]
    """
    Publications matching the filters, for paging
    """


class AiPlansAiPlan(TypedDict):
    _id: str
    id_client: str
    id_organization: str
    keycloak_identifier: NotRequired[str]
    """
    User who requested the generation.
    """
    accounts: list[str]
    """
    Accounts the plan was generated for.
    """
    prompt: str
    template: NotRequired[Literal["standard", "from_images", "from_text", "from_catalog", "campaign"]]
    """
    What this plan was generated from. Always present: a plan created before templates existed reads `standard`.
    """
    source: NotRequired[AiPlansAiPlanSource]
    """
    The source snapshot. Absent on a `standard` plan, which has no source.
    """
    options: AiPlansAiPlanOptions
    state: Literal["pending", "generating", "generated", "validated", "failed", "cancelled"]
    """
    State machine: pending -> generating -> generated -> validated | failed | cancelled. Poll the plan while state is pending or generating.
    """
    orchestrator_result: NotRequired[dict[str, Any]]
    """
    Raw plan returned by the orchestrator, kept for audit (before validation/trimming).
    """
    publications: list[str | Publication]
    """
    The generated publications — ordinary drafts of the publication domain.

    **It is not always the same shape.** Reading one plan (`GET`, `validate`, `retry`) returns whole publications with their files resolved; the LISTING returns their identifiers as strings. Check before using them.
    """
    credits_spent: int
    """
    AI credits actually consumed by the generation.
    """
    error: NotRequired[AiPlansAiPlanNotice]
    """
    Last generation error. Present only in state `failed`.
    """
    warnings: NotRequired[list[AiPlansAiPlanNotice]]
    """
    Non-blocking notices about the LAST attempt (they are cleared when a new one starts). The plan is generated and perfectly usable; your UI just has to say what happened.

    Today there is one: **2117 — some source items did not fit in the plan week.** A plan is weekly and the source does not extend it, so 12 photos with 6 slots left publish 6 and the rest are dropped. `data` carries `{ source_items, capacity }`. Better said BEFORE creating the plan (the slots are the publish days x the accounts) than after charging for it.
    """
    attempts: int
    """
    Generation attempts consumed (transient failures are retried, max 2).
    """
    creation_date: str
    generation_end_date: NotRequired[str]
    organization_context: NotRequired[AiContext]
    """
    SNAPSHOT of the organization's brand context taken when the plan was created, so a retry or a regeneration reproduces the same plan even if the configuration changed. Absent when the plan was asked for without context, or when the organization had none.
    """


class AiPlansAiPlanCreateResponse(TypedDict):
    ai_plan: AiPlansAiPlan
    estimated_cost: int
    """
    Shortcut to estimate.estimated_cost.
    """
    estimate: AiPlansAiPlanCostEstimate


class AiPlansAiPlanList(TypedDict):
    ai_plans: list[AiPlansAiPlan]
    total: int


class AiPlansAiPlanOne(TypedDict):
    ai_plan: AiPlansAiPlan


class ClientsClient(TypedDict):
    """
    Who contracts the plan and whom the organizations hang from.
    """

    _id: str
    name: str
    client_type: NotRequired[Literal["personal", "company"]]
    creation_date: str
    trial_tested: NotRequired[bool]
    """
    Whether this client has already used its trial.
    """
    actual_plan: ClientsPlan
    ai_settings: NotRequired[ClientsAiSettings]
    """
    Read-only view of the client's own AI provider configuration (BYOK). Written via `PUT /clients/{id_client}/ai-settings`. API keys are stored encrypted and are NEVER returned: each scope only exposes provider, model and has_api_key.
    """
    actual_use: NotRequired[PlanData]
    """
    Current consumption across every organization of the client. **Only present with `getUse=true`.** `twitter_credits` and `ai_credits` are what has been spent this calendar month.
    """
    actual_asigned: NotRequired[PlanData]
    """
    What is already handed out to the client's root organizations, which is what is left to assign. **Only present with `getUse=true`.**
    """


class ClientsClientList(TypedDict):
    clients: list[ClientsClient]
    total: int


class ClientsClientOne(TypedDict):
    client: ClientsClient


class ClientsOrganizationList(TypedDict):
    organizations: list[Organization]
    total: int


class ClientsOrganizationOne(TypedDict):
    organization: Organization


class CommentsComment(TypedDict):
    """
    A comment — or a review — as PlanVortex stores it. Remember it is a **snapshot** of what the network said at `collected_date`; the live thread endpoints return the same shape reconciled against the network.
    """

    _id: str
    id_account: str | Account
    """
    The connected account it arrived on.

    **It is not always the same shape.** The inbox listing (`GET /organizations/{id}/comments`) returns the whole account resolved; every other operation — the live threads, the reply, the update — returns its identifier as a string. Check before using it.
    """
    id_organization: str
    id_publication: NotRequired[str | Publication]
    """
    **Your** publication, when there is one — and there often is not: a video uploaded to the channel by hand, a post that predates PlanVortex, and every Google Business review have comments with no publication of ours behind them. What always identifies the target is `publication_external_id`.

    Same asymmetry as `id_account`: the inbox listing resolves it into the whole publication, every other operation returns the identifier as a string.
    """
    publication_external_id: str
    """
    What the comment hangs off, on the network: the post/video id in most networks, the **listing** (`locations/{id}`) for a Google Business review, and the published message's id on Telegram — where the thread that holds the comments *is* the forwarded post.
    """
    external_id: str
    """
    The comment's id on the network. Unique per account, and what makes repeated webhook deliveries idempotent.

    Two exceptions worth knowing, and both are composite ids you should treat as opaque:

    • A Google Business reply has no id of its own — it is a *field* of the review — so PlanVortex fabricates a stable one, `{reviewId}/reply`.
    • A Telegram comment lives in a **different chat** from the post it answers (the channel's linked discussion group), so it needs two ids at once and travels as `{thread}/{message}`: replying wants the first, deleting wants the second.
    """
    parent_external_id: NotRequired[str]
    """
    Present only when this is a reply to another comment
    """
    social_network: CommentsCommentNetworkName
    author: CommentsCommentAuthor
    text: str
    """
    **May legitimately be empty.** A stars-only review carries no text at all, so render `rating` alongside it and never assume a blank comment is a loading failure.
    """
    rating: NotRequired[int]
    """
    Star rating of a **review**. Present only on review networks — today Google Business. Its absence means "this network has no such thing", never zero.

    It is not decorative: without it a one-star review and a five-star one are the same row, and a stars-only review is a blank line.
    """
    creation_date: str
    """
    When it was written **on the network**. This is what orders the inbox.
    """
    collected_date: str
    """
    When PlanVortex last read it. The inbox is a photograph and this says how old it is.
    """
    read: bool
    """
    Yours, not the network's. A live read never overwrites it.
    """
    replied: bool
    """
    Yours, not the network's. Set when you reply through the API.
    """
    hidden: bool
    """
    Hidden on the network. A hidden comment is never swept as deleted: on YouTube, hiding one makes the API stop returning it forever, and without that exception hiding would be indistinguishable from deleting.
    """
    deleted: bool
    """
    Gone from the network. The row is kept so it is not created again by the next read or by a repeated webhook; it stops appearing in the inbox.
    """
    like_count: NotRequired[int]
    """
    Absent when the network does not publish it — not zero
    """
    reply_count: NotRequired[int]
    """
    Absent when the network does not publish it — not zero
    """
    our_reply_external_id: NotRequired[str]
    """
    The network id of your reply, so you can find it or delete it later
    """


class CommentsCommentThread(TypedDict):
    """
    A live read: asked of the network and reconciled with what was stored.
    """

    comments: list[CommentsComment]
    total: int
    """
    What the network says the total is. On a Google Business listing it is the number of **reviews**, which is not the length of `comments`: your replies travel in the same array as children of the review they answer.
    """
    next_cursor: NotRequired[str]
    """
    Opaque page token from the network. Pass it back as `offset`; absent means there is no next page.
    """
    credits_consumed: int
    """
    X credits this read spent from the client's monthly pool. `0` on every other network. Charged after the fact and by real units, so a failed read charges nothing.
    """


class Health(TypedDict):
    """
    What needs fixing today. Each half has its own permission: somebody who cannot read accounts still sees the failed publications.
    """

    accounts_with_errors: NotRequired[list[DashboardAccountWithError]]
    publications_with_errors: NotRequired[list[DashboardDashboardPublicationRef]]
    """
    Up to ten publications in state `with_errors`, newest first.
    """
    upcoming_publications: NotRequired[list[DashboardDashboardPublicationRef]]
    """
    Up to ten publications due in the next 48 hours.
    """
    total_drafts: NotRequired[int]


class Publications(DashboardPublicationsSummary):
    previous_total: NotRequired[int]
    """
    The same count for the previous period, for the delta.
    """


class PublicationMetrics(TypedDict):
    total: NormalizedMetrics
    previous_total: NormalizedMetrics
    by_network: list[ByNetworkItem]
    top: list[DashboardTopPublication]


class DashboardDashboard(TypedDict):
    """
    Everything the home screen needs, in ONE round trip.

    **A missing block is not an error.** Each one is checked against its own permission and omitted when the caller cannot read it, instead of failing the whole request; `available_blocks` says which ones were allowed. A block that is `true` in `available_blocks` and absent from the body means there was no data — except `messages`, which also turns to `false` when the plan does not include chat.
    """

    range: DashboardDashboardRange
    available_blocks: AvailableBlocks
    """
    Which blocks the caller was allowed to see. A `false` here is a permission (or plan) answer; a block that is `true` but empty means there is no data.
    """
    health: NotRequired[Health]
    """
    What needs fixing today. Each half has its own permission: somebody who cannot read accounts still sees the failed publications.
    """
    publications: NotRequired[Publications]
    publication_metrics: NotRequired[PublicationMetrics]
    account_metrics: NotRequired[AccountMetrics]
    plan_use: NotRequired[DashboardPlanUse]
    ai_plans: NotRequired[AiPlans]
    messages: NotRequired[Messages]


class Message(TypedDict):
    """
    A message exchanged with a contact.

    **Careful with the three reference fields.** `contact_id`, `from_contact_id` and `message_options.files` arrive **populated** — the whole object, not the identifier — in the messages list and in the webhook PlanVortex posts to your app, and as plain identifiers everywhere else. The types say `string | object` because both really happen.
    """

    _id: str
    id_account: str
    contact_id: NotRequired[str | Contact]
    """
    Set when **we** wrote to the contact. Exactly one of `contact_id` and `from_contact_id` is present, and which one tells you the direction of the message.
    """
    from_contact_id: NotRequired[str | Contact]
    """
    Set when the **contact** wrote to us.
    """
    read: bool
    text: NotRequired[str]
    """
    Absent on the messages that carry no text of their own, such as a `messaging_seen` acknowledgement.
    """
    message_type: MessageType
    message_options: MessageOptions
    message_errors: list[Error1]
    """
    Why the network refused this message, if it did. Same shape as an API error. Empty when nothing went wrong.
    """
    in_response_to: NotRequired[str]
    """
    Identifier of the PlanVortex message this one answers.
    """
    in_response_external_id: NotRequired[str]
    """
    Identifier on the network of the publication, comment or message this one answers.
    """
    element_external_id: NotRequired[str]
    """
    Identifier of this message on the network.
    """
    creation_date: str


class CommentsWebhookChange(TypedDict):
    """
    One change in the array PlanVortex posts to your app's `webhook_url`, when the change concerns a social **account**.

    An integration that stopped working has a shape of its own — `IntegrationWebhookChange` — and one delivery can mix both. Switch on `field`, and ignore what you do not handle.
    """

    field: Literal[
        "new_account",
        "change_state_account",
        "messages",
        "messaging_postbacks",
        "messaging_seen",
        "messaging_error",
        "comments",
    ]
    """
    What kind of change this is. **Treat it as an open list** and ignore what you do not handle: it grows with the product.

    - `new_account` / `change_state_account`: an account was connected, or its state changed — it stopped working, its token was refreshed, it was disconnected. On `telegram` this is the **only** way to hear about a connection: there is no callback there, so no request of yours ever returns that account.
    - `messages`: a message came in. It travels in `messageObj`.
    - `messaging_postbacks`: the contact pressed a button or a quick reply. Also in `messageObj`.
    - `messaging_seen`: the contact read the conversation. `messageObj` carries the message they read, when we still have it.
    - `messaging_error`: the network refused a message we sent. The reason is in `messageObj.message_errors`.
    - `comments`: a comment came in. It travels in `commentObj`, never in `messageObj`.
    """
    id_account: str
    id_organization: str
    social_network: SocialNetwork
    commentObj: NotRequired[CommentsComment]
    """
    The comment. Present only when `field` is `comments`, and absent even then if the author deleted a comment we had never seen.
    """
    messageObj: NotRequired[Message]
    """
    The message. Present for the messaging fields, never for a comment — a comment is not a message and does not travel in here.

    It arrives **populated**: `contact_id`, `from_contact_id` and `message_options.files` carry whole objects. On `messaging_seen` and `messaging_error` it can be absent, because the message being acknowledged may not be one of ours.
    """
    id_contact: NotRequired[str]
    """
    Only for messaging fields. A comment has no contact: its author is not someone you can write to.
    """
    originalChange: NotRequired[dict[str, Any]]
    """
    The raw payload the social network sent, passed through untouched. Absent on the changes PlanVortex raises itself, such as `new_account`.
    """
