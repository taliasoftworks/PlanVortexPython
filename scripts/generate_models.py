"""Genera los TypedDict del paquete a partir del OpenAPI publico (fase 4 del roadmap).

    uv run python scripts/generate_models.py

Son DOS ficheros, los dos commiteados:

  1. `openapi/planvortex.openapi.json` — el documento unido que publica PlanVortexHome en
     `public/openapi.json` (y en https://planvortex.com/openapi.json). Aqui se COPIA, no se
     construye: unir los `swagger/*-swagger.json` es cosa de Home desde la fase 1. Se commitea
     porque el spec vive en OTRO repositorio: sin la copia, la CI de este —que solo clona este— no
     tendria nada de lo que regenerar y el `git diff --exit-code` que vigila los tipos no vigilaria
     nada. Es el mismo montaje que en la libreria de Node, y a proposito: las dos copias y la de
     Home son byte a byte el mismo fichero.
  2. `src/planvortex/_generated/models.py` — `datamodel-code-generator` por encima del anterior. Se
     commitea porque instalar `planvortex` no puede exigir generar nada.

Con PlanVortexHome al lado se rehacen los dos; sin el, se rehace solo el segundo a partir de la
copia commiteada. Para regenerar sin tener Home clonado:

    PLANVORTEX_OPENAPI=https://planvortex.com/openapi.json uv run python scripts/generate_models.py

LA TRAMPA P1 ES REAL Y SALTA A LA PRIMERA. `datamodel-code-generator` SANEA los nombres que no
puede usar como atributo, y la clave primaria de cada recurso de PlanVortex se llama `_id`. Sin
tocar nada, `Publication` sale con un `field_id: str` — un campo que no existe en ninguna respuesta
del servidor — y el `_id` que si viaja desaparece del tipo. Es el fallo que compila y miente: mypy
aprueba `pub["field_id"]`, que revienta en ejecucion, y rechaza `pub["_id"]`, que es lo correcto.

Se arregla con `--special-field-name-prefix ""`: el prefijo que el generador antepone a esos
nombres se deja vacio y `_id` sale tal cual. La sintaxis de clase admite `_id` sin problema —lo
admiten el runtime, mypy y pyright—, asi que no hace falta bajar a la sintaxis funcional que el
roadmap dejaba como plan B. Y no se queda en un flag: `exigir_id_intacto` lo comprueba sobre el
arbol antes de escribir.

Y HAY UNA SEGUNDA TRAMPA, QUE NO SALE HASTA QUE SE INSTALA. Por defecto el generador importa
`NotRequired` de `typing_extensions` SIEMPRE —el suelo del paquete es 3.10— y `TypedDict` de
`typing`. Esa combinacion falla por los dos lados, y ninguno de los dos se ve desarrollando:

- `httpx2` solo arrastra `typing_extensions` en `python_version < '3.13'`, asi que en 3.13 y 3.14
  —dos de las cinco filas de la matriz— un integrador que instale solo `planvortex` no lo tendria y
  el `import planvortex` se caeria con un `ModuleNotFoundError`. Aqui no se nota porque mypy
  instala `typing_extensions` para lo suyo;
- y en 3.10, el `TypedDict` de `typing` **no entiende** el `NotRequired` de `typing_extensions`. No
  falla —eso seria facil—: da todas las claves por obligatorias, asi que `__required_keys__` viene
  con las opcionales dentro y `__optional_keys__` viene vacio. Los comprobadores de tipos aciertan
  (leen la PEP 655 directamente), asi que mypy sigue en verde y solo miente la introspeccion en
  ejecucion. Lo que documenta `typing_extensions`: por debajo de 3.11, `TypedDict` tiene que salir
  de alli **tambien**, no solo `NotRequired`. Coger uno y dejar el otro es justo la mezcla que
  informa mal.

`reescribir_imports` deja los dos detras de la misma guarda de `sys.version_info`. Se hace asi y no
con `--import-overrides` apuntando a un modulo nuestro —que tambien funciona— porque las
herramientas reconocen un `TypedDict` **por el modulo del que viene**: en cuanto deja de venir de
`typing` o de `typing_extensions`, `ruff` deja de saber que estas clases son TypedDict y empieza a
exigir `snake_case` en campos que son nombres de la API (`metaElements`, `groupValue`).
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "openapi" / "planvortex.openapi.json"
MODELS = ROOT / "src" / "planvortex" / "_generated" / "models.py"

# Los repositorios viven uno al lado del otro. `PLANVORTEX_OPENAPI` acepta una ruta o una URL.
DEFAULT_OPENAPI = ROOT.parent.parent / "PlanVortexHome" / "public" / "openapi.json"

# Lo mismo, publicado. Sirve para regenerar sin tener PlanVortexHome clonado al lado.
PUBLISHED_OPENAPI = "https://planvortex.com/openapi.json"

CABECERA = '''"""GENERADO POR `scripts/generate_models.py`. NO SE EDITA A MANO.

