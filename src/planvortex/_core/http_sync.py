"""GENERADO POR `scripts/generate_sync.py`. NO SE EDITA A MANO.

Gemelo sincrono de `src/planvortex/_core/http.py`.

Lo que haya que cambiar se cambia ALLI y se regenera con `uv run python scripts/generate_sync.py`;
la CI regenera y falla si hay diferencias.
"""

from __future__ import annotations

import random
import time
from collections.abc import Mapping
from typing import Any

import httpx2

from planvortex._core.errors import PlanVortexConnectionError, PlanVortexError, create_error_from_response
from planvortex._core.query import encode_query
from planvortex._core.transport import (
    DEFAULT_TIMEOUT_SECONDS,
    HttpHooks,
    HttpMethod,
    HttpRequest,
    HttpResponse,
    RequestInfo,
    ResponseInfo,
    RetryConfig,
    RetryInfo,
    parse_retry_after,
)

__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "PRE_FLIGHT_ERRORS",
    "RETRYABLE_STATUS",
    "HttpClient",
    "HttpHooks",
    "HttpMethod",
    "HttpRequest",
    "HttpResponse",
    "RequestInfo",
    "ResponseInfo",
    "RetryConfig",
    "RetryInfo",
    "parse_retry_after",
]

# Los unicos status que se reintentan. Un 400, un 401 o un 404 no se arreglan repitiendolos.
RETRYABLE_STATUS = frozenset({408, 429, 502, 503, 504})

# Excepciones de httpx2 que demuestran que la peticion NI SALIO. Son las unicas con las que se
# repite un POST (§ Trampa P10 del roadmap).
#
# `ReadTimeout`, `WriteTimeout`, `WriteError`, `ReadError` y `RemoteProtocolError` NO estan aqui a
# proposito: todas pueden ocurrir DESPUES de que el servidor recibiera el cuerpo, y entonces repetir
# el POST publica dos veces.
PRE_FLIGHT_ERRORS: tuple[type[Exception], ...] = (
    httpx2.ConnectError,
    httpx2.ConnectTimeout,
    httpx2.PoolTimeout,
)


def _is_idempotent(request: HttpRequest) -> bool:
    """Methods that can be repeated without changing anything on the server."""
    if request.idempotent is not None:
        return request.idempotent
    return request.method != "POST"


def _parse_body(response: httpx2.Response) -> Any:
    """JSON if possible; the raw text otherwise. An empty body is ``None``, never an exception."""
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return response.text


