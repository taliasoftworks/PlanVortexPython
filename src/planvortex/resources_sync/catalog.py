"""GENERADO POR `scripts/generate_sync.py`. NO SE EDITA A MANO.

Gemelo sincrono de `src/planvortex/resources/catalog.py`.

Lo que haya que cambiar se cambia ALLI y se regenera con `uv run python scripts/generate_sync.py`;
la CI regenera y falla si hay diferencias.
"""

from __future__ import annotations

from typing import Any

from planvortex._core.pagination import unwrap_one
from planvortex._core.transport import HttpMethod, HttpRequest
from planvortex._shapes import PublicationLimits
from planvortex.resources_sync.base import RequestSender, Resource
from planvortex.types import (
    AspectRatios,
    CommentActions,
    PlannerTemplate,
    SocialCapabilities,
    SocialLimits,
    SocialNetwork,
)


class CatalogResource(Resource):
    """The static metadata of the networks, asked once and kept on the instance."""

    def __init__(self, client: RequestSender) -> None:
        super().__init__(client)
        self._cache: dict[str, Any] = {}

    def social_networks(self, *, timeout: float | None = None) -> list[SocialNetwork]:
        """The supported networks.

        **The list grows several times a year.** Do not copy it into a constant of yours: ask for it.
        """
        redes: list[SocialNetwork] = self._cached("/social_networks", timeout=timeout)
        return redes

    def allowed_social_publications(self, *, timeout: float | None = None) -> list[SocialNetwork]:
        """The networks that accept publications. Neither WhatsApp nor Google Business is here."""
        redes: list[SocialNetwork] = self._cached("/allowed_social_publications", timeout=timeout)
        return redes

    def allowed_social_messages(self, *, timeout: float | None = None) -> list[SocialNetwork]:
        """The networks with conversations.

        It is a ``POST`` and not a ``GET``, which is odd and is what the route is. It sends no body.
        """
        redes: list[SocialNetwork] = self._cached("/allowed_social_messages", method="POST", timeout=timeout)
        return redes

    def social_capabilities(self, *, timeout: float | None = None) -> dict[str, SocialCapabilities]:
        """The network → what it can do matrix: publish, messages, products, webhooks, menu, comments.

        It is what stops an account being offered on a screen its network does not support —
        WhatsApp in the composer, LinkedIn in the chat.
        """
        matriz: dict[str, SocialCapabilities] = self._cached("/social_capabilities", timeout=timeout)
        return matriz

    def social_comment_actions(self, *, timeout: float | None = None) -> dict[str, CommentActions]:
        """The network → what may be done to a comment matrix: reply, hide, delete mine, delete theirs.

        It is published SEPARATELY from :meth:`social_capabilities` because that one is
        ``{capability: bool}`` and this is an object per network: putting it inside would break its
        shape. And knowing a network has comments does not say enough — Instagram, X and Bluesky do
        not let you delete somebody else's, LinkedIn has no "hide" (neither do Discord and Telegram),
        and Google Business only lets you delete **your own reply**.

        And this is about the NETWORK, not about one account of it: on Telegram deleting comes back
        ``true`` and still answers 969 when the bot is not an administrator of the discussion group.
        The matrix says which buttons to draw, not that each one will work on every account.
        """
        matriz: dict[str, CommentActions] = self._cached("/social_comment_actions", timeout=timeout)
        return matriz

    def social_limits(self, *, timeout: float | None = None) -> SocialLimits:
        """The caps of each network, the ones the server validates against.

        Bluesky carries **two** counts of the same text in different units: 300 graphemes in
        ``characters`` and 3.000 bytes in ``max_post_bytes``. ``len()`` lies in both directions — a
        family emoji is ONE grapheme and 25 bytes — so a counter built on it approves what the API
        rejects and the other way round.

        Telegram carries **two numbers for the same field**, and there ``len()`` is exactly the right
        unit: ``characters["telegram"]`` (4.096) while the publication is text only and
        ``characters["telegram_media"]`` (1.024) the moment it carries an image or a video, because
        then the text is a media caption. The counter changes when the file is ATTACHED, not when
        publish is pressed.
        """
        limites: SocialLimits = self._cached("/social_limits", timeout=timeout)
        return limites

    def publication_limits(self, *, timeout: float | None = None) -> PublicationLimits:
        """The caps of a publication that do not depend on the network: today, its manual retries."""
        limites: PublicationLimits = self._cached("/publication_limits", timeout=timeout)
        return limites

    def allowed_aspect_ratios(self, *, timeout: float | None = None) -> dict[str, AspectRatios]:
        """The crops each network accepts.

        It is indexed by network **and by format** (``facebook``, ``facebook_reels``,
        ``facebook_stories``), so not every key is a network. ``values`` and ``text`` are parallel
        arrays: same index, same crop.
        """
        recortes: dict[str, AspectRatios] = self._cached("/allowed_aspect_ratios", timeout=timeout)
        return recortes

    def planner_templates(self, *, timeout: float | None = None) -> list[PlannerTemplate]:
        """The AI planner templates: what a plan can be generated FROM, and what each source allows.

        You send the chosen one as ``template`` when creating the plan, together with its
        ``source``. It is catalogue for the same reason the limits are — whoever enforces
        something is who gets to announce it — and here a copy is especially expensive, because these
        are **prices**: a table written by hand in your interface would show a cost the server no
        longer charges.

        What to read from here rather than assume:

        - **``generates_images: False`` means the pictures come from the source**, and then the
          plan spends no image credits at all. The same week — 7 publications with a picture on each
          — goes from 519 credits to 48, and that is said BEFORE the plan is created.
        - **``regenerate`` is per template.** The one that did not generate the picture cannot
          regenerate it: drawing that button anyway charges the user 70 credits to replace their own
          photo with an invented one.
        - **``orchestration_cost`` is an ESTIMATE**, not the bill: the real charge is per use.
          ``orchestration_cost_per_source_item`` is what each unit of the source adds.
        - **A plan is WEEKLY and the source does not extend it.** With more units than slots left in
          the week, the extra ones are dropped and the plan carries warning 2117 in ``warnings``.
        - **``source_fields`` is what the source step is made of**, each with its own
          ``max`` and ``min`` — in the field's units: characters, items, or **days** on a
          date — and ``source_requires_any`` naming the fields of which at least one is needed
          (on ``from_text``, the URL or the pasted text).
        """
        plantillas: list[PlannerTemplate] = self._cached(
            "/planner_templates", envelope="templates", timeout=timeout
        )
        return plantillas

    def clear_cache(self) -> None:
        """Throw the cache away, for a long-lived process that wants to notice a new network."""
        self._cache.clear()

    def _cached(
        self,
        path: str,
        *,
        method: HttpMethod = "GET",
        envelope: str | None = None,
        timeout: float | None = None,
    ) -> Any:
        # `envelope` es para la unica ruta del catalogo que envuelve su respuesta
        # (`/planner_templates` -> `{templates}`). Sin desenvolver, quien la recorriera obtendria
        # nada y sin error: un `dict` de una clave no revienta al iterarlo.
        if path in self._cache:
            return self._cache[path]
        valor = self._request(HttpRequest(method=method, path=path, timeout=timeout))
        if envelope is not None:
            valor = unwrap_one(valor, envelope)
        self._cache[path] = valor
        return valor
