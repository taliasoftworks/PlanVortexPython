"""The PlanVortex error catalogue, by range, and the classes that come out of it.

THE RULE, and it is not negotiable: **errors are classified by ``body["code"]``, never by the HTTP
status.** Every domain error travels with a 400 — an expired token, a disconnected account, an
exhausted plan quota and a text that is too long are all four a 400. Only 520 (permissions) comes
back as 401, and an unexpected failure as 500. ``if response.status_code == 401: refresh()`` would
be a silent bug: the token codes, 501 and 522, travel inside a 400.

The server's catalogue grows every month, so a code outside these ranges is NOT a client error: it
lands on the base class with its ``code`` and its ``message`` intact. Never swallowed, never
renamed.
"""

from __future__ import annotations

from typing import Any, NamedTuple, TypeGuard


class ErrorRange(NamedTuple):
    """One range of the catalogue: ``[start, end]`` inclusive, and the family it belongs to."""

    start: int
    end: int
    family: str


# Los mismos 16 rangos que publica `swagger/common.json`, `PLANVORTEX_ERROR_RANGES` del paquete de
# Node y el apendice A del roadmap. SI SE TOCA UN RANGO, SE TOCAN LOS CINCO SITIOS.
PLANVORTEX_ERROR_RANGES: tuple[ErrorRange, ...] = (
    # Hasta 546, no 544: la API publica se abrio a todos los planes y trajo dos codigos nuevos
    # —545 (ritmo por plan, que sale 429) y 546 (correo sin verificar al crear una app)—.
    ErrorRange(500, 546, "auth"),
    ErrorRange(601, 612, "user"),
    ErrorRange(700, 715, "account"),
    ErrorRange(800, 810, "file"),
    # El techo sube con el catalogo del servidor, y subir tarde no da un error: da un consejo
    # equivocado. Los codigos de Bluesky, Discord, Telegram y Threads (961-977) y los dos frenos
    # de ritmo de la fase de publicaciones ilimitadas (978, 979) nacieron por encima de 960 y
    # caian fuera de toda familia.
    ErrorRange(900, 979, "publication"),
    ErrorRange(1000, 1003, "general"),
    ErrorRange(1100, 1111, "organization"),
    ErrorRange(1200, 1207, "role"),
    # 1308 es el tope de APPS del plan, que nacio al quitar el candado de precio de la API.
    ErrorRange(1300, 1308, "plan_limit"),
    ErrorRange(1400, 1408, "plan_limit"),
    ErrorRange(1500, 1512, "messaging"),
    ErrorRange(1600, 1601, "contact"),
    ErrorRange(1900, 1906, "payment"),
    ErrorRange(2000, 2099, "product"),
    ErrorRange(2100, 2199, "ai_plan"),
    ErrorRange(2200, 2299, "integration"),
)

# El `code` que lleva un error que NO trae codigo del servidor: un fallo de red, un timeout, un 502
# de un proxy con cuerpo HTML, o el propio constructor quejandose de la configuracion. El servidor
# no emite nunca el 0, asi que sirve de centinela sin pisar el catalogo. Cual de esos casos es se
# distingue por `family`: `connection`, `http`, `oauth`, `config` o `webhook`.
NO_ERROR_CODE = 0

# Los dos codigos que significan "tu token ya no sirve". Los dos llegan DENTRO de un 400, que es
# justo por lo que existe esta constante: quien mire el status no los va a encontrar.
#
# El 520 (permisos) NO esta aqui a proposito: sale 401, pero pedir un token nuevo no lo arregla — a
# la app le faltan permisos, y con un token recien emitido le seguiran faltando.
TOKEN_ERROR_CODES: tuple[int, ...] = (501, 522)


