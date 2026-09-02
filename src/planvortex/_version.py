"""The version and the default URL, in one place that imports nothing of ours.

``__init__.py`` cannot hold them: it imports the client, the client needs the version for its
``User-Agent``, and a module that imports the package it belongs to is a circular import waiting for
the first person who reorders two lines.

The number is repeated in ``pyproject.toml`` — see the comment there for why it is not dynamic — and
``tests/test_packaging.py`` fails if the two ever separate.
"""

from __future__ import annotations

import platform

VERSION = "0.5.0"

# Sin barra final, y con el `/v1.0.0` dentro: la version de la API es parte de la ruta, no una
# cabecera, asi que una `base_url` sin ella da 404 en todo.
PLANVORTEX_API_URL = "https://api.planvortex.com/v1.0.0"


def user_agent() -> str:
    """``planvortex-python/0.3.0 python/3.12.4``.

    Both halves earn their place in our logs: ours says which version of the library is failing and
    the interpreter's says whether the failure belongs to one row of the support matrix.
    """
    return f"planvortex-python/{VERSION} python/{platform.python_version()}"
