"""GENERADO POR `scripts/generate_sync.py`. NO SE EDITA A MANO.

Gemelo sincrono de `src/planvortex/resources/accounts.py`.

Lo que haya que cambiar se cambia ALLI y se regenera con `uv run python scripts/generate_sync.py`;
la CI regenera y falla si hay diferencias.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime
from typing import Any

from planvortex._core.errors import NO_ERROR_CODE, create_error_from_response
from planvortex._core.pagination import Page, PageParams
from planvortex._shapes import AccountConnectResponse, AccountUpdate, ConnectResult, EnableResult
from planvortex.resources_sync.base import Resource, require_id
from planvortex.types import (
    Account,
    AccountMetricNames,
    AccountMetrics,
    ConnectLink,
    PersistentMenu,
)

# Lo que la red social pego a la URL de vuelta. Se pasa TAL CUAL, sin tocar ni filtrar: cada red
# manda lo suyo (`code` y `state` casi todas, `oauth_token`/`oauth_verifier` X, ...).
ConnectCallbackParams = Mapping[str, "str | Sequence[str] | None"]


class AccountsResource(Resource):
    """The connected accounts, the connection flow and the metrics already measured."""

    def connect_links(
        self,
        id_organization: str,
        *,
        social_network: Sequence[str] | None = None,
        redirect_uri: str | None = None,
        timeout: float | None = None,
    ) -> list[ConnectLink]:
        """The authorization links of each connectable network, to send the person to theirs.

        **With app credentials it answers 519.** Call it with a client authenticated by the temporal
        token: ``pv.as_temporal_token(token).accounts.connect_links(org_id)``.

        **A network that cannot give a link simply does not appear**, and that is a legitimate answer
        rather than a failure: it is what happens to Discord in an organization that has not saved
        its own bot credentials yet.

        **LOOK AT ``authorization``, NOT AT WHETHER ``link`` IS EMPTY.** Nine of the ten networks are
        ``redirect`` and the person is sent to ``link``. **WhatsApp is not a URL**: its sign-up is
        Meta's Embedded Signup, a popup your own page raises with the Facebook JavaScript SDK, so its
        ``link`` is the empty string and what you need to open it travels in ``authorization``.
        Walking the list redirecting to ``link`` sends your user to your own page.

        CAREFUL: ``redirect_uri`` here is which PlanVortex front the NETWORK returns the user to, for
        a white-label deployment, and it has to be one the server has registered or the call answers
        532 — it cannot be a URL of yours, because the networks only accept redirect URIs registered
        in their own application. Where YOUR user ends up is decided in
        ``organizations.create_connect_token``.
        """
        enlaces: list[ConnectLink] = self._one(
            f"{self._organization_path(id_organization)}/connect_links",
            "links",
            {"social_network": social_network, "redirect_uri": redirect_uri},
            timeout=timeout,
        )
        return enlaces

    def connect(
        self,
        id_organization: str,
        social_network: str,
        params: ConnectCallbackParams | None = None,
        *,
        timeout: float | None = None,
    ) -> ConnectResult:
        """Complete the connection with whatever the network stuck onto the return URL.

        **Most integrations never need this call.** The return URL is built by the network from the
        link in :meth:`connect_links` and points at a PlanVortex front: it is that front which calls
        here. The method exists for whoever serves their own interface on one of the domains
        registered on the server. In the normal integration it is enough to send the user to the
        temporal token's ``url`` and wait for them to come back.

        **The endpoint answers 200 even when it failed**, with the error inside the body, because the
        browser lands here from a redirect and a bare 400 would be a broken page. The library undoes
        that patch: if ``errorCode`` arrives it **raises** the error it deserves, exactly like any
        other method, so what comes out of here is only good accounts.

        **And they come back DISABLED**: they take no plan slot and publish nothing until
        :meth:`enable` is called. One authorization can leave several — a Facebook user with four
        pages is four of them — which is why there is a choosing step in the middle.
        """
        ruta = (
            f"{self._organization_path(id_organization)}"
            f"/account-connect/{require_id(social_network, 'social_network')}"
        )
        cuerpo: AccountConnectResponse = self._get(ruta, params, timeout=timeout)

        codigo = cuerpo.get("errorCode")
        if codigo:
            # El `errorCode` viaja como CADENA y es el codigo del catalogo, asi que se reconstruye el
            # error como si hubiera venido en un cuerpo de error normal: asi quien llama coge un
            # `AccountError` o un `PlanLimitError` y no una forma distinta solo aqui.
            raise create_error_from_response(
                body={
                    "code": int(codigo) if codigo.lstrip("-").isdigit() else NO_ERROR_CODE,
                    "message": cuerpo.get("errorMsg") or f"The connection did not complete ({codigo}).",
                },
                status=200,
            )

        resultado: ConnectResult = {"accounts": cuerpo.get("accounts") or []}
        if "redirect_uri" in cuerpo:
            resultado["redirect_uri"] = cuerpo["redirect_uri"]
        return resultado

    def enable(self, id_organization: str, id_account: str, *, timeout: float | None = None) -> EnableResult:
        """Enable one of the accounts :meth:`connect` left behind, or recover one that got
        disconnected while its stored token still works (if it does not, error 700 and it has to be
        authorized again).

        **This is the step that takes a plan slot**: with the quota full it answers 706, so call it
        one at a time and check the room first (``organizations.limits``). It is also the step that
        turns the network's webhooks on, on any plan that is not the free one.
        """
        cuerpo: Any = self._post(f"{self._path(id_organization, id_account)}/enable", timeout=timeout)
        # `success: true` no se devuelve: un fallo llega como excepcion, asi que aqui solo interesa
        # si el token temporal traia un sitio al que mandar al usuario despues.
        destino = cuerpo.get("redirect_uri") if isinstance(cuerpo, dict) else None
        return {"redirect_uri": destino} if isinstance(destino, str) else {}

    def list(
        self,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        name: str | None = None,
        social_network: Sequence[str] | None = None,
        accounts: Sequence[str] | None = None,
        capability: str | None = None,
        timeout: float | None = None,
    ) -> Page[Account]:
        """An organization's accounts.

        ``capability`` filters by what the account's network can do — ``publications``, ``messages``,
        ``products``, ``webhooks``, ``persistent_menu``, ``comments`` — applied on the server with
        the same matrix ``catalog.social_capabilities()`` publishes. It is how you ask for "the
        accounts I can publish with" without keeping a table of your own.
        """
        pagina: Page[Account] = self._list(
            f"{self._organization_path(id_organization)}/accounts",
            "accounts",
            {
                "limit": limit,
                "offset": offset,
                "name": name,
                "social_network": social_network,
                "accounts": accounts,
                "capability": capability,
            },
            timeout=timeout,
        )
        return pagina

    def iterate(
        self,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        name: str | None = None,
        social_network: Sequence[str] | None = None,
        accounts: Sequence[str] | None = None,
        capability: str | None = None,
        timeout: float | None = None,
    ) -> Iterator[Account]:
        """An organization's accounts, chaining pages."""

        def buscar(params: PageParams) -> Page[Account]:
            return self.list(
                id_organization,
                limit=params.limit,
                offset=params.offset,
                name=name,
                social_network=social_network,
                accounts=accounts,
                capability=capability,
                timeout=timeout,
            )

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    def get(self, id_organization: str, id_account: str, *, timeout: float | None = None) -> Account:
        """One account's record."""
        cuenta: Account = self._one(self._path(id_organization, id_account), "account", timeout=timeout)
        return cuenta

    def update(
        self, id_organization: str, id_account: str, body: AccountUpdate, *, timeout: float | None = None
    ) -> Account:
        """Change the name the account is shown under inside PlanVortex. It is the only editable
        thing, and it renames nothing on the social network.
        """
        cuenta: Account = self._put_one(
            self._path(id_organization, id_account), "account", body, timeout=timeout
        )
        return cuenta

    def remove(self, id_organization: str, id_account: str, *, timeout: float | None = None) -> None:
        """Disconnect the account and **delete its publications**. What was already published on the
        network stays where it is: this does not touch it.
        """
        self._delete(self._path(id_organization, id_account), timeout=timeout)

    def metrics(
        self,
        id_organization: str,
        id_account: str,
        *,
        from_date: datetime | str | None = None,
        to_date: datetime | str | None = None,
        names: Sequence[str] | None = None,
        timeout: float | None = None,
    ) -> AccountMetrics:
        """The series of an account's already-measured metrics.

        It is a read of what was stored, not a call to the network: looking at the chart costs no
        credits. The grouping is decided by the range — up to 31 days by day, up to 720 by month, and
        beyond that by year — and comes said in ``group``.

        ``names`` are the RAW names, the ones :meth:`metric_list` returns. Without it every measure
        comes back. A ``datetime`` needs a timezone, or the library raises rather than guess
        (§ Trampa P8).
        """
        metricas: AccountMetrics = self._get(
            f"{self._path(id_organization, id_account)}/metrics",
            {"from_date": from_date, "to_date": to_date, "names": names},
            timeout=timeout,
        )
        return metricas

    def metric_list(
        self, id_organization: str, id_account: str, *, timeout: float | None = None
    ) -> AccountMetricNames:
        """The RAW names of the metrics this account's network publishes.

        They are what you pass to :meth:`metrics` and what comes back in every row. This is not the
        common vocabulary — that is a publication's ``metrics``: here each network speaks its own
        language (``page_impressions``, ``total_interactions``, ``allPageViews``).
        """
        nombres: AccountMetricNames = self._get(
            f"{self._path(id_organization, id_account)}/metric_list", timeout=timeout
        )
        return nombres

    def get_persistent_menu(
        self, id_organization: str, id_account: str, *, timeout: float | None = None
    ) -> PersistentMenu:
        """The chat's fixed menu, one entry per language.

        Only the networks with messaging have one: on the others the call returns error 710. Check it
        with ``persistent_menu`` in ``catalog.social_capabilities()``.
        """
        menu: PersistentMenu = self._one(
            f"{self._path(id_organization, id_account)}/persistent_menu",
            "persistent_menu",
            timeout=timeout,
        )
        return menu

    def set_persistent_menu(
        self,
        id_organization: str,
        id_account: str,
        menu: PersistentMenu,
        *,
        timeout: float | None = None,
    ) -> PersistentMenu:
        """Replace the chat's fixed menu. It is a REPLACEMENT: what is not in the list disappears.

        The entry with ``locale: "default"`` is compulsory — it is the one shown when no other fits.
        """
        guardado: PersistentMenu = self._post_one(
            f"{self._path(id_organization, id_account)}/persistent_menu",
            "persistent_menu",
            {"persistent_menu": menu},
            timeout=timeout,
        )
        return guardado

    def _organization_path(self, id_organization: str) -> str:
        return f"/organizations/{require_id(id_organization, 'id_organization')}"

    def _path(self, id_organization: str, id_account: str) -> str:
        cuenta = require_id(id_account, "id_account")
        return f"{self._organization_path(id_organization)}/accounts/{cuenta}"
