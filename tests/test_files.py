"""Las cuatro formas de mandar un fichero, y el reintento (capa 1: sin red).

ESTE FICHERO EXISTE POR LA § TRAMPA P5, que es la que no se ve venir. En Node se subia con un `Blob`
de `fs.openAsBlob`, que es RELEIBLE: si el transporte reintentaba, `fetch` volvia a leer desde el
principio. En Python lo natural es pasarle a `httpx2` el objeto abierto —que tambien hace streaming
y permite subir un video de 200 MB sin cargarlo en memoria— pero **el puntero se queda al final**.
Un reintento sobre ese mismo objeto sube CERO BYTES, y el servidor contesta un error de fichero que
no dice absolutamente nada de esto.

Asi que cada forma declara dos cosas: como volver al principio, y si puede volver siquiera. Lo que
no puede —un `stdin`, un socket, un generador— prohibe el reintento entero, incluidos los fallos
previos al vuelo que en cualquier otra peticion serian seguros.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import httpx2
import pytest

from planvortex import PlanVortexConfigError, PlanVortexConnectionError
from planvortex._core.files import MIME_BY_EXTENSION, guess_content_type, upload_part
from planvortex._core.transport import HttpRequest, RetryConfig
from tests.conftest import BASE_URL

BYTES = b"contenido de prueba"


def test_una_ruta_deduce_nombre_y_tipo_y_se_cierra_sola(tmp_path: Path) -> None:
    """Y se cierra sola, que es lo que evita un `ResourceWarning` en el proceso del integrador."""
    ruta = tmp_path / "hogaza.jpg"
    ruta.write_bytes(BYTES)

    with upload_part(ruta) as parte:
        nombre, fichero, tipo = parte.files["file"]
        assert (nombre, tipo) == ("hogaza.jpg", "image/jpeg")
        assert fichero.read() == BYTES
        assert parte.repeatable
        abierto = fichero

    assert abierto.closed


def test_una_ruta_como_cadena_vale_igual(tmp_path: Path) -> None:
    ruta = tmp_path / "video.mp4"
    ruta.write_bytes(BYTES)

    with upload_part(str(ruta)) as parte:
        assert parte.files["file"][2] == "video/mp4"


def test_unos_bytes_exigen_nombre(tmp_path: Path) -> None:
    """No hay de donde sacarlo, y el nombre es lo que decide el tipo."""
    with pytest.raises(PlanVortexConfigError, match="filename"), upload_part(BYTES) as _:
        pass


def test_unos_bytes_no_necesitan_rebobinado() -> None:
    """Se releen solos: no hay puntero que mover, y el reintento es seguro."""
    with upload_part(BYTES, filename="hogaza.png") as parte:
        assert parte.rewind is None
        assert parte.repeatable
        assert parte.files["file"][1] == BYTES


def test_un_fichero_abierto_se_rebobina_a_donde_estaba() -> None:
    """A DONDE ESTABA, no a cero. Para uno recien abierto son lo mismo; para uno ya posicionado,
    volver a cero mandaria un cuerpo distinto en el segundo intento que en el primero.
    """
    fichero = io.BytesIO(b"cabecera" + BYTES)
    fichero.seek(8)

    with upload_part(fichero, filename="hogaza.jpg") as parte:
        assert parte.repeatable
        assert fichero.read() == BYTES
        assert parte.rewind is not None
        parte.rewind()
        assert fichero.tell() == 8


def test_un_fichero_abierto_toma_su_nombre_del_disco(tmp_path: Path) -> None:
    """El `name` de un fichero abierto es la ruta entera; lo que viaja es el ultimo tramo."""
    ruta = tmp_path / "hogaza.jpg"
    ruta.write_bytes(BYTES)

    with ruta.open("rb") as fichero, upload_part(fichero) as parte:
        assert parte.files["file"][0] == "hogaza.jpg"


def test_un_bytesio_sin_nombre_lo_exige() -> None:
    """No tiene `name`, y sin extension no hay tipo que deducir."""
    with pytest.raises(PlanVortexConfigError, match="name"), upload_part(io.BytesIO(BYTES)) as _:
        pass


def test_un_flujo_que_no_se_puede_rebobinar_prohibe_el_reintento() -> None:
    """LA REGLA QUE IMPORTA. No es que se reintente mal: es que no se reintenta en absoluto."""

    class SinVuelta(io.BytesIO):
        def seekable(self) -> bool:
            return False

    with upload_part(SinVuelta(BYTES), filename="hogaza.jpg") as parte:
        assert parte.repeatable is False
        assert parte.rewind is None


def test_un_iterable_de_bytes_tampoco_se_repite() -> None:
    """Se consume al mandarlo y no hay forma de volver a empezar: se manda una vez o no se manda."""
    trozos = (fragmento for fragmento in (b"uno", b"dos"))

    with upload_part(trozos, filename="hogaza.jpg") as parte:
        assert parte.repeatable is False
        assert parte.files["file"][1] is trozos


def test_el_tipo_se_puede_imponer_y_gana_al_deducido() -> None:
    with upload_part(BYTES, filename="hogaza.jpg", content_type="image/heic") as parte:
        assert parte.files["file"][2] == "image/heic"


def test_una_extension_desconocida_falla_antes_de_salir() -> None:
    """Mandar `application/octet-stream` se lleva un 805 —"no es una imagen ni un video"— con un
    JPEG perfectamente valido dentro. Es mejor fallar aqui, y diciendo cuales se aceptan.
    """
    with pytest.raises(PlanVortexConfigError) as fallo, upload_part(BYTES, filename="cosa.txt") as _:
        pass

    assert "content_type" in str(fallo.value)
    assert "jpg" in str(fallo.value)


def test_lo_que_no_es_un_fichero_se_dice_claro() -> None:
    with pytest.raises(PlanVortexConfigError, match="int"), upload_part(42) as _:  # type: ignore[arg-type]
        pass


def test_heic_entra_por_la_puerta_aunque_no_salga_nunca() -> None:
    """El servidor lo convierte a JPEG durante la ingesta: la libreria lo manda tal cual."""
    assert guess_content_type("foto.HEIC") == "image/heic"
    assert set(MIME_BY_EXTENSION) == {"jpg", "jpeg", "png", "gif", "heic", "heif", "mp4"}


def test_el_campo_se_llama_file_y_no_es_negociable() -> None:
    """El servidor lo lee con `uploadMulter.single("file")`: cualquier otro nombre llega como
    "no se subio ningun fichero", que es un error que no dice lo que paso.
    """
    with upload_part(BYTES, filename="hogaza.jpg") as parte:
        assert list(parte.files) == ["file"]


# =================================================================================================
# Y el transporte lo respeta, que es la otra mitad de la trampa
# =================================================================================================
#
# Que `upload_part` declare `rewind` y `repeatable` no sirve de nada si el transporte no los mira.
# Estos dos van contra `HttpClient`/`AsyncHttpClient` directamente porque lo que se esta fijando es
# la regla del transporte, y montarla con un fichero de verdad la esconderia detras del multipart.


def test_el_transporte_rebobina_antes_de_repetir(nucleo: Any, httpx_mock: Any) -> None:
    """Un 503 se reintenta, y el cuerpo tiene que volver al principio ANTES del segundo intento."""
    httpx_mock.add_response(url=f"{BASE_URL}/x", status_code=503, json={})
    httpx_mock.add_response(url=f"{BASE_URL}/x", json={"ok": True})
    rebobinados = []

    http = nucleo.http_client(
        base_url=BASE_URL, retry=RetryConfig(max_retries=1, base_delay=0.0, max_delay=0.01)
    )
    try:
        respuesta = nucleo.esperar(
            http.request(HttpRequest(method="GET", path="/x", rewind=lambda: rebobinados.append(1)))
        )
    finally:
        nucleo.cerrar(http)

    assert respuesta.data == {"ok": True}
    # Una sola vez: antes del SEGUNDO intento, no antes del primero.
    assert rebobinados == [1]


def test_un_cuerpo_irrepetible_no_se_reintenta_ni_ante_un_fallo_previo_al_vuelo(
    nucleo: Any, httpx_mock: Any
) -> None:
    """LA REGLA ENTERA. Un `ConnectError` demuestra que la peticion ni salio, asi que un POST normal
    SI se repite; con un flujo que no se puede rebobinar, no hay segunda copia de esos bytes en
    ninguna parte y repetir subiria cero.
    """
    httpx_mock.add_exception(httpx2.ConnectError("sin conexion"), url=f"{BASE_URL}/x", is_reusable=True)

    http = nucleo.http_client(
        base_url=BASE_URL, retry=RetryConfig(max_retries=2, base_delay=0.0, max_delay=0.01)
    )
    try:
        with pytest.raises(PlanVortexConnectionError):
            nucleo.esperar(http.request(HttpRequest(method="POST", path="/x", repeatable=False)))
        irrepetible = len(httpx_mock.get_requests())

        with pytest.raises(PlanVortexConnectionError):
            nucleo.esperar(http.request(HttpRequest(method="POST", path="/x")))
        normal = len(httpx_mock.get_requests()) - irrepetible
    finally:
        nucleo.cerrar(http)

    assert irrepetible == 1
    assert normal == 3
