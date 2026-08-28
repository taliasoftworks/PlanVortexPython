"""Authentication: ``client_credentials`` against ``POST /oauth/token``, token held in memory.

The library **does not talk to Keycloak**. The identity provider is not part of the public contract:
the integrator configures a single URL, ``api.planvortex.com``, and the day we change provider
nobody finds out.

WHAT TO UNDERSTAND BEFORE TOUCHING THIS FILE:

- **One token, not twenty.** Ten calls in flight with an expired token have to make ONE token
  request, not ten. The server's brake is 30 attempts per minute per ``client_id``, so without the
  lock a cold start with twenty requests eats its own quota.
- **It refreshes BEFORE expiring**, with 60 seconds of margin. A token that expires mid-flight turns
  into a 400 with ``code: 501`` the integrator could not have prevented.
- **This route's error has an OAuth2 shape**, ``{error, error_description}``, not the
  ``{code, message, data}`` of the rest of the API. It is the server's only exception, and here it
  becomes :class:`PlanVortexAuthenticationError`.
- **The token state lives on the instance, never in a global.** Two clients with different
  credentials in the same process is a normal case — a multi-tenant integrator — and a token in a
  module variable crosses them over.

THIS FILE IS THE SOURCE OF ``auth_sync.py``. The lock is the reason the twin is generated rather
than written twice: ``asyncio.Lock`` protects nothing across threads, and the synchronous client
**is** shared across threads (Django under gunicorn, a ``ThreadPoolExecutor``). One line of the
generator, instead of a mistake waiting to happen.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from planvortex._core.errors import PlanVortexAuthenticationError, PlanVortexError
from planvortex._core.http import AsyncHttpClient, HttpRequest

# Margen con el que se pide un token nuevo antes de que caduque el que hay.
TOKEN_REFRESH_MARGIN_SECONDS = 60.0

# La ruta de la fachada OAuth2. Relativa a la `base_url`, que ya lleva el `/v1.0.0`.
TOKEN_PATH = "/oauth/token"

# Suelo conservador cuando el servidor no manda `expires_in`. Una hora es lo que dura el token mas
# largo que emite hoy, y el 501 cubre el resto.
DEFAULT_TOKEN_LIFETIME_SECONDS = 3600.0


@dataclass(frozen=True)
class _CachedToken:
    token: str
    expires_at: float


class AsyncStaticTokenAuth:
    """A token that is already issued and never renewed: the ``temporal_connect_token``.

    It is the piece a PERSON uses to connect their social account. It lasts fifteen minutes, is
    bound to a single organization and cannot be refreshed — when it expires, the app issues another
    one. That is why :meth:`invalidate` does nothing: there is nothing to ask for again. And it is
    spent as soon as an account connects; the next attempt answers 543.
    """

    def __init__(self, token: str) -> None:
        self._token = token

    async def get_token(self) -> str:
        return self._token

    def invalidate(self) -> None:
        """Deliberately empty: a temporal token does not renew itself."""


class AsyncClientCredentialsAuth:
    """``client_credentials``, cached on the instance, refreshed early, behind one lock."""

    def __init__(
        self,
        http: AsyncHttpClient,
        *,
        client_id: str,
        client_secret: str,
        scope: str | None = None,
    ) -> None:
        self._http = http
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._cached: _CachedToken | None = None
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        """The cached token, or a fresh one. Concurrent callers share a single request."""
        cached = self._cached
        if cached is not None and cached.expires_at - time.monotonic() > TOKEN_REFRESH_MARGIN_SECONDS:
            return cached.token

        async with self._lock:
            # Se vuelve a mirar DENTRO del cerrojo: entre el primer vistazo y llegar aqui, otro
            # llamante pudo haber pedido el token ya. Sin esta segunda comprobacion, diez llamadas
            # en paralelo hacen diez peticiones — en fila, que es incluso peor que a la vez.
            cached = self._cached
            if cached is not None and cached.expires_at - time.monotonic() > TOKEN_REFRESH_MARGIN_SECONDS:
                return cached.token
            return await self._fetch_token()

    def invalidate(self) -> None:
        """Drop the cached token. The client calls it when the server answers 501 or 522."""
        self._cached = None

    async def _fetch_token(self) -> str:
        body = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        if self._scope:
            body["scope"] = self._scope

        try:
            response = await self._http.request(
                HttpRequest(
                    method="POST",
                    path=TOKEN_PATH,
                    data=body,
                    # Es el unico POST reintentable de la libreria: pedir un token no crea nada.
                    idempotent=True,
                )
            )
        except PlanVortexError as error:
            raise to_authentication_error(error) from error

        payload = response.data
        access_token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(access_token, str) or not access_token:
            raise PlanVortexAuthenticationError(
                "server_error", "The token endpoint answered without an access_token"
            )

        lifetime = _lifetime_from(payload)
        self._cached = _CachedToken(access_token, time.monotonic() + lifetime)
        return access_token


def _lifetime_from(payload: dict[str, object]) -> float:
    """``expires_in`` in seconds. It is the server's datum, so it is never assumed."""
    raw = payload.get("expires_in")
    try:
        seconds = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_TOKEN_LIFETIME_SECONDS
    return seconds if seconds > 0 else DEFAULT_TOKEN_LIFETIME_SECONDS


def to_authentication_error(error: PlanVortexError) -> PlanVortexError:
    """Translate whatever comes out of the token endpoint.

    A network failure is passed through untouched: it is not that the credentials are wrong, it is
    that there was no conversation, and confusing the two sends the integrator to check a secret
    that is fine.
    """
    if error.status is None:
        return error

    body = error.data
    oauth_error = body.get("error")
    description = body.get("error_description")
    return PlanVortexAuthenticationError(
        oauth_error if isinstance(oauth_error, str) else "invalid_client",
        description if isinstance(description, str) else error.message,
        status=error.status,
        request_id=error.request_id,
        retry_after=error.retry_after,
    )
