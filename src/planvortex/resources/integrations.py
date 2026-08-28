"""Integrations: the tools an organization PULLS material from.

MIND THE WORD. An **integration** is a connection to a third party you bring content from — the
client's Drive, their blog's feed. Access to the PlanVortex API is another thing entirely: an **app**
(``pv.apps``), and only on the Custom plan. Half the marketing copy has used the same word for both
and it is a confusion not worth inheriting.

WHAT TO KNOW BEFORE CALLING ANYTHING HERE:

- **There are two ways to connect and the provider decides**: with OAuth (``requires_oauth: true``,
  Google Drive) you ask for a :meth:`AsyncIntegrationsResource.connect_link` and send the ``code``;
  without it (RSS) you send the form described by ``config_fields`` straight away. Never guess: read
  it from :meth:`AsyncIntegrationsResource.providers`.
- **It is a plan resource** (``integrations``, ``0`` on the free plan): going over answers error
  1404. Only the enabled ones count.
- **Credentials never come out.** What tells you whether the connection is alive is ``connected``,
  and the reason when it is not, ``error_code``.
- **Reconnecting is not creating.** It renews the credentials of the SAME document, goes by the
  ``update`` permission and does not take up quota again.
- **``config`` belongs to RSS.** On Google Drive it is an empty object: the Picker puts everything.

THIS FILE IS THE SOURCE OF ``resources_sync/integrations.py``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from planvortex._core.pagination import Page, PageParams
from planvortex._shapes import IntegrationPickerConfig, IntegrationUpdate
from planvortex.resources.base import AsyncResource, require_id
from planvortex.types import Integration, IntegrationConnectRequest, IntegrationProvider


class AsyncIntegrationsResource(AsyncResource):
    """The provider catalogue and the organization's connections to them."""

    async def providers(self, *, timeout: float | None = None) -> list[IntegrationProvider]:
        """The provider catalogue: how each one connects, what it contributes, and what its form asks.

        **It is the only source of truth about that.** Do not copy the RSS form into your code:
        ``config_fields`` describes it, and it changes with the server.

        It carries no organization: it is a constant of the deployment.
        """
        proveedores: list[IntegrationProvider] = await self._one(
            "/integration_providers", "providers", timeout=timeout
        )
        return proveedores

    async def list(
        self,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        provider: str | None = None,
        timeout: float | None = None,
    ) -> Page[Integration]:
        """The organization's integrations, from the newest to the oldest.

        **With no ``limit`` there is no limit**: they all come back. It is the only listing in this
        API that behaves that way — the rest stop at 10.
        """
        pagina: Page[Integration] = await self._list(
            self._path(id_organization),
            "integrations",
            {"limit": limit, "offset": offset, "provider": provider},
            timeout=timeout,
        )
        return pagina

    def aiterate(
        self,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        provider: str | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[Integration]:
        """The organization's integrations, chaining pages."""

        async def buscar(params: PageParams) -> Page[Integration]:
            return await self.list(
                id_organization,
                limit=params.limit,
                offset=params.offset,
                provider=provider,
                timeout=timeout,
            )

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    async def get(
        self, id_organization: str, id_integration: str, *, timeout: float | None = None
    ) -> Integration:
        """One integration."""
        integracion: Integration = await self._one(
            self._one_path(id_organization, id_integration), "integration", timeout=timeout
        )
        return integracion

    async def connect_link(
        self,
        id_organization: str,
        provider: str,
        *,
        redirect_uri: str | None = None,
        timeout: float | None = None,
    ) -> str:
        """The authorization link of a provider with OAuth. **Only the ones that use it**: asking for
        it for RSS answers error 2201.

        You send the user there, the provider returns them to ``redirect_uri`` with a ``code`` in the
        query, and that ``code`` is what you pass to :meth:`connect`. It is single-use.

        ``redirect_uri`` has to be on the deployment's allow-list (``FRONT_URL_REDIRECT``) or the API
        answers error 532.
        """
        cuerpo: dict[str, str] = await self._get(
            f"{self._path(id_organization)}/{require_id(provider, 'provider')}/connect_link",
            {"redirect_uri": redirect_uri},
            timeout=timeout,
        )
        return cuerpo["url"]

    async def connect(
        self,
        id_organization: str,
        body: IntegrationConnectRequest,
        *,
        timeout: float | None = None,
    ) -> Integration:
        """Connect a new integration. **It takes up plan quota** (error 1404 when there is none left).

        The body depends on the provider: ``{"provider": "google_drive", "code": ...}`` for the OAuth
        one, or the ``config_fields`` form **FLAT** — not inside a ``config`` — for the rest. The
        ``config`` is what the server builds and returns, not what you send.

        .. code-block:: python

            integration = await pv.integrations.connect(
                org_id,
                {"provider": "rss", "url": "https://blog.example/feed", "id_accounts": [account_id]},
            )
        """
        integracion: Integration = await self._post_one(
            self._path(id_organization), "integration", body, timeout=timeout
        )
        return integracion

    async def reconnect(
        self,
        id_organization: str,
        id_integration: str,
        body: IntegrationConnectRequest,
        *,
        timeout: float | None = None,
    ) -> Integration:
        """Renew the credentials of an integration that already exists — the token expired, the user
        revoked the permission — or revalidate a feed's configuration, without changing document.

        Same body as :meth:`connect`, because what reads it is the provider's same code. **It does not
        take up quota again** and it goes by the ``update`` permission, not ``create``.
        """
        integracion: Integration = await self._post_one(
            f"{self._one_path(id_organization, id_integration)}/reconnect",
            "integration",
            body,
            timeout=timeout,
        )
        return integracion

    async def update(
        self,
        id_organization: str,
        id_integration: str,
        body: IntegrationUpdate,
        *,
        timeout: float | None = None,
    ) -> Integration:
        """Change the name, the configuration or the switch.

        ``enabled: False`` leaves it connected but out of play: the job does not sweep it and **it
        stops counting against quota**. That is what to use to pause a feed instead of deleting it.
        """
        integracion: Integration = await self._put_one(
            self._one_path(id_organization, id_integration), "integration", body, timeout=timeout
        )
        return integracion

    async def remove(
        self, id_organization: str, id_integration: str, *, timeout: float | None = None
    ) -> None:
        """Delete the integration and **revoke at the provider** when it knows how.

        What was already imported stays: the files belong to the organization's library, not to the
        integration.
        """
        await self._delete(self._one_path(id_organization, id_integration), timeout=timeout)

    async def picker_config(
        self, id_organization: str, id_integration: str, *, timeout: float | None = None
    ) -> IntegrationPickerConfig:
        """What the browser needs to open the provider's picker. **Google Drive only**: on any other
        it answers error 2201.

        It carries a LIVE, short-lived ``access_token``. Do not store it, do not log it and do not
        send it anywhere that is not the Picker; ask for it right before opening it.
        """
        configuracion: IntegrationPickerConfig = await self._get(
            f"{self._one_path(id_organization, id_integration)}/picker_config", timeout=timeout
        )
        return configuracion

    def _path(self, id_organization: str) -> str:
        return f"/organizations/{require_id(id_organization, 'id_organization')}/integrations"

    def _one_path(self, id_organization: str, id_integration: str) -> str:
        integracion = require_id(id_integration, "id_integration")
        return f"{self._path(id_organization)}/{integracion}"
