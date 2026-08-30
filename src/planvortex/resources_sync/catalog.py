"""GENERADO POR `scripts/generate_sync.py`. NO SE EDITA A MANO.

Gemelo sincrono de `src/planvortex/resources/catalog.py`.

Lo que haya que cambiar se cambia ALLI y se regenera con `uv run python scripts/generate_sync.py`;
la CI regenera y falla si hay diferencias.
"""

from __future__ import annotations

from typing import Any

from planvortex._core.transport import HttpMethod, HttpRequest
from planvortex._shapes import PublicationLimits
from planvortex.resources_sync.base import RequestSender, Resource
from planvortex.types import AspectRatios, CommentActions, SocialCapabilities, SocialLimits, SocialNetwork


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

    def clear_cache(self) -> None:
        """Throw the cache away, for a long-lived process that wants to notice a new network."""
        self._cache.clear()

    def _cached(self, path: str, *, method: HttpMethod = "GET", timeout: float | None = None) -> Any:
        if path in self._cache:
            return self._cache[path]
        valor = self._request(HttpRequest(method=method, path=path, timeout=timeout))
        self._cache[path] = valor
        return valor
