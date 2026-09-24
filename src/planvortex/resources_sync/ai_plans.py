"""GENERADO POR `scripts/generate_sync.py`. NO SE EDITA A MANO.

Gemelo sincrono de `src/planvortex/resources/ai_plans.py`.

Lo que haya que cambiar se cambia ALLI y se regenera con `uv run python scripts/generate_sync.py`;
la CI regenera y falla si hay diferencias.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import datetime

from planvortex._core.pagination import Page, PageParams
from planvortex._shapes import AiPlanRegenerateResult
from planvortex.resources_sync.base import Query, Resource, require_id
from planvortex.types import AiPlan, AiPlanCreateRequest, AiPlanCreateResult, AiPlanResults


class AiPlansResource(Resource):
    """Queue a plan, follow it, validate it, retry it and regenerate one of its publications."""

    def create(
        self,
        id_client: str,
        id_organization: str,
        body: AiPlanCreateRequest,
        *,
        timeout: float | None = None,
    ) -> AiPlanCreateResult:
        """Queue a plan. **It does not return publications**: it returns the plan in ``pending`` and
        the budget that was computed to accept it.

        It fails BEFORE spending anything if there are no credits for the unavoidable cost (941), if
        there is no publication quota left (924), if one of the accounts does not publish — WhatsApp,
        Google Business — (942), or if the chosen days leave no future slot in the week (2108).

        .. code-block:: python

            queued = pv.ai_plans.create(
                client_id,
                org_id,
                {
                    "prompt": "Pan de masa madre, horno de leña, barrio",
                    "accounts": [account_id],
                    "options": {"publish_days": [1, 3, 5], "timezone": "Europe/Madrid"},
                },
            )
            queued["ai_plan"]["state"], queued["estimate"]["estimated_cost"]

        With a template it also carries ``template`` and its ``source``, which **is validated
        here**: the URL is downloaded and the catalogue is read inside this call, so its errors arrive
        while the user is still in front of it — 2111 (no such template), 2112 (a source that does not
        match the template), 2113 (the URL could not be read), 2114 (the URL points at a non-public
        address), 2115 (the account has no usable catalogue) and 2116 (the source has no usable
        items).

        .. code-block:: python

            pv.ai_plans.create(
                client_id,
                org_id,
                {
                    "prompt": "Nuestra carta de otoño",
                    "accounts": [account_id],
                    "template": "from_images",
                    "source": {
                        "images": [
                            {"id_upload": first, "description": "Masa reposando en el banco"},
                            {"id_upload": second, "description": "La hogaza saliendo del horno"},
                        ]
                    },
                },
            )

        **The order of ``images`` and of ``products`` is the story**: the orchestrator keeps
        each one's position, so photo 3 can be the "before" and photo 7 the "after".

        **With Pinterest in the plan, each account's board goes in ``destinations``** and it is
        required (2118, listing every account that fails). And a plan that would leave pins without
        an image is refused here with the 2119, before a credit is spent. See
        :data:`~planvortex.types.AiPlanCreateRequest`.

        .. code-block:: python

            pv.ai_plans.create(
                client_id,
                org_id,
                {
                    "prompt": "Recetas de otoño",
                    "accounts": [pinterest_id, instagram_id],
                    "destinations": [
                        {
                            "id_account": pinterest_id,
                            "destination": {"id": board["id"], "name": board["name"]},
                        }
                    ],
                    "options": {"link": "https://panaderia.example/otono"},
                },
            )
        """
        encolado: AiPlanCreateResult = self._post(
            self._path(id_client, id_organization), body, timeout=timeout
        )
        return encolado

    def get(
        self,
        id_client: str,
        id_organization: str,
        id_ai_plan: str,
        *,
        timeout: float | None = None,
    ) -> AiPlan:
        """One plan, with its publications **already resolved** and with each one's files.

        It is the endpoint you poll while ``state`` is ``pending`` or ``generating``. There is no
        webhook for this yet.

        Read ``warnings`` on a plan that came out ``generated``, which is the place nobody
        looks: it is not an error of the response, it is a notice about a plan that generated fine.
        Today there are two: **2117**, part of the source did not fit in the plan week — twelve
        photos with six slots publish six, and ``data`` carries ``{"source_items": ...,
        "capacity": ...}`` — and **922**, a pin whose image failed during the generation, with the
        draft that was left without it in ``data["id_publication"]``.
        """
        plan: AiPlan = self._one(
            self._one_path(id_client, id_organization, id_ai_plan), "ai_plan", timeout=timeout
        )
        return plan

    def list(
        self,
        id_client: str,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        archived: bool | None = None,
        timeout: float | None = None,
    ) -> Page[AiPlan]:
        """The organization's ACTIVE plans, from the newest to the oldest.

        **The cancelled ones do not show up** — nor the archived ones, which are asked for with
        ``archived=True`` — and here ``publications`` are identifiers, not the whole publications:
        for that there is :meth:`get`. With no ``limit`` they all come back.

        ``archived`` opens the other cupboard, never both at once: archiving moves a plan somewhere
        else, it does not put a label on it and leave it where it was.

        .. code-block:: python

            activos = pv.ai_plans.list(client_id, org_id)
            guardados = pv.ai_plans.list(client_id, org_id, archived=True)
        """
        pagina: Page[AiPlan] = self._list(
            self._path(id_client, id_organization),
            "ai_plans",
            self._list_query(limit, offset, archived),
            timeout=timeout,
        )
        return pagina

    def iterate(
        self,
        id_client: str,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        archived: bool | None = None,
        timeout: float | None = None,
    ) -> Iterator[AiPlan]:
        """The organization's plans, chaining pages."""

        def buscar(params: PageParams) -> Page[AiPlan]:
            return self.list(
                id_client,
                id_organization,
                limit=params.limit,
                offset=params.offset,
                archived=archived,
                timeout=timeout,
            )

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    def results(
        self,
        id_client: str,
        id_organization: str,
        *,
        from_date: datetime | str | None = None,
        to_date: datetime | str | None = None,
        sort: str | None = None,
        template: str | None = None,
        social_network: Sequence[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        timeout: float | None = None,
    ) -> AiPlanResults:
        """What every plan achieved with what it published, the aggregate per template and the
        total: the answer to «which plan worked best?». It needs ``ai_plans:read`` **and**
        ``publication_stats:read``.

        What surprises people:

        - **The range filters on the plan's WEEK** (``week_start``), not on when it was created: a
          plan created today for next week has published nothing yet.
        - **Only the plans that published something come back.** Archived ones do — archiving is
          visibility only —; cancelled ones do not.
        - **The default order is interactions per measured publication**, not the total: the total
          rewards the plan with seven accounts even when each post does half as well. And only plans
          with ``ranked: True`` compete in it; the rest come after.
        - **``social_network`` recomputes every plan with only its publications on those networks**,
          which is what makes plans on different networks comparable. With that filter
          ``credits_per_engagement`` does not come: the cost belongs to the whole plan.
        - **It covers THIS organization, not its children**, unlike the ``ai_plan_results`` block of
          :meth:`~planvortex.resources_sync.dashboard.DashboardResource.summary`.

        It is not a :class:`~planvortex.Page`: besides the page it carries ``totals`` and
        ``by_template``, which do not depend on it, so it comes back whole. ``sort`` is one of
        :data:`~planvortex.types.AiPlanResultsSort`.

        .. code-block:: python

            results = pv.ai_plans.results(client_id, org_id, social_network=["instagram"])
            best = next((plan for plan in results["ai_plans"] if plan["ranked"]), None)
            results["by_template"][0]["template"]
        """
        resultados: AiPlanResults = self._get(
            f"{self._path(id_client, id_organization)}/results",
            {
                "from_date": from_date,
                "to_date": to_date,
                "sort": sort,
                "template": template,
                "social_network": social_network,
                "limit": limit,
                "offset": offset,
            },
            timeout=timeout,
        )
        return resultados

    def validate(
        self,
        id_client: str,
        id_organization: str,
        id_ai_plan: str,
        *,
        timeout: float | None = None,
    ) -> AiPlan:
        """Accept the plan: the drafts generated WITHOUT errors move to ``ready`` and from there the
        robot publishes them like any scheduled publication.

        **Only from ``generated``** (error 2102 in any other state). The drafts that do have errors
        stay in ``draft``: they are fixed or deleted with ``pv.publications``.
        """
        plan: AiPlan = self._post_one(
            f"{self._one_path(id_client, id_organization, id_ai_plan)}/validate",
            "ai_plan",
            timeout=timeout,
        )
        return plan

    def retry(
        self,
        id_client: str,
        id_organization: str,
        id_ai_plan: str,
        *,
        timeout: float | None = None,
    ) -> AiPlan:
        """Queue a ``failed`` plan again with the same data. The state goes back to ``pending`` and you
        have to poll again.

        It uses the brand context copied when the plan was created, not today's: a plan is
        reproducible even if somebody edited the configuration in the meantime.
        """
        plan: AiPlan = self._post_one(
            f"{self._one_path(id_client, id_organization, id_ai_plan)}/retry",
            "ai_plan",
            timeout=timeout,
        )
        return plan

    def regenerate(
        self,
        id_client: str,
        id_organization: str,
        id_ai_plan: str,
        id_publication: str,
        target: str,
        *,
        timeout: float | None = None,
    ) -> AiPlanRegenerateResult:
        """Regenerate with AI the ``text`` or the ``image`` of ONE publication of the plan.
        **It costs credits** every time.

        ``credits_spent`` in the answer is the plan's total, not what this call cost.

        **Asking for an ``image`` depends on the plan's TEMPLATE**, not only on the plan having
        allowed images: the one that did not generate the picture cannot regenerate it. Check
        ``regenerate["image"]`` in
        :meth:`~planvortex.resources_sync.catalog.CatalogResource.planner_templates` before offering
        that button — on ``from_images`` and on ``from_catalog`` it would charge the user 70
        credits to replace their own photo with an invented one.
        """
        publicacion = require_id(id_publication, "id_publication")
        ruta = (
            f"{self._one_path(id_client, id_organization, id_ai_plan)}/publications/{publicacion}/regenerate"
        )
        resultado: AiPlanRegenerateResult = self._post(ruta, {"target": target}, timeout=timeout)
        return resultado

    def archive(
        self,
        id_client: str,
        id_organization: str,
        id_ai_plan: str,
        *,
        timeout: float | None = None,
    ) -> AiPlan:
        """Archive the plan: it leaves the listing and moves to the archived one
        (``list(..., archived=True)``).

        It is **visibility only**. No publication is touched — anything scheduled keeps publishing —
        no credits are refunded and nothing is cancelled, so it works in ANY state, ``generating``
        included: it does not interrupt the job. Undone with :meth:`unarchive`.

        It is what people are after almost every time they think of "removing" a plan: :meth:`remove`
        takes the publications that have not gone out with it, and this does not.
        """
        plan: AiPlan = self._post_one(
            f"{self._one_path(id_client, id_organization, id_ai_plan)}/archive",
            "ai_plan",
            timeout=timeout,
        )
        return plan

    def unarchive(
        self,
        id_client: str,
        id_organization: str,
        id_ai_plan: str,
        *,
        timeout: float | None = None,
    ) -> AiPlan:
        """Put the plan back in the active listing. On a plan that was not archived it does nothing."""
        plan: AiPlan = self._post_one(
            f"{self._one_path(id_client, id_organization, id_ai_plan)}/unarchive",
            "ai_plan",
            timeout=timeout,
        )
        return plan

    def remove(
        self,
        id_client: str,
        id_organization: str,
        id_ai_plan: str,
        *,
        timeout: float | None = None,
    ) -> None:
        """Delete the plan **and its publications that have not gone out yet**: the generated drafts
        and, if it had already been validated, whatever was still scheduled. The already published
        ones stay — deleting them here would not take them off the network, it would only lose their
        history — and neither is the one being published at that very moment touched.

        The plan itself is not wiped: it moves to ``cancelled``, disappears from :meth:`list` and
        :meth:`get` still returns it. Spent credits are not refunded and a ``generating`` plan cannot
        be deleted (2102): wait for the job to finish.

        To stop seeing it without losing anything, :meth:`archive`.
        """
        self._delete(self._one_path(id_client, id_organization, id_ai_plan), timeout=timeout)

    def _list_query(self, limit: int | None, offset: int | None, archived: bool | None) -> Query:
        return {
            "limit": limit,
            "offset": offset,
            # El servidor enciende el filtro con el literal "true": mandar `archived=false` pediria
            # lo mismo que no mandar nada, asi que un `False` se omite en vez de viajar como ruido.
            "archived": True if archived else None,
        }

    def _path(self, id_client: str, id_organization: str) -> str:
        cliente = require_id(id_client, "id_client")
        organizacion = require_id(id_organization, "id_organization")
        return f"/clients/{cliente}/organizations/{organizacion}/ai_plans"

    def _one_path(self, id_client: str, id_organization: str, id_ai_plan: str) -> str:
        plan = require_id(id_ai_plan, "id_ai_plan")
        return f"{self._path(id_client, id_organization)}/{plan}"
