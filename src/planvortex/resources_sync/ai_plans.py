"""GENERADO POR `scripts/generate_sync.py`. NO SE EDITA A MANO.

Gemelo sincrono de `src/planvortex/resources/ai_plans.py`.

Lo que haya que cambiar se cambia ALLI y se regenera con `uv run python scripts/generate_sync.py`;
la CI regenera y falla si hay diferencias.
"""

from __future__ import annotations

from collections.abc import Iterator

from planvortex._core.pagination import Page, PageParams
from planvortex._shapes import AiPlanRegenerateResult
from planvortex.resources_sync.base import Resource, require_id
from planvortex.types import AiPlan, AiPlanCreateRequest, AiPlanCreateResult


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
        Today there is one, **2117**, part of the source did not fit in the plan week — twelve photos
        with six slots publish six, and ``data`` carries ``{"source_items": ..., "capacity":
        ...}``.
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
        timeout: float | None = None,
    ) -> Page[AiPlan]:
        """The organization's plans, from the newest to the oldest.

        **The cancelled ones do not show up**, and here ``publications`` are identifiers, not the
        whole publications: for that there is :meth:`get`. With no ``limit`` they all come back.
        """
        pagina: Page[AiPlan] = self._list(
            self._path(id_client, id_organization),
            "ai_plans",
            {"limit": limit, "offset": offset},
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
        timeout: float | None = None,
    ) -> Iterator[AiPlan]:
        """The organization's plans, chaining pages."""

        def buscar(params: PageParams) -> Page[AiPlan]:
            return self.list(
                id_client,
                id_organization,
                limit=params.limit,
                offset=params.offset,
                timeout=timeout,
            )

        return self._iterate_pages(buscar, limit=limit, offset=offset)

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

    def remove(
        self,
        id_client: str,
        id_organization: str,
        id_ai_plan: str,
        *,
        timeout: float | None = None,
    ) -> None:
        """Cancel the plan. **It does not delete it**: it moves to ``cancelled``, disappears from
        :meth:`list` and :meth:`get` still returns it.
        """
        self._delete(self._one_path(id_client, id_organization, id_ai_plan), timeout=timeout)

    def _path(self, id_client: str, id_organization: str) -> str:
        cliente = require_id(id_client, "id_client")
        organizacion = require_id(id_organization, "id_organization")
        return f"/clients/{cliente}/organizations/{organizacion}/ai_plans"

    def _one_path(self, id_client: str, id_organization: str, id_ai_plan: str) -> str:
        plan = require_id(id_ai_plan, "id_ai_plan")
        return f"{self._path(id_client, id_organization)}/{plan}"
