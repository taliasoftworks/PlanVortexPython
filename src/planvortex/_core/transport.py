"""The vocabulary of the transport: what a request is, what a response is, and how it is tuned.

WHY THIS FILE EXISTS, and it is not a tidiness thing. ``http.py`` is the SOURCE of ``http_sync.py``:
whatever it declares is declared twice, once per twin. That is right for the client — ``httpx2`` has
two of those and they are not interchangeable — and wrong for everything that carries no I/O, because
two dataclasses with the same name and the same fields are still **two different types**. An
integrator who writes ``from planvortex import HttpHooks`` would get one of them, and handing it to
the other client would be a type error over a value that is identical field by field.

So the pieces that cross the public boundary live here, ONCE, and both twins import them:
:class:`RetryConfig` and :class:`HttpHooks` because they are constructor arguments,
:class:`HttpRequest` and :class:`HttpResponse` because ``PlanVortex.request`` is public, and the
three ``*Info`` because they are what a hook receives.

There is no async in here, so there is no twin to generate: ``scripts/generate_sync.py`` does not
know about this file and does not need to.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Literal

import httpx2

from planvortex._core.query import QueryValue

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]

# 120 s, como el panel: subir y publicar un video es lento de verdad.
DEFAULT_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True)
class RetryConfig:
    """How many times a failed request is repeated, and how long it waits in between."""

    #: How many times a failed request is REPEATED. ``0`` disables retries.
    max_retries: int = 2
    #: Base of the exponential backoff, in seconds. The real wait is random between 0 and the cap.
    base_delay: float = 0.5
    #: Cap on the wait between attempts, in seconds.
    #:
    #: Besides trimming the backoff, it decides what to do with a long ``Retry-After``: if the
    #: server asks for more than this, the library does **not** wait — it raises the error with
    #: ``retry_after`` set and lets the caller decide. A ``Retry-After: 300`` from the token
    #: endpoint's brake cannot turn into a call that hangs for five minutes.
    max_delay: float = 8.0


@dataclass(frozen=True)
class RequestInfo:
    """What is about to be sent. ``attempt`` is 1 the first time."""

    method: HttpMethod
    url: str
    attempt: int


@dataclass(frozen=True)
class ResponseInfo:
    """What came back, and how long that attempt took."""

    method: HttpMethod
    url: str
    attempt: int
    status: int
    duration: float


@dataclass(frozen=True)
class RetryInfo:
    """Why we are going round again, and how long we are waiting first."""

    method: HttpMethod
    url: str
    attempt: int
    delay: float
    #: The status that caused the retry, or ``None`` when it was a network failure.
    status: int | None
    #: The network error, if there was one.
    error: BaseException | None


@dataclass
class HttpHooks:
    """Hooks for the integrator's logger.

    They are synchronous on purpose, in both clients: if one raises, it raises on its own call
    rather than in the middle of a retry.
    """

    on_request: Callable[[RequestInfo], None] | None = None
    on_response: Callable[[ResponseInfo], None] | None = None
    on_retry: Callable[[RetryInfo], None] | None = None


@dataclass
class HttpRequest:
    """One request, before it knows anything about authentication."""

    method: HttpMethod
    #: Starts with ``/``, relative to the base URL.
    path: str
    query: Mapping[str, QueryValue] | None = None
    #: A mapping is serialised as JSON. ``httpx2`` primitives (``files``, ``data``) travel through
    #: their own fields.
    json: Any = None
    #: form-urlencoded body. Today only ``POST /oauth/token`` uses it.
    data: Mapping[str, str] | None = None
    files: Any = None
    headers: dict[str, str] = field(default_factory=dict)
    timeout: float | None = None
    #: Forces the request to be retryable even though it is a POST. Only for POSTs that create
    #: nothing — today, ``POST /oauth/token``.
    idempotent: bool | None = None
    #: ``"none"`` skips body parsing. By default JSON is attempted.
    parse: Literal["json", "none"] = "json"
    #: Puts a streamed body back where it started before a second attempt. Only an upload sets it:
    #: ``httpx2`` reads an open file from its current position, so a repeat over the same handle
    #: would send **zero bytes** and the server would answer a file error that says nothing about
    #: it (§ Trampa P5 del roadmap).
    rewind: Callable[[], None] | None = None
    #: ``False`` forbids EVERY repeat of this request, the pre-flight failures included — the ones
    #: that prove the request never left. It is what an upload from a stream that cannot be rewound
    #: (a pipe, a socket, a generator) sets: there is no second copy of those bytes anywhere, so
    #: "the request never left" stops being a reason to try again.
    repeatable: bool = True


@dataclass(frozen=True)
class HttpResponse:
    """A successful response, already unwrapped as far as the transport goes."""

    data: Any
    status: int
    headers: httpx2.Headers
    #: ``x-request-id``, when the deployment sets it.
    request_id: str | None


def parse_retry_after(header: str | None, *, now: datetime | None = None) -> float | None:
    """``Retry-After`` arrives in seconds or as an HTTP date. Returns seconds, or ``None``."""
    if not header:
        return None
    try:
        seconds = float(header)
    except ValueError:
        pass
    else:
        return seconds if seconds >= 0 else None

    try:
        fecha = parsedate_to_datetime(header)
    except (TypeError, ValueError):
        return None
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    ahora = now or datetime.now(timezone.utc)
    return max(0.0, (fecha - ahora).total_seconds())
