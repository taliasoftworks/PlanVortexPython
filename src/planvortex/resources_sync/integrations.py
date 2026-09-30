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
from planvortex.types import (
    Integration,
    IntegrationCatalogPage,
    IntegrationConnectRequest,
    IntegrationProvider,
)


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
        url: str | None = None,
        id_integration: str | None = None,
        timeout: float | None = None,
    ) -> str:
        """The link to send the user to, on the providers with ``connect_link``. **Only those**:
        asking for it for RSS answers error 2201.

        - **Google Drive**: its consent screen. The provider returns the user to ``redirect_uri`` with
          a ``code`` in the query, and that ``code`` is what you pass to :meth:`connect`. It is
          single-use.
        - **WooCommerce**: the approval page of THEIR store, so it takes ``url``. The store is
          checked NOW and without keys (https, a firewall in front, whether WooCommerce is there), so
          what is going to fail fails with the user still in front of you. After approving, the store
          sends us the key directly and the user comes back with ``id_integration`` in the query.
          **Do not trust ``success``: read that integration** with :meth:`get`. A 2200 means the key
          never arrived (they cancelled); ``error_code`` 2219, that it is being checked (a few
          seconds: read it again); another code, what failed; none, connected. The link lasts 15
          minutes and works once. With "plain" permalinks the store has no button (2216
          ``plain_permalinks``): connect it with keys.

        ``id_integration`` reconnects THAT store with the button instead of connecting a new one: the
        key is renewed on the same document, no quota is taken, and it needs the ``update``
        permission.

        ``redirect_uri`` has to be on the deployment's allow-list (``FRONT_URL_REDIRECT``) or the API
        answers error 532.
        """
        cuerpo: dict[str, str] = self._get(
            f"{self._path(id_organization)}/{require_id(provider, 'provider')}/connect_link",
            {"redirect_uri": redirect_uri, "url": url, "id_integration": id_integration},
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

        A store with keys created by hand (with **read** permission) goes the same way; the keys are
        tried against the store before anything is saved, and an organization can connect several.

        .. code-block:: python

            integration = pv.integrations.connect(
                org_id,
                {"provider": "rss", "url": "https://blog.example/feed", "id_accounts": [account_id]},
            )

            store = pv.integrations.connect(
                org_id,
                {
                    "provider": "woocommerce",
                    "url": "https://tienda.example.com",
                    "consumer_key": "ck_...",
                    "consumer_secret": "cs_...",
                },
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

        **WooCommerce does not**: an app cannot delete its own key. After disconnecting a store, tell
        the user to delete it in WooCommerce > Settings > Advanced > REST API; it is the one ending in
        ``config["key_ending"]`` (read it BEFORE deleting the integration).

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

    def products(
        self,
        id_organization: str,
        id_integration: str,
        *,
        cursor: str | None = None,
        search: str | None = None,
        limit: int | None = None,
        timeout: float | None = None,
    ) -> IntegrationCatalogPage:
        """One page of the catalogue of a connected store (a provider with ``catalog``), to choose the
        products of a ``from_catalog`` plan: their ``external_id`` is what goes in
        ``source["products"]``. On any other provider, error 2207; with the integration disabled, 2209.

        It is read LIVE from the store on every call, and that is why there is no ``iterate_products``:
        every page is a request to the client's own hosting, and walking ten thousand products to find
        three is what ``search`` is for.

        - **It pages by an opaque cursor**: send ``next_cursor`` back as ``cursor`` exactly as it
          came, and without it that was the last page. One this API did not issue is a 2208.
        - **What the public cannot see does not come** (drafts, private, hidden). **What is out of
          stock DOES come, with** ``available: False``: show it marked and do not let it be chosen,
          or the plan answers 2112.
        - ``price`` is text to copy verbatim. Absent means "no price", and so it is on the taxable
          products of a store with ``config["tax_location_missing"]``.
        - A store that rejects its key (2211) is marked with that ``error_code`` until it is
          reconnected; a firewall (2212) or a store that does not answer (2213) is not.

        ``limit`` is 50 when not given, and the server keeps it between 1 and 100.

        .. code-block:: python

            page = pv.integrations.products(org_id, store_id, search="taza")
            choosable = [product for product in page["items"] if product["available"]]
        """
        pagina: IntegrationCatalogPage = self._get(
            f"{self._one_path(id_organization, id_integration)}/products",
            {"cursor": cursor, "search": search, "limit": limit},
            timeout=timeout,
        )
        return pagina

    def _path(self, id_organization: str) -> str:
        return f"/organizations/{require_id(id_organization, 'id_organization')}/integrations"

    def _one_path(self, id_organization: str, id_integration: str) -> str:
        integracion = require_id(id_integration, "id_integration")
        return f"{self._path(id_organization)}/{integracion}"
