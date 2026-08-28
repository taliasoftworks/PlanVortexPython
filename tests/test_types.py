"""Las ayudas para los campos que la API devuelve de DOS formas.

No es una comodidad: es la unica forma de escribir codigo que funcione con las dos respuestas del
servidor sin repetir un `isinstance` en cada sitio. `id_account` llega resuelto en unas operaciones
y como cadena en otras —en publicaciones, las de una sola frente al listado; en comentarios, justo
al reves—, y lo mismo pasa con `id_publication` y con los tres campos de referencia de un mensaje.

Cada prueba se hace con LAS DOS formas, que es lo unico que demuestra que la ayuda sirve: una que
solo se probara con la poblada pasaria igual escribiendo `resource["id_account"]["_id"]` a pelo.
"""

from __future__ import annotations

from typing import Any, TypeGuard, cast, get_type_hints

from planvortex.types import (
    PUBLISHABLE_NETWORKS,
    SOCIAL_NETWORKS,
    Account,
    Comment,
    Message,
    MetaEmbeddedSignupAuthorization,
    Publication,
    PublishableNetwork,
    RedirectAuthorization,
    SocialAuthorizationMethod,
    Upload,
    account,
    account_id,
    is_meta_embedded_signup,
    is_publishable_network,
    is_redirect_authorization,
    message_contact,
    message_contact_id,
    message_direction,
    message_file_ids,
    message_files,
    publication,
    publication_id,
)

CUENTA = cast("Account", {"_id": "acc1", "name": "Panaderia", "social_network": "instagram"})
FICHERO = cast("Upload", {"_id": "up1", "name": "hogaza.jpg", "file_type": "image"})
CONTACTO: dict[str, Any] = {"_id": "con1", "name": "Marta"}


def _publicacion(id_account: Any) -> Publication:
    return cast("Publication", {"_id": "pub1", "id_account": id_account})


def _comentario(**extra: Any) -> Comment:
    return cast("Comment", {"_id": "com1", "id_account": "acc1", **extra})


def _mensaje(**extra: Any) -> Message:
    return cast("Message", {"_id": "msg1", "message_options": {"files": []}, **extra})


# ------------------------------------------------------------------------------ la cuenta


def test_el_id_de_la_cuenta_sale_de_las_dos_formas() -> None:
    """Con la cadena que devuelve el listado y con la cuenta entera que devuelve leer una."""
    assert account_id(_publicacion("acc1")) == "acc1"
    assert account_id(_publicacion(CUENTA)) == "acc1"


def test_la_cuenta_solo_sale_cuando_de_verdad_viene() -> None:
    """`None` y no un diccionario a medias: inventar una cuenta con un solo campo seria peor."""
    assert account(_publicacion("acc1")) is None
    assert account(_publicacion(CUENTA)) == CUENTA


def test_lo_mismo_vale_para_un_comentario() -> None:
    """La asimetria de los comentarios va al reves que la de las publicaciones, y da igual: las dos
    ayudas miran la forma del valor y no de que operacion viene.
    """
    assert account_id(_comentario(id_account=CUENTA)) == "acc1"
    assert account(_comentario(id_account="acc1")) is None


# -------------------------------------------------------------------------- la publicacion


def test_el_id_de_la_publicacion_de_un_comentario_sale_de_las_dos_formas() -> None:
    assert publication_id(_comentario(id_publication="pub1")) == "pub1"
    assert publication_id(_comentario(id_publication=_publicacion("acc1"))) == "pub1"


def test_un_comentario_sin_publicacion_no_es_un_fallo() -> None:
    """Y no es raro: la resena de Google Business cuelga de la FICHA, y un video subido a mano o un
    post anterior a PlanVortex tampoco tienen publicacion nuestra detras.
    """
    assert publication_id(_comentario()) is None
    assert publication(_comentario()) is None


def test_la_publicacion_solo_sale_cuando_viene_poblada() -> None:
    """Solo la bandeja de comentarios la resuelve; todo lo demas manda el identificador."""
    assert publication(_comentario(id_publication="pub1")) is None
    assert publication(_comentario(id_publication=_publicacion("acc1"))) == _publicacion("acc1")


# ------------------------------------------------------------------------------ el mensaje


def test_la_direccion_del_mensaje_se_deduce_de_que_contacto_trae() -> None:
    """No es un campo. `from_contact_id` es el contacto escribiendonos y `contact_id` nosotros a el,
    y el servidor garantiza que viene exactamente uno (1503 si ninguno, 1504 si los dos).
    """
    assert message_direction(_mensaje(from_contact_id="con1")) == "incoming"
    assert message_direction(_mensaje(contact_id="con1")) == "outgoing"
    assert message_direction(_mensaje()) == "unknown"


def test_el_contacto_del_mensaje_es_el_mismo_escriba_quien_escriba() -> None:
    """Para la direccion esta `message_direction`; aqui lo que importa es CON QUIEN se habla."""
    assert message_contact_id(_mensaje(from_contact_id=CONTACTO)) == "con1"
    assert message_contact_id(_mensaje(contact_id="con1")) == "con1"
    assert message_contact_id(_mensaje()) is None


def test_el_contacto_poblado_se_devuelve_entero() -> None:
    assert message_contact(_mensaje(from_contact_id=CONTACTO)) == CONTACTO
    assert message_contact(_mensaje(contact_id="con1")) is None


def test_los_adjuntos_se_separan_en_los_poblados_y_los_identificadores() -> None:
    """El listado y el webhook mandan los ficheros enteros; el resto, sus identificadores. Y una
    misma lista puede traer de los dos, que es lo que hace falso el `if` de una sola comprobacion.
    """
    mensaje = _mensaje(message_options={"files": ["up0", FICHERO]})

    assert message_files(mensaje) == [FICHERO]
    assert message_file_ids(mensaje) == ["up0", "up1"]


