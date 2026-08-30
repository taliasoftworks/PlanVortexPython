"""GENERADO POR `scripts/generate_sync.py`. NO SE EDITA A MANO.

Gemelo sincrono de `src/planvortex/resources/products.py`.

Lo que haya que cambiar se cambia ALLI y se regenera con `uv run python scripts/generate_sync.py`;
la CI regenera y falla si hay diferencias.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from planvortex._core.errors import NO_ERROR_CODE, PlanVortexError
from planvortex._core.pagination import Page, PageParams, unwrap_one
from planvortex.resources_sync.base import Resource, require_id
from planvortex.types import Product, ProductCatalog, ProductCatalogInput, ProductInput


class ProductsResource(Resource):
    """Catalogues and products of an account, in Meta's own vocabulary."""

    def list(
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

            page = pv.products.list(org_id, account_id, catalog_id, limit=50)
        """
        pagina: Page[Product] = self._list(
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

    def iterate(
        self,
        id_organization: str,
        id_account: str,
        id_catalog: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        timeout: float | None = None,
    ) -> Iterator[Product]:
        """The products of a catalogue, chaining pages.

        It stops on a page shorter than the limit and not when it reaches ``total``: in this listing
        ``total`` is always ``0``.
        """

        def buscar(params: PageParams) -> Page[Product]:
            return self.list(
                id_organization,
                id_account,
                id_catalog,
                limit=params.limit,
                offset=params.offset,
                timeout=timeout,
            )

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    def get(
        self, id_organization: str, id_account: str, product_id: str, *, timeout: float | None = None
    ) -> Product:
        """ONE product, by its identifier **on the network** (Meta's, not a PlanVortex ``_id``).

        It used to be forwarded to the SDK under a name it does not read, so it never reached the
        network and the call died with a 2000; that was fixed on 2026-08-24. This library exposed it
        first, in ``0.1.0``; the Node one followed in ``0.3.0``.

        **The answer is shaped differently from the listing.** Asking for one product goes to that
        product's own node, so the network answers with the product rather than with a list and
        ``items`` carries an object. This method accepts both shapes, which is why it exists instead
        of a ``product_id`` argument on :meth:`list`: a ``Page`` cannot be built out of an object.
        """
        cuerpo: Any = self._get(
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

    def create(
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
        cuerpo: dict[str, str] = self._post(
            f"{self._path(id_organization, id_account)}/products",
            product,
            query={"product_catalog_id": require_id(id_catalog, "id_catalog")},
            timeout=timeout,
        )
        return cuerpo["product_id"]

    def catalogs(
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
        pagina: Page[ProductCatalog] = self._list(
            f"{self._path(id_organization, id_account)}/products_catalogs",
            "items",
            {"limit": limit, "offset": offset},
            timeout=timeout,
        )
        return pagina

    def iterate_catalogs(
        self,
        id_organization: str,
        id_account: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        timeout: float | None = None,
    ) -> Iterator[ProductCatalog]:
        """The account's catalogues, chaining pages."""

        def buscar(params: PageParams) -> Page[ProductCatalog]:
            return self.catalogs(
                id_organization,
                id_account,
                limit=params.limit,
                offset=params.offset,
                timeout=timeout,
            )

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    def create_catalog(
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
        cuerpo: dict[str, str] = self._post(
            f"{self._path(id_organization, id_account)}/products_catalogs", catalog, timeout=timeout
        )
        return cuerpo["product_catalog"]

    def _path(self, id_organization: str, id_account: str) -> str:
        organizacion = require_id(id_organization, "id_organization")
        cuenta = require_id(id_account, "id_account")
        return f"/organizations/{organizacion}/accounts/{cuenta}"
