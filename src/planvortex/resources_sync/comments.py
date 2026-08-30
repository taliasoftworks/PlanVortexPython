"""GENERADO POR `scripts/generate_sync.py`. NO SE EDITA A MANO.

Gemelo sincrono de `src/planvortex/resources/comments.py`.

Lo que haya que cambiar se cambia ALLI y se regenera con `uv run python scripts/generate_sync.py`;
la CI regenera y falla si hay diferencias.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from planvortex._core.pagination import Page, PageParams
from planvortex._shapes import CommentReplyResult, CommentUpdate
from planvortex.resources_sync.base import Query, RequestSender, Resource, require_id
from planvortex.resources_sync.catalog import CatalogResource
from planvortex.types import Comment, CommentActions, CommentThread


class CommentsResource(Resource):
    """The inbox, the live threads, and what may be done to a comment on each network."""

    def __init__(self, client: RequestSender, catalog: CatalogResource) -> None:
        super().__init__(client)
        # El catalogo se RECIBE en vez de pedirse otra vez: `social_comment_actions()` es una
        # constante del despliegue y el recurso del catalogo ya la cachea por instancia. Pedirla
        # aqui por nuestra cuenta seria una segunda copia de lo mismo, con su propia caducidad.
        self._catalog = catalog

    def list(
        self,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        social_network: Sequence[str] | None = None,
        id_account: str | None = None,
        id_publication: str | None = None,
        unread: bool | None = None,
        search: str | None = None,
        rating: Sequence[int] | None = None,
        timeout: float | None = None,
    ) -> Page[Comment]:
        """THE INBOX of the whole organization, ordered by the network's date.

        It comes out of the database: it calls no network, spends no credits and does not fail
        because an account is disconnected. It is a photograph — ``collected_date`` says of when — so
        to see the state of a conversation right now you open :meth:`thread`.

        **What we write does not show up here**: our replies are stored (the thread needs them) but
        they are not incoming mail.

        **On Telegram this is ALL there is**, and it starts the day the channel was connected: there
        is no live read to complete it with, and no way to import what came before.

        Here, and only here, ``id_account`` and ``id_publication`` come POPULATED.

        ``rating`` is what makes a review inbox usable — "show me the one and two star ones" — and it
        leaves nothing out on the networks without stars, because their comments carry no rating.

        .. code-block:: python

            page = pv.comments.list(org_id, unread=True, rating=[1, 2])
        """
        pagina: Page[Comment] = self._list(
            f"{self._organization_path(id_organization)}/comments",
            "comments",
            self._list_query(
                limit, offset, social_network, id_account, id_publication, unread, search, rating
            ),
            timeout=timeout,
        )
        return pagina

    def iterate(
        self,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        social_network: Sequence[str] | None = None,
        id_account: str | None = None,
        id_publication: str | None = None,
        unread: bool | None = None,
        search: str | None = None,
        rating: Sequence[int] | None = None,
        timeout: float | None = None,
    ) -> Iterator[Comment]:
        """The inbox, chaining pages. It is a database read: it costs no credits."""

        def buscar(params: PageParams) -> Page[Comment]:
            return self.list(
                id_organization,
                limit=params.limit,
                offset=params.offset,
                social_network=social_network,
                id_account=id_account,
                id_publication=id_publication,
                unread=unread,
                search=search,
                rating=rating,
                timeout=timeout,
            )

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    def unread_count(self, id_organization: str, *, timeout: float | None = None) -> int:
        """How many are left unread in the organization. It is the badge's number.

        Ours do not count: a comment we wrote is not waiting to be read.
        """
        cuerpo: dict[str, int] = self._get(
            f"{self._organization_path(id_organization)}/unread_comments", timeout=timeout
        )
        return cuerpo["total"]

    def thread(
        self,
        id_organization: str,
        id_publication: str,
        *,
        limit: int | None = None,
        offset: str | int | None = None,
        timeout: float | None = None,
    ) -> CommentThread:
        """THE THREAD of a publication, read LIVE against the network.

        The network wins: the text, the counters and the very existence come from it, and of what was
        stored only ``_id``, ``read`` and ``replied`` survive. A comment the network no longer
        returns is marked deleted and stops showing up in the inbox.

        **On X it costs one credit per comment returned** (``credits_consumed`` says so afterwards).
        A publication that never went out answers error 936: there is no thread to read.

        **On Telegram it is NOT live**, and that is the one exception to everything above: the Bot
        API has no method that lists the replies to a post, so what comes back is PlanVortex's own
        inbox — what the bot has seen since the channel was connected. Nothing is reconciled and
        nothing is swept as deleted, because there is nothing to compare against. And a channel with
        no linked discussion group has no comments at all: error 965.

        ``offset`` here is the ``next_cursor`` of the previous page, not a number of elements.
        """
        hilo: CommentThread = self._get(
            f"{self._publication_path(id_organization, id_publication)}/comments",
            {"limit": limit, "offset": offset},
            timeout=timeout,
        )
        return hilo

    def thread_by_account(
        self,
        id_organization: str,
        id_account: str,
        *,
        limit: int | None = None,
        offset: str | int | None = None,
        timeout: float | None = None,
    ) -> CommentThread:
        """THE THREAD of an ACCOUNT, the twin of the previous one, for the networks whose comments do
        not hang off a publication of ours.

        Today that is Google Business: a review hangs off the LISTING, not off a post, so that
        account has no publication to call :meth:`thread` with. Careful with ``total``: it is the
        number of REVIEWS, which is not the length of ``comments`` — our replies travel in the same
        array, hanging off the review they answer.
        """
        hilo: CommentThread = self._get(
            f"{self._account_path(id_organization, id_account)}/comments",
            {"limit": limit, "offset": offset},
            timeout=timeout,
        )
        return hilo

    def replies(
        self,
        id_organization: str,
        id_comment: str,
        *,
        limit: int | None = None,
        offset: str | int | None = None,
        timeout: float | None = None,
    ) -> CommentThread:
        """The REPLIES to a comment, also live (and also billed on X).

        On the first page — and only on the first — OUR replies that the network is not listing yet
        are slipped in: they have just been written and indexing takes its time. Without that,
        refreshing the thread right after replying would show nothing and look like it never sent.
        """
        hilo: CommentThread = self._get(
            f"{self._path(id_organization, id_comment)}/replies",
            {"limit": limit, "offset": offset},
            timeout=timeout,
        )
        return hilo

    def reply(
        self, id_organization: str, id_comment: str, text: str, *, timeout: float | None = None
    ) -> CommentReplyResult:
        """Reply IN PUBLIC, hanging off that comment.

        It is not a private message: to write to the commenter through the chat there is
        ``pv.messages.send()``, and not every network allows it. The text cannot be empty and has its
        own limit, ``comment_characters``, which **is not a publication's** (Facebook takes 60.000 in
        a post and 8.000 in a comment); going over answers error 948.

        **On Google Business this is an upsert**: a review has at most one reply, so replying again
        replaces the text of the one that is there. Label the button accordingly.

        It leaves the comment marked read and replied.
        """
        respuesta: CommentReplyResult = self._post(
            f"{self._path(id_organization, id_comment)}/reply", {"text": text}, timeout=timeout
        )
        return respuesta

    def update(
        self, id_organization: str, id_comment: str, body: CommentUpdate, *, timeout: float | None = None
    ) -> Comment:
        """Change ``read`` (ours) and/or ``hidden`` (the network's) in a single call.

        Both are accepted together because the screen changes them from the same place, but they are
        not the same thing: ``read`` never leaves PlanVortex and ``hidden`` goes to the network and
        may not be allowed there.
        """
        comentario: Comment = self._put_one(
            self._path(id_organization, id_comment), "comment", body, timeout=timeout
        )
        return comentario

    def mark_read(
        self, id_organization: str, id_comment: str, read: bool = True, *, timeout: float | None = None
    ) -> Comment:
        """Mark read or unread. A shortcut for :meth:`update` for what is done all the time."""
        return self.update(id_organization, id_comment, {"read": read}, timeout=timeout)

    def remove(self, id_organization: str, id_comment: str, *, timeout: float | None = None) -> None:
        """Delete the comment **on the social network**.

        Only where the network allows it: ``delete_own`` and ``delete_others`` in :meth:`actions` are
        two different permissions, and on Google Business the only deletable thing is our own reply
        to a review. The row is kept, marked as deleted, so the next read does not resurrect it.

        On Telegram the network allows both, and both still depend on a permission the customer
        controls: the bot has to be an administrator of the discussion group with the right to
        delete. When it is not, the answer is error 969 — which is the difference between "this
        network cannot" and "this particular channel cannot".
        """
        self._delete(self._path(id_organization, id_comment), timeout=timeout)

    def actions(self, *, timeout: float | None = None) -> dict[str, CommentActions]:
        """What may be done to each network's comments: reply, hide, delete your own, delete theirs.

        It is what decides which buttons get painted, and **it does not follow from
        ``social_capabilities``**: that a network has comments says nothing about what it lets you do
        with them. Cached along with the rest of the catalogue.
        """
        matriz: dict[str, CommentActions] = self._catalog.social_comment_actions(timeout=timeout)
        return matriz

    def actions_for(self, social_network: str, *, timeout: float | None = None) -> CommentActions | None:
        """The four flags of ONE network, or ``None`` if that network has no comments.

        Two methods instead of one overloaded on the argument's type — which is what the Node library
        does — because in Python an overload that changes the return type by looking at ``isinstance``
        is a footgun for whoever is not running a type checker, and this reads better at the call
        site anyway: ``if (pv.comments.actions_for("linkedin")) is None``.
        """
        matriz = self.actions(timeout=timeout)
        return matriz.get(social_network)

    def _list_query(
        self,
        limit: int | None,
        offset: int | None,
        social_network: Sequence[str] | None,
        id_account: str | None,
        id_publication: str | None,
        unread: bool | None,
        search: str | None,
        rating: Sequence[int] | None,
    ) -> Query:
        return {
            "limit": limit,
            "offset": offset,
            "social_network": social_network,
            "id_account": id_account,
            "id_publication": id_publication,
            # El servidor enciende el filtro con la MERA PRESENCIA del parametro: cualquier valor
            # que no sea el literal "false" cuenta como "si". Mandar `unread=false` pediria justo lo
            # contrario de lo que dice el codigo de quien llama, asi que un `False` se omite.
            "unread": True if unread else None,
            "search": search,
            "rating": rating,
        }

    def _organization_path(self, id_organization: str) -> str:
        return f"/organizations/{require_id(id_organization, 'id_organization')}"

    def _path(self, id_organization: str, id_comment: str) -> str:
        comentario = require_id(id_comment, "id_comment")
        return f"{self._organization_path(id_organization)}/comments/{comentario}"

    def _account_path(self, id_organization: str, id_account: str) -> str:
        cuenta = require_id(id_account, "id_account")
        return f"{self._organization_path(id_organization)}/accounts/{cuenta}"

    def _publication_path(self, id_organization: str, id_publication: str) -> str:
        publicacion = require_id(id_publication, "id_publication")
        return f"{self._organization_path(id_organization)}/publish/{publicacion}"