class HttpClient:
    """The httpx2 transport, with retries, hooks and this API's error shapes."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        retry: RetryConfig | None = None,
        hooks: HttpHooks | None = None,
        headers: Mapping[str, str] | None = None,
        client: httpx2.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._retry = retry or RetryConfig()
        self._hooks = hooks or HttpHooks()
        # En minusculas para que no convivan `User-Agent` y `user-agent` en la misma peticion.
        self._headers = {key.lower(): value for key, value in (headers or {}).items()}
        # Un cliente inyectado es del integrador: se usa pero no se cierra.
        self._owns_client = client is None
        self._client = client or httpx2.Client(timeout=timeout)

    @property
    def base_url(self) -> str:
        return self._base_url

    def request(self, request: HttpRequest) -> HttpResponse:
        """Send it, retry it if the rules allow, and translate the failure if it fails."""
        url = f"{self._base_url}{request.path}"
        params = encode_query(request.query)
        headers = {"accept": "application/json", **self._headers}
        headers.update({key.lower(): value for key, value in request.headers.items()})
        timeout = request.timeout if request.timeout is not None else self._timeout
        retryable = _is_idempotent(request) and request.repeatable

        attempt = 0
        while True:
            attempt += 1
            if attempt > 1:
                rewind_body(request)
            self._notify_request(RequestInfo(request.method, url, attempt))
            started = time.monotonic()

            try:
                response = self._client.request(
                    request.method,
                    url,
                    # Tupla y no lista: `list` es INVARIANTE, asi que un `list[tuple[str, str]]`
                    # no encaja donde httpx2 pide `list[tuple[str, str | int | ...]]`. Una tupla
                    # si, porque es covariante — y de paso nadie puede mutarla por el camino.
                    params=tuple(params) or None,
                    json=request.json,
                    data=request.data,
                    files=request.files,
                    headers=headers,
                    timeout=timeout,
                )
            except httpx2.HTTPError as error:
                fallo = _to_connection_error(error, request, timeout)
                # Un POST solo se repite si el fallo demuestra que la peticion ni salio; y un cuerpo
                # que no se puede rebobinar no se repite ni asi.
                puede = retryable or (request.repeatable and isinstance(error, PRE_FLIGHT_ERRORS))
                if not puede or attempt > self._retry.max_retries:
                    raise fallo from error
                delay = self._backoff(attempt)
                self._notify_retry(RetryInfo(request.method, url, attempt, delay, None, error))
                time.sleep(delay)
                continue

            self._notify_response(
                ResponseInfo(request.method, url, attempt, response.status_code, time.monotonic() - started)
            )
            request_id = response.headers.get("x-request-id")

            if response.is_success:
                vacia = request.parse == "none" or response.status_code == 204
                datos = None if vacia else _parse_body(response)
                return HttpResponse(datos, response.status_code, response.headers, request_id)

            retry_after = parse_retry_after(response.headers.get("retry-after"))
            debe_reintentar = (
                retryable and response.status_code in RETRYABLE_STATUS and attempt <= self._retry.max_retries
            )
            espera = self._backoff(attempt) if retry_after is None else retry_after

            # Un `Retry-After` mas largo que el tope no se espera: se devuelve el error con el dato
            # dentro para que lo decida quien llama.
            if not debe_reintentar or espera > self._retry.max_delay:
                raise create_error_from_response(
                    body=_parse_body(response),
                    status=response.status_code,
                    request_id=request_id,
                    retry_after=retry_after,
                )

            self._notify_retry(RetryInfo(request.method, url, attempt, espera, response.status_code, None))
            time.sleep(espera)

    def _backoff(self, attempt: int) -> float:
        """Exponential backoff with full jitter: random between 0 and that attempt's cap."""
        # `2.0` y no `2`: en typeshed, `int ** int` devuelve `Any` (podria ser float con un
        # exponente negativo), y ese `Any` se comia el tipo de todo el calculo sin avisar.
        techo = min(self._retry.max_delay, self._retry.base_delay * 2.0 ** (attempt - 1))
        # `random` a secas y no `secrets`: esto es jitter para desincronizar reintentos, no un
        # valor que nadie pueda adivinar en su perjuicio.
        return random.random() * techo

    def _notify_request(self, info: RequestInfo) -> None:
        if self._hooks.on_request is not None:
            self._hooks.on_request(info)

    def _notify_response(self, info: ResponseInfo) -> None:
        if self._hooks.on_response is not None:
            self._hooks.on_response(info)

    def _notify_retry(self, info: RetryInfo) -> None:
        if self._hooks.on_retry is not None:
            self._hooks.on_retry(info)

    def close(self) -> None:
        """Close the underlying httpx2 client, unless the integrator supplied their own."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def rewind_body(request: HttpRequest) -> None:
    """Put a streamed body back where it started, before repeating the request.

    It lives outside the client because the token retry in ``_client.py`` repeats a request too —
    once, after a 501 or a 522 — and that repeat has exactly the same problem: the body of an upload
    is an open file whose pointer is already at the end.
    """
    if request.rewind is not None:
        request.rewind()


def _to_connection_error(error: httpx2.HTTPError, request: HttpRequest, timeout: float) -> PlanVortexError:
    """Translate an httpx2 failure into ours, keeping whether it was a timeout."""
    if isinstance(error, httpx2.TimeoutException):
        return PlanVortexConnectionError(
            f"{request.method} {request.path} ran out of its {timeout}s timeout",
            timeout=True,
        )
    return PlanVortexConnectionError(
        f"{request.method} {request.path} could not connect ({type(error).__name__})",
        timeout=False,
    )
