"""Cuantas rutas del alcance tienen ya metodo en `resources/`, y cuales no (fase 6 del roadmap).

    uv run python scripts/route_coverage.py

QUE PREGUNTA CONTESTA: la libreria cubre la API publica ENTERA menos roles, y esa afirmacion no la
puede sostener nadie leyendo. Son 112 operaciones repartidas en catorce recursos, y la unica forma
de que "no falta ninguna" siga siendo verdad dentro de un ano es que lo compruebe una maquina.

COMO SE SABE QUE UNA RUTA ESTA CUBIERTA: no hay ninguna tabla escrita a mano. El script parsea
`src/planvortex/resources/*.py` con `ast` y RECONSTRUYE las rutas que cada modulo construye, sacando
el verbo del ayudante al que se las pasa —`self._get(...)` es un GET, `self._put_one(...)` un PUT—
y resolviendo por el camino los ayudantes privados de ruta (`self._path(...)`,
`self._organization_path(...)`), que es donde vive la mitad de cada URL. Lo que sale se compara
contra el bundle del OpenAPI en las DOS direcciones:

  - una operacion del alcance que ningun recurso construye es una ruta SIN CUBRIR;
  - una ruta que un recurso construye y el spec no declara es una ruta INVENTADA, que es el fallo
    que de verdad se paga: sale un 404 en produccion y en los tests no, porque el banco de pruebas
    contesta lo que se le diga.

Una tabla escrita a mano no habria cazado ninguna de las dos: diria lo que alguien creyo al
escribirla.

LO QUE ESTE SCRIPT NO COMPRUEBA, y conviene tenerlo claro: que la ruta se construya BIEN. Un
`{id_account}` en el sitio del `{id_organization}` sale igual de "/organizations/{}/accounts/{}", y
lo que fija eso es el test de contrato de cada metodo. Aqui se comprueba que NO FALTA NINGUNA, que
es lo que ningun test de contrato puede comprobar por su cuenta.

FUERA DE ALCANCE, y por eso no cuentan: las 19 operaciones de roles e invitaciones (los dos
documentos `*_roles-swagger.json`), que la libreria no cubre a proposito desde la fase 0, y
`POST /oauth/token`, que no es un recurso sino el propio mecanismo de autenticacion — lo pide
`_core/auth.py` y no `resources/`.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "openapi" / "planvortex.openapi.json"
RECURSOS = ROOT / "src" / "planvortex" / "resources"

# Las etiquetas del spec que quedan fuera de la libreria. Se filtra por etiqueta y no por prefijo de
# ruta porque las rutas de roles se parecen mucho a las que si cubrimos
# (`/clients/{id}/roles` contra `/clients/{id}/apps`), y una lista de prefijos se equivoca sola.
FUERA_DE_ALCANCE = frozenset({"client_roles", "organization_roles", "authentication"})

METODOS_HTTP = ("get", "post", "put", "delete", "patch")

# El ayudante de `resources/base.py` -> el verbo que acaba saliendo por el cable.
VERBOS: dict[str, str] = {
    "_get": "GET",
    "_list": "GET",
    "_one": "GET",
    "_post": "POST",
    "_post_one": "POST",
    "_put": "PUT",
    "_put_one": "PUT",
    "_delete": "DELETE",
    "_delete_one": "DELETE",
}

# El comodin con el que se reemplaza cualquier trozo interpolado de una ruta. Es tambien lo que se
# pone en lugar de `{id_organization}` al normalizar el spec, para que las dos formas se comparen.
COMODIN = "{}"


class Operacion(tuple[str, str]):
    """Un `(VERBO, /ruta/normalizada)`, con un `__str__` que se lee en un listado de fallos."""

    def __str__(self) -> str:
        return f"{self[0]:<6} {self[1]}"


def operaciones_del_spec() -> dict[Operacion, str]:
    """Las operaciones EN ALCANCE del bundle, con su `operationId` para poder nombrarlas."""
    spec = json.loads(BUNDLE.read_text(encoding="utf8"))
    operaciones: dict[Operacion, str] = {}

    for ruta, entrada in spec["paths"].items():
        for metodo, operacion in entrada.items():
            if metodo not in METODOS_HTTP:
                continue
            if FUERA_DE_ALCANCE.intersection(operacion.get("tags", [])):
                continue
            operaciones[Operacion((metodo.upper(), normalizar(ruta)))] = operacion.get("operationId", "?")

    return operaciones


def normalizar(ruta: str) -> str:
    """`/organizations/{id_organization}/accounts/{id_account}` -> `/organizations/{}/accounts/{}`.

    El nombre del parametro no se compara a proposito: en el spec es `{id_organization}` y en el
    codigo es el valor de una variable, y lo que se esta comprobando es que la ruta existe, no como
    se llaman sus huecos.
    """
    trozos = []
    for trozo in ruta.split("/"):
        trozos.append(COMODIN if trozo.startswith("{") and trozo.endswith("}") else trozo)
    return "/".join(trozos)


class Modulo:
    """Un modulo de `resources/`, y las rutas que construye.

    Se resuelve en dos pasadas porque los ayudantes de ruta se llaman entre ellos —`_path` usa
    `_organization_path`— y en el fichero pueden estar en cualquier orden.
    """

    def __init__(self, fichero: Path) -> None:
        self.fichero = fichero
        self.arbol = ast.parse(fichero.read_text(encoding="utf8"))
        self.ayudantes: dict[str, str] = {}
        self._resolver_ayudantes()

    def _resolver_ayudantes(self) -> None:
        """Los metodos privados cuyo cuerpo es (asignaciones y) un `return` de una ruta.

        Son `_path`, `_organization_path`, `_account_path`... : la mitad de cada URL vive ahi, y sin
        resolverlos lo unico que se reconstruiria de `f"{self._path(a, b)}/enable"` es `"{}/enable"`.
        """
        pendientes = [
            nodo
            for nodo in ast.walk(self.arbol)
            if isinstance(nodo, ast.FunctionDef) and nodo.name.endswith("path")
        ]
        # Dos vueltas bastan para el encadenado que hay hoy (`_path` -> `_organization_path`); una
        # tercera no cambiaria nada, y un bucle hasta punto fijo seria mas maquinaria de la que este
        # problema pide.
        for _ in range(3):
            for nodo in pendientes:
                plantilla = self._plantilla_de_funcion(nodo)
                if plantilla is not None:
                    self.ayudantes[nodo.name] = plantilla

    def _plantilla_de_funcion(self, nodo: ast.FunctionDef) -> str | None:
        locales: dict[str, str] = {}
        for sentencia in nodo.body:
            if isinstance(sentencia, ast.Assign) and len(sentencia.targets) == 1:
                objetivo = sentencia.targets[0]
                if isinstance(objetivo, ast.Name):
                    locales[objetivo.id] = self.plantilla(sentencia.value, locales)
            elif isinstance(sentencia, ast.Return) and sentencia.value is not None:
                return self.plantilla(sentencia.value, locales)
        return None

    def plantilla(self, nodo: ast.expr, locales: dict[str, str] | None = None) -> str:
        """El texto de una expresion, con `{}` donde haya algo que solo se sabe en ejecucion."""
        locales = locales or {}

        if isinstance(nodo, ast.Constant):
            return nodo.value if isinstance(nodo.value, str) else COMODIN

        if isinstance(nodo, ast.JoinedStr):
            return "".join(self.plantilla(trozo, locales) for trozo in nodo.values)

        if isinstance(nodo, ast.FormattedValue):
            return self.plantilla(nodo.value, locales)

        if isinstance(nodo, ast.Name):
            return locales.get(nodo.id, COMODIN)

        if isinstance(nodo, ast.Call):
            # `self._organization_path(...)` se sustituye por su plantilla; cualquier otra llamada
            # —`require_id(...)`, `str(...)`— es un valor de ejecucion.
            funcion = nodo.func
            if isinstance(funcion, ast.Attribute) and _es_self(funcion.value):
                return self.ayudantes.get(funcion.attr, COMODIN)
            return COMODIN

        return COMODIN

    def rutas(self) -> set[Operacion]:
        """Las `(verbo, ruta)` que este modulo construye.

        Se descarta lo que no empiece por `/`: es lo que sale de los ayudantes de `base.py`, que
        reciben la ruta como parametro y por tanto reconstruyen un `{}` pelado que casaria con todo.
        """
        buscador = _Buscador(self)
        buscador.visit(self.arbol)
        return buscador.encontradas

    def verbo(self, ayudante: str, llamada: ast.Call) -> str | None:
        """El verbo del ayudante, con el caso aparte de `_cached`, que lo lleva como argumento.

        `catalog.py` cachea el valor de una constante del despliegue y una de las suyas
        —`/allowed_social_messages`— es un `POST` que no manda cuerpo. Ahi el verbo viaja en un
        `method=`, asi que se lee de la llamada en vez de la tabla.
        """
        if ayudante == "_cached":
            for clave in llamada.keywords:
                if clave.arg == "method":
                    valor = self.plantilla(clave.value)
                    return valor if valor != COMODIN else None
            return "GET"
        return VERBOS.get(ayudante)


class _Buscador(ast.NodeVisitor):
    """Recorre un modulo llevando la cuenta de las variables locales de cada metodo.

    Hace falta llevarla porque un par de metodos arman la ruta en un paso previo —
    `ruta = (f"{self._account_path(...)}" f"/publish/{...}")` y despues `self._put_one(ruta, ...)`—
    y sin seguir la asignacion lo unico que se ve en la llamada es un nombre. La primera version de
    este script no lo hacia y daba por descubiertas dos rutas que si estaban.
    """

    def __init__(self, modulo: Modulo) -> None:
        self.modulo = modulo
        self.encontradas: set[Operacion] = set()
        self._ambitos: list[dict[str, str]] = [{}]

    @property
    def _locales(self) -> dict[str, str]:
        return self._ambitos[-1]

    def visit_FunctionDef(self, nodo: ast.FunctionDef) -> None:
        self._en_ambito(nodo)

    def visit_AsyncFunctionDef(self, nodo: ast.AsyncFunctionDef) -> None:
        self._en_ambito(nodo)

    def _en_ambito(self, nodo: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        # Hereda las del metodo de fuera: los iteradores definen un `async def buscar(...)` dentro.
        self._ambitos.append(dict(self._locales))
        self.generic_visit(nodo)
        self._ambitos.pop()

    def visit_Assign(self, nodo: ast.Assign) -> None:
        if len(nodo.targets) == 1 and isinstance(nodo.targets[0], ast.Name):
            self._locales[nodo.targets[0].id] = self.modulo.plantilla(nodo.value, self._locales)
        self.generic_visit(nodo)

    def visit_Call(self, nodo: ast.Call) -> None:
        funcion = nodo.func
        if isinstance(funcion, ast.Attribute) and _es_self(funcion.value) and nodo.args:
            verbo = self.modulo.verbo(funcion.attr, nodo)
            if verbo is not None:
                ruta = self.modulo.plantilla(nodo.args[0], self._locales)
                if ruta.startswith("/"):
                    self.encontradas.add(Operacion((verbo, ruta)))
        self.generic_visit(nodo)


def _es_self(nodo: ast.expr) -> bool:
    return isinstance(nodo, ast.Name) and nodo.id == "self"


def rutas_de_la_libreria() -> dict[Operacion, list[str]]:
    """Todas las rutas que construye `resources/`, con el modulo (o modulos) que las construye."""
    encontradas: dict[Operacion, list[str]] = {}
    for fichero in sorted(RECURSOS.glob("*.py")):
        for operacion in Modulo(fichero).rutas():
            encontradas.setdefault(operacion, []).append(fichero.stem)
    return encontradas


def informe() -> tuple[list[Operacion], list[Operacion], int]:
    """`(sin cubrir, inventadas, total en alcance)`."""
    spec = operaciones_del_spec()
    libreria = rutas_de_la_libreria()

    sin_cubrir = sorted((operacion for operacion in spec if operacion not in libreria), key=str)
    inventadas = sorted((operacion for operacion in libreria if operacion not in spec), key=str)
    return sin_cubrir, inventadas, len(spec)


def main() -> int:
    sin_cubrir, inventadas, total = informe()
    print(f"cobertura: {total - len(sin_cubrir)} de {total} operaciones del alcance")

    if sin_cubrir:
        spec = operaciones_del_spec()
        print(f"\nSIN CUBRIR ({len(sin_cubrir)}): ningun recurso construye esta ruta")
        for operacion in sin_cubrir:
            print(f"  {operacion}   ({spec[operacion]})")

    if inventadas:
        libreria = rutas_de_la_libreria()
        print(f"\nINVENTADAS ({len(inventadas)}): el spec no declara esta ruta")
        for operacion in inventadas:
            print(f"  {operacion}   ({', '.join(libreria[operacion])})")

    return 1 if sin_cubrir or inventadas else 0


if __name__ == "__main__":
    raise SystemExit(main())
