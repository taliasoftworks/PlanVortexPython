"""El gemelo sincrono, y el guardia que impide que se genere uno roto.

Lo que la CI comprueba es otra cosa y es la principal: regenera y hace `git diff --exit-code`, o sea
que el gemelo commiteado corresponde a su fuente. Aqui se comprueba lo que ese diff NO puede ver:

- que en el gemelo no quede **nada** de asincronia, mirando el arbol y no el texto;
- que el cerrojo se haya traducido, que es la sustitucion que de verdad importa (§ Trampa P7);
- y que el guardia del generador **salta** cuando una sustitucion se escapa. Un guardia que nunca se
  ha visto fallar no es un guardia.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import generate_sync  # noqa: E402


@pytest.mark.parametrize("gemelo", [destino for _, destino in generate_sync.pares()], ids=lambda p: p.name)
def test_el_gemelo_no_conserva_ni_un_await(gemelo: Path) -> None:
    """Ni `async def`, ni `await`, ni `async for`, ni `async with`, en todo el arbol.

    Se mira con `ast` y no buscando la cadena: un `await` dentro de un comentario no importa, y uno
    dentro de un `def` normal es un `SyntaxError` que solo se veria al importar el modulo.
    """
    arbol = ast.parse(gemelo.read_text(encoding="utf8"))
    restos = sorted(
        {
            type(nodo).__name__
            for nodo in ast.walk(arbol)
            if isinstance(nodo, (ast.AsyncFunctionDef, ast.Await, ast.AsyncFor, ast.AsyncWith))
        }
    )
    assert restos == []


@pytest.mark.parametrize("gemelo", [destino for _, destino in generate_sync.pares()], ids=lambda p: p.name)
def test_el_gemelo_avisa_de_que_es_generado(gemelo: Path) -> None:
    """La cabecera es lo unico que impide que alguien lo edite y pierda el cambio al regenerar."""
    assert gemelo.read_text(encoding="utf8").startswith('"""GENERADO POR `scripts/generate_sync.py`')


def test_el_cerrojo_del_gemelo_es_de_hilos_y_no_de_corrutinas() -> None:
    """LA sustitucion de este generador.

    El cliente sincrono SI se comparte entre hilos —un Django con gunicorn, un
    `ThreadPoolExecutor`— y ahi un `asyncio.Lock` no protege absolutamente nada: no falla, no avisa,
    simplemente deja pasar a los diez a la vez. Escrito a mano dos veces seria un despiste posible.
    """
    generado = (generate_sync.PACKAGE / "_core" / "auth_sync.py").read_text(encoding="utf8")

    assert "threading.Lock()" in generado
    assert "asyncio" not in generado
    assert "import threading" in generado


def test_el_gemelo_importa_del_gemelo_y_no_del_original() -> None:
    """`auth_sync` tiene que usar el `HttpClient` sincrono, no el `AsyncHttpClient`."""
    generado = (generate_sync.PACKAGE / "_core" / "auth_sync.py").read_text(encoding="utf8")

    assert "from planvortex._core.http_sync import HttpClient" in generado
    assert "planvortex._core.http import" not in generado


def test_el_guardia_salta_si_una_sustitucion_se_escapa(tmp_path: Path) -> None:
    """El generador se niega a escribir si queda asincronia. Comprobado provocandolo.

    `async def` esta en la tabla, pero `asend` —o cualquier construccion que nadie penso— no. Este
    test simula ese caso pasandole al guardia un texto que aun tiene un `await`.
    """
    with pytest.raises(generate_sync.GeneracionError) as fallo:
        generate_sync.exigir_sin_async("async def f():\n    await g()\n", tmp_path / "x_sync.py")

    assert "asincronia" in str(fallo.value)
    assert "AsyncFunctionDef" in str(fallo.value)


def test_el_guardia_tambien_rechaza_lo_que_ni_siquiera_compila(tmp_path: Path) -> None:
    """Una sustitucion a medias deja Python invalido, y eso tiene que parar el generador."""
    with pytest.raises(generate_sync.GeneracionError) as fallo:
        generate_sync.exigir_sin_async("def f(:\n", tmp_path / "x_sync.py")

    assert "no es Python valido" in str(fallo.value)


def test_errors_y_query_no_tienen_gemelo() -> None:
    """No hacen E/S, asi que no hay nada de async que quitarles y los usan los dos clientes.

    Generarles un gemelo seria duplicar la jerarquia de errores, y entonces un
    `except PlanVortexError` del integrador dejaria de coger la mitad de los casos segun el cliente
    que hubiera usado.
    """
    fuentes = {origen.name for origen, _ in generate_sync.pares()}

    assert "errors.py" not in fuentes
    assert "query.py" not in fuentes
    assert not (generate_sync.PACKAGE / "_core" / "errors_sync.py").exists()
    assert not (generate_sync.PACKAGE / "_core" / "query_sync.py").exists()
