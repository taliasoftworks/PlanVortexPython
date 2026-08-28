"""``planvortex.webhooks`` — the events PlanVortex posts to your app, and how to prove they are its.

It lives in a module of its own, imported by nobody else, because whoever receives webhooks is
almost never the same process that publishes: a Flask endpoint has no reason to build a client.

TWO THINGS TRIP UP EVERYONE, and that is why they are written above the code:

1. **The body is an ARRAY of changes**, not an object. Iterate over what arrives.
2. **The signature is computed over the RAW body.** If your framework already parsed the JSON and
   you serialise it again, the bytes are not the same ones and the signature never matches. The
   line that gives you the raw body is different in each framework, and it is the only line of the
   recipe that matters:

   =========== ==========================================================
   Flask       ``request.get_data()``          — never ``request.json``
   FastAPI     ``await request.body()``        — never the parsed model
   Django      ``request.body``                — never ``request.POST``
   =========== ==========================================================

And a third one that trips nobody up but costs money: **PlanVortex does not retry a failed
delivery.** A 500 of yours loses the event — the inbox endpoints (``pv.comments.list``,
``pv.messages.list``) are how you catch up. If your work is slow, queue it and answer.

    import os

    from planvortex.webhooks import handle_webhook_request, is_comment_change

    changes = handle_webhook_request(
        body=request.get_data(),
        headers=request.headers,
        secret=os.environ["PLANVORTEX_CLIENT_SECRET"],
    )
    for change in changes:
        if is_comment_change(change):
            moderate(change.get("commentObj"))

The secret is your client app's — the same one you ask for the token with, and the one
``pv.apps.secret(client_id, app_id)`` gives you back.
"""

import hashlib
import hmac
import json
import sys
from typing import Any, Literal, Protocol, TypeAlias, TypeGuard, cast

from planvortex._core.errors import NO_ERROR_CODE, PlanVortexConfigError, PlanVortexError
from planvortex.types import Comment, Message, SocialNetwork

# Igual que en `_shapes.py` y por lo mismo (§ Trampa P13 del roadmap): NO hay `from __future__
# import annotations` en este fichero, y `TypedDict` y `NotRequired` salen del MISMO sitio. Con las
# anotaciones convertidas en cadenas, o con las dos mitades mezcladas, todas las claves de estos
# `TypedDict` se declaran obligatorias en ejecucion mientras mypy sigue en verde.
if sys.version_info >= (3, 11):
    from typing import NotRequired, TypedDict
else:  # pragma: no cover - la rama la elige el interprete, no un test
    from typing_extensions import NotRequired, TypedDict


# =================================================================================================
# El contrato: cabeceras y eventos
# =================================================================================================

WEBHOOK_SIGNATURE_HEADERS: dict[str, str] = {
    "sha1": "x-hub-signature",
    "sha256": "x-hub-signature-256",
}
"""The two signature headers PlanVortex sends, each with the HMAC of the raw body.

The value carries the algorithm in front: ``sha256=<hex>``. Verify the 256 one if you can; the sha1
one is there for whoever already integrated webhooks Meta-style.
"""

WebhookAlgorithm: TypeAlias = Literal["sha1", "sha256"]
"""Which of the two headers you are checking against."""

WEBHOOK_EVENTS: tuple[str, ...] = (
    "new_account",
    "change_state_account",
    "messages",
    "messaging_postbacks",
    "messaging_seen",
    "messaging_error",
    "comments",
    "integration_error",
)
"""The events delivered today, taken from the specification and not from memory.

**The list grows**, so a ``field`` this release has never heard of is not an error: it lands on
:class:`UnknownWebhookChange` and your default branch ignores it. ``tests/test_webhooks.py`` walks
the committed OpenAPI bundle and fails if this tuple and the specification disagree in either
direction.
"""


# =================================================================================================
# Los tipos de los eventos
# =================================================================================================


class AccountWebhookChangeBase(TypedDict):
    """What every change hanging off an ACCOUNT carries, whatever else it brings."""

    id_account: str
    id_organization: str
    social_network: SocialNetwork
    originalChange: NotRequired[dict[str, Any]]
    """The change exactly as the social network sent it, untouched.

    Absent on the ones PlanVortex raises by itself, such as ``new_account``.
    """


class AccountStateChange(AccountWebhookChangeBase):
    """An account was connected, or its state changed: it stopped working, was refreshed, was cut."""

    field: Literal["new_account", "change_state_account"]


