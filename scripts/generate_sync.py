"""Genera el gemelo SINCRONO a partir del codigo asincrono.

    uv run python scripts/generate_sync.py

POR QUE EXISTE ESTO, y no un envoltorio (§ Trampa P3 del roadmap). El atajo obvio es escribir solo
el async y envolverlo con `asyncio.run(...)`. No sirve: `asyncio.run` **lanza `RuntimeError` si ya
hay un bucle corriendo**, que es exactamente la situacion de un integrador dentro de FastAPI, dentro
de un notebook o dentro de cualquier framework async — o sea, de la mitad del publico. Y `httpx2`
tiene dos clases separadas, `Client` y `AsyncClient`, que no se sustituyen la una por la otra.

Asi que hay dos implementaciones de verdad y la segunda se GENERA de la primera. Es lo que hacen
`httpcore` y el cliente oficial de Elasticsearch. Reglas de la casa:

- el fichero generado **se commitea**, como los tipos de la libreria de Node, para que instalar el
  paquete no exija generar nada;
- **la CI regenera y hace `git diff --exit-code`**: el gemelo quedandose atras en silencio es el
  unico fallo posible de este montaje, y es invisible desde el lado async;
- el generador se escribe **antes** del primer recurso. Retro-encajar un gemelo generado en 133
  metodos escritos a mano es otra fase entera.

LA SUSTITUCION MAS IMPORTANTE NO ES `await`, ES EL CERROJO. `asyncio.Lock` -> `threading.Lock`: el
cliente sincrono SI se comparte entre hilos (un Django con gunicorn, un `ThreadPoolExecutor`) y alli
un `asyncio.Lock` no protege absolutamente nada. Escrito a mano dos veces, es un despiste posible;
aqui es una linea de una tabla.

COMO SE SABE QUE UNA SUSTITUCION NO SE HA ESCAPADO: no se revisa a ojo. Despues de generar, el
resultado se parsea con `ast` y se recorre entero buscando nodos `async`/`await`. Si queda uno, el
generador se niega a escribir. Es la unica comprobacion que no depende de que la tabla de regex este
completa.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "planvortex"

# Fuente async -> gemelo sincrono, lo que NO sale de recorrer un directorio.
#
# `errors.py`, `query.py`, `transport.py`, `pagination.py` y `files.py` NO estan y no lo estaran: no
# hacen E/S, asi que no tienen nada de async que quitar. Y ademas no PUEDEN estar: sus clases
# —`Page`, `HttpRequest`, `RetryConfig`, `HttpHooks`— cruzan la frontera publica, y generar un
# gemelo las duplicaria en dos tipos distintos con los mismos campos. Un `HttpHooks` construido
# para un cliente seria un error de tipo en el otro.
FIJOS: tuple[tuple[Path, Path], ...] = (
    (PACKAGE / "_core" / "http.py", PACKAGE / "_core" / "http_sync.py"),
    (PACKAGE / "_core" / "auth.py", PACKAGE / "_core" / "auth_sync.py"),
    (PACKAGE / "_client.py", PACKAGE / "_client_sync.py"),
)

# `resources/` entero, fichero a fichero. Se recorre el directorio en vez de escribir la lista
# porque la fase 6 anade ocho recursos mas y una lista escrita a mano es justo lo que se olvida: un
# recurso sin gemelo no rompe nada del lado async, y el cliente sincrono se queda sin ese atributo.
FUENTE_RECURSOS = PACKAGE / "resources"
DESTINO_RECURSOS = PACKAGE / "resources_sync"


def pares() -> tuple[tuple[Path, Path], ...]:
    """Los fijos y un par por cada modulo de `resources/`, en orden estable."""
    recursos = tuple(
        (origen, DESTINO_RECURSOS / origen.name) for origen in sorted(FUENTE_RECURSOS.glob("*.py"))
    )
    return FIJOS + recursos


# La ruta va en su propia linea: con `resources/` los nombres crecieron y la cabecera se pasaba
# de las 110 columnas, dejando un fichero generado que el `ruff format --check` de la CI
# rechazaba y que su propia cabecera prohibe arreglar a mano.
CABECERA = '''"""GENERADO POR `scripts/generate_sync.py`. NO SE EDITA A MANO.

Gemelo sincrono de `{origen}`.