def test_un_mensaje_sin_adjuntos_devuelve_listas_vacias_y_no_falla() -> None:
    assert message_files(_mensaje()) == []
    assert message_file_ids(_mensaje()) == []


# --------------------------------------------------------------- como se autoriza cada red

REDIRECT = cast("SocialAuthorizationMethod", {"type": "redirect"})
POPUP = cast(
    "SocialAuthorizationMethod",
    {
        "type": "meta_embedded_signup",
        "app_id": "123",
        "config_id": "456",
        "graph_version": "v23.0",
        "feature_type": "whatsapp_business_app_onboarding",
        "session_info_version": "3",
    },
)


def test_cada_predicado_reconoce_lo_suyo_y_solo_lo_suyo() -> None:
    """Las dos formas, con los dos predicados: es lo unico que demuestra que discriminan.

    Uno que solo se probara con la suya pasaria igual devolviendo `True` siempre.

    Los que niegan van PRIMERO, y no es manía: un `TypeGuard` estrecha la rama positiva, asi que en
    cuanto se afirma `is_redirect_authorization(REDIRECT)` mypy da esa constante por
    `RedirectAuthorization` para el resto de la funcion y pasarsela despues al otro predicado es un
    error de tipos. Que ese error aparezca al reordenarlo es, de hecho, la mejor prueba de que el
    estrechado funciona de verdad y no solo sobre el papel.
    """
    assert not is_meta_embedded_signup(REDIRECT)
    assert not is_redirect_authorization(POPUP)
    assert is_redirect_authorization(REDIRECT)
    assert is_meta_embedded_signup(POPUP)


def test_una_tercera_forma_de_autorizar_no_es_ninguna_de_las_dos() -> None:
    """El caso que hace falta escribir un `else`, y que hoy no existe.

    La lista de redes crece y la de metodos puede crecer con ella. Los dos predicados contestan que
    no, que es la respuesta correcta: quien recorra `connect_links` con un `if/elif` y sin `else` se
    saltaria esa red en silencio en vez de mandar al usuario a una pagina en blanco.
    """
    futura = cast("SocialAuthorizationMethod", {"type": "device_code"})
    assert not is_redirect_authorization(futura)
    assert not is_meta_embedded_signup(futura)


def test_los_predicados_estrechan_y_no_solo_contestan_si_o_no() -> None:
    """Lo que hace util a un predicado aqui es su ANOTACION, no lo que devuelve.

    Devolver `bool` funciona igual en ejecucion y deja el codigo de quien llama sin estrechar: el
    tipo generado es plano y con los cinco campos opcionales, asi que dentro del `if` se seguirian
    leyendo campos que ahi no estan y `mypy --strict` seguiria en verde (§ Trampa P13). Esto fija la
    firma, que es la parte que se pierde sin hacer ruido si alguien "simplifica" el `TypeGuard`.
    """
    assert get_type_hints(is_redirect_authorization)["return"] == TypeGuard[RedirectAuthorization]
    assert get_type_hints(is_meta_embedded_signup)["return"] == TypeGuard[MetaEmbeddedSignupAuthorization]


# =================================================================================================
# La red que publica
# =================================================================================================


def test_la_red_que_publica_se_reconoce_y_google_business_no() -> None:
    """La unica de las diez que no publica, contra una que si.

    Un predicado que contestara `True` siempre pasaria la mitad de esto, asi que hacen falta las
    dos. Y `google_business` no es un caso raro: es una red conectable de pleno derecho que aparece
    en `accounts.list` sin filtro, o sea que quien recorra sus cuentas se la encuentra.
    """
    assert not is_publishable_network("google_business")
    assert is_publishable_network("instagram")


def test_una_red_que_esta_version_no_conoce_no_publica_todavia() -> None:
    """Contesta que no, que es la respuesta segura y no la correcta.

    La lista crece varias veces al ano, asi que este predicado se queda corto entre versiones. Falso
    negativo: quien lo use se salta una red que si publicaria, en vez de mandar un `social_network`
    que el servidor contesta con un 702. Si eso importa, lo que manda es
    `catalog.allowed_social_publications()`, que lo pregunta.
    """
    assert not is_publishable_network("mastodon")


def test_el_predicado_estrecha_y_no_solo_contesta_si_o_no() -> None:
    """Igual que los dos de `authorization`: lo que vale aqui es la ANOTACION.

    Devolver `bool` funciona identico en ejecucion y deja a quien llama exactamente donde estaba —
    con un `str` que no cabe en `PublicationInput["social_network"]`—, que es justo el error que
    este predicado existe para quitar.
    """
    assert get_type_hints(is_publishable_network)["return"] == TypeGuard[PublishableNetwork]


def test_las_que_publican_son_las_de_siempre_menos_una() -> None:
    """Las dos tuplas de runtime, una contra la otra.

    Salen las dos de `get_args` sobre su `Literal`, asi que esto no compara dos listas copiadas: lo
    que fija es la RELACION entre ellas, que es lo que un lector da por hecho al ver los dos nombres
    juntos. Que las dos casen con el spec ya lo mira `tests/test_shapes_parity.py`.
    """
    assert set(PUBLISHABLE_NETWORKS) < set(SOCIAL_NETWORKS)
    assert set(SOCIAL_NETWORKS) - set(PUBLISHABLE_NETWORKS) == {"google_business"}
    assert all(is_publishable_network(red) for red in PUBLISHABLE_NETWORKS)