class MessageChange(AccountWebhookChangeBase):
    """Something happened in messaging: a message came in, the contact pressed a button, read the
    conversation, or the network refused one of ours.

    ``messageObj`` arrives **populated** — ``contact_id``, ``from_contact_id`` and
    ``message_options.files`` carry whole objects — and can be **missing** on ``messaging_seen`` and
    ``messaging_error``, because the message being acknowledged may not be one of ours. To read it
    without writing the same check everywhere there are ``message_contact``, ``message_contact_id``
    and ``message_files`` in :mod:`planvortex.types`.
    """

    field: Literal["messages", "messaging_postbacks", "messaging_seen", "messaging_error"]
    messageObj: NotRequired[Message]
    id_contact: NotRequired[str]
    """The contact on the other side. A comment has none, which is why it is here and not there."""


class CommentChange(AccountWebhookChangeBase):
    """A comment came in.

    It travels in ``commentObj`` and **never** in ``messageObj``: a comment is not a message, it has
    no contact and it hangs off a publication. It is missing when the author deleted one we had
    never seen — the notice goes out anyway, with ``originalChange``, but there is nothing to mark.

    **Meta repeats deliveries.** The same comment can arrive more than once; deduplicate on
    ``commentObj["external_id"]``.

    Only Facebook and Instagram arrive this way, because Meta pushes them. YouTube, LinkedIn, Google
    Business and X have no comment webhook and are polled by a background job, so those show up in
    ``pv.comments.list`` within hours rather than instantly.
    """

    field: Literal["comments"]
    commentObj: NotRequired[Comment]


class IntegrationErrorChange(TypedDict):
    """An integration stopped working: a revoked Drive token, a feed that no longer answers, an
    exhausted publication quota.

    **It carries no ``id_account`` and no ``social_network``**, and that is why it is a type of its
    own: an integration hangs off the organization, not off any account.
    """

    field: Literal["integration_error"]
    id_integration: str
    id_organization: str
    provider: str
    """``google_drive`` or ``rss`` today. **This list grows**: treat it as an open enumeration."""
    error_code: int
    """The PlanVortex code saying what went wrong. Integration codes live in the 2200-2299 range."""


class UnknownWebhookChange(TypedDict):
    """A ``field`` this release of the package does not know yet.

    It is in the union on purpose: the server's list grows, and a library that rejected what it does
    not understand would break the day an event is added. If you need the fields of a new one before
    the package types it, cast it yourself.
    """

    field: str


WebhookChange: TypeAlias = (
    AccountStateChange | MessageChange | CommentChange | IntegrationErrorChange | UnknownWebhookChange
)
"""One of the changes that come in the array. Discriminated by ``field``.

**Do not narrow it with an ``if change["field"] == ...``**: :class:`UnknownWebhookChange` declares
``field: str``, so no type checker can rule it out of a branch and you are left with
``CommentChange | UnknownWebhookChange``. The predicates below — :func:`is_comment_change` and
friends — are what narrows for real, and they are the recommended way.
"""

_ACCOUNT_STATE_EVENTS = frozenset({"new_account", "change_state_account"})
_MESSAGE_EVENTS = frozenset({"messages", "messaging_postbacks", "messaging_seen", "messaging_error"})


def is_account_state_change(change: WebhookChange) -> TypeGuard[AccountStateChange]:
    """An account was connected, or changed state."""
    return change["field"] in _ACCOUNT_STATE_EVENTS


def is_message_change(change: WebhookChange) -> TypeGuard[MessageChange]:
    """Something happened in messaging. Includes the read receipt and the network's refusal."""
    return change["field"] in _MESSAGE_EVENTS


def is_comment_change(change: WebhookChange) -> TypeGuard[CommentChange]:
    """A comment came in."""
    return change["field"] == "comments"


def is_integration_error_change(change: WebhookChange) -> TypeGuard[IntegrationErrorChange]:
    """An integration stopped working."""
    return change["field"] == "integration_error"


# =================================================================================================
# Errores
# =================================================================================================


class WebhookSignatureError(PlanVortexError):
    """The signature does not match, or none came.

    It inherits from :class:`~planvortex.PlanVortexError` so one ``except PlanVortexError`` catches
    everything this package raises. It carries ``family="webhook"`` and
    :data:`~planvortex.NO_ERROR_CODE`, because it does not come from the server's catalogue: this
    library raises it.
    """

    def __init__(self, message: str) -> None:
        super().__init__(NO_ERROR_CODE, message, family="webhook")


class WebhookBodyError(PlanVortexError):
    """The body is not what it has to be: not raw bytes, not JSON, or not an array.

    The first case takes almost every appearance, and always for the same reason: the framework's
    parsed body was handed over instead of the bytes that arrived.
    """

    def __init__(self, message: str) -> None:
        super().__init__(NO_ERROR_CODE, message, family="webhook")