Sale de `openapi/planvortex.openapi.json`, que a su vez sale de los `swagger/*-swagger.json` de
PlanVortexHome. Si algo de aqui no cuadra con la API, lo que hay que arreglar es el spec.

Estos tipos son un DETALLE INTERNO: los nombres van prefijados por dominio para que el `Plan` de un
cliente y el de una organizacion no se pisen, y los objetos declarados en linea reciben el nombre
que el generador se inventa. La superficie publica del paquete son los tipos con nombre legible de
`planvortex/types.py`, que se construyen encima de estos.
"""

'''

# Lo que el generador emite, y lo que tiene que quedar en su lugar. Los DOS nombres detras de la
# misma guarda: coger `NotRequired` de `typing_extensions` y `TypedDict` de `typing` es la mezcla
# que en 3.10 da todas las claves por obligatorias sin avisar de nada.
IMPORT_GENERADO = "from typing_extensions import NotRequired\n"
IMPORT_CON_GUARDA = """if sys.version_info >= (3, 11):
    from typing import NotRequired, TypedDict
else:  # pragma: no cover - la rama la elige el interprete, no un test
    from typing_extensions import NotRequired, TypedDict
"""

# Las opciones no son negociables de una en una: cada una tapa un fallo concreto y estan explicadas
# aqui al lado.
OPCIONES: tuple[str, ...] = (
    "--input-file-type",
    "openapi",
    "--output-model-type",
    "typing.TypedDict",
    # El SUELO del paquete, no el interprete que ejecute esto: con 3.11+ saldria `NotRequired` de
    # `typing` y el fichero commiteado dependeria de con que maquina se genero.
    "--target-python-version",
    "3.10",
    # § Trampa P1. Sin esto, `_id` sale como `field_id`.
    "--special-field-name-prefix",
    "",
    # Lo que vigila la CI es que el diff este vacio, y una marca de tiempo lo mueve en cada
    # ejecucion: el guardia se volveria ruido y se acabaria desactivando.
    "--disable-timestamp",
    # Sin dependencias de formateo (ni black ni isort): el texto final lo decide `ruff`, que es la
    # unica autoridad de formato del repositorio. Ver `formatear`.
    "--formatters",
    "builtin",
    "--use-double-quotes",
    # Los nombres limpios se reservan para lo declarado en `components/schemas`, y el sufijo se lo
    # llevan los objetos en linea. Importa mas de lo que parece: `types.py` mapea `Publication` al
    # `Publication` publico, asi que un objeto anonimo quedandose con ese nombre seria otro fallo
    # que compila y miente.
    "--naming-strategy",
    "primary-first",
    # SIN `from __future__ import annotations`, y esto no es cosmetico. Con el, las anotaciones se
    # quedan en CADENAS, y `TypedDict` no puede leer un `NotRequired` que es texto: da todas las
    # claves por obligatorias, asi que `Publication.__optional_keys__` sale vacio en todas las
    # versiones. Los comprobadores de tipos aciertan igual y solo miente la introspeccion en
    # ejecucion — el mismo fallo silencioso que la guarda de version, por otra causa.
    #
    # Quitarlo es seguro porque el suelo del paquete es 3.10: `str | Account` y `list[Upload]` se
    # evaluan alli sin problema, y las referencias hacia adelante (`cover_image` es otro `Upload`)
    # el generador ya las emite entrecomilladas.
    "--disable-future-imports",
    # Las descripciones del spec —auditadas campo a campo en la fase 6 de Node— viajan al fichero
    # como docstrings y de ahi al editor del integrador. Es lo que hace que el aviso de que
    # `id_account` cambia de forma este donde se lee, y no solo en la documentacion.
    "--use-schema-description",
    "--use-field-description",
)


class GeneracionError(Exception):
    """Algo no se ha podido generar. El mensaje dice que, y que hacer."""


# ------------------------------------------------------------------------------------ el bundle


def origen_del_bundle() -> str:
    return os.environ.get("PLANVORTEX_OPENAPI") or str(DEFAULT_OPENAPI)


def es_remoto(origen: str) -> bool:
    return origen.startswith(("http://", "https://"))


def leer_upstream(origen: str) -> str | None:
    """El documento tal cual lo publica Home, en TEXTO. `None` es "no esta", no "esta vacio".

    Se devuelve sin parsear a proposito: lo commiteado aqui tiene que ser byte a byte lo que hay
    alli, y un `json.loads` + `json.dumps` por el medio es justo la forma de que dejen de serlo sin
    que nadie lo note.
    """
    if not es_remoto(origen):
        ruta = Path(origen)
        return ruta.read_text(encoding="utf8") if ruta.exists() else None

    # La URL la elige quien ejecuta el script (`PLANVORTEX_OPENAPI`), no llega de fuera.
    with urllib.request.urlopen(origen) as respuesta:
        if respuesta.status != 200:
            raise GeneracionError(f"{origen} respondio {respuesta.status}")
        crudo = respuesta.read()
    assert isinstance(crudo, bytes)
    return crudo.decode("utf8")


def refrescar_bundle() -> None:
    """Trae el documento de Home si esta a mano; si no, avisa y sigue con la copia commiteada."""
    origen = origen_del_bundle()
    upstream = leer_upstream(origen)

    if upstream is not None:
        BUNDLE.parent.mkdir(parents=True, exist_ok=True)
        # `newline=""` para no traducir los saltos de linea en Windows: la copia tiene que ser byte
        # a byte la de Home, y el `.gitattributes` del repositorio ya la marca como `-text`.
        BUNDLE.write_text(upstream, encoding="utf8", newline="")
        print(f"openapi: {_operaciones(json.loads(upstream))} operaciones desde {origen}")
        return

    if not BUNDLE.exists():
        raise GeneracionError(f"No encuentro ni el documento ({origen}) ni la copia ({BUNDLE}).")

    # Sin un aviso bien visible, un checkout suelto regeneraria contra una copia vieja y diria que
    # todo esta en orden.
    print(f"openapi: no encuentro el documento en {origen}.", file=sys.stderr)
    print(
        "openapi: uso la copia commiteada. Clona PlanVortexHome al lado, apunta PLANVORTEX_OPENAPI "
        f"a su public/openapi.json, o usa {PUBLISHED_OPENAPI}.",
        file=sys.stderr,
    )


def _operaciones(spec: dict[str, Any]) -> int:
    metodos = {"get", "put", "post", "delete", "patch", "head", "options", "trace"}
    return sum(len(metodos & set(item)) for item in spec.get("paths", {}).values())


# ----------------------------------------------------------------------------------- los modelos


def generar(destino: Path) -> None:
    """`datamodel-codegen` sobre la copia commiteada, con las opciones de `OPCIONES`.

    Se invoca con `-m` y el interprete actual, y no con el ejecutable `datamodel-codegen` del PATH:
    asi lo que genera es la version que fija `uv.lock` y no la que alguien tenga instalada suelta.
    """
    orden = [
        sys.executable,
        "-m",
        "datamodel_code_generator",
        "--input",
        str(BUNDLE),
        *OPCIONES,
        "--output",
        str(destino),
    ]
    resultado = subprocess.run(orden, cwd=ROOT, capture_output=True, text=True, check=False)
    if resultado.returncode != 0:
        raise GeneracionError(f"`datamodel-codegen` fallo:\n{resultado.stdout}\n{resultado.stderr}")


def retocar(texto: str) -> str:
    """Nuestra cabecera y la guarda de version. Lo demas sale del generador tal cual."""
    lineas = texto.splitlines(keepends=True)
    # El generador deja dos lineas de comentario (`# generated by datamodel-codegen:` y el fichero
    # de entrada). Se quitan porque arriba va nuestra cabecera, que dice ademas que hacer.
    while lineas and lineas[0].startswith("#"):
        lineas.pop(0)
    return CABECERA + reescribir_imports("".join(lineas).lstrip("\n"))


def reescribir_imports(cuerpo: str) -> str:
    """`TypedDict` y `NotRequired`, los dos detras de la misma guarda de `sys.version_info`.

    El porque esta en el docstring del modulo; lo que hay que saber al leer esto es que el
    generador emite `TypedDict` desde `typing` y `NotRequired` desde `typing_extensions`, y que esa
    combinacion es incorrecta en las dos puntas de la matriz.
    """
    if IMPORT_GENERADO not in cuerpo:
        raise GeneracionError(
            f"No encuentro `{IMPORT_GENERADO.strip()}` en la salida. Si el generador ha cambiado "
            "de donde importa, hay que rehacer la guarda de version — y comprobarlo en 3.10 (donde "
            "`NotRequired` no esta en `typing`) y en 3.13 (donde `typing_extensions` no se "
            f"instala). Lo generado empieza asi:\n{cuerpo[:400]}"
        )

    # `TypedDict` sale de la lista de `typing`: se lo lleva la guarda. `Any`, `Literal` y
    # `TypeAlias` se quedan, que estan en `typing` desde 3.10.
    def _sin_typeddict(coincidencia: re.Match[str]) -> str:
        nombres = [nombre.strip() for nombre in coincidencia.group(1).split(",")]
        if "TypedDict" not in nombres:
            raise GeneracionError(f"`{coincidencia.group(0)}` no trae `TypedDict`; la guarda sobra.")
        resto = [nombre for nombre in nombres if nombre != "TypedDict"]
        return f"from typing import {', '.join(resto)}\n" if resto else ""

    cuerpo, sustituciones = re.subn(
        r"^from typing import (.+)\n", _sin_typeddict, cuerpo, count=1, flags=re.M
    )
    if sustituciones != 1:
        raise GeneracionError("No encuentro el `from typing import ...` del fichero generado.")

    cuerpo = cuerpo.replace(IMPORT_GENERADO, IMPORT_CON_GUARDA, 1)
    # `sys` lo necesita la guarda y el generador no lo importa. Va delante de todo; luego `ruff` lo
    # coloca donde le toca.
    return "import sys\n" + cuerpo


def exigir_id_intacto(texto: str) -> None:
    """§ Trampa P1: `_id` esta y `field_id` no. El guardia de verdad de este script.

    Una opcion del generador siempre puede cambiar de nombre o de comportamiento en una version
    nueva, y el fallo que produce es invisible: un `field_id: str` en el tipo se ve perfectamente
    razonable, y lo que hace es que mypy apruebe una clave que no existe y rechace la que si.

    Lo mismo que en `generate_sync.py`: se recorre el arbol, no el texto.
    """
    try:
        arbol = ast.parse(texto)
    except SyntaxError as error:
        raise GeneracionError(f"La salida no es Python valido: {error}") from error

    claves: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ClassDef):
            claves.update(
                campo.target.id
                for campo in nodo.body
                if isinstance(campo, ast.AnnAssign) and isinstance(campo.target, ast.Name)
            )

    saneadas = sorted(clave for clave in claves if clave.startswith("field_"))
    if saneadas:
        raise GeneracionError(
            f"El generador ha saneado nombres de campo: {saneadas}. Es la § Trampa P1: la clave "
            "primaria de la API se llama `_id` y un `field_id` en el tipo es un campo que no "
            "existe en ninguna respuesta. Comprueba `--special-field-name-prefix`."
        )
    if "_id" not in claves:
        raise GeneracionError(
            "En la salida no hay un solo `_id`, y la clave primaria de todos los recursos de "
            "PlanVortex se llama asi. O el spec ha cambiado, o el generador ha vuelto a sanear."
        )


def formatear(destino: Path) -> None:
    """`ruff` ordena los imports y formatea la salida.

    Se formatea a proposito, igual que en `generate_sync.py`: si no, el fichero generado podria
    fallar el `ruff format --check` de la CI y no habria forma de arreglarlo sin editarlo a mano,
    que es justo lo que su cabecera prohibe.
    """
    for orden in (
        ["ruff", "check", "--fix-only", "--quiet", "--select", "I", str(destino)],
        ["ruff", "format", "--quiet", str(destino)],
    ):
        resultado = subprocess.run(orden, cwd=ROOT, capture_output=True, text=True, check=False)
        if resultado.returncode != 0:
            raise GeneracionError(f"`{' '.join(orden[:2])}` fallo:\n{resultado.stdout}\n{resultado.stderr}")


def main() -> int:
    """Refresca el bundle, genera los modelos y dice si han cambiado.

    NO hay modo `--check`, por lo mismo que en `generate_sync.py`: la CI regenera de verdad y
    despues hace `git diff --exit-code`, que comprueba exactamente lo mismo.
    """
    try:
        refrescar_bundle()

        MODELS.parent.mkdir(parents=True, exist_ok=True)
        anterior = MODELS.read_text(encoding="utf8") if MODELS.exists() else None

        # Se genera a un lado y se retoca antes de tocar el fichero bueno: si algo falla, lo
        # commiteado sigue siendo valido en vez de quedarse a medias.
        crudo = MODELS.with_name("models.generated.tmp")
        try:
            generar(crudo)
            texto = retocar(crudo.read_text(encoding="utf8"))
        finally:
            crudo.unlink(missing_ok=True)

        exigir_id_intacto(texto)
        MODELS.write_text(texto, encoding="utf8", newline="\n")

        # `ruff` es quien decide el texto final, asi que se compara DESPUES de pasar por el.
        formatear(MODELS)

        cambiado = anterior != MODELS.read_text(encoding="utf8")
        print(
            f"models: {MODELS.relative_to(ROOT).as_posix()} ({'actualizado' if cambiado else 'sin cambios'})"
        )
    except GeneracionError as fallo:
        print(f"models: {fallo}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
