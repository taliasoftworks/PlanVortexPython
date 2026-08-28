"""Publications: the path ``/developers`` sells.

WHAT TO KNOW BEFORE CALLING ANYTHING HERE:

- **Creating a publication with invalid content IS NOT AN ERROR.** The server stores it in state
  ``withErrors`` with the reason inside (``publication_errors``), because the content is validated
  against the network and that is not a failure of the request. A ``try/except`` is not enough: you
  have to look at ``state``.
- **With no ``publish_date`` it goes out NOW**, inside this very request. With a future date it stays
  ``ready`` and the robot sends it at its hour.
- **``files`` is SENT as identifiers and comes back POPULATED.** What arrives in the response are
  whole ``Upload`` objects, not ids.
- **``id_account`` changes shape depending on the operation**: here (create, read, retry) it comes
  resolved, and in the listing and on update it comes as an identifier. ``planvortex.types.account_id``
  covers it.
- **Deleting a publication deletes it FROM THE SOCIAL NETWORK TOO.** It is not just taking it out of
  the library.

THIS FILE IS THE SOURCE OF ``resources_sync/publications.py``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from typing import Any

from planvortex._core.pagination import Page, PageParams
from planvortex._core.query import format_datetime
from planvortex.resources.base import AsyncResource, Query, require_id
from planvortex.types import (
    Publication,
    PublicationInput,
    PublicationRetryResult,
    PublicationStats,
    PublicationStatsHistory,
)


class AsyncPublicationsResource(AsyncResource):
    """Create, schedule, edit, retry and measure a publication."""

    async def create(
        self,
        id_organization: str,
        id_account: str,
        body: PublicationInput,
        *,
        timeout: float | None = None,
    ) -> Publication:
        """Create a publication on an account.

        With no ``publish_date`` it is sent in this same request and the response already says
        whether it went out (``state == "sended"``) or failed and why. With a future date it stays
        ``ready``.

        .. code-block:: python

            publication = await pv.publications.create(
                org_id,
                account_id,
                {
                    "social_network": "instagram",
                    "text": "Nuevo horno, nuevas hogazas",
                    "files": [upload["_id"]],
                    "publish_date": datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
                },
            )
        """
        publicacion: Publication = await self._post_one(
            f"{self._account_path(id_organization, id_account)}/publish",
            "publication",
            _serialize(body),
            timeout=timeout,
        )
        return publicacion

    async def get(
        self, id_organization: str, id_publication: str, *, timeout: float | None = None
    ) -> Publication:
        """One publication, with its files and its account already resolved.

        A **deleted** publication answers 917, the same as one that never existed.
        """
        publicacion: Publication = await self._one(
            self._path(id_organization, id_publication), "publication", timeout=timeout
        )
        return publicacion

    async def list(
        self,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        from_date: datetime | str | None = None,
        to_date: datetime | str | None = None,
        search: str | None = None,
        order_by_publish: bool | None = None,
        state: Sequence[str] | None = None,
        accounts: Sequence[str] | None = None,
        social_network: Sequence[str] | None = None,
        timeout: float | None = None,
    ) -> Page[Publication]:
        """An organization's publications.

        ``order_by_publish`` orders and filters by ``publish_date`` instead of ``creation_date``,
        which is what you want for a calendar and not for an activity log. A ``datetime`` needs a
        timezone or the library raises rather than guess (§ Trampa P8).
        """
        pagina: Page[Publication] = await self._list(
            f"{self._organization_path(id_organization)}/publish",
            "publications",
            _list_query(
                limit,
                offset,
                from_date,
                to_date,
                search,
                order_by_publish,
                state,
                accounts,
                social_network,
            ),
            timeout=timeout,
        )
        return pagina

    def aiterate(
        self,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        from_date: datetime | str | None = None,
        to_date: datetime | str | None = None,
        search: str | None = None,
        order_by_publish: bool | None = None,
        state: Sequence[str] | None = None,
        accounts: Sequence[str] | None = None,
        social_network: Sequence[str] | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[Publication]:
        """An organization's publications, chaining pages."""

        async def buscar(params: PageParams) -> Page[Publication]:
            return await self.list(
                id_organization,
                limit=params.limit,
                offset=params.offset,
                from_date=from_date,
                to_date=to_date,
                search=search,
                order_by_publish=order_by_publish,
                state=state,
                accounts=accounts,
                social_network=social_network,
                timeout=timeout,
            )

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    async def list_by_account(
        self,
        id_organization: str,
        id_account: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        from_date: datetime | str | None = None,
        to_date: datetime | str | None = None,
        search: str | None = None,
        order_by_publish: bool | None = None,
        state: Sequence[str] | None = None,
        timeout: float | None = None,
    ) -> Page[Publication]:
        """ONE account's publications. Same filters as :meth:`list`."""
        pagina: Page[Publication] = await self._list(
            f"{self._account_path(id_organization, id_account)}/publish",
            "publications",
            _list_query(limit, offset, from_date, to_date, search, order_by_publish, state, None, None),
            timeout=timeout,
        )
        return pagina

    async def update(
        self,
        id_organization: str,
        id_publication: str,
        body: PublicationInput,
        *,
        timeout: float | None = None,
    ) -> Publication:
        """Change a publication that has not gone out yet. A ``sended`` one returns error 921.

        Editing PUTS THE RETRY COUNTER BACK TO ZERO: the counter counts attempts at publishing *that*
        content, and you have just changed it. It is also the way out when the three are used up.
        """
        publicacion: Publication = await self._put_one(
            self._path(id_organization, id_publication), "publication", _serialize(body), timeout=timeout
        )
        return publicacion

    async def update_by_account(
        self,
        id_organization: str,
        id_account: str,
        id_publication: str,
        body: PublicationInput,
        *,
        timeout: float | None = None,
    ) -> Publication:
        """The same as :meth:`update`, through the route that also names the account.

        The API has both and **the same handler serves them**: it makes no difference which one you
        call, and ``id_account`` is only used to check that the account exists and belongs to that
        organization. It is here because it is a public route and whoever comes reading the
        documentation will look for it; for new code, :meth:`update`.
        """
        ruta = (
            f"{self._account_path(id_organization, id_account)}"
            f"/publish/{require_id(id_publication, 'id_publication')}"
        )
        publicacion: Publication = await self._put_one(ruta, "publication", _serialize(body), timeout=timeout)
        return publicacion

    async def remove(
        self, id_organization: str, id_publication: str, *, timeout: float | None = None
    ) -> None:
        """Delete a publication **and the post on the social network too**.

        On X deleting costs credits: without them it returns a 940 rather than a generic error.
        Afterwards it stops being readable by id — :meth:`get` answers 917, and therefore so does a
        second :meth:`remove`.
        """
        await self._delete(self._path(id_organization, id_publication), timeout=timeout)

    async def retry(
        self, id_organization: str, id_publication: str, *, timeout: float | None = None
    ) -> PublicationRetryResult:
        """Try a failed publication again, without touching its content.

        It is retried IN THE REQUEST, so the answer already says whether it went out this time. Every
        call spends a retry even if it fails on the content again; only X's credits stop it before
        spending one. A publication that is not in ``withErrors`` returns 949, and running out of
        retries, 950. The cap comes back in ``max_retries``: read it from there.
        """
        reintento: PublicationRetryResult = await self._post(
            f"{self._path(id_organization, id_publication)}/retry", timeout=timeout
        )
        return reintento

    async def metrics(
        self, id_organization: str, id_publication: str, *, timeout: float | None = None
    ) -> PublicationStats:
        """Ask the NETWORK for the metrics, live, and return its raw breakdown.

        **On X this costs one credit per read.** To paint a chart use :meth:`stats`, which reads what
        was already measured and costs nothing.
        """
        metricas: PublicationStats = await self._get(
            f"{self._path(id_organization, id_publication)}/metrics", timeout=timeout
        )
        return metricas

    async def stats(
        self, id_organization: str, id_publication: str, *, timeout: float | None = None
    ) -> PublicationStatsHistory:
        """A publication's measured evolution: one row per day, plus its last measurement.

        It is a pure read of what was stored: looking at the chart calls no network and costs no
        credits. An empty ``series`` is a valid answer — just sent, or a network with no statistics —
        and not an error. Each ``metrics`` is the RUNNING TOTAL at that date, not the day's increment.
        """
        historico: PublicationStatsHistory = await self._get(
            f"{self._path(id_organization, id_publication)}/stats", timeout=timeout
        )
        return historico

    async def list_on_network(
        self,
        id_organization: str,
        id_account: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        timeout: float | None = None,
    ) -> Page[Publication]:
        """What is published on the account's wall **according to the network**, not according to
        PlanVortex: it includes whatever was published outside.

        **On X it costs one credit per element read**, so here the ``limit`` is money.
        """
        pagina: Page[Publication] = await self._list(
            f"{self._account_path(id_organization, id_account)}/social_publications",
            "publications",
            {"limit": limit, "offset": offset},
            timeout=timeout,
        )
        return pagina

    def _organization_path(self, id_organization: str) -> str:
        return f"/organizations/{require_id(id_organization, 'id_organization')}"

    def _account_path(self, id_organization: str, id_account: str) -> str:
        cuenta = require_id(id_account, "id_account")
        return f"{self._organization_path(id_organization)}/accounts/{cuenta}"

    def _path(self, id_organization: str, id_publication: str) -> str:
        publicacion = require_id(id_publication, "id_publication")
        return f"{self._organization_path(id_organization)}/publish/{publicacion}"