# =================================================================================================
# Verificacion
# =================================================================================================

RawWebhookBody: TypeAlias = str | bytes | bytearray | memoryview
"""The raw body, in any of the shapes a framework leaves it in."""

_ERROR_CUERPO_PARSEADO = (
    "The webhook body has to be the BYTES that arrived (bytes, bytearray, memoryview or str), not "
    "the parsed JSON: the signature is computed over those bytes and serialising the object again "
    "changes them. Flask: request.get_data(). FastAPI: await request.body(). Django: request.body."
)


def verify_webhook_signature(
    payload: RawWebhookBody,
    signature: str | None,
    secret: str | bytes,
    *,
    algorithm: WebhookAlgorithm = "sha256",
) -> bool:
    """Did PlanVortex sign this body with your app's secret?

    Returns ``True`` or ``False`` and **does not raise** on a malformed, absent or wrong-length
    signature: all of that is a ``False``. It raises only if you hand it something that is not bytes
    (:class:`WebhookBodyError`) or leave out the secret
    (:class:`~planvortex.PlanVortexConfigError`), which are bugs in your code and not in whoever
    called your endpoint.

    The comparison is constant-time (``hmac.compare_digest``). The lengths are checked first:
    ``compare_digest`` does not raise on a truncated signature, but an HMAC always measures the
    same, so the length is no secret and returning early says what happened instead of hiding it
    inside the comparison.

    :param payload: The **raw** body, exactly as it arrived. A parsed object is not valid and raises.
    :param signature: The header's value, with ``sha256=`` in front or without it.
    :param secret: Your client app's ``client_secret``: the same one you ask for the token with.
    :param algorithm: Which of the two headers you are comparing against. ``sha256`` by default.
    """
    if not secret:
        raise PlanVortexConfigError(
            "There is no client_secret to verify the signature with. It is your client app's "
            "secret — the same one you ask for the token with — not the organization's id."
        )
    cuerpo = _a_bytes(payload)
    recibida = _normalizar_firma(signature, algorithm)
    if recibida is None:
        return False

    esperada = hmac.new(
        secret.encode("utf-8") if isinstance(secret, str) else secret,
        cuerpo,
        hashlib.sha256 if algorithm == "sha256" else hashlib.sha1,
    ).hexdigest()
    # `compare_digest` con cadenas exige ASCII y revienta con un `TypeError` si no lo es; una firma
    # con un caracter raro es exactamente lo que manda quien esta probando el endpoint a mano.
    if len(esperada) != len(recibida) or not recibida.isascii():
        return False
    return hmac.compare_digest(esperada, recibida)


def _normalizar_firma(signature: str | None, algorithm: WebhookAlgorithm) -> str | None:
    """La firma en hex pelado, o `None` si no sirve.

    Acepta `sha256=<hex>` y el hex a secas, pero RECHAZA el prefijo de otro algoritmo: comparar un
    sha1 contra el sha256 esperado no cuadraria nunca, y devolver `False` sin mas esconderia que lo
    que pasa es que se esta leyendo la cabecera equivocada.
    """
    if not signature:
        return None
    separador = signature.find("=")
    if separador == -1:
        return signature
    return signature[separador + 1 :] if signature[:separador] == algorithm else None


def _a_bytes(payload: RawWebhookBody) -> bytes:
    if isinstance(payload, str):
        return payload.encode("utf-8")
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, (bytearray, memoryview)):
        return bytes(payload)
    raise WebhookBodyError(_ERROR_CUERPO_PARSEADO)


# =================================================================================================
# El camino agnostico: bytes + cabeceras -> cambios
# =================================================================================================


class WebhookHeaders(Protocol):
    """The headers as your framework hands them over.

    It is a protocol and not a ``dict`` so that Flask's, FastAPI's and Django's — which are all
    case-insensitive mappings of their own — fit with no conversion and no cast. A plain ``dict``
    fits too, and its keys are matched without minding case.
    """

    def get(self, key: str) -> Any: ...


