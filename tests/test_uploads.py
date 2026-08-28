"""La biblioteca de ficheros (capa 2), con los siete metodos del recurso.

Aqui se fija el `multipart` entero, que es lo que no se puede improvisar: **el campo se llama
`file`** —el servidor lo lee con `uploadMulter.single("file")` y cualquier otro nombre llega como
"no se subio ningun fichero"—, y **el `content-type` de la parte decide que guarda el servidor**, no
el contenido ni la extension. Un `application/octet-stream` se lleva un error 805 con un JPEG
perfectamente valido dentro.

Las reglas del reintento de la § Trampa P5 —el `seek(0)`, el flujo que no se puede repetir— viven en
`test_files.py`, donde se prueban sin red.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_httpx2 import HTTPXMock

from planvortex import PlanVortexConfigError
from tests.conftest import BASE_URL, ClienteDePrueba
from tests.contrato import cuerpo, partes_multipart, peticiones, query, ruta, unica

ORG = f"{BASE_URL}/organizations/org1"
FICHERO = {"_id": "up1", "name": "hogaza.jpg", "file_type": "image"}
BYTES = b"\xff\xd8\xff\xe0 no es un jpeg de verdad, pero pesa"


def test_sube_desde_una_ruta_y_monta_el_multipart(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    """El nombre sale de la ruta y el tipo de la extension. Y la libreria abre y cierra ella."""
    httpx_mock.add_response(url=f"{ORG}/uploads", method="POST", json={"upload": FICHERO})
    ruta_local = tmp_path / "hogaza.jpg"
    ruta_local.write_bytes(BYTES)

    assert cliente.esperar(cliente.pv.uploads.create("org1", ruta_local)) == FICHERO

    peticion = unica(httpx_mock)
    partes = partes_multipart(peticion)
    assert partes["file"] == BYTES
    assert b'filename="hogaza.jpg"' in partes["file:headers"]
    assert b"image/jpeg" in partes["file:headers"]
    assert ruta(peticion) == "/organizations/org1/uploads"


def test_sube_desde_bytes_con_su_nombre(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{ORG}/uploads", method="POST", json={"upload": FICHERO})

    subido = cliente.esperar(cliente.pv.uploads.create("org1", BYTES, filename="hogaza.png"))

    assert subido == FICHERO
    assert b"image/png" in partes_multipart(unica(httpx_mock))["file:headers"]


def test_el_content_type_se_puede_imponer(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """Para el nombre que no lleva extension o que miente. Es lo que decide `file_type` en el servidor."""
    httpx_mock.add_response(url=f"{ORG}/uploads", method="POST", json={"upload": FICHERO})

    cliente.esperar(cliente.pv.uploads.create("org1", BYTES, filename="descarga", content_type="image/jpeg"))

    assert b"image/jpeg" in partes_multipart(unica(httpx_mock))["file:headers"]


def test_un_nombre_sin_extension_conocida_no_llega_a_salir(cliente: ClienteDePrueba) -> None:
    """Antes que mandar un `octet-stream` que el servidor rechaza con un 805 poco explicativo."""
    with pytest.raises(PlanVortexConfigError, match="content_type"):
        cliente.esperar(cliente.pv.uploads.create("org1", BYTES, filename="descarga"))


def test_lista_lee_e_itera_la_biblioteca(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{ORG}/uploads?limit=2&offset=0", json={"uploads": [FICHERO], "total": 1})
    httpx_mock.add_response(url=f"{ORG}/uploads?limit=1&offset=0", json={"uploads": [FICHERO], "total": 1})
    httpx_mock.add_response(url=f"{ORG}/uploads?limit=1&offset=1", json={"uploads": [], "total": 1})
    httpx_mock.add_response(url=f"{ORG}/uploads/up1", json={"upload": FICHERO})

    pagina = cliente.esperar(cliente.pv.uploads.list("org1", limit=2, offset=0))
    todos = cliente.iterar(cliente.pv.uploads, "aiterate", "org1", limit=1)
    uno = cliente.esperar(cliente.pv.uploads.get("org1", "up1"))

    assert pagina.data == todos == [FICHERO]
    assert uno == FICHERO


def test_cambia_la_portada_de_un_video(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """Los dos campos viajan juntos: `cover_offset` se escribe siempre y omitirlo lo borra."""
    httpx_mock.add_response(url=f"{ORG}/uploads/up1", method="PUT", json={"upload": FICHERO})

    portada = {"cover_image": "up2", "cover_offset": 1500}
    assert cliente.esperar(cliente.pv.uploads.update("org1", "up1", portada)) == FICHERO
    assert cuerpo(unica(httpx_mock)) == portada


def test_el_borrado_forzado_va_en_camelcase_y_solo_cuando_se_pide(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """`forceDelete` es el quinto camelCase, el que faltaba en la lista escrita a mano del roadmap."""
    httpx_mock.add_response(
        url=f"{ORG}/uploads/up1?forceDelete=true", method="DELETE", json={"success": True}
    )
    httpx_mock.add_response(url=f"{ORG}/uploads/up2", method="DELETE", json={"success": True})

    cliente.esperar(cliente.pv.uploads.remove("org1", "up1", force=True))
    cliente.esperar(cliente.pv.uploads.remove("org1", "up2"))

    forzado, normal = (query(peticion) for peticion in peticiones(httpx_mock))
    assert forzado == {"forceDelete": ["true"]}
    assert normal == {}


def test_la_importacion_es_parcial_a_proposito(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """De dos ficheros entra uno, y `errors` dice cual fallo y por que. Los dos arrays vuelven."""
    httpx_mock.add_response(
        url=f"{ORG}/uploads/import",
        method="POST",
        json={
            "uploads": [FICHERO],
            "errors": [
                {
                    "external_id": "drive-2",
                    "name": "presupuesto",
                    "code": 2204,
                    "message": "El proveedor no da los bytes",
                }
            ],
        },
    )

    resultado = cliente.esperar(
        cliente.pv.uploads.import_files(
            "org1",
            "int1",
            [{"external_id": "drive-1", "name": "hogaza.jpg"}, {"external_id": "drive-2"}],
        )
    )

    assert resultado["uploads"] == [FICHERO]
    assert resultado["errors"][0]["code"] == 2204
    assert cuerpo(unica(httpx_mock)) == {
        "id_integration": "int1",
        "files": [{"external_id": "drive-1", "name": "hogaza.jpg"}, {"external_id": "drive-2"}],
    }
