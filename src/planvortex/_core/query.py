"""Turning Python keyword arguments into the query string the server actually reads.

Two things happen here and nowhere else.

**One: five parameters of the API are camelCase.** The rest of the surface is ``snake_case``
(``from_date``, ``social_network``, ``id_account``...) and needs no translation at all — which is
luck, not design: none of them collides with a Python keyword. But five do, and in Python they would
stand out like a sore thumb, so the public argument is ``get_use`` and what goes on the wire is
``?getUse=true``.

The translation lives in ONE map on purpose. Written by hand into the four or five methods that need
it, the sixth one that appears a year from now gets forgotten — and filtering by a parameter the
server does not read **returns the whole list without warning anybody**, which is exactly what
happened with ``account_type`` in the Node library. ``tests/test_query.py`` walks the committed
OpenAPI bundle and fails if the map and the specification disagree in either direction.

**Two: lists travel as a repeated key.** ``state=["pending", "error"]`` becomes
``?state=pending&state=error``, which is what ``getArrayParams`` on the server understands. It also
accepts the comma-joined form, but the repeated one is what the Node client sends and the two
libraries are meant to behave the same.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any

from planvortex._core.errors import PlanVortexConfigError

# Argumento en Python -> nombre en el cable. Son los UNICOS parametros de la API que no van en
# snake_case, sacados del bundle del OpenAPI y no de la memoria.
#
# `forceDelete` no estaba en la lista del roadmap, que hablaba de cuatro: aparecio recorriendo el
# spec, que es justo el motivo por el que el test lo recorre en vez de fiarse de una lista escrita a
# mano. Es el quinto, y habra un sexto.
CAMEL_CASE_PARAMS: dict[str, str] = {
    "get_use": "getUse",
    "offset_organizations": "offsetOrganizations",
    "limit_organizations": "limitOrganizations",
    "order_by_publish": "orderByPublish",
    "force_delete": "forceDelete",
}

# El camino de vuelta, para el test de paridad y para quien lea un spec y busque el argumento.
WIRE_TO_PYTHON: dict[str, str] = {wire: python for python, wire in CAMEL_CASE_PARAMS.items()}

QueryValue = Any


def wire_name(name: str) -> str:
    """The name this argument travels under. Anything not in the map goes through untouched."""
    return CAMEL_CASE_PARAMS.get(name, name)


def format_datetime(value: datetime, *, field: str = "datetime") -> str:
    """ISO-8601 **with offset**, or an exception. Never a guess. See § Trampa P8 of the roadmap.

    ``publish_date`` ends up in a Typegoose ``Date``, and Mongoose casts the string with
    JavaScript's ``new Date(...)``. There, ``"2026-09-01T10:00:00"`` with no offset is read in the
    **server process's** timezone and ``"2026-09-01T10:00:00Z"`` in UTC. That the containers run in
    UTC is a deployment accident, not a contract.

    A naive ``datetime`` therefore raises instead of assuming anything. Assuming UTC publishes at
    the wrong time for whoever is in Madrid; assuming the process's local zone publishes at the
    wrong time for whoever is in Docker. Raising is the only option that does not lie.
    """
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise PlanVortexConfigError(
            f"{field} is a naive datetime ({value.isoformat()}) and PlanVortex would read it in the "
            "server's timezone, which is not something you can rely on. Attach a timezone: "
            "datetime(..., tzinfo=timezone.utc), or .astimezone(), or pass an ISO-8601 string with "
            "an offset."
        )
    return value.isoformat()


def _scalar(value: object, *, field: str) -> str:
    if isinstance(value, bool):
        # Antes que `int`: en Python un bool ES un int, y `str(True)` daria "True", que el servidor
        # no lee como verdadero — compara contra la cadena "true".
        return "true" if value else "false"
    if isinstance(value, datetime):
        return format_datetime(value, field=field)
    return str(value)


def encode_query(params: Mapping[str, QueryValue] | None) -> list[tuple[str, str]]:
    """``{"state": ["pending"], "get_use": True}`` -> ``[("state", "pending"), ("getUse", "true")]``.

    ``None`` values are dropped — that is what makes an optional argument optional — and so are
    empty lists: sending ``?state=`` filters by the empty string and would come back with nothing.
    """
    if not params:
        return []

    pares: list[tuple[str, str]] = []
    for name, value in params.items():
        if value is None:
            continue
        clave = wire_name(name)
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            pares.append((clave, _scalar(value, field=name)))
            continue
        # Una lista viaja como clave repetida, no aplanada con comas.
        for item in _as_sequence(value):
            if item is None:
                continue
            pares.append((clave, _scalar(item, field=name)))
    return pares


def _as_sequence(value: Iterable[object]) -> Sequence[object]:
    return value if isinstance(value, Sequence) else list(value)