def handle_webhook_request(
    body: RawWebhookBody,
    headers: WebhookHeaders,
    secret: str | bytes,
    *,
    algorithm: WebhookAlgorithm | None = None,
) -> list[WebhookChange]:
    """Verify the signature and return the changes, knowing nothing about your framework.

        changes = handle_webhook_request(
            body=await request.body(),
            headers=request.headers,
            secret=os.environ["PLANVORTEX_CLIENT_SECRET"],
        )

    :param body: The **raw** body. ``request.get_data()``, ``await request.body()``, ``request.body``.
    :param headers: The request's headers.
    :param secret: Your client app's ``client_secret``.
    :param algorithm: Forces one of the two headers. By default the ``sha256`` one if it came, and
        the ``sha1`` one only if it did not.
    :raises WebhookSignatureError: no signature came, or it does not match.
    :raises WebhookBodyError: the body is not bytes, not JSON, or not an array.
    """
    elegido: WebhookAlgorithm = algorithm or (
        "sha256" if _leer_cabecera(headers, WEBHOOK_SIGNATURE_HEADERS["sha256"]) else "sha1"
    )
    cabecera = WEBHOOK_SIGNATURE_HEADERS[elegido]
    firma = _leer_cabecera(headers, cabecera)
    if not firma:
        raise WebhookSignatureError(
            f"The delivery carries no {cabecera} header. If you are behind a proxy, check that it "
            "is not stripping it."
        )
    if not verify_webhook_signature(body, firma, secret, algorithm=elegido):
        raise WebhookSignatureError(
            f"The {cabecera} signature does not match the body received. The two usual causes: the "
            "body is not the raw one, or the secret is not this app's."
        )
    return parse_webhook_body(body)


def parse_webhook_body(payload: RawWebhookBody) -> list[WebhookChange]:
    """Parse the body of an **already verified** delivery and return the changes.

    Separate it from the verification only if you have a reason: calling it on its own is accepting
    whatever reaches your endpoint. It checks that the body is an array because the natural mistake
    — treating it as an object — has no symptom until a field that is always missing gets read.
    """
    texto = _a_bytes(payload).decode("utf-8", errors="replace")
    try:
        cargado = json.loads(texto)
    except ValueError as causa:
        raise WebhookBodyError(f"The webhook body is not valid JSON: {causa}") from causa
    if not isinstance(cargado, list):
        raise WebhookBodyError(
            "The webhook body is an ARRAY of changes, and "
            f"{'null' if cargado is None else type(cargado).__name__} arrived. Iterate over what "
            "you get."
        )
    for posicion, elemento in enumerate(cargado):
        if not isinstance(elemento, dict) or not isinstance(elemento.get("field"), str):
            raise WebhookBodyError(
                f"Change {posicion} of the delivery is not an object with a `field` saying what it "
                "is. Every change carries one, so this body did not come from PlanVortex."
            )
    return cast("list[WebhookChange]", cargado)


def _leer_cabecera(headers: WebhookHeaders, nombre: str) -> str | None:
    """Una cabecera de un mapa cualquiera, sin depender de mayusculas.

    Los tres frameworks del README ya dan mapas insensibles a mayusculas, asi que el `get` directo
    resuelve el caso real. El recorrido es para un `dict` pelado —el de un test, el de un servidor
    escrito a mano— y de paso entiende el `HTTP_X_HUB_SIGNATURE_256` del `request.META` de Django,
    que es lo que queda de un WSGI crudo.
    """
    for clave in (nombre, nombre.title(), nombre.upper()):
        valor = _primer_valor(headers.get(clave))
        if valor:
            return valor
    items = getattr(headers, "items", None)
    if items is None:
        return None
    for clave, valor_crudo in items():
        if _normalizar_nombre(str(clave)) == nombre:
            valor = _primer_valor(valor_crudo)
            if valor:
                return valor
    return None


def _normalizar_nombre(clave: str) -> str:
    normalizada = clave.lower().replace("_", "-")
    return normalizada[len("http-") :] if normalizada.startswith("http-") else normalizada


def _primer_valor(valor: Any) -> str | None:
    if isinstance(valor, str):
        return valor
    if isinstance(valor, (list, tuple)):
        return next((elemento for elemento in valor if isinstance(elemento, str)), None)
    return None


__all__ = [
    "WEBHOOK_EVENTS",
    "WEBHOOK_SIGNATURE_HEADERS",
    "AccountStateChange",
    "AccountWebhookChangeBase",
    "CommentChange",
    "IntegrationErrorChange",
    "MessageChange",
    "RawWebhookBody",
    "UnknownWebhookChange",
    "WebhookAlgorithm",
    "WebhookBodyError",
    "WebhookChange",
    "WebhookHeaders",
    "WebhookSignatureError",
    "handle_webhook_request",
    "is_account_state_change",
    "is_comment_change",
    "is_integration_error_change",
    "is_message_change",
    "parse_webhook_body",
    "verify_webhook_signature",
]
