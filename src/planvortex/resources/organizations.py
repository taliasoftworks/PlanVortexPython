"""Organizations: the container of accounts, publications and files, and who hands out the quota.

WHAT SURPRISES PEOPLE: ``organization["actual_plan"]`` is what was ASSIGNED, and **it is missing when
nothing was assigned**. An organization with no plan of its own shares the plan of the first parent
that has one, and failing that, the client's unallocated remainder. So to know what it can actually
do you do not read ``actual_plan``: you call :meth:`AsyncOrganizationsResource.limits`, which is
what resolves the cascade.

THIS FILE IS THE SOURCE OF ``resources_sync/organizations.py``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from planvortex._core.pagination import Page, PageParams
from planvortex._shapes import ConnectToken, OrganizationUse
from planvortex.resources.base import AsyncResource, require_id
from planvortex.types import (
    AiContext,
    Limit,
    Organization,
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationUser,
    SocialCredentialsInput,
)


class AsyncOrganizationsResource(AsyncResource):
    """One organization's record, its children, its real quota and the connection token."""

    async def get(
        self, id_organization: str, *, get_use: bool | None = None, timeout: float | None = None
    ) -> Organization:
        """One organization's record.

        ``get_use`` also brings ``actual_use`` and ``actual_asigned``, which cost an aggregation over
        everything underneath: do not ask for them out of habit.
        """
        organizacion: Organization = await self._one(
            self._path(id_organization),
            "organization",
            {"get_use": True} if get_use else None,
            timeout=timeout,
        )
        return organizacion

    async def update(
        self, id_organization: str, body: OrganizationUpdate, *, timeout: float | None = None
    ) -> Organization:
        """Change an organization's assigned quota or its statistics settings.

        **The name is not editable, here or anywhere**, and it is not rejected either: the server
        keeps the current one and ignores whatever arrives. Assigning less than the organization
        already uses IS rejected, with a 1400-1408.
        """
        organizacion: Organization = await self._put_one(
            self._path(id_organization), "organization", body, timeout=timeout
        )
        return organizacion

    async def remove(self, id_organization: str, *, timeout: float | None = None) -> None:
        """Delete an organization **with everything inside it**: its children, its accounts, its
        publications, its files and its comments. It does not undo.
        """
        await self._delete(self._path(id_organization), timeout=timeout)

    async def children(
        self,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        name: str | None = None,
        get_use: bool | None = None,
        timeout: float | None = None,
    ) -> Page[Organization]:
        """The organizations hanging from this one."""
        pagina: Page[Organization] = await self._list(
            f"{self._path(id_organization)}/organizations",
            "organizations",
            {
                "limit": limit,
                "offset": offset,
                "name": name,
                "get_use": True if get_use else None,
            },
            timeout=timeout,
        )
        return pagina

    def aiterate_children(
        self,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        name: str | None = None,
        get_use: bool | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[Organization]:
        """The child organizations, chaining pages."""

        async def buscar(params: PageParams) -> Page[Organization]:
            return await self.children(
                id_organization,
                limit=params.limit,
                offset=params.offset,
                name=name,
                get_use=get_use,
                timeout=timeout,
            )

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    async def create_child(
        self, id_organization: str, body: OrganizationCreate, *, timeout: float | None = None
    ) -> Organization:
        """Create a child organization with whatever is handed down from this one's plan."""
        organizacion: Organization = await self._post_one(
            f"{self._path(id_organization)}/organizations", "organization", body, timeout=timeout
        )
        return organizacion

    async def limits(self, id_organization: str, *, timeout: float | None = None) -> Limit:
        """What this organization can really use, with the cascade already resolved: its own plan, or
        the first parent's, or the client's unallocated remainder.

        This is what to look at before connecting an account or scheduling a publication — not
        ``organization["actual_plan"]``, which is only what was explicitly assigned and is often not
        there at all.
        """
        limites: Limit = await self._get(f"{self._path(id_organization)}/limits", timeout=timeout)
        return limites

    async def use(self, id_organization: str, *, timeout: float | None = None) -> OrganizationUse:
        """This organization's consumption and what it has already handed down to its children.

        It is a shortcut for ``get(id, get_use=True)`` that returns only the two figures, which is
        what you want when painting a "3 of 5 accounts" bar. For the client-wide numbers and the
        rest of the dashboard there is ``pv.dashboard``.
        """
        organizacion = await self.get(id_organization, get_use=True, timeout=timeout)
        uso: OrganizationUse = {}
        if "actual_use" in organizacion:
            uso["actual_use"] = organizacion["actual_use"]
        if "actual_asigned" in organizacion:
            uso["actual_asigned"] = organizacion["actual_asigned"]
        return uso

    async def create_connect_token(
        self,
        id_organization: str,
        *,
        social_network: str | None = None,
        redirect_uri: str | None = None,
        timeout: float | None = None,
    ) -> ConnectToken:
        """Issue the temporal token a **person** connects a social account to this organization with.
        It is the only way an app can get an account connected to it.

        And it is the exact reverse of the rest of the flow: this is the endpoint that **demands app
        credentials** — with a user token it answers 514 — while the three that come after it
        (``accounts.connect_links``, ``accounts.connect``, ``accounts.enable``) refuse them with 519.

        **A temporal token cannot ask for another one either**: also 514. A credential that renewed
        itself would never expire, and this one is loose in your user's browser.

        It expires in **fifteen minutes** and **is only good for this organization**: using it
        against another answers 1101. **And it connects once**: as soon as an ``accounts.connect``
        succeeds, that token stops being able to connect and answers 543 — the ``accounts.enable``
        calls finishing that same connection keep working until it expires. Issue one per
        connection: they are free and immediate.

        **If you pass ``social_network`` the token is tied to that network** and connects no other
        (544). Without it, the token opens any of them and the person chooses.

        ``redirect_uri`` is where YOUR user comes back to when they finish, and it has to be one of
        the ``redirect_urls`` registered on the app or the call answers 532.
        """
        token: ConnectToken = await self._get(
            f"{self._path(id_organization)}/temporal_connect_token",
            {"social_network": social_network, "redirect_uri": redirect_uri},
            timeout=timeout,
        )
        return token

    async def update_ai_context(
        self, id_organization: str, body: AiContext, *, timeout: float | None = None
    ) -> Organization:
        """Write the brand context the AI writes with for this organization.

        It REPLACES the whole block; it does not patch it field by field. And it does not affect
        plans already created: each plan takes a copy of the context at the moment it was asked for,
        so that a retry generates the same thing.
        """
        organizacion: Organization = await self._put_one(
            f"{self._path(id_organization)}/ai-context", "organization", body, timeout=timeout
        )
        return organizacion

    async def update_social_credentials(
        self,
        id_organization: str,
        social_network: str,
        body: SocialCredentialsInput,
        *,
        timeout: float | None = None,
    ) -> Organization:
        """Save the organization's OWN application credentials for a network (BYOB).

        Today only Discord: without this, Discord does not even appear as a connectable network
        (error 960). The reason the application belongs to the client and not to us is not technical
        — it is that the permission to read the TEXT of messages is reviewed per application past
        10.000 reachable users, and a shared app would drag the whole platform into that review.

        **The secrets are write-only and never come back.** All three credentials are needed the
        first time; afterwards, whatever is omitted is kept, so the ``client_id`` can be corrected
        without sending the secret and the token again. The bot token is validated against Discord
        before anything is stored.
        """
        organizacion: Organization = await self._put_one(
            self._credentials_path(id_organization, social_network),
            "organization",
            body,
            timeout=timeout,
        )
        return organizacion

    async def delete_social_credentials(
        self, id_organization: str, social_network: str, *, timeout: float | None = None
    ) -> Organization:
        """Delete a network's own credentials. The accounts already connected with them **stop
        working**: there is nobody left to ask for a token.
        """
        organizacion: Organization = await self._delete_one(
            self._credentials_path(id_organization, social_network), "organization", timeout=timeout
        )
        return organizacion

    async def users(self, id_organization: str, *, timeout: float | None = None) -> list[OrganizationUser]:
        """The people with any role in this organization, with their name and their email.

        It is a READ of who is there, not role management: creating roles, changing them and inviting
        people are the nineteen routes this library deliberately does not cover. This one is here
        because a custom panel needs to paint the team, and because an app token can call it.

        The identifier of each one is ``user["id"]`` — Keycloak's — and not an ``_id``: these people
        do not live in PlanVortex's database.
        """
        cuerpo: Any = await self._get(f"{self._path(id_organization)}/users", timeout=timeout)
        usuarios: list[OrganizationUser] = cuerpo.get("users", []) if isinstance(cuerpo, dict) else []
        return usuarios

    def _path(self, id_organization: str) -> str:
        return f"/organizations/{require_id(id_organization, 'id_organization')}"

    def _credentials_path(self, id_organization: str, social_network: str) -> str:
        red = require_id(social_network, "social_network")
        return f"{self._path(id_organization)}/social_credentials/{red}"
