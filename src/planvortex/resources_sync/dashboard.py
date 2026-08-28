"""GENERADO POR `scripts/generate_sync.py`. NO SE EDITA A MANO.

Gemelo sincrono de `src/planvortex/resources/dashboard.py`.

Lo que haya que cambiar se cambia ALLI y se regenera con `uv run python scripts/generate_sync.py`;
la CI regenera y falla si hay diferencias.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from planvortex._shapes import (
    MetricsResult,
    PublicationsSummaryResult,
    TopPublicationsResult,
)
from planvortex.resources_sync.base import Query, Resource, require_id
from planvortex.types import Dashboard, PlanUse, PublicationsStatsResult


class DashboardResource(Resource):
    """The home screen, the aggregated metrics and the plan's consumption."""

    def summary(
        self,
        id_organization: str,
        *,
        from_date: datetime | str | None = None,
        to_date: datetime | str | None = None,
        timeout: float | None = None,
    ) -> Dashboard:
        """The whole home screen in ONE trip: operational health, publications, publication and
        account metrics, plan consumption, AI plans and unread messages.

        **A block that is missing is not an error.** Each one is checked against its own permission
        and left out when the caller cannot read it, instead of failing the whole request;
        ``available_blocks`` says which ones were allowed. A block that is ``True`` and does not
        arrive means there was no data — except ``messages``, which also goes off when the plan does
        not include chat.
        """
        pantalla: Dashboard = self._get(
            f"{self._path(id_organization)}/dashboard",
            self._range_query(from_date, to_date),
            timeout=timeout,
        )
        return pantalla

    def metrics(
        self,
        id_organization: str,
        *,
        from_date: datetime | str | None = None,
        to_date: datetime | str | None = None,
        group_by: str | None = None,
        names: Sequence[str] | None = None,
        timeout: float | None = None,
    ) -> MetricsResult:
        """The aggregated ACCOUNT metrics: followers, impressions, reach, profile visits.

        ``group_by`` decides the axis — ``day`` for a series, ``network`` or ``account`` for a
        breakdown, ``total`` for a single number — and any other value answers error 1000. In
        ``total`` every row carries ``group: None``, which is why the field is not a plain string.

        The names are the ones of the common vocabulary, not each network's raw ones: for those there
        is ``accounts.metric_list``.
        """
        agregado: MetricsResult = self._get(
            f"{self._path(id_organization)}/metrics",
            {**self._range_query(from_date, to_date), "group_by": group_by, "names": names},
            timeout=timeout,
        )
        return agregado

    def publications(
        self,
        id_organization: str,
        *,
        from_date: datetime | str | None = None,
        to_date: datetime | str | None = None,
        timeout: float | None = None,
    ) -> PublicationsSummaryResult:
        """Publication counts of the range: by state, by network and by day.

        Careful with the two series, which answer different questions over different sets: ``by_day``
        counts what was CREATED each day (work done, scheduled ones and drafts included) and
        ``published_by_day`` counts what WENT OUT each day, only the ``sended`` ones. A publication
        created last month and published yesterday shows up in the second and not in the first.

        The day is computed in UTC: a post in the small hours can fall on the previous day.
        """
        resumen: PublicationsSummaryResult = self._get(
            f"{self._path(id_organization)}/publications/summary",
            self._range_query(from_date, to_date),
            timeout=timeout,
        )
        return resumen

    def top_publications(
        self,
        id_organization: str,
        *,
        from_date: datetime | str | None = None,
        to_date: datetime | str | None = None,
        metric: str | None = None,
        limit: int | None = None,
        timeout: float | None = None,
    ) -> TopPublicationsResult:
        """The ranking of the range's publications by one metric (``engagement`` by default).

        **Only what has already been measured gets in**: a publication the network has not reported
        yet, or one on a network that does not publish that metric, does not compete — it is not that
        it scored 0. To see them all with their gap, :meth:`publication_stats`.

        Careful with the shape: a row is not a ``Publication``. It has no ``_id`` — the identifier is
        ``id_publication`` — and the content travels nested under ``publication``.
        """
        ranking: TopPublicationsResult = self._get(
            f"{self._path(id_organization)}/publications/top",
            {**self._range_query(from_date, to_date), "metric": metric, "limit": limit},
            timeout=timeout,
        )
        return ranking

    def publication_stats(
        self,
        id_organization: str,
        *,
        from_date: datetime | str | None = None,
        to_date: datetime | str | None = None,
        metric: str | None = None,
        social_network: Sequence[str] | None = None,
        accounts: Sequence[str] | None = None,
        summary: bool | None = None,
        limit: int | None = None,
        offset: int | None = None,
        timeout: float | None = None,
    ) -> PublicationsStatsResult:
        """The listing of the range's publications WITH their metrics, paginated and ordered by the
        metric asked for. It is the whole statistics screen in one call.

        Two things that cost dearly when ignored:

        - **``summary`` always covers the whole organization**; ``social_network`` and ``accounts``
          filter the listing only. The header does not change when you filter by Instagram, and that
          is deliberate.
        - **When paginating, ``summary=False``.** The aggregates only depend on the range, so
          recomputing them on every page is three aggregations thrown away.

        Unlike :meth:`top_publications`, the unmeasured publications DO show up here, with ``metrics``
        missing. Ordering descending drops them to the end by themselves.
        """
        pagina: PublicationsStatsResult = self._get(
            f"{self._path(id_organization)}/publications/stats",
            {
                **self._range_query(from_date, to_date),
                "metric": metric,
                "social_network": social_network,
                "accounts": accounts,
                # El servidor lo lee como el literal "false": cualquier otra cosa deja los agregados,
                # asi que solo se manda cuando de verdad se quieren apagar.
                "summary": False if summary is False else None,
                "limit": limit,
                "offset": offset,
            },
            timeout=timeout,
        )
        return pagina

    def use(self, id_organization: str, *, timeout: float | None = None) -> PlanUse:
        """The organization's plan consumption: what it spends, what it has handed down to its
        children, and the limits that apply to it.

        An organization with no plan of its own inherits the first parent that has one, so ``limits``
        may not be its own. It is the cheap way to paint a progress bar: before this you had to
        download the client's whole organization listing.

        **It is not ``organizations.use()``**, which is a two-field shortcut over the organization
        record. This one is a route of its own and brings ``limits`` as well.
        """
        consumo: PlanUse = self._get(f"{self._path(id_organization)}/use", timeout=timeout)
        return consumo

    def _range_query(self, from_date: datetime | str | None, to_date: datetime | str | None) -> Query:
        return {"from_date": from_date, "to_date": to_date}

    def _path(self, id_organization: str) -> str:
        return f"/organizations/{require_id(id_organization, 'id_organization')}"