def _list_query(
    limit: int | None,
    offset: int | None,
    from_date: datetime | str | None,
    to_date: datetime | str | None,
    search: str | None,
    order_by_publish: bool | None,
    state: Sequence[str] | None,
    accounts: Sequence[str] | None,
    social_network: Sequence[str] | None,
) -> Query:
    return {
        "limit": limit,
        "offset": offset,
        "from_date": from_date,
        "to_date": to_date,
        "search": search,
        # El servidor lo lee como el literal "true": un `false` no cambia nada, asi que se omite.
        "order_by_publish": True if order_by_publish else None,
        "state": state,
        "accounts": accounts,
        "social_network": social_network,
    }


def _serialize(body: PublicationInput) -> dict[str, Any]:
    """Every ``datetime`` in the body goes out in ISO-8601 **with its offset**, or it does not go.

    The query encoder already does this for a parameter, but the body travels through the JSON
    serializer, which does not know what a ``datetime`` is and would raise a ``TypeError`` that says
    nothing about publishing. Today ``publish_date`` is the only date in this shape and the loop
    still walks the whole body: the alternative is finding out through that ``TypeError`` the day
    the spec grows a second one.

    A naive one raises, deliberately and with an explanation, for the reasons in § Trampa P8:
    assuming UTC publishes at the wrong time for whoever is in Madrid, and assuming the process's
    zone does it for whoever is in Docker.
    """
    return {
        clave: format_datetime(valor, field=clave) if isinstance(valor, datetime) else valor
        for clave, valor in body.items()
    }
