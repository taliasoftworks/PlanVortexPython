"""Lo que hace que un solo test valga para las DOS variantes del cliente.

El nucleo esta escrito una vez, en async, y el gemelo sincrono se genera de el. Si los tests se
escribieran solo contra el async, lo generado no lo probaria nadie — y el unico fallo posible de
este montaje es precisamente que el gemelo se quede atras o traduzca mal.

Asi que casi todos los tests reciben un `nucleo` PARAMETRIZADO y corren dos veces: una contra
`AsyncHttpClient`/`AsyncClientCredentialsAuth` y otra contra `HttpClient`/`ClientCredentialsAuth`.
El cuerpo del test es identico porque `nucleo.esperar(...)` bloquea en las dos: en la variante async
mete la corrutina en un bucle propio del test, y en la sincrona devuelve el valor tal cual.

`nucleo.en_paralelo(...)` es el que de verdad justifica todo esto: en async lanza un `gather` y en
sincrono un `ThreadPoolExecutor`, que es lo unico que puede demostrar que el cerrojo del gemelo es
un `threading.Lock` de verdad y no un `asyncio.Lock` que entre hilos no protege nada
(§ Trampa P7 del roadmap).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from planvortex import AsyncPlanVortex, PlanVortex
from planvortex._core.auth import AsyncClientCredentialsAuth, AsyncStaticTokenAuth
from planvortex._core.auth_sync import ClientCredentialsAuth, StaticTokenAuth
from planvortex._core.http import AsyncHttpClient
from planvortex._core.http_sync import HttpClient
from planvortex._core.transport import RetryConfig

BASE_URL = "https://api.planvortex.test/v1.0.0"


class _NucleoAsync:
    """La variante asincrona, con UN bucle para todo el test.

    Un bucle por llamada (`asyncio.run` en cada una) dejaria el cliente de httpx2 atado a un bucle
    ya cerrado en la segunda, que es un fallo que no dice de donde sale.
    """

    variante = "async"
    http_client = AsyncHttpClient
    credentials_auth = AsyncClientCredentialsAuth
    static_auth = AsyncStaticTokenAuth
    plan_vortex = AsyncPlanVortex

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def esperar(self, valor: Any) -> Any:
        return self._loop.run_until_complete(valor)

    def en_paralelo(self, hacer: Callable[[], Any], veces: int) -> list[Any]:
        async def todas() -> list[Any]:
            return list(await asyncio.gather(*(hacer() for _ in range(veces))))

        return self._loop.run_until_complete(todas())

    def recorrer(self, iterador: Any) -> list[Any]:
        async def todos() -> list[Any]:
            return [elemento async for elemento in iterador]

        return self._loop.run_until_complete(todos())

    def cerrar(self, cliente: Any) -> None:
        self._loop.run_until_complete(cliente.aclose())


class _NucleoSync:
    """La variante sincrona: la generada, y la que se comparte entre hilos de verdad."""

    variante = "sync"
    http_client = HttpClient
    credentials_auth = ClientCredentialsAuth
    static_auth = StaticTokenAuth
    plan_vortex = PlanVortex

    def esperar(self, valor: Any) -> Any:
        return valor

    def en_paralelo(self, hacer: Callable[[], Any], veces: int) -> list[Any]:
        with ThreadPoolExecutor(max_workers=veces) as pool:
            futuros = [pool.submit(hacer) for _ in range(veces)]
            return [futuro.result() for futuro in futuros]

    def recorrer(self, iterador: Any) -> list[Any]:
        return list(iterador)

    def cerrar(self, cliente: Any) -> None:
        cliente.close()


@pytest.fixture(params=["async", "sync"])
def nucleo(request: pytest.FixtureRequest) -> Iterator[Any]:
    if request.param == "async":
        loop = asyncio.new_event_loop()
        try:
            yield _NucleoAsync(loop)
        finally:
            loop.close()
    else:
        yield _NucleoSync()


# =================================================================================================
# La capa 2: el banco de pruebas de contrato
# =================================================================================================
#
# Lo mismo de arriba, un piso mas arriba: un `cliente` parametrizado que es `AsyncPlanVortex` en una
# vuelta y `PlanVortex` en la otra, contra `pytest_httpx2`. Se prueban las DOS variantes porque la
# sincrona esta GENERADA y su unico fallo posible —traducir mal, o quedarse atras— es invisible
# desde el lado async.
#
# LAS DOS AUSENCIAS LAS VIGILA EL PLUGIN, y son la mitad que se olvida siempre:
#
#   - `assert_all_requests_were_expected` tumba el test ante una peticion SIN simular. Sin eso, un
#     metodo que llamase a una ruta equivocada saldria a la red de verdad.
#   - `assert_all_responses_were_requested` tumba el test ante un mock DECLARADO Y NO USADO. Sin
#     eso, un test que simula una llamada que el metodo ya no hace deja de comprobar lo que cree.
#
# Las dos vienen puestas por defecto y no se tocan: es exactamente el trato de la capa 2 del
# servidor y el de la libreria de Node.


class ClienteDePrueba:
    """Un cliente ya autenticado contra el banco, y con que bloquear en las dos variantes."""

    def __init__(self, nucleo: Any, pv: Any) -> None:
        self.nucleo = nucleo
        self.pv = pv

    @property
    def variante(self) -> str:
        variante: str = self.nucleo.variante
        return variante

    def esperar(self, valor: Any) -> Any:
        return self.nucleo.esperar(valor)

    def recorrer(self, iterador: Any) -> list[Any]:
        """Vacia un iterador de paginacion, sea `aiterate` o `iterate`."""
        elementos: list[Any] = self.nucleo.recorrer(iterador)
        return elementos

    def iterar(self, recurso: Any, metodo: str, *args: Any, **kwargs: Any) -> list[Any]:
        """Recorre entero el iterador de un recurso, llamandolo por su nombre en ESTA variante.

        Es la unica diferencia de nombre entre los dos clientes —`aiterate` contra `iterate`— y por
        eso se resuelve aqui: escrito en cada test, la mitad de la suite solo probaria una variante.
        """
        nombre = metodo if self.variante == "async" else metodo.replace("aiterate", "iterate", 1)
        elementos: list[Any] = self.recorrer(getattr(recurso, nombre)(*args, **kwargs))
        return elementos


def stub_token(httpx_mock: Any, *, expires_in: int = 300) -> None:
    """El token va aparte de los mocks del contrato y es OPCIONAL a proposito.

    Es infraestructura, no el contrato que se esta probando: ni cuenta como mock sin usar cuando el
    test no llega a hacer ninguna llamada, ni ensucia lo que se afirma sobre la peticion. Es
    reutilizable porque un test puede construir dos clientes —`as_temporal_token`— y cada uno pide
    el suyo.
    """
    httpx_mock.add_response(
        url=f"{BASE_URL}/oauth/token",
        method="POST",
        json={"access_token": "token-de-prueba", "token_type": "Bearer", "expires_in": expires_in},
        is_optional=True,
        is_reusable=True,
    )


@pytest.fixture
def cliente(nucleo: Any, httpx_mock: Any) -> Iterator[ClienteDePrueba]:
    """`pv`, autenticado, sin reintentos y contra el banco. Se cierra al acabar el test."""
    stub_token(httpx_mock)
    pv = nucleo.plan_vortex(
        client_id="app-1",
        client_secret="s3cr3t",
        base_url=BASE_URL,
        retry=RetryConfig(max_retries=0, base_delay=0.0, max_delay=0.0),
    )
    try:
        yield ClienteDePrueba(nucleo, pv)
    finally:
        nucleo.cerrar(pv)
