"""Publication plans generated with AI.

THE CYCLE, which is what to have clear before anything else::

    create()  ->  pending  ->  generating  ->  generated  ->  validate()  ->  validated
                                    |              |
                                  failed      (each draft is edited through pv.publications)
                                    |
                                  retry()

AND WHAT SURPRISES PEOPLE:

- **``create()`` generates nothing**: it queues the plan and returns the budget. The generating is
  done by a separate job, so you poll :meth:`AsyncAiPlansResource.get` while the state is ``pending``
  or ``generating``. It can take minutes.
- **What is generated are NORMAL publications in state ``draft``.** They are edited and deleted with
  ``pv.publications``, not with anything here. Validating is what moves them to ``ready``.
- **It is paid for in AI credits and the price is known BEFOREHAND.** The budget is computed by the
  server, never by the model; if the unavoidable cost does not fit in the available credits, the plan
  is rejected with error 941 instead of being half generated.
- **The size of the plan is set by the days.** There is at most one publication per day and account,
  so Monday/Wednesday/Friday with 3 accounts is 9 publications, not 21.
- **These routes hang off the CLIENT**, not only off the organization: they carry both identifiers.
- **Deleting is cancelling.** The plan moves to ``cancelled`` and stops appearing in the listing, but
  :meth:`AsyncAiPlansResource.get` still returns it. What does go for good are its publications that
  had not gone out yet: the drafts and, if the plan was already validated, whatever was still
  scheduled.
- **Archiving is NOT deleting, and it is the action people are usually after.**
  :meth:`AsyncAiPlansResource.archive` takes the plan out of the listing and touches no publication
  — anything scheduled keeps publishing — works in any state and can be undone. The archived ones
  are read with ``list(..., archived=True)``, never next to the active ones.

THE TEMPLATES: WHAT THE PLAN IS GENERATED FROM

``template`` says where the content comes from, and it is the only thing that changes between one
plan and another: the publish days, the language, the tone, ``shared`` and the images stay
cross-cutting options. It is **optional** — without it the plan is ``standard``, exactly what
every plan did before templates existed — and each template declares which options it accepts:
sending one it does not accept is a 2106, not a silent ignore.

- **``standard``** — a theme prompt, and the model generates the pictures. The one of always.
- **``from_images``** — the user's own photos, each with its own description. One vision pass over
  ALL of them at once, so the model can sequence a narrative (photo 3 the "before", photo 7 the
  "after") instead of writing seven independent posts.
- **``from_text``** — an article: a URL downloaded when the plan is created, or the pasted text.
- **``from_catalog``** — the products of a connected catalogue, read LIVE with their name, their
  price and their picture.
- **``campaign``** — a countdown towards a date, with a narrative arc: teaser, announcement,
  reminder, today, thank you.

And what surprises people about them:

- **The one that does not generate images spends no image credits, and images are 94 % of a plan.**
  The same week — 7 publications with a picture on each — costs 519 credits as ``standard`` and 48
  as ``from_images``.
- **The source is validated when the plan is CREATED**, not when it is generated: the article is
  downloaded, the catalogue is read and the product pictures are copied right there. So a broken
  source fails while the user is still in front of it (2112 to 2116), and what is stored is a
  SNAPSHOT — a ``retry`` three days later does not depend on the article still being online.
- **A plan is WEEKLY and the source does not extend it.** 12 photos with 6 slots publish 6, and the
  plan carries warning 2117 in ``warnings``; the slots are the publish days times the accounts,
  so it can be said before creating it.
- **The list, the costs and the fields are asked for**, with
  :meth:`~planvortex.resources.catalog.AsyncCatalogResource.planner_templates`. Do not write them by
  hand: they are prices.

THIS FILE IS THE SOURCE OF ``resources_sync/ai_plans.py``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from planvortex._core.pagination import Page, PageParams
from planvortex._shapes import AiPlanRegenerateResult
from planvortex.resources.base import AsyncResource, Query, require_id
from planvortex.types import AiPlan, AiPlanCreateRequest, AiPlanCreateResult


class AsyncAiPlansResource(AsyncResource):
    """Queue a plan, follow it, validate it, retry it and regenerate one of its publications."""

    async def create(
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

            queued = await pv.ai_plans.create(
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

            await pv.ai_plans.create(
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
        encolado: AiPlanCreateResult = await self._post(
            self._path(id_client, id_organization), body, timeout=timeout
        )
        return encolado

    async def get(
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
        plan: AiPlan = await self._one(
            self._one_path(id_client, id_organization, id_ai_plan), "ai_plan", timeout=timeout
        )
        return plan

    async def list(
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

            activos = await pv.ai_plans.list(client_id, org_id)
            guardados = await pv.ai_plans.list(client_id, org_id, archived=True)
        """
        pagina: Page[AiPlan] = await self._list(
            self._path(id_client, id_organization),
            "ai_plans",
            self._list_query(limit, offset, archived),
            timeout=timeout,
        )
        return pagina

    def aiterate(
        self,
        id_client: str,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        archived: bool | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[AiPlan]:
        """The organization's plans, chaining pages."""

        async def buscar(params: PageParams) -> Page[AiPlan]:
            return await self.list(
                id_client,
                id_organization,
                limit=params.limit,
                offset=params.offset,
                archived=archived,
                timeout=timeout,
            )

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    async def validate(
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
        plan: AiPlan = await self._post_one(
            f"{self._one_path(id_client, id_organization, id_ai_plan)}/validate",
            "ai_plan",
            timeout=timeout,
        )
        return plan

    async def retry(
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
        plan: AiPlan = await self._post_one(
            f"{self._one_path(id_client, id_organization, id_ai_plan)}/retry",
            "ai_plan",
            timeout=timeout,
        )
        return plan

    async def regenerate(
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
        :meth:`~planvortex.resources.catalog.AsyncCatalogResource.planner_templates` before offering
        that button — on ``from_images`` and on ``from_catalog`` it would charge the user 70
        credits to replace their own photo with an invented one.
        """
        publicacion = require_id(id_publication, "id_publication")
        ruta = (
            f"{self._one_path(id_client, id_organization, id_ai_plan)}/publications/{publicacion}/regenerate"
        )
        resultado: AiPlanRegenerateResult = await self._post(ruta, {"target": target}, timeout=timeout)
        return resultado

    async def archive(
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
        plan: AiPlan = await self._post_one(
            f"{self._one_path(id_client, id_organization, id_ai_plan)}/archive",
            "ai_plan",
            timeout=timeout,
        )
        return plan

    async def unarchive(
        self,
        id_client: str,
        id_organization: str,
        id_ai_plan: str,
        *,
        timeout: float | None = None,
    ) -> AiPlan:
        """Put the plan back in the active listing. On a plan that was not archived it does nothing."""
        plan: AiPlan = await self._post_one(
            f"{self._one_path(id_client, id_organization, id_ai_plan)}/unarchive",
            "ai_plan",
            timeout=timeout,
        )
        return plan

    async def remove(
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
        await self._delete(self._one_path(id_client, id_organization, id_ai_plan), timeout=timeout)

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