class PlanVortexError(Exception):
    """The base of everything this library raises.

    ``except PlanVortexError`` catches them all: domain errors, network errors and configuration
    errors. Use the subclasses and ``code`` to narrow.
    """

    def __init__(
        self,
        code: int,
        message: str,
        *,
        data: dict[str, Any] | None = None,
        status: int | None = None,
        request_id: str | None = None,
        retry_after: float | None = None,
        family: str | None = None,
    ) -> None:
        super().__init__(message)
        #: The ``code`` from the body, as it came. :data:`NO_ERROR_CODE` when the error is not from
        #: the catalogue.
        self.code = code
        #: The message, already unwrapped — the same thing ``str(error)`` gives you.
        self.message = message
        #: The range's family: ``auth``, ``publication``, ``plan_limit``... See
        #: :data:`PLANVORTEX_ERROR_RANGES`.
        self.family = family or error_family_for_code(code) or "unknown"
        #: The ``data`` from the body — whatever the server attached. ``{}`` if nothing came.
        self.data: dict[str, Any] = data if data is not None else {}
        #: HTTP status, or ``None`` when the request never got a response.
        self.status = status
        #: ``x-request-id``, when the deployment sets it. The server does not emit it today; a proxy
        #: in front does.
        self.request_id = request_id
        #: Seconds the ``Retry-After`` header asked for, when it arrived.
        self.retry_after = retry_after

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code}, status={self.status}, message={self.message!r})"


class AuthError(PlanVortexError):
    """500-546 — tokens, client apps, permissions. Includes 501 and 522, the expired-token ones."""


class UserError(PlanVortexError):
    """601-612 — the end user."""


class AccountError(PlanVortexError):
    """700-715 — social accounts: disconnected, missing permissions on the network, not refreshed."""


class FileError(PlanVortexError):
    """800-810 — files: unsupported format, too large, conversion failed."""


class PublicationError(PlanVortexError):
    """900-979 — publications, including per-network limits (characters, images, duration) and the
    two rate brakes: 978 (publishing too fast on this account) and 979 (that network's daily cap).
    """


class OrganizationError(PlanVortexError):
    """1100-1111 — organizations, and the temporal token bound to a single one of them (1101)."""


class PlanLimitError(PlanVortexError):
    """1300-1308 and 1400-1408 — the plan's quota, on the client or on the organization.

    This is the error an integrator actually wants to tell apart: it is not fixed by retrying, it is
    fixed by changing plan. That is why both ranges share a class.
    """


class MessagingError(PlanVortexError):
    """1500-1512 — conversations, messages and templates. Requires a paid plan."""


class ContactError(PlanVortexError):
    """1600-1601 — contacts."""


class ProductError(PlanVortexError):
    """2000-2099 — catalogues and products (Facebook and Instagram only)."""


class AiPlanError(PlanVortexError):
    """2100-2199 — AI-generated publication plans."""


class IntegrationError(PlanVortexError):
    """2200-2299 — integrations: Google Drive, RSS."""


class PlanVortexConnectionError(PlanVortexError):
    """The request never got a response: DNS, refused connection, a cut socket or a timeout.

    It carries no catalogue code because the server never got to have an opinion.
    """

    def __init__(
        self,
        message: str,
        *,
        timeout: bool = False,
        status: int | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            NO_ERROR_CODE,
            message,
            status=status,
            request_id=request_id,
            family="connection",
        )
        #: ``True`` when what ran out was our own timeout, not the network.
        self.timeout = timeout


