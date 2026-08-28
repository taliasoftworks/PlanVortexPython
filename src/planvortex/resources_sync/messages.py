"""GENERADO POR `scripts/generate_sync.py`. NO SE EDITA A MANO.

Gemelo sincrono de `src/planvortex/resources/messages.py`.

Lo que haya que cambiar se cambia ALLI y se regenera con `uv run python scripts/generate_sync.py`;
la CI regenera y falla si hay diferencias.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from planvortex._core.pagination import Page, PageParams
from planvortex.resources_sync.base import Resource, require_id
from planvortex.types import (
    Conversation,
    ConversationTotals,
    Message,
    MessageInput,
    MessageTemplate,
)


class MessagesResource(Resource):
    """Conversations, threads, sending, templates and the unread counter."""

    def conversations(
        self,
        id_organization: str,
        id_account: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        timeout: float | None = None,
    ) -> Page[Conversation]:
        """An account's conversations: a contact, the date of the last message, and how many of
        theirs are unread. Ordered by activity, the most recent first.

        **The first call for an account can take a while**: with nothing stored, the server downloads
        the conversations and their messages from the network before answering. Raise ``timeout`` for
        that one.

        A conversation has no ``_id`` of its own: what opens the thread is
        ``conversation["contact"]["_id"]``.
        """
        pagina: Page[Conversation] = self._list(
            f"{self._account_path(id_organization, id_account)}/conversations",
            "conversations",
            {"limit": limit, "offset": offset},
            timeout=timeout,
        )
        return pagina

    def iterate_conversations(
        self,
        id_organization: str,
        id_account: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        timeout: float | None = None,
    ) -> Iterator[Conversation]:
        """An account's conversations, chaining pages."""

        def buscar(params: PageParams) -> Page[Conversation]:
            return self.conversations(
                id_organization,
                id_account,
                limit=params.limit,
                offset=params.offset,
                timeout=timeout,
            )

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    def conversation_totals(
        self,
        id_organization: str,
        *,
        from_date: datetime | str | None = None,
        to_date: datetime | str | None = None,
        group_by: str | None = None,
        timeout: float | None = None,
    ) -> ConversationTotals:
        """How many conversations the WHOLE organization had in a range, in total or grouped.

        **A conversation is a contact on a day**, not a thread: the same person writing on Monday and
        on Tuesday counts twice. And ``group_value`` is the NUMBER Mongo produces (``$dayOfYear``,
        ``$month``, ``$year``), not a date — with ``group_by="day"`` two years of the same range fall
        on the same value, so narrow the range before grouping by day.

        Without ``group_by`` you get ``{total}`` and with it ``{stats, group}``: two different
        answers, not one with extra fields. The default range is the current month, decided by the
        server.
        """
        totales: ConversationTotals = self._get(
            f"{self._organization_path(id_organization)}/conversations_total",
            {"from_date": from_date, "to_date": to_date, "group_by": group_by},
            timeout=timeout,
        )
        return totales

    def account_conversation_totals(
        self,
        id_organization: str,
        id_account: str,
        *,
        from_date: datetime | str | None = None,
        to_date: datetime | str | None = None,
        group_by: str | None = None,
        timeout: float | None = None,
    ) -> ConversationTotals:
        """The same count, for ONE account.

        Two methods and not one with an optional ``id_account``, which is what the Node library does
        with an overload: they are two different routes, and a keyword that silently changes the URL
        is the kind of thing that reads fine and gets the wrong number.
        """
        totales: ConversationTotals = self._get(
            f"{self._account_path(id_organization, id_account)}/conversations_total",
            {"from_date": from_date, "to_date": to_date, "group_by": group_by},
            timeout=timeout,
        )
        return totales

    def list(
        self,
        id_organization: str,
        id_account: str,
        id_contact: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        timeout: float | None = None,
    ) -> Page[Message]:
        """The thread with a contact, from the most recent to the oldest.

        **Asking for the first page (``offset`` 0 or no ``offset``) marks the thread as read.** It is
        what makes :meth:`unread_count` go down; there is no way to read it without marking it.

        Here, and in the webhook, ``contact_id``, ``from_contact_id`` and ``message_options["files"]``
        come POPULATED. Use ``planvortex.types.message_contact``, ``message_contact_id`` and
        ``message_files`` instead of assuming it.
        """
        pagina: Page[Message] = self._list(
            self._thread_path(id_organization, id_account, id_contact),
            "messages",
            {"limit": limit, "offset": offset},
            timeout=timeout,
        )
        return pagina

    def iterate(
        self,
        id_organization: str,
        id_account: str,
        id_contact: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        timeout: float | None = None,
    ) -> Iterator[Message]:
        """The thread with a contact, chaining pages.

        Careful: the first page marks the thread as read, so walking it whole marks it too.
        """

        def buscar(params: PageParams) -> Page[Message]:
            return self.list(
                id_organization,
                id_account,
                id_contact,
                limit=params.limit,
                offset=params.offset,
                timeout=timeout,
            )

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    def send(
        self,
        id_organization: str,
        id_account: str,
        id_contact: str,
        body: MessageInput,
        *,
        timeout: float | None = None,
    ) -> Message:
        """Send a message to a contact.

        ``simple_message`` and ``file_message`` work on every network with a chat; the rest are Meta's
        or WhatsApp's own shapes and each one needs its block in ``message_options``
        (``template_name`` + ``template_language``, ``whatsappInteractive``, ``metaElements``,
        ``metaQuickReplies``). The text is validated against ``characters`` in
        ``pv.catalog.social_limits()``, which is the CHAT's limit and not a publication's.

        On Facebook and Instagram only **one** attachment per message is accepted (error 1509), and on
        WhatsApp outside the 24-hour window only a template is.

        ``comment_message`` and ``publication_message`` need ``in_response_external_id``: the
        identifier ON THE NETWORK of what is being answered — a comment's ``external_id``, a
        publication's ``external_identifier`` — never a PlanVortex ``_id``, and error 1510 without it.
        The endpoint did not read it from the body until 2026-08-24, which left both types unreachable
        from the public API; they work now, on Facebook and Instagram.

        .. code-block:: python

            pv.messages.send(
                org_id,
                account_id,
                contact_id,
                {"message_type": "simple_message", "text": "Abrimos de 9 a 14"},
            )
        """
        mensaje: Message = self._post_one(
            self._thread_path(id_organization, id_account, id_contact),
            "message",
            body,
            timeout=timeout,
        )
        return mensaje

    def unread_count(self, id_organization: str, *, timeout: float | None = None) -> int:
        """How many messages are left unread in the organization. It is the badge's number."""
        cuerpo: dict[str, int] = self._get(
            f"{self._organization_path(id_organization)}/unread_messages", timeout=timeout
        )
        return cuerpo["total"]

    def remove_by_account(
        self, id_organization: str, id_account: str, *, timeout: float | None = None
    ) -> None:
        """Delete ALL of an account's messages. There is no undo and no confirmation.

        The contacts stay: what goes is the messages.
        """
        self._delete(f"{self._account_path(id_organization, id_account)}/messages", timeout=timeout)

    def templates(
        self,
        id_organization: str,
        id_account: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        timeout: float | None = None,
    ) -> Page[MessageTemplate]:
        """The account's message templates.

        **WHATSAPP ONLY.** No other network implements them, and asking on another does not give the
        1502 of "this network has no chat": the SDK raises a bare error and the global handler turns
        it into an **HTTP 500 with ``code: 500``**. Check the account is WhatsApp's before calling.

        What comes back is what Meta returns, with its names: ``name``, ``status``, ``components`` and
        ``language``. It is not translated into anything of ours because the template you have to name
        when sending is theirs.
        """
        pagina: Page[MessageTemplate] = self._list(
            f"{self._account_path(id_organization, id_account)}/message_templates",
            "templates",
            {"limit": limit, "offset": offset},
            timeout=timeout,
        )
        return pagina

    def create_template(
        self,
        id_organization: str,
        id_account: str,
        template: MessageTemplate,
        *,
        timeout: float | None = None,
    ) -> MessageTemplate:
        """Create a template. **WhatsApp only** (§ :meth:`templates`).

        The body travels in Meta's format, as is; a new template is born under review and cannot be
        used until Meta approves it.
        """
        guardada: MessageTemplate = self._post_one(
            f"{self._account_path(id_organization, id_account)}/message_templates",
            "template",
            template,
            timeout=timeout,
        )
        return guardada

    def delete_template(
        self,
        id_organization: str,
        id_account: str,
        template_id: str,
        template_name: str,
        *,
        timeout: float | None = None,
    ) -> None:
        """Delete a template. **WhatsApp only** (§ :meth:`templates`).

        BOTH things are needed, the identifier and the name: Meta deletes by name and uses the ``id``
        to tell apart the languages of the same template. They travel in the query, not in the body.
        """
        self._delete(
            f"{self._account_path(id_organization, id_account)}/message_templates",
            {"template_id": template_id, "template_name": template_name},
            timeout=timeout,
        )

    def _organization_path(self, id_organization: str) -> str:
        return f"/organizations/{require_id(id_organization, 'id_organization')}"

    def _account_path(self, id_organization: str, id_account: str) -> str:
        cuenta = require_id(id_account, "id_account")
        return f"{self._organization_path(id_organization)}/accounts/{cuenta}"

    def _thread_path(self, id_organization: str, id_account: str, id_contact: str) -> str:
        contacto = require_id(id_contact, "id_contact")
        return f"{self._account_path(id_organization, id_account)}/messages/{contacto}"