Lo que haya que cambiar se cambia ALLI y se regenera con `uv run python scripts/generate_sync.py`;
la CI regenera y falla si hay diferencias.
"""

'''

# El orden importa: las mas largas primero, para que `async def` no se quede en `def` a medias.
SUSTITUCIONES: tuple[tuple[str, str], ...] = (
    (r"\basync def\b", "def"),
    (r"\basync with\b", "with"),
    (r"\basync for\b", "for"),
    # `await ` con el espacio primero para no dejar dos seguidos donde habia uno.
    (r"\bawait\s+", ""),
    (r"\bAsyncClient\b", "Client"),
    (r"\bAsyncIterator\b", "Iterator"),
    (r"\bAsyncGenerator\b", "Generator"),
    (r"\bAsyncContextManager\b", "ContextManager"),
    (r"\basyncio\.Lock\b", "threading.Lock"),
    (r"\basyncio\.sleep\b", "time.sleep"),
    (r"\basyncio\.gather\b", "_gather_not_available"),
    (r"\b__aenter__\b", "__enter__"),
    (r"\b__aexit__\b", "__exit__"),
    (r"\b__anext__\b", "__next__"),
    (r"\b__aiter__\b", "__iter__"),
    (r"\baclose\b", "close"),
    # SIN limite de palabra al final, a proposito: los iteradores compuestos se llaman
    # `aiterate_children` y `aiterate_organizations`, y ahi no hay frontera despues de
    # `aiterate` — el gemelo se quedaba con el nombre asincrono y `pv.clients.iterate_
    # organizations` no existia en el cliente sincrono.
    (r"\baiterate", "iterate"),
    # Los nombres publicos: `AsyncPlanVortex` -> `PlanVortex`, `AsyncHttpClient` -> `HttpClient`,
    # `AsyncClientCredentialsAuth` -> `ClientCredentialsAuth`... Va el ultimo porque es el mas
    # general y se comeria a los de arriba.
    (r"\bAsync(?=[A-Z])", ""),
    # Los modulos hermanos tambien son gemelos: el sync importa del sync.
    (r"\bplanvortex\._core\.http\b", "planvortex._core.http_sync"),
    (r"\bplanvortex\._core\.auth\b", "planvortex._core.auth_sync"),
    (r"\bplanvortex\.resources\b", "planvortex.resources_sync"),
    # Y el texto en prosa, para que el docstring del gemelo no hable de asincronia.
    (r"\basynchronous\b", "synchronous"),
    (r"\basynchronously\b", "synchronously"),
)

# Modulos de la biblioteca estandar que el gemelo puede necesitar y el original no. Se anaden solo
# si el codigo generado los usa de verdad, para no dejar un import muerto que `ruff` marcaria.
IMPORTS_CONDICIONALES = ("threading", "time")


class GeneracionError(Exception):
    """Algo no se ha podido traducir. El mensaje dice que, y donde."""


def traducir(origen: Path) -> str:
    """El texto del gemelo: sustituciones, arreglo de imports y cabecera de generado."""
    codigo = origen.read_text(encoding="utf8")

    # El docstring del original explica que es la FUENTE del gemelo; en el gemelo sobra, porque
    # arriba va la cabecera de "generado".
    codigo = re.sub(
        r"\n\nTHIS FILE IS THE SOURCE OF ``[a-z_/]+\.py``\..*?(?=\n"
        r'"""|\n\n[A-Z])',
        "",
        codigo,
        flags=re.S,
    )

    for patron, reemplazo in SUSTITUCIONES:
        codigo = re.sub(patron, reemplazo, codigo)

    codigo = _arreglar_imports(codigo)
    relativo = origen.relative_to(ROOT).as_posix()
    return CABECERA.format(origen=relativo) + _sin_docstring_de_modulo(codigo)


def _arreglar_imports(codigo: str) -> str:
    """`import asyncio` fuera, y `threading`/`time` dentro si el resultado los usa.

    Va por USO y no por una tabla fija porque cada fichero necesita cosas distintas: `http.py` usa
    `asyncio.sleep` (que pasa a `time.sleep`) y `auth.py` usa `asyncio.Lock` (que pasa a
    `threading.Lock`). Una tabla global dejaria un import muerto en uno de los dos, y `ruff` lo
    marcaria — con razon.
    """
    codigo = re.sub(r"^import asyncio\n", "", codigo, flags=re.M)
    faltan = [
        modulo
        for modulo in IMPORTS_CONDICIONALES
        if _usa_modulo(codigo, modulo) and not re.search(rf"^import {modulo}$", codigo, flags=re.M)
    ]
    if not faltan:
        return codigo
    # Se cuelan detras del `from __future__`, que tiene que ir el primero. Luego `ruff` los ordena.
    bloque = "".join(f"import {modulo}\n" for modulo in faltan)
    futuro = "from __future__ import annotations\n\n"
    return codigo.replace(futuro, futuro + bloque, 1)