class PlanVortexAuthenticationError(PlanVortexError):
    """``POST /oauth/token`` rejected the credentials.

    This is the ONLY place in the API with a different error shape: OAuth2's
    ``{error, error_description}``, not the ``{code, message, data}`` of everything else. And that
    is why ``code`` is :data:`NO_ERROR_CODE`: the server does have codes for this (538-541) but
    **does not send them in the body**, so putting them here would be inventing something nobody
    said. What does travel is ``oauth_error``.
    """

    def __init__(
        self,
        oauth_error: str,
        description: str,
        *,
        status: int | None = None,
        request_id: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(
            NO_ERROR_CODE,
            description,
            status=status,
            request_id=request_id,
            retry_after=retry_after,
            family="oauth",
        )
        #: ``invalid_client``, ``invalid_request``, ``unsupported_grant_type``, ``slow_down`` or
        #: ``server_error``.
        self.oauth_error = oauth_error


class PlanVortexConfigError(PlanVortexError):
    """The library is misconfigured and never left home: no credentials, a naive ``datetime``.

    It is raised before any request goes out, so there is nothing to retry — the fix is in the
    calling code.
    """

    def __init__(self, message: str) -> None:
        super().__init__(NO_ERROR_CODE, message, family="config")


# Familia -> clase. Las que faltan —`general`, `role`, `payment` y cualquier rango nuevo— caen a
# proposito en la clase base: existen en el servidor pero no son superficie de integracion, y darles
# clase propia seria prometer un `except` que luego habria que mantener.
_FAMILY_CLASSES: dict[str, type[PlanVortexError]] = {
    "auth": AuthError,
    "user": UserError,
    "account": AccountError,
    "file": FileError,
    "publication": PublicationError,
    "organization": OrganizationError,
    "plan_limit": PlanLimitError,
    "messaging": MessagingError,
    "contact": ContactError,
    "product": ProductError,
    "ai_plan": AiPlanError,
    "integration": IntegrationError,
}


def error_family_for_code(code: int) -> str | None:
    """The family a code belongs to, or ``None`` when it falls outside the known catalogue."""
    for rango in PLANVORTEX_ERROR_RANGES:
        if rango.start <= code <= rango.end:
            return rango.family
    return None


def error_class_for_code(code: int) -> type[PlanVortexError]:
    """The class a code maps to. Anything unmapped lands on :class:`PlanVortexError`."""
    family = error_family_for_code(code)
    if family is None:
        return PlanVortexError
    return _FAMILY_CLASSES.get(family, PlanVortexError)


def _is_api_error_body(body: object) -> TypeGuard[dict[str, Any]]:
    """``{"code": 1301, ...}``, the shape every domain error of this API has.

    The ``bool`` check is not paranoia: in Python ``True`` **is** an ``int``, so a body carrying
    ``{"code": true}`` would otherwise be read as error code 1.

    It returns a ``TypeGuard`` rather than a plain ``bool`` so the caller gets the narrowing too —
    otherwise mypy still sees ``object`` on the other side of the ``if`` and the whole check buys
    nothing but a runtime guard.
    """
    if not isinstance(body, dict):
        return False
    code = body.get("code")
    return isinstance(code, int) and not isinstance(code, bool)


def create_error_from_response(
    *,
    body: object,
    status: int,
    request_id: str | None = None,
    retry_after: float | None = None,
) -> PlanVortexError:
    """Turn an error response into the class it deserves.

    A body with no ``code`` — a proxy's 502, a load balancer's HTML page — is not a domain error: it
    comes out as the base class with ``family="http"`` and the whole body in ``data``, which is also
    what ``auth.py`` needs to recognise OAuth2's ``{error, error_description}``.
    """
    if _is_api_error_body(body):
        code = int(body["code"])
        datos = body.get("data")
        return error_class_for_code(code)(
            code,
            str(body.get("message") or "PlanVortex error"),
            data=datos if isinstance(datos, dict) else {},
            status=status,
            request_id=request_id,
            retry_after=retry_after,
        )

    return PlanVortexError(
        NO_ERROR_CODE,
        f"HTTP {status}",
        data=body if isinstance(body, dict) else {"body": body},
        status=status,
        request_id=request_id,
        retry_after=retry_after,
        family="http",
    )


def is_token_error(error: object) -> bool:
    """Does this error say the token is no longer valid? (codes 501 and 522, both inside a 400).

    This is what triggers the client's single retry with a fresh token.
    """
    return isinstance(error, PlanVortexError) and error.code in TOKEN_ERROR_CODES
