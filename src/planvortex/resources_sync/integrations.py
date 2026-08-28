"""GENERADO POR `scripts/generate_sync.py`. NO SE EDITA A MANO.

Gemelo sincrono de `src/planvortex/resources/integrations.py`.

Lo que haya que cambiar se cambia ALLI y se regenera con `uv run python scripts/generate_sync.py`;
la CI regenera y falla si hay diferencias.
"""

from __future__ import annotations

from collections.abc import Iterator

from planvortex._core.pagination import Page, PageParams
from planvortex._shapes import IntegrationPickerConfig, IntegrationUpdate
from planvortex.resources_sync.base import Resource, require_id
from planvortex.types import Integration, IntegrationConnectRequest, IntegrationProvider


class IntegrationsResource(Resource):
    """The provider catalogue and the organization's connections to them."""

    def providers(self, *, timeout: float | None = None) -> list[IntegrationProvider]:
        """The provider catalogue: how each one connects, what it contributes, and what its form asks.

        **It is the only source of truth about that.** Do not copy the RSS form into your code:
        ``config_fields`` describes it, and it changes with the server.

        It carries no organization: it is a constant of the deployment.
        """
        proveedores: list[IntegrationProvider] = self._one(
            "/integration_providers", "providers", timeout=timeout
        )
        return proveedores

    def list(
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
        pagina: Page[Integration] = self._list(
            self._path(id_organization),
            "integrations",
            {"limit": limit, "offset": offset, "provider": provider},
            timeout=timeout,
        )
        return pagina

    def iterate(
        self,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        provider: str | None = None,
        timeout: float | None = None,
    ) -> Iterator[Integration]:
        """The organization's integrations, chaining pages."""

        def buscar(params: PageParams) -> Page[Integration]:
            return self.list(
                id_organization,
                limit=params.limit,
                offset=params.offset,
                provider=provider,
                timeout=timeout,
            )

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    def get(self, id_organization: str, id_integration: str, *, timeout: float | None = None) -> Integration:
        """One integration."""
        integracion: Integration = self._one(
            self._one_path(id_organization, id_integration), "integration", timeout=timeout
        )
        return integracion

    def connect_link(
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
        cuerpo: dict[str, str] = self._get(
            f"{self._path(id_organization)}/{require_id(provider, 'provider')}/connect_link",
            {"redirect_uri": redirect_uri},
            timeout=timeout,
        )
        return cuerpo["url"]

    def connect(
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

            integration = pv.integrations.connect(
                org_id,
                {"provider": "rss", "url": "https://blog.example/feed", "id_accounts": [account_id]},
            )
        """
        integracion: Integration = self._post_one(
            self._path(id_organization), "integration", body, timeout=timeout
        )
        return integracion

    def reconnect(
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
        integracion: Integration = self._post_one(
            f"{self._one_path(id_organization, id_integration)}/reconnect",
            "integration",
            body,
            timeout=timeout,
        )
        return integracion

    def update(
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
        integracion: Integration = self._put_one(
            self._one_path(id_organization, id_integration), "integration", body, timeout=timeout
        )
        return integracion

    def remove(self, id_organization: str, id_integration: str, *, timeout: float | None = None) -> None:
        """Delete the integration and **revoke at the provider** when it knows how.

        What was already imported stays: the files belong to the organization's library, not to the
        integration.
        """
        self._delete(self._one_path(id_organization, id_integration), timeout=timeout)

    def picker_config(
        self, id_organization: str, id_integration: str, *, timeout: float | None = None
    ) -> IntegrationPickerConfig:
        """What the browser needs to open the provider's picker. **Google Drive only**: on any other
        it answers error 2201.

        It carries a LIVE, short-lived ``access_token``. Do not store it, do not log it and do not
        send it anywhere that is not the Picker; ask for it right before opening it.
        """
        configuracion: IntegrationPickerConfig = self._get(
            f"{self._one_path(id_organization, id_integration)}/picker_config", timeout=timeout
        )
        return configuracion

    def _path(self, id_organization: str) -> str:
        return f"/organizations/{require_id(id_organization, 'id_organization')}/integrations"

    def _one_path(self, id_organization: str, id_integration: str) -> str:
        integracion = require_id(id_integration, "id_integration")
        return f"{self._path(id_organization)}/{integracion}"
