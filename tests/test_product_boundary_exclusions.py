from __future__ import annotations

import pytest

from tigrcorn.contract import product_surface_excluded, product_surface_status, require_product_boundary_exclusion
from tigrcorn.errors import ConfigError


@pytest.mark.parametrize("surface", ["asgi2", "wsgi", "rsgi", "rest", "jsonrpc", "json-rpc", "json_rpc"])
def test_product_boundary_exclusions_are_explicit(surface: str) -> None:
    status = require_product_boundary_exclusion(surface)

    assert product_surface_excluded(surface)
    assert not status.runtime_available


@pytest.mark.parametrize("surface", ["auto", "tigr-asgi-contract", "tigr_asgi_contract", "asgi3"])
def test_supported_product_surfaces_are_not_exclusions(surface: str) -> None:
    assert product_surface_status(surface).runtime_available
    assert not product_surface_excluded(surface)
    with pytest.raises(ConfigError, match="not excluded"):
        require_product_boundary_exclusion(surface)


@pytest.mark.parametrize("surface", ["", "   ", "cgi", "fastcgi", "grpc", None, 123])
def test_unknown_or_malformed_product_surfaces_fail_closed(surface: object) -> None:
    with pytest.raises(ConfigError):
        product_surface_status(surface)  # type: ignore[arg-type]
