"""Pagination: the envelope the API wraps a list in, and the page that comes out of it.

WHY THIS IS A FILE AND NOT THREE LINES IN EVERY RESOURCE: the API paginates with ``offset``/``limit``
and wraps each list under the name of its own resource — ``{publications, total}``,
``{accounts, total}``, ``{uploads, total}`` (§ trampa 6 of the Node roadmap). The envelope is a
detail of the transport, so it is opened here once and every domain returns the same :class:`Page`.

THERE IS NO SYNCHRONOUS TWIN OF THIS FILE, and that is a decision rather than an oversight. The
chaining loop — the part that really is asynchronous — lives in ``resources/base.py``, which *is*
generated, so :class:`Page` stays **one** class. Had this module been the twin's source there would
be two ``Page`` types with the same fields, ``isinstance`` would answer no across the two clients,
and a function annotated for one of them would refuse the other.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Generic, NamedTuple, TypeVar

from planvortex._core.errors import NO_ERROR_CODE, PlanVortexError

T = TypeVar("T")

# Elementos por pagina cuando quien itera no pide un `limit`.
DEFAULT_PAGE_SIZE = 50

# El seguro contra un bucle infinito. NO es un limite de cuanto se puede leer: es lo que hace que un
# servidor que ignore el `offset` falle en vez de colgar el proceso del integrador. A 100 elementos
# por pagina son un millon.
MAX_PAGES = 10_000


@dataclass(frozen=True)
class Page(Generic[T]):
    """One page of a listing, with the envelope already opened.

    ``total`` is what the server counted for the whole query, not what this page carries — a page of
    50 out of 1.284 has ``len(page.data) == 50`` and ``page.total == 1284``.
    """

    #: The elements of this page, in the order the server sent them.
    data: list[T]
    #: How many there are in total, ignoring the pagination.
    total: int

    def __len__(self) -> int:
        """How many elements THIS page carries. For the whole count there is ``total``."""
        return len(self.data)

    def __iter__(self) -> Iterator[T]:
        """``for account in page`` walks this page. To walk them all there is ``iterate()``."""
        return iter(self.data)

    def __bool__(self) -> bool:
        """A page with no elements is falsy, whatever ``total`` says."""
        return bool(self.data)


class PageParams(NamedTuple):
    """The page the chaining loop is asking for. Both fields always travel."""

    limit: int
    offset: int


def unwrap_list(body: object, key: str) -> Page[Any]:
    """Take ``{data, total}`` out of the envelope the API wraps a list in.

    ``key`` is the EXACT name of the field carrying the array (``publications``, ``accounts``...).
    If it is not there, either the envelope changed or the wrong name was passed, and that is said
    out loud: without this check the method would return ``Page(data=None)`` and the failure would
    surface three layers further up. It is literally what happened to the publications spec, which
    announced ``{uploads, total}``.
    """
    envelope = body if isinstance(body, dict) else None
    data = envelope.get(key) if envelope is not None else None

    if not isinstance(data, list):
        raise PlanVortexError(
            NO_ERROR_CODE,
            f'The response does not carry "{key}": the list envelope is not the expected one.',
            data={"expected": key, "received": sorted(envelope) if envelope is not None else body},
            family="http",
        )

    total = envelope.get("total") if envelope is not None else None
    # `total` viaja siempre, pero si un despliegue viejo no lo mandara, la longitud de la pagina es
    # mejor respuesta que un `None` colandose como numero. Un `bool` NO cuenta: en Python es un int,
    # asi que un `total: true` se convertiria en una pagina de un elemento.
    if isinstance(total, int) and not isinstance(total, bool):
        return Page(data=data, total=total)
    return Page(data=data, total=len(data))


def unwrap_one(body: object, key: str) -> Any:
    """Take a single resource out of the envelope the API wraps it in (``{publication}``, ...)."""
    envelope = body if isinstance(body, dict) else None
    value = envelope.get(key) if envelope is not None else None

    if value is None:
        raise PlanVortexError(
            NO_ERROR_CODE,
            f'The response does not carry "{key}".',
            data={"expected": key, "received": sorted(envelope) if envelope is not None else body},
            family="http",
        )
    return value


def too_many_pages(paginas: int) -> PlanVortexError:
    """The error the chaining loop raises when it hits its page cap.

    It lives here and not in ``base.py`` so that the message is written once for the two twins, and
    it takes the number instead of reading :data:`MAX_PAGES` so that the message cannot say one
    thing while the loop did another.
    """
    return PlanVortexError(
        NO_ERROR_CODE,
        f"Pagination went past {paginas} pages: the server is not advancing with the offset.",
        family="http",
    )
