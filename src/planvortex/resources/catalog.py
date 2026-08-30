"""The catalogue: which networks exist, what each one can do, and what they are validated against.

WHY IT IS CACHED: these are constants of the deployment. They do not depend on the client, they do
not depend on the organization and they do not change between two calls — they change when the
server is deployed. A composer validating text as it is typed would ask ``/social_limits`` on every
keystroke; with the cache it asks once per client instance.

WHY THEY ARE ASKED FOR AND NOT WRITTEN HERE: it is the house rule — whoever enforces a limit is who
gets to announce it. The dashboard kept its own table and drifted: it counted LinkedIn up to 3.000
while the server rejected at 1.300, so the user wrote a text the counter approved and the API
refused. A copy inside this library would be the same bug one floor down, and shipped on PyPI.

THE CACHE HOLDS THE VALUE, NOT THE PENDING CALL, and that is a deliberate difference from the Node
library. There, the promise is cached and two concurrent cold calls share one request. The
equivalent here would be an ``asyncio.Task``, which has no synchronous twin — ``scripts/
generate_sync.py`` could not translate it — and the whole cost of not having it is one extra GET of
a constant on a cold start. Caching the value also gets the important half right for free: **a
failure is never cached**, so a 502 during a deployment does not leave the instance broken for ever.

THIS FILE IS THE SOURCE OF ``resources_sync/catalog.py``.
"""

from __future__ import annotations

from typing import Any

from planvortex._core.transport import HttpMethod, HttpRequest
from planvortex._shapes import PublicationLimits
from planvortex.resources.base import AsyncRequestSender, AsyncResource
from planvortex.types import AspectRatios, CommentActions, SocialCapabilities, SocialLimits, SocialNetwork


class AsyncCatalogResource(AsyncResource):
    """The static metadata of the networks, asked once and kept on the instance."""

    def __init__(self, client: AsyncRequestSender) -> None:
        super().__init__(client)
        self._cache: dict[str, Any] = {}

    async def social_networks(self, *, timeout: float | None = None) -> list[SocialNetwork]:
        """The supported networks.

        **The list grows several times a year.** Do not copy it into a constant of yours: ask for it.
        """
        redes: list[SocialNetwork] = await self._cached("/social_networks", timeout=timeout)
        return redes

    async def allowed_social_publications(self, *, timeout: float | None = None) -> list[SocialNetwork]:
        """The networks that accept publications. Neither WhatsApp nor Google Business is here."""
        redes: list[SocialNetwork] = await self._cached("/allowed_social_publications", timeout=timeout)
        return redes

    async def allowed_social_messages(self, *, timeout: float | None = None) -> list[SocialNetwork]:
        """The networks with conversations.

        It is a ``POST`` and not a ``GET``, which is odd and is what the route is. It sends no body.
        """
        redes: list[SocialNetwork] = await self._cached(
            "/allowed_social_messages", method="POST", timeout=timeout
        )
        return redes

    async def social_capabilities(self, *, timeout: float | None = None) -> dict[str, SocialCapabilities]:
        """The network → what it can do matrix: publish, messages, products, webhooks, menu, comments.

        It is what stops an account being offered on a screen its network does not support —
        WhatsApp in the composer, LinkedIn in the chat.
        """
        matriz: dict[str, SocialCapabilities] = await self._cached("/social_capabilities", timeout=timeout)
        return matriz

    async def social_comment_actions(self, *, timeout: float | None = None) -> dict[str, CommentActions]:
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
        matriz: dict[str, CommentActions] = await self._cached("/social_comment_actions", timeout=timeout)
        return matriz

    async def social_limits(self, *, timeout: float | None = None) -> SocialLimits:
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
        limites: SocialLimits = await self._cached("/social_limits", timeout=timeout)
        return limites

    async def publication_limits(self, *, timeout: float | None = None) -> PublicationLimits:
        """The caps of a publication that do not depend on the network: today, its manual retries."""
        limites: PublicationLimits = await self._cached("/publication_limits", timeout=timeout)
        return limites

    async def allowed_aspect_ratios(self, *, timeout: float | None = None) -> dict[str, AspectRatios]:
        """The crops each network accepts.

        It is indexed by network **and by format** (``facebook``, ``facebook_reels``,
        ``facebook_stories``), so not every key is a network. ``values`` and ``text`` are parallel
        arrays: same index, same crop.
        """
        recortes: dict[str, AspectRatios] = await self._cached("/allowed_aspect_ratios", timeout=timeout)
        return recortes

    def clear_cache(self) -> None:
        """Throw the cache away, for a long-lived process that wants to notice a new network."""
        self._cache.clear()

    async def _cached(self, path: str, *, method: HttpMethod = "GET", timeout: float | None = None) -> Any:
        if path in self._cache:
            return self._cache[path]
        valor = await self._request(HttpRequest(method=method, path=path, timeout=timeout))
        self._cache[path] = valor
        return valor
