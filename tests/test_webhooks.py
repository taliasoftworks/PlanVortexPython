"""Los webhooks: la firma sobre el cuerpo CRUDO, el array, y los tipos contra el spec (capa 1).

EL TEST QUE JUSTIFICA EL FICHERO es `test_reserializar_el_cuerpo_rompe_la_firma`, y es el que pide
la fase 7 del roadmap: firma un cuerpo, lo verifica, y falla con el MISMO cuerpo pasado por
`json.dumps`. Es el error que comete todo el mundo —el framework ya parseo el JSON, se vuelve a
serializar, y los bytes no son los mismos— y no da ningun sintoma: la firma simplemente no cuadra
nunca y no hay nada en el mensaje que diga por que.

La segunda mitad es paridad contra el bundle del OpenAPI, por lo mismo que `test_shapes_parity.py`:
los cinco `TypedDict` de `webhooks.py` estan escritos a mano —el generador emite `CommentsWebhookChange`
de una pieza y aqui hace falta partido por `field`, que es lo unico que permite estrechar— asi que no
los vigila ningun `git diff --exit-code`. Se comparan campo a campo y en las DOS direcciones.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, cast, get_args

import pytest

from planvortex import PlanVortexConfigError, PlanVortexError
from planvortex.webhooks import (
    WEBHOOK_EVENTS,
    WEBHOOK_SIGNATURE_HEADERS,
    AccountStateChange,
    CommentChange,
    IntegrationErrorChange,
    MessageChange,
    UnknownWebhookChange,
    WebhookBodyError,
    WebhookChange,
    WebhookSignatureError,
    handle_webhook_request,
    is_account_state_change,
    is_comment_change,
    is_integration_error_change,
    is_message_change,
    parse_webhook_body,
    verify_webhook_signature,
)

SECRETO = "cl13nt-s3cr3t"

# El cuerpo tal y como sale del servidor: `JSON.stringify` de Node, sin un solo espacio. Se guarda en
# BYTES a proposito, porque es lo unico que se firma.
CAMBIOS: list[dict[str, Any]] = [
    {
        "field": "comments",
        "id_account": "66b0f4a1c2d3e4f5a6b7c8d1",
        "id_organization": "66b0f4a1c2d3e4f5a6b7c8d0",
        "social_network": "instagram",
        "commentObj": {"_id": "com1", "external_id": "17900", "text": "que pinta"},
    },
    {
        "field": "integration_error",
        "id_integration": "66b0f4a1c2d3e4f5a6b7c8d9",
        "id_organization": "66b0f4a1c2d3e4f5a6b7c8d0",
        "provider": "google_drive",
        "error_code": 2201,
    },
]
CRUDO = json.dumps(CAMBIOS, separators=(",", ":")).encode("utf8")


def _firmar(cuerpo: bytes, algoritmo: str = "sha256", secreto: str = SECRETO) -> str:
    digest = hashlib.sha256 if algoritmo == "sha256" else hashlib.sha1
    return f"{algoritmo}=" + hmac.new(secreto.encode("utf8"), cuerpo, digest).hexdigest()


# ============================================================================== la firma


def test_una_entrega_de_verdad_se_verifica() -> None:
    assert verify_webhook_signature(CRUDO, _firmar(CRUDO), SECRETO)


def test_reserializar_el_cuerpo_rompe_la_firma() -> None:
    """EL TEST DE LA FASE 7. Mismo objeto, mismos campos, otros bytes.

    `json.dumps` de Python mete un espacio detras de cada coma y de cada dos puntos, y con eso basta.
    Pero el fallo no depende de los espacios: aunque se replicaran los separadores de `JSON.stringify`
    el orden de las claves no tiene por que coincidir, y por eso no hay forma honesta de recuperar los
    bytes originales a partir del objeto parseado.
    """
    firma = _firmar(CRUDO)
    reserializado = json.dumps(json.loads(CRUDO)).encode("utf8")

    assert reserializado != CRUDO
    assert json.loads(reserializado) == json.loads(CRUDO)
    assert verify_webhook_signature(CRUDO, firma, SECRETO)
    assert not verify_webhook_signature(reserializado, firma, SECRETO)


def test_el_cuerpo_ya_parseado_no_es_un_false_sino_una_excepcion() -> None:
    """Y el mensaje trae la linea de cada framework, que es lo unico que arregla esto."""
    with pytest.raises(WebhookBodyError) as fallo:
        verify_webhook_signature(cast("Any", CAMBIOS), _firmar(CRUDO), SECRETO)

    assert "request.get_data()" in str(fallo.value)
    assert "await request.body()" in str(fallo.value)
    assert "request.body" in str(fallo.value)


def test_los_cuatro_tipos_de_cuerpo_crudo_valen_igual() -> None:
    firma = _firmar(CRUDO)
    texto = CRUDO.decode("utf8")

    assert verify_webhook_signature(texto, firma, SECRETO)
    assert verify_webhook_signature(bytearray(CRUDO), firma, SECRETO)
    assert verify_webhook_signature(memoryview(CRUDO), firma, SECRETO)


def test_el_secreto_equivocado_no_cuadra() -> None:
    assert not verify_webhook_signature(CRUDO, _firmar(CRUDO, secreto="otro"), SECRETO)


def test_el_secreto_en_bytes_vale_igual() -> None:
    assert verify_webhook_signature(CRUDO, _firmar(CRUDO), SECRETO.encode("utf8"))


def test_sin_secreto_es_un_fallo_de_configuracion_y_no_un_false() -> None:
    """Es un bug de quien llama, no de quien le llama a el: un `False` lo esconderia hasta produccion."""
    with pytest.raises(PlanVortexConfigError, match="client_secret"):
        verify_webhook_signature(CRUDO, _firmar(CRUDO), "")


@pytest.mark.parametrize(
    "firma",
    [
        pytest.param(None, id="ninguna"),
        pytest.param("", id="vacia"),
        pytest.param("sha256=", id="solo-el-prefijo"),
        pytest.param("sha256=abc", id="recortada"),
        pytest.param("sha256=" + "z" * 64, id="no-es-hex"),
        pytest.param("sha256=" + "ñ" * 64, id="ni-siquiera-es-ascii"),
    ],
)
def test_una_firma_mal_formada_es_false_y_nunca_una_excepcion(firma: str | None) -> None:
    """Esto es lo que manda quien esta probando tu endpoint a mano. Un `raise` aqui seria un 500 tuyo.

    El caso de la longitud recortada y el del no-ASCII son los dos que en otras librerias revientan:
    `timingSafeEqual` en Node lanza con longitudes distintas, y `compare_digest` en Python lanza un
    `TypeError` con una cadena que no es ASCII.
    """
    assert verify_webhook_signature(CRUDO, firma, SECRETO) is False


def test_el_hex_pelado_sin_prefijo_tambien_vale() -> None:
    pelada = _firmar(CRUDO).split("=", 1)[1]

    assert verify_webhook_signature(CRUDO, pelada, SECRETO)


def test_el_prefijo_de_otro_algoritmo_no_cuela() -> None:
    """Un sha1 comparado contra el sha256 esperado no cuadraria nunca; lo que hay que ver es que la
    cabecera que se esta leyendo es la que no es.
    """
    assert not verify_webhook_signature(CRUDO, _firmar(CRUDO, "sha1"), SECRETO)
    assert verify_webhook_signature(CRUDO, _firmar(CRUDO, "sha1"), SECRETO, algorithm="sha1")


def test_la_cabecera_de_sha1_sigue_valiendo() -> None:
    """Esta por compatibilidad con quien ya integraba webhooks al estilo de Meta."""
    assert WEBHOOK_SIGNATURE_HEADERS == {"sha1": "x-hub-signature", "sha256": "x-hub-signature-256"}
    assert verify_webhook_signature(CRUDO, _firmar(CRUDO, "sha1"), SECRETO, algorithm="sha1")


# ============================================================================== el cuerpo


def test_el_cuerpo_es_un_array() -> None:
    cambios = parse_webhook_body(CRUDO)

    assert [cambio["field"] for cambio in cambios] == ["comments", "integration_error"]


def test_un_objeto_en_vez_de_un_array_lo_dice() -> None:
    """El error natural —tratar el cuerpo como un objeto— no da sintoma hasta que se lee un campo."""
    with pytest.raises(WebhookBodyError, match="ARRAY"):
        parse_webhook_body(json.dumps(CAMBIOS[0]).encode("utf8"))


def test_un_null_tambien_lo_dice_por_su_nombre() -> None:
    with pytest.raises(WebhookBodyError, match="null"):
        parse_webhook_body(b"null")


def test_lo_que_no_es_json_lo_dice() -> None:
    with pytest.raises(WebhookBodyError, match="not valid JSON"):
        parse_webhook_body(b"<html>502 Bad Gateway</html>")


def test_un_cambio_sin_field_no_viene_de_planvortex() -> None:
    """Todo cambio lleva `field`: sin el, el `switch` del integrador se queda sin discriminante."""
    with pytest.raises(WebhookBodyError, match="`field`"):
        parse_webhook_body(json.dumps([{"id_account": "a"}]).encode("utf8"))

    with pytest.raises(WebhookBodyError, match="Change 1"):
        parse_webhook_body(json.dumps([CAMBIOS[0], "comments"]).encode("utf8"))


# ============================================================================== el camino completo


def test_la_entrega_entera_con_las_cabeceras_del_framework() -> None:
    cambios = handle_webhook_request(
        CRUDO,
        {"x-hub-signature-256": _firmar(CRUDO), "content-type": "application/json"},
        SECRETO,
    )

    assert len(cambios) == 2


@pytest.mark.parametrize(
    "clave",
    [
        pytest.param("x-hub-signature-256", id="minusculas"),
        pytest.param("X-Hub-Signature-256", id="como-la-manda-el-servidor"),
        pytest.param("HTTP_X_HUB_SIGNATURE_256", id="el-request.META-de-django"),
    ],
)
def test_la_cabecera_se_encuentra_escriba_quien_la_escriba(clave: str) -> None:
    """Los cuatro frameworks dan mapas insensibles a mayusculas; un `dict` pelado, no."""
    assert handle_webhook_request(CRUDO, {clave: _firmar(CRUDO)}, SECRETO)


def test_sin_cabecera_de_firma_es_401_y_no_400() -> None:
    with pytest.raises(WebhookSignatureError, match="x-hub-signature"):
        handle_webhook_request(CRUDO, {"content-type": "application/json"}, SECRETO)


def test_una_firma_que_no_cuadra_dice_las_dos_causas_de_siempre() -> None:
    with pytest.raises(WebhookSignatureError) as fallo:
        handle_webhook_request(CRUDO, {"x-hub-signature-256": _firmar(b"otro cuerpo")}, SECRETO)

    assert "raw" in str(fallo.value)
    assert "secret" in str(fallo.value)


def test_si_solo_viene_la_de_sha1_se_usa_esa() -> None:
    """La entrega real trae las dos, pero un proxy que filtre cabeceras puede dejar una sola."""
    assert handle_webhook_request(CRUDO, {"x-hub-signature": _firmar(CRUDO, "sha1")}, SECRETO)


def test_forzar_el_algoritmo_ignora_la_otra_cabecera() -> None:
    cabeceras = {"x-hub-signature-256": _firmar(CRUDO), "x-hub-signature": "sha1=roto"}

    with pytest.raises(WebhookSignatureError):
        handle_webhook_request(CRUDO, cabeceras, SECRETO, algorithm="sha1")


def test_los_dos_errores_son_planvortexerror_de_familia_webhook() -> None:
    """Un solo `except PlanVortexError` coge todo lo que levanta el paquete."""
    for fallo in (WebhookSignatureError("x"), WebhookBodyError("y")):
        assert isinstance(fallo, PlanVortexError)
        assert fallo.family == "webhook"
        assert fallo.code == 0


def test_una_cabecera_repetida_toma_el_primer_valor() -> None:
    """Algunos servidores entregan las cabeceras como listas."""
    cabeceras = {"x-hub-signature-256": [_firmar(CRUDO), "sha256=otra"]}

    assert handle_webhook_request(CRUDO, cast("Any", cabeceras), SECRETO)


class _SoloGet:
    """Unas cabeceras que solo saben `get`: lo minimo que declara el protocolo `WebhookHeaders`.

    Existe para probar que ese minimo BASTA. Si un dia `_leer_cabecera` empezara a exigir `items()`,
    el protocolo estaria mintiendo y esto es lo unico que se daria cuenta.
    """

    def __init__(self, valores: dict[str, str]) -> None:
        self._valores = valores

    def get(self, key: str) -> Any:
        return self._valores.get(key)


def test_unas_cabeceras_que_solo_saben_get_valen_igual() -> None:
    assert handle_webhook_request(CRUDO, _SoloGet({"x-hub-signature-256": _firmar(CRUDO)}), SECRETO)


def test_y_si_encima_no_se_dejan_recorrer_lo_dice_en_vez_de_reventar() -> None:
    """Sin `items()` no hay busqueda insensible a mayusculas que valga: se responde que no vino.

    Y se queja de la cabecera de sha1, que es la que se elige cuando la de sha256 no aparece: sin
    encontrarla no hay forma de saber si es que el proxy la filtro o es que nunca vino.
    """
    cabeceras = _SoloGet({"X_HUB_SIGNATURE_256": _firmar(CRUDO)})

    with pytest.raises(WebhookSignatureError, match="x-hub-signature") as fallo:
        handle_webhook_request(CRUDO, cabeceras, SECRETO)

    assert "x-hub-signature-256" not in str(fallo.value)


def test_la_misma_cabecera_escrita_dos_veces_no_para_el_recorrido() -> None:
    """Un WSGI crudo puede dejar la clave repetida en dos formas, y una de ellas sin valor."""
    cabeceras = {"HTTP_X_HUB_SIGNATURE_256": [], "Http-X-Hub-Signature-256": _firmar(CRUDO)}

    assert handle_webhook_request(CRUDO, cast("Any", cabeceras), SECRETO)


# ============================================================================== los predicados


def _cambio(field: str, **extra: Any) -> WebhookChange:
    base = {"id_account": "a", "id_organization": "o", "social_network": "instagram"}
    return cast("WebhookChange", {"field": field, **base, **extra})


@pytest.mark.parametrize(
    ("field", "predicado"),
    [
        ("new_account", is_account_state_change),
        ("change_state_account", is_account_state_change),
        ("messages", is_message_change),
        ("messaging_postbacks", is_message_change),
        ("messaging_seen", is_message_change),
        ("messaging_error", is_message_change),
        ("comments", is_comment_change),
        ("integration_error", is_integration_error_change),
    ],
)
def test_cada_evento_lo_reconoce_su_predicado_y_solo_el_suyo(field: str, predicado: Any) -> None:
    cambio = _cambio(field)
    todos = (is_account_state_change, is_message_change, is_comment_change, is_integration_error_change)

    assert predicado(cambio)
    assert [otro for otro in todos if otro(cambio)] == [predicado]


def test_un_evento_desconocido_no_lo_reconoce_nadie_y_no_rompe() -> None:
    """La lista del servidor crece: un `field` nuevo tiene que caer en la rama por defecto."""
    nuevo = _cambio("live_comments")

    assert not is_account_state_change(nuevo)
    assert not is_message_change(nuevo)
    assert not is_comment_change(nuevo)
    assert not is_integration_error_change(nuevo)
    assert nuevo["field"] == "live_comments"


def test_el_comentario_no_viaja_nunca_en_messageobj() -> None:
    """Un comentario no es un mensaje: no tiene contacto y cuelga de una publicacion."""
    assert "messageObj" not in CommentChange.__optional_keys__
    assert "commentObj" not in MessageChange.__optional_keys__
    assert "id_contact" not in CommentChange.__optional_keys__


def test_el_error_de_integracion_no_cuelga_de_ninguna_cuenta() -> None:
    claves = IntegrationErrorChange.__required_keys__ | IntegrationErrorChange.__optional_keys__

    assert "id_account" not in claves
    assert "social_network" not in claves


# ======================================================== § Trampa P13: la introspeccion en verde

TIPOS = (AccountStateChange, MessageChange, CommentChange, IntegrationErrorChange, UnknownWebhookChange)


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: cast("str", tipo.__name__))
def test_el_field_es_obligatorio_y_lo_opcional_sigue_siendo_opcional(tipo: Any) -> None:
    """La § Trampa P13 leida desde fuera: si alguien anade un `from __future__ import annotations`
    al principio de `webhooks.py`, o mezcla `TypedDict` y `NotRequired` de dos sitios, TODAS las
    claves salen obligatorias aqui y mypy no dice ni una palabra.
    """
    assert "field" in tipo.__required_keys__


def test_lo_que_puede_faltar_de_verdad_esta_declarado_opcional() -> None:
    assert "originalChange" in AccountStateChange.__optional_keys__
    assert MessageChange.__optional_keys__ >= {"messageObj", "id_contact", "originalChange"}
    assert CommentChange.__optional_keys__ >= {"commentObj", "originalChange"}
    assert IntegrationErrorChange.__optional_keys__ == frozenset()


# ============================================================== paridad contra el OpenAPI

OPENAPI = Path(__file__).resolve().parent.parent / "openapi" / "planvortex.openapi.json"
SPEC: dict[str, Any] = json.loads(OPENAPI.read_text(encoding="utf8"))
ESQUEMAS: dict[str, Any] = SPEC["components"]["schemas"]
CUENTA_SPEC: dict[str, Any] = ESQUEMAS["CommentsWebhookChange"]
INTEGRACION_SPEC: dict[str, Any] = ESQUEMAS["CommentsIntegrationWebhookChange"]


def _claves(tipo: Any) -> frozenset[str]:
    return cast("frozenset[str]", tipo.__required_keys__ | tipo.__optional_keys__)


def test_la_lista_de_eventos_es_la_del_spec_en_las_dos_direcciones() -> None:
    """La tupla escrita a mano contra las dos enumeraciones del bundle. Si el servidor anade un
    evento y el spec lo documenta, esto se pone rojo y hay que decidir si se tipa.
    """
    del_spec = tuple(CUENTA_SPEC["properties"]["field"]["enum"]) + tuple(
        INTEGRACION_SPEC["properties"]["field"]["enum"]
    )

    assert set(WEBHOOK_EVENTS) == set(del_spec)
    assert len(WEBHOOK_EVENTS) == len(del_spec), "hay un evento repetido en la tupla"


def test_los_tres_tipos_de_cuenta_cubren_el_esquema_del_spec() -> None:
    """`CommentsWebhookChange` se parte aqui en tres por `field` —que es lo unico que deja
    estrechar—, asi que la union de sus claves tiene que ser exactamente la del spec.
    """
    partido = _claves(AccountStateChange) | _claves(MessageChange) | _claves(CommentChange)

    assert partido == set(CUENTA_SPEC["properties"])


def test_el_error_de_integracion_es_el_esquema_del_spec() -> None:
    assert _claves(IntegrationErrorChange) == set(INTEGRACION_SPEC["properties"])
    assert IntegrationErrorChange.__required_keys__ == set(INTEGRACION_SPEC["required"])


@pytest.mark.parametrize(
    "tipo",
    [AccountStateChange, MessageChange, CommentChange],
    ids=lambda tipo: cast("str", tipo.__name__),
)
def test_lo_que_el_spec_declara_obligatorio_lo_es_en_los_tres(tipo: Any) -> None:
    assert set(CUENTA_SPEC["required"]) <= set(tipo.__required_keys__)


def test_cada_field_del_spec_cae_en_uno_de_los_tres_tipos() -> None:
    """El reparto por `field`: ni un evento sin tipo, ni un tipo con un `field` que el spec no
    declara — que es como se colaria un evento inventado con toda la pinta de ser real.
    """
    repartidos: list[str] = []
    for tipo in (AccountStateChange, MessageChange, CommentChange):
        repartidos.extend(get_args(tipo.__annotations__["field"]))

    assert sorted(repartidos) == sorted(CUENTA_SPEC["properties"]["field"]["enum"])


def test_el_spec_sigue_documentando_la_entrega_como_un_array() -> None:
    """Si esto cambiara, `parse_webhook_body` estaria rechazando la forma buena."""
    cuerpo = SPEC["webhooks"]["comments"]["post"]["requestBody"]["content"]["application/json"]

    assert isinstance(cuerpo["example"], list)
    assert cuerpo["schema"]["type"] == "array"
