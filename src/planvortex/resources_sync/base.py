"""GENERADO POR `scripts/generate_sync.py`. NO SE EDITA A MANO.

Gemelo sincrono de `src/planvortex/resources/base.py`.

Lo que haya que cambiar se cambia ALLI y se regenera con `uv run python scripts/generate_sync.py`;
la CI regenera y falla si hay diferencias.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Protocol

from planvortex._core.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGES,
    Page,
    PageParams,
    too_many_pages,
    unwrap_list,
    unwrap_one,
)
from planvortex._core.query import QueryValue
from planvortex._core.transport import HttpRequest, HttpResponse

Query = Mapping[str, QueryValue]


class RequestSender(Protocol):
    """The only thing a resource needs from the client."""

    def request(self, request: HttpRequest) -> HttpResponse: ...


class PageFetcher(Protocol):
    """A function that returns one page. It is what a resource hands to the chaining loop."""

    def __call__(self, params: PageParams, /) -> Page[Any]: ...


class Resource:
    """The base of every resource. All of it is private: the public API is each domain's."""

    def __init__(self, client: RequestSender) -> None:
        self._client = client

    def _request(self, request: HttpRequest) -> Any:
        """The request, and the parsed body out of the transport. The only untyped step."""
        response = self._client.request(request)
        return response.data

    def _get(self, path: str, query: Query | None = None, *, timeout: float | None = None) -> Any:
        datos: Any = self._request(HttpRequest(method="GET", path=path, query=query, timeout=timeout))
        return datos

    def _post(
        self,
        path: str,
        body: Any = None,
        *,
        query: Query | None = None,
        files: Any = None,
        rewind: Any = None,
        repeatable: bool = True,
        timeout: float | None = None,
    ) -> Any:
        datos: Any = self._request(
            HttpRequest(
                method="POST",
                path=path,
                query=query,
                json=body,
                files=files,
                rewind=rewind,
                repeatable=repeatable,
                timeout=timeout,
            )
        )
        return datos

    def _put(self, path: str, body: Any = None, *, timeout: float | None = None) -> Any:
        datos: Any = self._request(HttpRequest(method="PUT", path=path, json=body, timeout=timeout))
        return datos

    def _delete(self, path: str, query: Query | None = None, *, timeout: float | None = None) -> Any:
        datos: Any = self._request(HttpRequest(method="DELETE", path=path, query=query, timeout=timeout))
        return datos

    def _list(
        self, path: str, key: str, query: Query | None = None, *, timeout: float | None = None
    ) -> Page[Any]:
        """A ``GET`` of a list, already out of its envelope as a :class:`Page`."""
        cuerpo: Any = self._get(path, query, timeout=timeout)
        pagina: Page[Any] = unwrap_list(cuerpo, key)
        return pagina

    def _one(self, path: str, key: str, query: Query | None = None, *, timeout: float | None = None) -> Any:
        """A ``GET`` of a single resource, already out of its envelope."""
        cuerpo: Any = self._get(path, query, timeout=timeout)
        recurso: Any = unwrap_one(cuerpo, key)
        return recurso

    def _post_one(
        self,
        path: str,
        key: str,
        body: Any = None,
        *,
        query: Query | None = None,
        files: Any = None,
        rewind: Any = None,
        repeatable: bool = True,
        timeout: float | None = None,
    ) -> Any:
        """A ``POST`` that answers with a wrapped resource."""
        cuerpo: Any = self._post(
            path,
            body,
            query=query,
            files=files,
            rewind=rewind,
            repeatable=repeatable,
            timeout=timeout,
        )
        recurso: Any = unwrap_one(cuerpo, key)
        return recurso

    def _put_one(self, path: str, key: str, body: Any = None, *, timeout: float | None = None) -> Any:
        """A ``PUT`` that answers with a wrapped resource."""
        cuerpo: Any = self._put(path, body, timeout=timeout)
        recurso: Any = unwrap_one(cuerpo, key)
        return recurso

    def _delete_one(
        self, path: str, key: str, query: Query | None = None, *, timeout: float | None = None
    ) -> Any:
        """A ``DELETE`` that answers with a wrapped resource, which only a couple of routes do."""
        cuerpo: Any = self._delete(path, query, timeout=timeout)
        recurso: Any = unwrap_one(cuerpo, key)
        return recurso

    def _iterate_pages(
        self,
        fetch: PageFetcher,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Iterator[Any]:
        """Chain pages until they run out, handing over the elements one by one.

        TWO THINGS TO KNOW:

        1. **It stops on an empty page**, not when it has read ``total``. ``total`` is counted with
           a separate query, so on a collection that is moving it can disagree with what the pages
           return; trusting it would give either an endless loop or a lost page. It also stops on a
           page shorter than the limit, which is the signal that there is no more.
        2. **It has a page cap.** A server ignoring the ``offset`` would return the same page for
           ever, and a loop with no cap takes the integrator's process down with it. :data:`MAX_PAGES`
           is a fuse and not a usage limit: at 100 elements a page it is a million of them.
        """
        tamano = limit if limit is not None else DEFAULT_PAGE_SIZE
        salto = offset if offset is not None else 0

        for _ in range(MAX_PAGES):
            page = fetch(PageParams(limit=tamano, offset=salto))
            if not page.data:
                return
            for item in page.data:
                yield item
            # Una pagina mas corta que el limite es la ultima: pedir la siguiente seria una llamada
            # que ya se sabe vacia.
            if len(page.data) < tamano:
                return
            salto += len(page.data)

        raise too_many_pages(MAX_PAGES)


def require_id(value: object, name: str) -> str:
    """A Mongo identifier as it travels in the URL, checked here and not by the server.

    An empty one interpolated into the path gives a 404 for ``/organizations//accounts``, and a
    ``None`` that slipped through gives one for ``/organizations/None/accounts``. Neither error says
    what actually happened, which is that the caller forgot an argument.

    Its parameter is ``object`` and not ``str`` on purpose: the check is there for the caller who
    is NOT running a type checker, which is the only one it can save. Annotated ``str``, the
    ``isinstance`` would be dead code that mypy would rightly point at.
    """
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{name} is required and has to be a non-empty identifier, not {value!r}.")
    return value
