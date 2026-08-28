"""GENERADO POR `scripts/generate_sync.py`. NO SE EDITA A MANO.

Gemelo sincrono de `src/planvortex/resources/clients.py`.

Lo que haya que cambiar se cambia ALLI y se regenera con `uv run python scripts/generate_sync.py`;
la CI regenera y falla si hay diferencias.
"""

from __future__ import annotations

from collections.abc import Iterator

from planvortex._core.pagination import Page, PageParams
from planvortex._shapes import ClientUpdate, ClientWithOrganizations
from planvortex.resources_sync.base import Query, Resource, require_id
from planvortex.types import AiSettings, Client, Organization, OrganizationCreate, OrganizationUpdate


class ClientsResource(Resource):
    """The client, its root organizations and the AI providers it pays for itself."""

    def list(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
        get_use: bool | None = None,
        timeout: float | None = None,
    ) -> Page[Client]:
        """The clients the caller can see. With app credentials, its own.

        ``get_use`` also brings ``actual_use`` and ``actual_asigned``. It costs an aggregation: do
        not ask for it out of habit.
        """
        pagina: Page[Client] = self._list(
            "/clients", "clients", _list_query(limit, offset, get_use), timeout=timeout
        )
        return pagina

    def iterate(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
        get_use: bool | None = None,
        timeout: float | None = None,
    ) -> Iterator[Client]:
        """The clients, page after page, without carrying the ``offset`` by hand."""

        def buscar(params: PageParams) -> Page[Client]:
            return self.list(limit=params.limit, offset=params.offset, get_use=get_use, timeout=timeout)

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    def get(self, id_client: str, *, get_use: bool | None = None, timeout: float | None = None) -> Client:
        """One client's record."""
        cliente: Client = self._one(
            f"/clients/{require_id(id_client, 'id_client')}",
            "client",
            {"get_use": True} if get_use else None,
            timeout=timeout,
        )
        return cliente

    def update(self, id_client: str, body: ClientUpdate, *, timeout: float | None = None) -> Client:
        """Change the little a client lets you change: its name and its type."""
        cliente: Client = self._put_one(
            f"/clients/{require_id(id_client, 'id_client')}", "client", body, timeout=timeout
        )
        return cliente

    def organizations(
        self,
        id_client: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        name: str | None = None,
        get_use: bool | None = None,
        timeout: float | None = None,
    ) -> Page[Organization]:
        """A client's ROOT organizations. The children hang from each of those."""
        query = dict(_list_query(limit, offset, get_use))
        query["name"] = name
        pagina: Page[Organization] = self._list(
            f"/clients/{require_id(id_client, 'id_client')}/organizations",
            "organizations",
            query,
            timeout=timeout,
        )
        return pagina

    def iterate_organizations(
        self,
        id_client: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        name: str | None = None,
        get_use: bool | None = None,
        timeout: float | None = None,
    ) -> Iterator[Organization]:
        """A client's root organizations, chaining pages."""

        def buscar(params: PageParams) -> Page[Organization]:
            return self.organizations(
                id_client,
                limit=params.limit,
                offset=params.offset,
                name=name,
                get_use=get_use,
                timeout=timeout,
            )

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    def create_organization(
        self, id_client: str, body: OrganizationCreate, *, timeout: float | None = None
    ) -> Organization:
        """Create a root organization. What is assigned to it comes off what the client has."""
        organizacion: Organization = self._post_one(
            f"/clients/{require_id(id_client, 'id_client')}/organizations",
            "organization",
            body,
            timeout=timeout,
        )
        return organizacion

    def update_organization(
        self,
        id_client: str,
        id_organization: str,
        body: OrganizationUpdate,
        *,
        timeout: float | None = None,
    ) -> Organization:
        """Change a root organization's assigned quota.

        **The name is not editable here**, and it is not rejected either: the server keeps the
        current one and ignores it silently. To rename one there is ``organizations.update``.
        """
        organizacion: Organization = self._put_one(
            self._organization_path(id_client, id_organization), "organization", body, timeout=timeout
        )
        return organizacion

    def delete_organization(
        self, id_client: str, id_organization: str, *, timeout: float | None = None
    ) -> None:
        """Delete a root organization **with everything inside it**: its child organizations, its
        accounts, its publications, its files and its comments. It does not undo.
        """
        self._delete(self._organization_path(id_client, id_organization), timeout=timeout)

    def update_ai_settings(self, id_client: str, body: AiSettings, *, timeout: float | None = None) -> Client:
        """Configure the client's AI providers (BYOK), scope by scope.

        A scope set to ``None`` DELETES its configuration and returns that scope to PlanVortex's
        credits; with a provider of your own, generating costs no credits because the client pays
        their provider. ``orchestrator`` and ``text`` need a text provider and ``image`` an image one.

        **The key is sent and never comes back**: the response is the client, with no secrets.
        """
        cliente: Client = self._put_one(
            f"/clients/{require_id(id_client, 'id_client')}/ai-settings", "client", body, timeout=timeout
        )
        return cliente

    def with_organizations(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
        limit_organizations: int | None = None,
        offset_organizations: int | None = None,
        get_use: bool | None = None,
        timeout: float | None = None,
    ) -> Page[ClientWithOrganizations]:
        """The clients the caller can see **with their root organizations inside**, in one call.

        It is the shortcut for starting up: with :meth:`list` and :meth:`organizations` it takes
        ``1 + N`` requests to paint an organization picker. Here each client carries its own
        ``organizations`` array and its own ``total``.

        The two ``*_organizations`` arguments paginate the inner array, which is the reason they
        exist: a client with two hundred organizations would otherwise bring all of them.
        """
        pagina: Page[ClientWithOrganizations] = self._list(
            "/clients_organizations",
            "clients",
            {
                "limit": limit,
                "offset": offset,
                "limit_organizations": limit_organizations,
                "offset_organizations": offset_organizations,
                "get_use": True if get_use else None,
            },
            timeout=timeout,
        )
        return pagina

    def _organization_path(self, id_client: str, id_organization: str) -> str:
        return (
            f"/clients/{require_id(id_client, 'id_client')}"
            f"/organizations/{require_id(id_organization, 'id_organization')}"
        )


def _list_query(limit: int | None, offset: int | None, get_use: bool | None) -> Query:
    # `get_use` solo se manda cuando se pide: un `getUse=false` en la query es ruido en el log y el
    # servidor lo compara contra la cadena "true" de todos modos.
    return {"limit": limit, "offset": offset, "get_use": True if get_use else None}
