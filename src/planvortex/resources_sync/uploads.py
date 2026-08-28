"""GENERADO POR `scripts/generate_sync.py`. NO SE EDITA A MANO.

Gemelo sincrono de `src/planvortex/resources/uploads.py`.

Lo que haya que cambiar se cambia ALLI y se regenera con `uv run python scripts/generate_sync.py`;
la CI regenera y falla si hay diferencias.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from planvortex._core.files import FileSource, upload_part
from planvortex._core.pagination import Page, PageParams
from planvortex._shapes import ImportFile, ImportResult, UploadUpdate
from planvortex.resources_sync.base import Resource, require_id
from planvortex.types import Upload


class UploadsResource(Resource):
    """Upload, list, re-cover and delete the files a publication is built from."""

    def create(
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

            pv.uploads.create(org_id, "./hogaza.jpg")
            pv.uploads.create(org_id, bytes_, filename="hogaza.jpg")
            with open("video.mp4", "rb") as fh:
                pv.uploads.create(org_id, fh)

        ``content_type`` is worth passing whenever the name has no extension or lies: it is what
        decides ``file_type`` and ``file_format`` on the server (§ ``_core/files.py``).
        """
        with upload_part(file, filename=filename, content_type=content_type) as parte:
            fichero: Upload = self._post_one(
                f"{self._organization_path(id_organization)}/uploads",
                "upload",
                files=parte.files,
                rewind=parte.rewind,
                repeatable=parte.repeatable,
                timeout=timeout,
            )
            return fichero

    def list(
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
        pagina: Page[Upload] = self._list(
            f"{self._organization_path(id_organization)}/uploads",
            "uploads",
            {"limit": limit, "offset": offset},
            timeout=timeout,
        )
        return pagina

    def iterate(
        self,
        id_organization: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        timeout: float | None = None,
    ) -> Iterator[Upload]:
        """The library's files, chaining pages."""

        def buscar(params: PageParams) -> Page[Upload]:
            return self.list(id_organization, limit=params.limit, offset=params.offset, timeout=timeout)

        return self._iterate_pages(buscar, limit=limit, offset=offset)

    def get(self, id_organization: str, id_upload: str, *, timeout: float | None = None) -> Upload:
        """One file. Ask for it again whenever you need a ``public_path`` that still works."""
        fichero: Upload = self._one(self._path(id_organization, id_upload), "upload", timeout=timeout)
        return fichero

    def update(
        self, id_organization: str, id_upload: str, body: UploadUpdate, *, timeout: float | None = None
    ) -> Upload:
        """Change a video's cover.

        CAREFUL WITH ``cover_offset``: it is written unconditionally, so omitting it clears the
        stored value. To change only ``cover_image``, send back the offset the upload already had.
        """
        fichero: Upload = self._put_one(
            self._path(id_organization, id_upload), "upload", body, timeout=timeout
        )
        return fichero

    def remove(
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
        self._delete(
            self._path(id_organization, id_upload),
            {"force_delete": True} if force else None,
            timeout=timeout,
        )

    def import_files(
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
        importacion: ImportResult = self._post(
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
