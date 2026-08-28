"""GENERADO POR `scripts/generate_sync.py`. NO SE EDITA A MANO.

Gemelo sincrono de `src/planvortex/_client.py`.

Lo que haya que cambiar se cambia ALLI y se regenera con `uv run python scripts/generate_sync.py`;
la CI regenera y falla si hay diferencias.
"""

from __future__ import annotations

import os

import httpx2

from planvortex._core.auth_sync import ClientCredentialsAuth, StaticTokenAuth
from planvortex._core.errors import PlanVortexConfigError, PlanVortexError, is_token_error
from planvortex._core.http_sync import HttpClient, rewind_body
from planvortex._core.transport import (
    DEFAULT_TIMEOUT_SECONDS,
    HttpHooks,
    HttpRequest,
    HttpResponse,
    RetryConfig,
)
from planvortex._version import PLANVORTEX_API_URL, user_agent
from planvortex.resources_sync.accounts import AccountsResource
from planvortex.resources_sync.ai_plans import AiPlansResource
from planvortex.resources_sync.apps import AppsResource
from planvortex.resources_sync.catalog import CatalogResource
from planvortex.resources_sync.clients import ClientsResource
from planvortex.resources_sync.comments import CommentsResource
from planvortex.resources_sync.contacts import ContactsResource
from planvortex.resources_sync.dashboard import DashboardResource
from planvortex.resources_sync.integrations import IntegrationsResource
from planvortex.resources_sync.messages import MessagesResource
from planvortex.resources_sync.organizations import OrganizationsResource
from planvortex.resources_sync.products import ProductsResource
from planvortex.resources_sync.publications import PublicationsResource
from planvortex.resources_sync.uploads import UploadsResource


class PlanVortex:
    """The synchronous client. Everything the API does hangs from here.

    .. code-block:: python

        with PlanVortex() as pv:  # credentials from the environment
            page = pv.accounts.list(org_id, limit=50)

    Credentials come from ``client_id``/``client_secret`` or, failing that, from
    ``PLANVORTEX_CLIENT_ID`` and ``PLANVORTEX_CLIENT_SECRET``. The base URL comes from ``base_url``,
    ``PLANVORTEX_BASE_URL`` or production, in that order.

    **This is a server-side package.** The ``client_credentials`` grant needs the ``client_secret``,
    and a secret inside a front-end bundle is the whole account given away. For the browser there is
    the temporal connection token — see ``organizations.create_connect_token``. There is no guard
    against it here because Python has no ``window`` to look at, so this paragraph is the guard.
    """

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        access_token: str | None = None,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        retry: RetryConfig | None = None,
        hooks: HttpHooks | None = None,
        scope: str | None = None,
        http_client: httpx2.Client | None = None,
    ) -> None:
        #: The base URL in use, with no trailing slash. Useful for composing a URL by hand.
        self.base_url = (base_url or os.environ.get("PLANVORTEX_BASE_URL") or PLANVORTEX_API_URL).rstrip("/")

        # Se guardan para `as_temporal_token`, que construye OTRO cliente con la misma configuracion
        # y credenciales distintas.
        self._timeout = timeout
        self._retry = retry
        self._hooks = hooks
        self._scope = scope
        self._http_client = http_client

        self._http = HttpClient(
            base_url=self.base_url,
            timeout=timeout,
            retry=retry,
            hooks=hooks,
            headers={"user-agent": user_agent()},
            client=http_client,
        )

        identificador = client_id or os.environ.get("PLANVORTEX_CLIENT_ID")
        secreto = client_secret or os.environ.get("PLANVORTEX_CLIENT_SECRET")

        if access_token:
            self._auth: StaticTokenAuth | ClientCredentialsAuth = StaticTokenAuth(access_token)
        elif identificador and secreto:
            self._auth = ClientCredentialsAuth(
                self._http, client_id=identificador, client_secret=secreto, scope=scope
            )
        else:
            raise PlanVortexConfigError(
                "No credentials: pass client_id and client_secret (or PLANVORTEX_CLIENT_ID and "
                "PLANVORTEX_CLIENT_SECRET in the environment), or an access_token."
            )

        #: Static metadata of the networks: what exists, what each can do, and its limits. Cached.
        self.catalog = CatalogResource(self)
        #: Clients: the contracted plan and their root organizations.
        self.clients = ClientsResource(self)
        #: Organizations: the record, the children, and the quota they have and spend.
        self.organizations = OrganizationsResource(self)
        #: Connected social accounts. Connecting one is another matter: it takes a person.
        self.accounts = AccountsResource(self)
        #: An organization's file library.
        self.uploads = UploadsResource(self)
        #: Publications: create, schedule, retry and measure.
        self.publications = PublicationsResource(self)
        #: Comments and reviews: the inbox out of the database, and the thread read live.
        self.comments = CommentsResource(self, self.catalog)
        #: The private inbox: conversations, threads, sending and WhatsApp templates.
        self.messages = MessagesResource(self)
        #: The address book of the people messages are exchanged with.
        self.contacts = ContactsResource(self)
        #: Meta Commerce catalogues and products. Facebook and Instagram only.
        self.products = ProductsResource(self)
        #: Connections to the tools the organization pulls material from: Drive, an RSS feed.
        self.integrations = IntegrationsResource(self)
        #: Publication plans generated with AI, and their credits.
        self.ai_plans = AiPlansResource(self)
        #: The home screen's numbers, already aggregated and compared.
        self.dashboard = DashboardResource(self)
        #: Client apps: the credentials an integration authenticates with. Custom plan.
        self.apps = AppsResource(self)

    def request(self, request: HttpRequest) -> HttpResponse:
        """An authenticated request. This is what every resource uses.

        An integrator should not need it, but it is public so that nobody is left stuck in front of
        an endpoint the library does not cover yet.

        It retries **once only** on the token codes (501 and 522), which arrive inside a 400. A token
        can die before its ``expires_in`` — a Keycloak deployment, the app revoked — and that case is
        fixed by asking for another one; if the second attempt fails too, the error comes out.

        **The repeat obeys the same body rules as the transport.** A request whose body is a stream
        that cannot be rewound is not repeated even here: the bytes are already gone, and a second
        attempt would upload nothing while looking like it worked.
        """
        try:
            return self._send(request)
        except PlanVortexError as error:
            if not is_token_error(error) or not request.repeatable:
                raise
            self._auth.invalidate()
            rewind_body(request)
            return self._send(request)

    def as_temporal_token(self, token: str) -> PlanVortex:
        """The same client, with the same shape, authenticated with a temporal connection token.

        It is the piece of the account-connection flow: an app **cannot** connect an Instagram
        account — that is an OAuth with a person in front of it — so it issues a temporal token,
        hands it to its user, and the connection endpoints are called with this client. The token is
        tied to a single organization: using it against another returns error 1101.

        The new client gets its own ``httpx2`` connection: closing one does not close the other.
        """
        return type(self)(
            access_token=token,
            base_url=self.base_url,
            timeout=self._timeout,
            retry=self._retry,
            hooks=self._hooks,
            scope=self._scope,
            http_client=self._http_client,
        )

    def close(self) -> None:
        """Close the underlying connection, unless the integrator supplied their own client."""
        self._http.close()

    def __enter__(self) -> PlanVortex:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _send(self, request: HttpRequest) -> HttpResponse:
        token = self._auth.get_token()
        request.headers = {**request.headers, "authorization": f"Bearer {token}"}
        return self._http.request(request)
