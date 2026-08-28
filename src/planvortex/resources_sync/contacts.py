"""GENERADO POR `scripts/generate_sync.py`. NO SE EDITA A MANO.

Gemelo sincrono de `src/planvortex/resources/contacts.py`.

Lo que haya que cambiar se cambia ALLI y se regenera con `uv run python scripts/generate_sync.py`;
la CI regenera y falla si hay diferencias.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence

from planvortex._core.pagination import Page, PageParams
from planvortex.resources_sync.base import Query, Resource, require_id
from planvortex.types import Contact, ContactCreate, ContactExtraData, ContactUpdate

# Un filtro por un campo propio del contacto: `{"key": "city", "value": ["Madrid", "Toledo"]}`. Una
# lista de valores se lee como "cualquiera de".
ContactExtraFilter = Mapping[str, "str | int | Sequence[str] | Sequence[int]"]


class ContactsResource(Resource):
    """The address book: list, read, create, change and delete."""

    def list(
        self,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        search: str | None = None,
        social_network: str | None = None,
        extra_data: Sequence[ContactExtraFilter] | None = None,
        timeout: float | None = None,
    ) -> Page[Contact]:
        """The organization's address book, from the newest to the oldest.

        ``search`` goes by NAME, with Mongo's text index: it matches whole words, not fragments.
        "pana" does not find "Panadería"; "Panadería" does.

        ``social_network`` keeps the contacts reachable on that network, matching on
        ``social_identifiers[].social_network``, so a contact with several channels comes back
        through any of them. **It used to return an empty list always** — the server compared the
        whole array of objects against the name of the network — and that was fixed on 2026-08-24;
        the Node library still documents it as broken and this one does not.

        ``extra_data`` filters by your own fields and the filters are combined with AND.

        .. code-block:: python

            page = pv.contacts.list(org_id, extra_data=[{"key": "city", "value": "Madrid"}])
        """
        pagina: Page[Contact] = self._list(
            self._path(id_organization),
            "contacts",
            self._list_query(limit, offset, search, social_network, extra_data),
            timeout=timeout,
        )
        return pagina

    def iterate(
        self,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        search: str | None = None,
        social_network: str | None = None,
        extra_data: Sequence[ContactExtraFilter] | None = None,
        timeout: float | None = None,
    ) -> Iterator[Contact]:
        """The address book, chaining pages."""

        def buscar(params: PageParams) -> Page[Contact]:
            return self.list(
                id_organization,
                limit=params.limit,
                offset=params.offset,
                search=search,
                social_network=social_network,
                extra_data=extra_data,
                timeout=timeout,
            )

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    def get(self, id_organization: str, id_contact: str, *, timeout: float | None = None) -> Contact:
        """One contact."""
        contacto: Contact = self._one(self._one_path(id_organization, id_contact), "contact", timeout=timeout)
        return contacto

    def create(self, id_organization: str, body: ContactCreate, *, timeout: float | None = None) -> Contact:
        """Register a contact, or get back the one that was already there.

        It needs **at least one identifier** (error 1601): a contact with no channel is a contact
        nobody can write to. And if one already exists with the first channel and the same
        ``external_identifier``, THAT one comes back as it is, with nothing of what was sent applied.

        .. code-block:: python

            contact = pv.contacts.create(
                org_id,
                {
                    "name": "Marta",
                    "social_identifiers": [
                        {"social_network": "whatsapp", "external_identifier": "34600111222"}
                    ],
                },
            )
        """
        contacto: Contact = self._post_one(self._path(id_organization), "contact", body, timeout=timeout)
        return contacto

    def update(
        self, id_organization: str, id_contact: str, body: ContactUpdate, *, timeout: float | None = None
    ) -> None:
        """Change a contact. **It does not return the contact**: the API answers ``{success: true}``,
        so this returns nothing and you have to read it again to see the result.

        CAREFUL WITH ``extra_data``: it is the only field NOT kept when omitted. The server writes it
        with whatever the body carries, so an update without ``extra_data`` leaves the contact with
        none of its own fields. ``name``, ``profile_image`` and ``social_identifiers`` are respected
        when they do not travel. So nobody has to remember, :meth:`merge`.

        ``social_identifiers`` REPLACES the whole list; it is not merged into it.
        """
        self._put(self._one_path(id_organization, id_contact), body, timeout=timeout)

    def merge(
        self, id_organization: str, id_contact: str, body: ContactUpdate, *, timeout: float | None = None
    ) -> None:
        """Like :meth:`update`, but reading the contact first so its ``extra_data`` is not lost.

        It is TWO requests and it is not free; it exists because the silent wiping of ``extra_data``
        is the mistake you make once and find out about weeks later. What you pass in ``extra_data``
        is merged over what was there, field by field; to really empty it, :meth:`update` with
        ``extra_data: {}``.
        """
        actual = self.get(id_organization, id_contact, timeout=timeout)
        propios: ContactExtraData = {**actual.get("extra_data", {}), **body.get("extra_data", {})}
        self.update(id_organization, id_contact, {**body, "extra_data": propios}, timeout=timeout)

    def remove(self, id_organization: str, id_contact: str, *, timeout: float | None = None) -> None:
        """Delete the contact **and all of its messages**."""
        self._delete(self._one_path(id_organization, id_contact), timeout=timeout)

    def remove_all(self, id_organization: str, *, timeout: float | None = None) -> None:
        """Delete ALL of the organization's contacts and ALL of their messages.

        It asks for no confirmation and there is no undo. It is here because the API has it, not
        because it is an everyday operation.
        """
        self._delete(self._path(id_organization), timeout=timeout)

    def _list_query(
        self,
        limit: int | None,
        offset: int | None,
        search: str | None,
        social_network: str | None,
        extra_data: Sequence[ContactExtraFilter] | None,
    ) -> Query:
        consulta: dict[str, object] = {
            "limit": limit,
            "offset": offset,
            "search": search,
            "social_network": social_network,
        }
        # Los filtros por `extra_data` viajan como `extra_data[0][key]=...&extra_data[0][value]=...`,
        # que es como Express los vuelve a montar en un array de objetos. No es una invencion: es la
        # unica forma de mandar una lista de pares por query string a un servidor con el parser
        # extendido.
        for indice, filtro in enumerate(extra_data or ()):
            consulta[f"extra_data[{indice}][key]"] = filtro["key"]
            consulta[f"extra_data[{indice}][value]"] = filtro["value"]
        return consulta

    def _path(self, id_organization: str) -> str:
        return f"/organizations/{require_id(id_organization, 'id_organization')}/contacts"

    def _one_path(self, id_organization: str, id_contact: str) -> str:
        return f"{self._path(id_organization)}/{require_id(id_contact, 'id_contact')}"