def _usa_modulo(codigo: str, modulo: str) -> bool:
    """Whether the CODE uses ``modulo.algo``, looking at the tree and not at the text.

    A `re.search(r"\\btime\\.")` was enough until a docstring ended a sentence with "this
    time." and the twin came out with an `import time` nobody used — a generated file the CI
    rejects and that its own header forbids fixing. The tree does not read prose.
    """
    arbol = ast.parse(codigo)
    return any(
        isinstance(nodo, ast.Attribute) and isinstance(nodo.value, ast.Name) and nodo.value.id == modulo
        for nodo in ast.walk(arbol)
    )


def _sin_docstring_de_modulo(codigo: str) -> str:
    """Quita el docstring del modulo original: la cabecera de generado ocupa su sitio."""
    arbol = ast.parse(codigo)
    if not arbol.body:
        return codigo
    primero = arbol.body[0]
    if not (isinstance(primero, ast.Expr) and isinstance(primero.value, ast.Constant)):
        return codigo
    if not isinstance(primero.value.value, str):
        return codigo
    lineas = codigo.splitlines(keepends=True)
    fin = primero.end_lineno or 1
    return "".join(lineas[fin:]).lstrip("\n")


def exigir_sin_async(texto: str, destino: Path) -> None:
    """Ni un `async` ni un `await` en el arbol. Es el guardia de verdad de este script.

    Una tabla de regex siempre puede estar incompleta, y una sustitucion que se escapa produce un
    fichero que ni siquiera es sintacticamente valido en el mejor caso — o que lo es y arrastra un
    `await` dentro de un `def` normal en el peor. `ast` no se equivoca en esto.
    """
    try:
        arbol = ast.parse(texto)
    except SyntaxError as error:
        raise GeneracionError(f"{destino.name} no es Python valido tras traducir: {error}") from error

    restos = [
        type(nodo).__name__
        for nodo in ast.walk(arbol)
        if isinstance(nodo, (ast.AsyncFunctionDef, ast.Await, ast.AsyncFor, ast.AsyncWith))
    ]
    if restos:
        raise GeneracionError(
            f"{destino.name} sigue teniendo asincronia despues de traducir: {sorted(set(restos))}. "
            "Falta una entrada en SUSTITUCIONES."
        )


def formatear(destinos: list[Path]) -> None:
    """`ruff` ordena los imports y formatea la salida.

    El generador formatea a proposito: si no, el fichero generado podria fallar el
    `ruff format --check` de la CI y no habria forma de arreglarlo sin editarlo a mano — que es
    justo lo que la cabecera prohibe.
    """
    rutas = [str(ruta) for ruta in destinos]
    for orden in (
        ["ruff", "check", "--fix-only", "--quiet", "--select", "I", *rutas],
        ["ruff", "format", "--quiet", *rutas],
    ):
        resultado = subprocess.run(orden, cwd=ROOT, capture_output=True, text=True, check=False)
        if resultado.returncode != 0:
            raise GeneracionError(f"`{' '.join(orden[:3])}` fallo:\n{resultado.stdout}\n{resultado.stderr}")


def main() -> int:
    """Genera los gemelos y dice cuales han cambiado.

    NO hay modo `--check`, y es a proposito: la CI regenera de verdad y despues hace
    `git diff --exit-code`, que comprueba exactamente lo mismo sin que este script tenga que
    escribir y restaurar ficheros para compararlos.
    """
    try:
        generados: list[tuple[Path, str]] = []
        for origen, destino in pares():
            texto = traducir(origen)
            exigir_sin_async(texto, destino)
            generados.append((destino, texto))

        anteriores = {
            destino: (destino.read_text(encoding="utf8") if destino.exists() else None)
            for destino, _ in generados
        }
        for destino, texto in generados:
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(texto, encoding="utf8", newline="\n")

        # `ruff` es quien decide el texto final, asi que se compara DESPUES de pasar por el: lo que
        # se commitea es su salida, no la del traductor.
        formatear([destino for destino, _ in generados])

        for destino, _ in generados:
            cambiado = anteriores[destino] != destino.read_text(encoding="utf8")
            print(
                f"sync: {destino.relative_to(ROOT).as_posix()} "
                f"({'actualizado' if cambiado else 'sin cambios'})"
            )
    except GeneracionError as fallo:
        print(f"sync: {fallo}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
