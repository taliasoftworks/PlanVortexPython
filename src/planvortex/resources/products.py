"""Meta Commerce product catalogues.

WHAT TO KNOW BEFORE CALLING ANYTHING HERE:

- **Facebook and Instagram only.** They are the only two networks with ``products: true`` in
  ``pv.catalog.social_capabilities()``; WhatsApp does not have it either, despite having its own
  catalogue.
- **This speaks Meta**, with Meta's field names. There is no common vocabulary here as there is in
  statistics: what you send and what comes back is what the Graph API documents.
- **``total`` is no use for paginating.** On products it is always ``0`` (it comes from a ``summary``
  PlanVortex does not ask for) and on catalogues it is the length of the page. Page until you see a
  short page.
- **The account has to be a page with a business behind it**: the catalogue hangs off the
  ``business_id``, not off the profile.

THIS FILE IS THE SOURCE OF ``resources_sync/products.py``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from planvortex._core.errors import NO_ERROR_CODE, PlanVortexError
from planvortex._core.pagination import Page, PageParams, unwrap_one
from planvortex.resources.base import AsyncResource, require_id
from planvortex.types import Product, ProductCatalog, ProductCatalogInput, ProductInput


class AsyncProductsResource(AsyncResource):
    """Catalogues and products of an account, in Meta's own vocabulary."""

    async def list(
        self,
        id_organization: str,
        id_account: str,
        id_catalog: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        timeout: float | None = None,
    ) -> Page[Product]:
        """The products of a catalogue.

        ``id_catalog`` is required in practice even though the API paints it optional: without it —
        and without a product identifier — the request fails with error 2000.

        .. code-block:: python

            page = await pv.products.list(org_id, account_id, catalog_id, limit=50)
        """
        pagina: Page[Product] = await self._list(
            f"{self._path(id_organization, id_account)}/products",
            "items",
            {
                "product_catalog_id": require_id(id_catalog, "id_catalog"),
                "limit": limit,
                "offset": offset,
            },
            timeout=timeout,
        )
        return pagina

    def aiterate(
        self,
        id_organization: str,
        id_account: str,
        id_catalog: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[Product]:
        """The products of a catalogue, chaining pages.

        It stops on a page shorter than the limit and not when it reaches ``total``: in this listing
        ``total`` is always ``0``.
        """

        async def buscar(params: PageParams) -> Page[Product]:
            return await self.list(
                id_organization,
                id_account,
                id_catalog,
                limit=params.limit,
                offset=params.offset,
                timeout=timeout,
            )

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    async def get(
        self, id_organization: str, id_account: str, product_id: str, *, timeout: float | None = None
    ) -> Product:
        """ONE product, by its identifier **on the network** (Meta's, not a PlanVortex ``_id``).

        It used to be forwarded to the SDK under a name it does not read, so it never reached the
        network and the call died with a 2000; that was fixed on 2026-08-24 and this is the first
        library to expose it — the Node one still documents it as broken.

        **The answer is shaped differently from the listing.** Asking for one product goes to that
        product's own node, so the network answers with the product rather than with a list and
        ``items`` carries an object. This method accepts both shapes, which is why it exists instead
        of a ``product_id`` argument on :meth:`list`: a ``Page`` cannot be built out of an object.
        """
        cuerpo: Any = await self._get(
            f"{self._path(id_organization, id_account)}/products",
            {"product_id": require_id(product_id, "product_id")},
            timeout=timeout,
        )
        contenido: Any = unwrap_one(cuerpo, "items")
        # Una lista tambien se acepta: es lo que devolveria un despliegue que envolviera la respuesta,
        # y coger el primero es mejor respuesta que reventar por la forma del sobre.
        if isinstance(contenido, list):
            if not contenido:
                raise PlanVortexError(
                    NO_ERROR_CODE,
                    f'The network returned no product for "{product_id}".',
                    data={"product_id": product_id},
                    family="http",
                )
            contenido = contenido[0]
        producto: Product = contenido
        return producto

    async def create(
        self,
        id_organization: str,
        id_account: str,
        id_catalog: str,
        product: ProductInput,
        *,
        timeout: float | None = None,
    ) -> str:
        """Register a product in a catalogue, or **update an existing one** if the body carries ``id``.

        It returns the identifier ON THE NETWORK, not the product.
        """
        cuerpo: dict[str, str] = await self._post(
            f"{self._path(id_organization, id_account)}/products",
            product,
            query={"product_catalog_id": require_id(id_catalog, "id_catalog")},
            timeout=timeout,
        )
        return cuerpo["product_id"]

    async def catalogs(
        self,
        id_organization: str,
        id_account: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        timeout: float | None = None,
    ) -> Page[ProductCatalog]:
        """The account's catalogues. This is where the ``id_catalog`` of everything else comes from.

        ``total`` is the length of the page, so it never says there is another one.
        """
        pagina: Page[ProductCatalog] = await self._list(
            f"{self._path(id_organization, id_account)}/products_catalogs",
            "items",
            {"limit": limit, "offset": offset},
            timeout=timeout,
        )
        return pagina

    def aiterate_catalogs(
        self,
        id_organization: str,
        id_account: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[ProductCatalog]:
        """The account's catalogues, chaining pages."""

        async def buscar(params: PageParams) -> Page[ProductCatalog]:
            return await self.catalogs(
                id_organization,
                id_account,
                limit=params.limit,
                offset=params.offset,
                timeout=timeout,
            )

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    async def create_catalog(
        self,
        id_organization: str,
        id_account: str,
        catalog: ProductCatalogInput,
        *,
        timeout: float | None = None,
    ) -> str:
        """Create a catalogue and return **its identifier**, not the catalogue.

        The field of the answer is called ``product_catalog`` and carries a string; to see the rest
        you have to ask :meth:`catalogs` again.
        """
        cuerpo: dict[str, str] = await self._post(
            f"{self._path(id_organization, id_account)}/products_catalogs", catalog, timeout=timeout
        )
        return cuerpo["product_catalog"]

    def _path(self, id_organization: str, id_account: str) -> str:
        organizacion = require_id(id_organization, "id_organization")
        cuenta = require_id(id_account, "id_account")
        return f"/organizations/{organizacion}/accounts/{cuenta}"
