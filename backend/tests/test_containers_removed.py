"""Assert the broken per-user Docker container track has been fully removed."""
import importlib

import pytest

from hermeshq.main import app


def _all_paths(application) -> set[str]:
    """Walk FastAPI's app.routes, descending into _IncludedRouter entries."""
    paths: set[str] = set()
    for r in application.routes:
        p = getattr(r, "path", None)
        if p:
            paths.add(p)
        # _IncludedRouter holds nested routes; recurse via its router.
        nested = getattr(r, "router", None)
        if nested is not None:
            paths.update(_all_paths(nested))
    return paths


@pytest.mark.asyncio
async def test_containers_router_not_mounted() -> None:
    paths = _all_paths(app)
    assert "/api/containers" not in paths
    assert "/api/containers/{container_id}" not in paths
    assert "/api/containers/provision" not in paths


def test_container_supervisor_not_on_app_state() -> None:
    # After lifespan starts, app.state.container_supervisor should be None
    # (or the attribute should not exist). We assert pre-lifespan first;
    # the in-container smoke test after Task 7 covers post-lifespan state.
    val = getattr(app.state, "container_supervisor", None)
    assert val is None


def test_container_supervisor_module_not_importable() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("hermeshq.services.container_supervisor")


def test_containers_router_module_not_importable() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("hermeshq.routers.containers")
