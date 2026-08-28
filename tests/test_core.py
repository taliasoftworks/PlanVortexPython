"""Los seis casos que la fase 4 de la libreria de Node exigio, aqui en las dos variantes.

Son los que deciden si el nucleo sirve o no, y ninguno se puede comprobar mirando el codigo:

1. el token se cachea entre llamadas;
2. se refresca ANTES de caducar;
3. diez llamadas en paralelo piden UN token, no diez;
4. un 503 se reintenta con backoff;
5. un 400 de dominio NO se reintenta nunca;
6. un 400 con `code: 1301` llega como `PlanLimitError`.

Alrededor van las trampas de la API que el nucleo tiene que respetar: el POST que solo se repite si
no llego a salir (§ P10), el `Retry-After` largo que se devuelve en vez de esperarse, y el
`datetime` naive que lanza en vez de suponer (§ P8).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx2
import pytest
from pytest_httpx2 import HTTPXMock

from planvortex._core.errors import (
    AccountError,
    PlanLimitError,
    PlanVortexAuthenticationError,
    PlanVortexConfigError,
    PlanVortexConnectionError,
    PlanVortexError,
    PublicationError,
    create_error_from_response,
    error_class_for_code,
    is_token_error,
)
from planvortex._core.http import HttpHooks, HttpRequest, RetryConfig, RetryInfo, parse_retry_after
from planvortex._core.query import encode_query, format_datetime
from tests.conftest import BASE_URL

# Backoff diminuto: lo que se comprueba es que reintenta y cuantas veces, no cuanto duerme. Con el
# medio segundo de produccion, la suite tardaria segundos en cada caso.
RETRY_RAPIDO = RetryConfig(max_retries=2, base_delay=0.001, max_delay=0.05)


def _http(nucleo: Any, **kwargs: Any) -> Any:
    kwargs.setdefault("retry", RETRY_RAPIDO)
    return nucleo.http_client(base_url=BASE_URL, **kwargs)


def _auth(nucleo: Any, http: Any) -> Any:
    return nucleo.credentials_auth(http, client_id="app-id", client_secret="app-secret")


def _token_response(httpx_mock: HTTPXMock, *, expires_in: int = 3600) -> None:
    httpx_mock.add_response(
        url=f"{BASE_URL}/oauth/token",
        method="POST",
        json={"access_token": f"token-{expires_in}", "token_type": "Bearer", "expires_in": expires_in},
    )


def _peticiones_de_token(httpx_mock: HTTPXMock) -> int:
    return len([r for r in httpx_mock.get_requests() if r.url.path.endswith("/oauth/token")])


# --------------------------------------------------------------------------- los seis casos


def test_el_token_se_cachea_entre_llamadas(nucleo: Any, httpx_mock: HTTPXMock) -> None:
    """Dos llamadas, una sola peticion de token.

    El freno del servidor son 30 intentos por minuto y por `client_id`: sin cache, una app con
    trafico normal se come su propio cupo pidiendo tokens.
    """
    _token_response(httpx_mock, expires_in=3600)
    http = _http(nucleo)
    auth = _auth(nucleo, http)

    primero = nucleo.esperar(auth.get_token())
    segundo = nucleo.esperar(auth.get_token())

    assert primero == segundo == "token-3600"
    assert _peticiones_de_token(httpx_mock) == 1
    nucleo.cerrar(http)


def test_el_token_se_refresca_antes_de_caducar(nucleo: Any, httpx_mock: HTTPXMock) -> None:
    """Con 30 s de vida y 60 s de margen, la segunda llamada ya pide uno nuevo.

    El margen existe para que un token no caduque A MITAD DE VUELO: eso llega como un 400 con
    `code: 501` que el integrador no podia prevenir de ninguna manera.
    """
    _token_response(httpx_mock, expires_in=30)
    _token_response(httpx_mock, expires_in=3600)
    http = _http(nucleo)
    auth = _auth(nucleo, http)

    assert nucleo.esperar(auth.get_token()) == "token-30"
    assert nucleo.esperar(auth.get_token()) == "token-3600"
    assert _peticiones_de_token(httpx_mock) == 2
    nucleo.cerrar(http)


def test_diez_llamadas_en_paralelo_piden_un_solo_token(nucleo: Any, httpx_mock: HTTPXMock) -> None:
    """El caso que justifica el cerrojo, y el que distingue las dos variantes de verdad.

    En async son diez corrutinas bajo un `asyncio.Lock`; en sincrono, diez HILOS bajo un
    `threading.Lock`. Si el gemelo se hubiera generado mal y el sincrono llevara un `asyncio.Lock`,
    aqui saldrian varias peticiones de token — que es exactamente el fallo de la § Trampa P7.
    """
    _token_response(httpx_mock, expires_in=3600)
    http = _http(nucleo)
    auth = _auth(nucleo, http)

    tokens = nucleo.en_paralelo(auth.get_token, 10)

    assert tokens == ["token-3600"] * 10
    assert _peticiones_de_token(httpx_mock) == 1
    nucleo.cerrar(http)


def test_un_503_se_reintenta(nucleo: Any, httpx_mock: HTTPXMock) -> None:
    """503 y luego 200: la llamada sale bien y el hook `on_retry` lo cuenta."""
    httpx_mock.add_response(url=f"{BASE_URL}/organizations", method="GET", status_code=503)
    httpx_mock.add_response(url=f"{BASE_URL}/organizations", method="GET", json={"data": []})

    reintentos: list[RetryInfo] = []
    http = _http(nucleo, hooks=HttpHooks(on_retry=reintentos.append))

    respuesta = nucleo.esperar(http.request(HttpRequest(method="GET", path="/organizations")))

    assert respuesta.status == 200
    assert [info.status for info in reintentos] == [503]
    nucleo.cerrar(http)


def test_un_400_de_dominio_no_se_reintenta_nunca(nucleo: Any, httpx_mock: HTTPXMock) -> None:
    """Repetir "la cuenta esta desconectada" no la conecta.

    Es la regla que hace que clasificar por `code` y no por status importe: en esta API TODO error
    de dominio es un 400, asi que un cliente que reintentase los 4xx reintentaria absolutamente
    todo lo que puede salir mal.
    """
    httpx_mock.add_response(
        url=f"{BASE_URL}/organizations",
        method="GET",
        status_code=400,
        json={"code": 703, "message": "Account disconnected", "data": {}},
    )
    http = _http(nucleo)

    with pytest.raises(AccountError) as fallo:
        nucleo.esperar(http.request(HttpRequest(method="GET", path="/organizations")))

    assert fallo.value.code == 703
    assert len(httpx_mock.get_requests()) == 1
    nucleo.cerrar(http)


def test_un_400_con_code_1301_llega_como_plan_limit_error(nucleo: Any, httpx_mock: HTTPXMock) -> None:
    """El error que un integrador SI quiere distinguir: no se arregla reintentando, se arregla pagando."""
    httpx_mock.add_response(
        url=f"{BASE_URL}/organizations/o1/publish",
        method="POST",
        status_code=400,
        json={"code": 1301, "message": "Publication limit reached", "data": {"limit": 40}},
    )
    http = _http(nucleo)

    with pytest.raises(PlanLimitError) as fallo:
        nucleo.esperar(http.request(HttpRequest(method="POST", path="/organizations/o1/publish")))

    assert fallo.value.code == 1301
    assert fallo.value.family == "plan_limit"
    assert fallo.value.data == {"limit": 40}
    assert fallo.value.status == 400
    nucleo.cerrar(http)


# ------------------------------------------------------------------ las trampas de alrededor


def test_un_post_no_se_repite_por_un_503(nucleo: Any, httpx_mock: HTTPXMock) -> None:
    """§ Trampa P10. Un 5xx es la respuesta de un servidor que SI recibio la peticion.

    Publicar dos veces es peor que fallar, y la API no tiene clave de idempotencia.
    """
    httpx_mock.add_response(url=f"{BASE_URL}/organizations/o1/publish", method="POST", status_code=503)
    http = _http(nucleo)

    with pytest.raises(PlanVortexError):
        nucleo.esperar(http.request(HttpRequest(method="POST", path="/organizations/o1/publish")))

    assert len(httpx_mock.get_requests()) == 1
    nucleo.cerrar(http)


def test_un_post_si_se_repite_si_ni_llego_a_salir(nucleo: Any, httpx_mock: HTTPXMock) -> None:
    """La otra mitad de la § Trampa P10: un `ConnectError` demuestra que el cuerpo no salio."""
    httpx_mock.add_exception(httpx2.ConnectError("connection refused"))
    httpx_mock.add_response(url=f"{BASE_URL}/organizations/o1/publish", method="POST", json={"_id": "p1"})
    http = _http(nucleo)

    respuesta = nucleo.esperar(http.request(HttpRequest(method="POST", path="/organizations/o1/publish")))

    assert respuesta.data == {"_id": "p1"}
    assert len(httpx_mock.get_requests()) == 2
    nucleo.cerrar(http)


def test_un_retry_after_mas_largo_que_el_tope_no_se_espera(nucleo: Any, httpx_mock: HTTPXMock) -> None:
    """El freno del endpoint de token pide hasta 300 s, y eso no puede ser una llamada colgada.

    Se devuelve el error con `retry_after` puesto y decide quien llama.
    """
    httpx_mock.add_response(
        url=f"{BASE_URL}/organizations",
        method="GET",
        status_code=429,
        headers={"retry-after": "300"},
    )
    http = _http(nucleo)

    with pytest.raises(PlanVortexError) as fallo:
        nucleo.esperar(http.request(HttpRequest(method="GET", path="/organizations")))

    assert fallo.value.retry_after == 300
    assert len(httpx_mock.get_requests()) == 1
    nucleo.cerrar(http)


def test_un_timeout_llega_como_error_de_conexion(nucleo: Any, httpx_mock: HTTPXMock) -> None:
    """Un timeout no es un error del servidor: no hubo respuesta, asi que no hay `code` que dar."""
    httpx_mock.add_exception(httpx2.ReadTimeout("too slow"))
    http = _http(nucleo, retry=RetryConfig(max_retries=0))

    with pytest.raises(PlanVortexConnectionError) as fallo:
        nucleo.esperar(http.request(HttpRequest(method="GET", path="/organizations")))

    assert fallo.value.timeout is True
    assert fallo.value.status is None
    assert fallo.value.family == "connection"
    nucleo.cerrar(http)


def test_el_error_del_endpoint_de_token_tiene_forma_oauth(nucleo: Any, httpx_mock: HTTPXMock) -> None:
    """El unico sitio de la API que NO devuelve `{code, message, data}`.

    El servidor tiene codigos para esto (538-541) pero no los manda en el cuerpo, asi que ponerlos
    seria inventarse algo que nadie dijo: viaja `oauth_error` y el `code` se queda en 0.
    """
    httpx_mock.add_response(
        url=f"{BASE_URL}/oauth/token",
        method="POST",
        status_code=401,
        json={"error": "invalid_client", "error_description": "Client authentication failed"},
    )
    http = _http(nucleo)
    auth = _auth(nucleo, http)

    with pytest.raises(PlanVortexAuthenticationError) as fallo:
        nucleo.esperar(auth.get_token())

    assert fallo.value.oauth_error == "invalid_client"
    assert fallo.value.code == 0
    assert fallo.value.family == "oauth"
    nucleo.cerrar(http)


def test_el_token_temporal_no_se_refresca(nucleo: Any) -> None:
    """`invalidate()` no hace nada a proposito: un token temporal no se renueva solo."""
    auth = nucleo.static_auth("temporal-abc")

    assert nucleo.esperar(auth.get_token()) == "temporal-abc"
    auth.invalidate()
    assert nucleo.esperar(auth.get_token()) == "temporal-abc"


def test_las_listas_viajan_como_clave_repetida(nucleo: Any, httpx_mock: HTTPXMock) -> None:
    """`state=["pending", "error"]` -> `?state=pending&state=error`, que es lo que lee el servidor."""
    httpx_mock.add_response(url=None, method="GET", json={"data": []})
    http = _http(nucleo)

    nucleo.esperar(
        http.request(
            HttpRequest(method="GET", path="/organizations/o1/publish", query={"state": ["pending", "error"]})
        )
    )

    enviada = httpx_mock.get_requests()[0]
    assert str(enviada.url).endswith("?state=pending&state=error")
    nucleo.cerrar(http)


# ------------------------------------------------------- lo que no necesita las dos variantes


def test_cada_rango_del_catalogo_cae_en_su_clase() -> None:
    """El apendice A del roadmap, comprobado codigo a codigo en las fronteras.

    Los rangos sin clase propia —`general`, `role`, `payment`— caen en la base a proposito: existen
    en el servidor pero no son superficie de integracion.
    """
    assert error_class_for_code(500) is error_class_for_code(544)
    assert error_class_for_code(900).__name__ == "PublicationError"
    assert error_class_for_code(1300).__name__ == "PlanLimitError"
    assert error_class_for_code(1408).__name__ == "PlanLimitError"
    assert error_class_for_code(2299).__name__ == "IntegrationError"
    # Fuera de todo rango conocido, y el catalogo crece cada mes.
    assert error_class_for_code(9999) is PlanVortexError
    assert error_class_for_code(1000) is PlanVortexError
    assert error_class_for_code(1900) is PlanVortexError


def test_un_codigo_desconocido_conserva_code_y_message() -> None:
    """Nunca se traga y nunca se renombra: el catalogo del servidor va por delante del paquete."""
    error = create_error_from_response(body={"code": 7777, "message": "Something new"}, status=400)

    assert type(error) is PlanVortexError
    assert error.code == 7777
    assert error.message == "Something new"
    assert error.family == "unknown"


def test_un_cuerpo_sin_code_no_es_un_error_de_dominio() -> None:
    """El 502 de un proxy con una pagina HTML dentro. No tiene `code` y no se le inventa uno."""
    error = create_error_from_response(body="<html>502 Bad Gateway</html>", status=502)

    assert error.code == 0
    assert error.family == "http"
    assert error.data == {"body": "<html>502 Bad Gateway</html>"}


def test_un_code_booleano_no_se_lee_como_el_codigo_1() -> None:
    """En Python `True` ES un `int`, asi que `{"code": true}` colaria como codigo 1 sin el guardia."""
    error = create_error_from_response(body={"code": True}, status=400)

    assert error.code == 0
    assert error.family == "http"


def test_los_dos_codigos_de_token_viajan_dentro_de_un_400() -> None:
    """501 y 522 son los que disparan el reintento con token nuevo. El 520 NO, y sale 401."""
    assert is_token_error(PlanVortexError(501, "expired"))
    assert is_token_error(PlanVortexError(522, "invalid"))
    assert not is_token_error(PlanVortexError(520, "no permissions"))
    assert not is_token_error(ValueError("nothing to do with us"))


def test_un_datetime_naive_lanza_en_vez_de_suponer() -> None:
    """§ Trampa P8. Suponer UTC publica a la hora equivocada al que esta en Madrid.

    Y suponer la zona local del proceso publica a la hora equivocada al que esta en Docker. Lanzar
    es lo unico que no miente.
    """
    with pytest.raises(PlanVortexConfigError) as fallo:
        format_datetime(datetime(2026, 9, 1, 10, 0), field="publish_date")

    assert "publish_date" in str(fallo.value)
    assert "naive" in str(fallo.value)


def test_un_datetime_con_zona_viaja_con_offset() -> None:
    con_zona = datetime(2026, 9, 1, 10, 0, tzinfo=timezone(timedelta(hours=2)))
    assert format_datetime(con_zona) == "2026-09-01T10:00:00+02:00"


def test_los_booleanos_van_en_minuscula() -> None:
    """`str(True)` daria "True", y el servidor compara contra la cadena "true"."""
    assert encode_query({"get_use": True, "force_delete": False}) == [
        ("getUse", "true"),
        ("forceDelete", "false"),
    ]


def test_un_none_no_viaja_y_una_lista_vacia_tampoco() -> None:
    """Un `?state=` filtraria por la cadena vacia y devolveria nada, que no es lo que nadie pidio."""
    assert encode_query({"state": None, "social_network": [], "limit": 10}) == [("limit", "10")]


@pytest.mark.parametrize(
    ("cabecera", "esperado"),
    [("120", 120.0), ("0", 0.0), ("-5", None), (None, None), ("", None), ("no es un numero", None)],
)
def test_retry_after_en_segundos(cabecera: str | None, esperado: float | None) -> None:
    assert parse_retry_after(cabecera) == esperado


def test_retry_after_como_fecha_http() -> None:
    ahora = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    assert parse_retry_after("Tue, 01 Sep 2026 10:01:00 GMT", now=ahora) == 60.0
    # Una fecha ya pasada no es una espera negativa: es cero.
    assert parse_retry_after("Tue, 01 Sep 2026 09:59:00 GMT", now=ahora) == 0.0


def test_publication_error_es_la_clase_del_rango_900() -> None:
    error = create_error_from_response(body={"code": 951, "message": "Text too long"}, status=400)
    assert isinstance(error, PublicationError)
    assert error.family == "publication"
