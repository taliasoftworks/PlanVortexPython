"""An organization's file library: what gets attached to a publication.

THREE WARNINGS THAT SAVE AN AFTERNOON:

1. **``public_path`` expires.** It is a signed URL, not a permanent link: it stays byte-identical
   within the same hour — caching it that long is correct — and stops serving afterwards. Storing it
   in your database is the classic mistake; three days later every one of them is broken.
2. **The type is decided by the ``content-type`` you send**, not by the content and not by the
   extension. The library guesses it from the name; if the name has no extension, pass it
   (see ``_core/files.py``).
3. **The caps are the server's**: 5 MB per image and 200 MB per video, plus the organization's
   storage quota. All three are checked against the bytes that actually arrive, so a big file fails
   halfway through the upload with an 802, an 803 or an 804 — not before starting.

THIS FILE IS THE SOURCE OF ``resources_sync/uploads.py``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from planvortex._core.files import FileSource, upload_part
from planvortex._core.pagination import Page, PageParams
from planvortex._shapes import ImportFile, ImportResult, UploadUpdate
from planvortex.resources.base import AsyncResource, require_id
from planvortex.types import Upload


class AsyncUploadsResource(AsyncResource):
    """Upload, list, re-cover and delete the files a publication is built from."""

    async def create(
        self,
        id_organization: str,
        file: FileSource,
        *,
        filename: str | None = None,
        content_type: str | None = None,
        timeout: float | None = None,
    ) -> Upload:
        """Upload a file. Takes a path, ``bytes``, an open binary file or an iterable of ``bytes``.

        A path is the good one for anything big: it is the only form that neither goes through
        memory nor asks you to remember to close anything.

        .. code-block:: python

            await pv.uploads.create(org_id, "./hogaza.jpg")
            await pv.uploads.create(org_id, bytes_, filename="hogaza.jpg")
            with open("video.mp4", "rb") as fh:
                await pv.uploads.create(org_id, fh)

        ``content_type`` is worth passing whenever the name has no extension or lies: it is what
        decides ``file_type`` and ``file_format`` on the server (§ ``_core/files.py``).
        """
        with upload_part(file, filename=filename, content_type=content_type) as parte:
            fichero: Upload = await self._post_one(
                f"{self._organization_path(id_organization)}/uploads",
                "upload",
                files=parte.files,
                rewind=parte.rewind,
                repeatable=parte.repeatable,
                timeout=timeout,
            )
            return fichero

    async def list(
        self,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        timeout: float | None = None,
    ) -> Page[Upload]:
        """The library's files.

        The crops the platform makes for itself (``is_temporal``) are not here, and neither are video
        covers, which are another upload and travel inside theirs.
        """
        pagina: Page[Upload] = await self._list(
            f"{self._organization_path(id_organization)}/uploads",
            "uploads",
            {"limit": limit, "offset": offset},
            timeout=timeout,
        )
        return pagina

    def aiterate(
        self,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[Upload]:
        """The library's files, chaining pages."""

        async def buscar(params: PageParams) -> Page[Upload]:
            return await self.list(id_organization, limit=params.limit, offset=params.offset, timeout=timeout)

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    async def get(self, id_organization: str, id_upload: str, *, timeout: float | None = None) -> Upload:
        """One file. Ask for it again whenever you need a ``public_path`` that still works."""
        fichero: Upload = await self._one(self._path(id_organization, id_upload), "upload", timeout=timeout)
        return fichero

    async def update(
        self, id_organization: str, id_upload: str, body: UploadUpdate, *, timeout: float | None = None
    ) -> Upload:
        """Change a video's cover.

        CAREFUL WITH ``cover_offset``: it is written unconditionally, so omitting it clears the
        stored value. To change only ``cover_image``, send back the offset the upload already had.
        """
        fichero: Upload = await self._put_one(
            self._path(id_organization, id_upload), "upload", body, timeout=timeout
        )
        return fichero

    async def remove(
        self,
        id_organization: str,
        id_upload: str,
        *,
        force: bool = False,
        timeout: float | None = None,
    ) -> None:
        """Delete a file.

        With ``force`` it goes even if a publication still points at it; without it, a file in use is
        kept and only taken out of the library.
        """
        await self._delete(
            self._path(id_organization, id_upload),
            {"force_delete": True} if force else None,
            timeout=timeout,
        )

    async def import_files(
        self,
        id_organization: str,
        id_integration: str,
        files: Sequence[ImportFile],
        *,
        timeout: float | None = None,
    ) -> ImportResult:
        """Bring files chosen in an integration — the Drive picker — into the library.

        The answer is PARTIAL on purpose: look at ``errors`` even when ``uploads`` brought something,
        because of six files four can get in. A ``2204`` means the provider has no bytes to give: a
        native Google document is not a file you can download.

        It is called ``import_files`` and not ``import`` because ``import`` is a Python keyword. It is
        the one name in this library that could not stay as the API writes it.
        """
        importacion: ImportResult = await self._post(
            f"{self._organization_path(id_organization)}/uploads/import",
            {
                "id_integration": require_id(id_integration, "id_integration"),
                "files": list(files),
            },
            timeout=timeout,
        )
        return importacion

    def _organization_path(self, id_organization: str) -> str:
        return f"/organizations/{require_id(id_organization, 'id_organization')}"

    def _path(self, id_organization: str, id_upload: str) -> str:
        fichero = require_id(id_upload, "id_upload")
        return f"{self._organization_path(id_organization)}/uploads/{fichero}"
