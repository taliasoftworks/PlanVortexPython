"""Client apps: the credentials an integration authenticates against PlanVortex with.

THIS RESOURCE IS ODD AND IT IS WORTH KNOWING WHY BEFORE USING IT:

- **Almost everything here needs a USER token, not an app one.** With ``client_credentials`` — that
  is, with the client ``PlanVortex(client_id=..., client_secret=...)`` gives you — listing, creating,
  deleting and reading the secret all answer error 512. The only things an app can do in this section
  are READ and UPDATE its own record. It is here for whoever builds their own panel.
- **A client can only have ONE app.** Creating the second answers error 536.
- **It needs the CUSTOM plan** (error 542). Not "a paid plan": pro is paid and does not create apps.
  Apps are what that plan adds, and with no app there is no ``client_id`` to ask for a token with, so
  this is the error whoever tries to integrate without it runs into.
- **The secret is not in the record.** It lives in Keycloak and is asked for separately.
- **Updating REPLACES**: the five fields are written with whatever the body carries, so leaving out
  ``webhook_url`` turns the webhook off (§ :meth:`AsyncAppsResource.update`).
- **Not to be confused with an integration** (``pv.integrations``), which is a connection to Google
  Drive or an RSS feed. They are two different things and half the web has called them the same.

THIS FILE IS THE SOURCE OF ``resources_sync/apps.py``.
"""

from __future__ import annotations

from planvortex._core.pagination import Page
from planvortex.resources.base import AsyncResource, require_id
from planvortex.types import ClientApp, ClientAppInput


class AsyncAppsResource(AsyncResource):
    """The client's apps: the record, its credentials and its webhook."""

    async def list(
        self,
        id_client: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        timeout: float | None = None,
    ) -> Page[ClientApp]:
        """The client's apps. **Needs a user token** (512) and returns at most one.

        There is no chaining iterator here, and it is not an oversight: a client has one app, so a
        loop over pages would be machinery for a list that never has a second page.
        """
        pagina: Page[ClientApp] = await self._list(
            self._path(id_client),
            "client_apps",
            {"limit": limit, "offset": offset},
            timeout=timeout,
        )
        return pagina

    async def get(self, id_client: str, id_app: str, *, timeout: float | None = None) -> ClientApp:
        """One app. It is one of the few things in this section that an app token **can** do: an app
        may read its own record.
        """
        aplicacion: ClientApp = await self._one(
            self._one_path(id_client, id_app), "client_app", timeout=timeout
        )
        return aplicacion

    async def create(
        self, id_client: str, body: ClientAppInput, *, timeout: float | None = None
    ) -> ClientApp:
        """Create the client's app. **Needs a user token** (512) and there can only be one (536).

        ``keycloak_client_idenfifier`` — with the typo, which is the field's name — is the
        ``client_id`` you later ask for a token with, and it has to be unique across all of PlanVortex
        (534). The domains and the redirect urls have to be valid URLs (531 and 532), and
        ``webhook_url`` too (535).
        """
        aplicacion: ClientApp = await self._post_one(
            self._path(id_client), "client_app", body, timeout=timeout
        )
        return aplicacion

    async def update(
        self, id_client: str, id_app: str, body: ClientAppInput, *, timeout: float | None = None
    ) -> ClientApp:
        """Change the app. It accepts an app token: an app may update its own record.

        **IT REPLACES the five fields with whatever the body carries.** It is not a ``PATCH``: an
        update with no ``webhook_url`` turns the webhook off, and one with no ``redirect_urls`` leaves
        the list empty — with which the account connection flow stops accepting any redirect. Read the
        app first and send it back whole.
        """
        aplicacion: ClientApp = await self._put_one(
            self._one_path(id_client, id_app), "client_app", body, timeout=timeout
        )
        return aplicacion

    async def remove(self, id_client: str, id_app: str, *, timeout: float | None = None) -> None:
        """Delete the app. **Needs a user token** (512).

        The Keycloak client is really deleted — so the credentials stop working there and then — and
        the document is marked as deleted instead of disappearing.
        """
        await self._delete(self._one_path(id_client, id_app), timeout=timeout)

    async def secret(self, id_client: str, id_app: str, *, timeout: float | None = None) -> str:
        """The app's ``client_secret``. **Needs a user token** (512).

        It comes from Keycloak, so it is the live secret and not a copy: treat it as a credential, do
        not write it to a log and do not keep it anywhere you would not keep a password.
        """
        cuerpo: dict[str, str] = await self._get(
            f"{self._one_path(id_client, id_app)}/secret", timeout=timeout
        )
        return cuerpo["secret"]

    def _path(self, id_client: str) -> str:
        return f"/clients/{require_id(id_client, 'id_client')}/apps"

    def _one_path(self, id_client: str, id_app: str) -> str:
        return f"{self._path(id_client)}/{require_id(id_app, 'id_app')}"
