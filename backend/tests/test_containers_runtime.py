from types import SimpleNamespace

import pytest

from hermeshq.models.agent import Agent
from hermeshq.models.runtime_container import RuntimeContainer
from hermeshq.models.user import User
from hermeshq.services.container_supervisor import RuntimeContainerSupervisor


def _all_paths(application) -> set[str]:
    paths: set[str] = set()
    for route in application.routes:
        path = getattr(route, "path", None)
        if path:
            paths.add(path)
        nested = getattr(route, "router", None)
        if nested is not None:
            paths.update(_all_paths(nested))
    return paths


def test_containers_router_is_mounted() -> None:
    try:
        from hermeshq.main import app
    except ModuleNotFoundError as exc:
        if exc.name == "fcntl":
            pytest.skip("Full FastAPI app import requires Linux PTY support")
        raise

    paths = _all_paths(app)
    assert "/api/containers" in paths
    assert "/api/containers/provision" in paths
    assert "/api/containers/cleanup" in paths
    assert "/api/containers/{container_id}/health" in paths


@pytest.mark.asyncio
async def test_run_container_uses_latest_configured_image_and_private_network(monkeypatch) -> None:
    settings = SimpleNamespace(
        runtime_container_image="headmaster-hermes-runtime:latest",
        runtime_container_network="hermes_runtime",
        container_host_url="https://hermeshq.gcaplabs.com",
        public_base_url=None,
    )
    supervisor = RuntimeContainerSupervisor(settings)
    calls: list[tuple[str, ...]] = []

    async def fake_docker(*args: str) -> str:
        calls.append(args)
        return "container-id"

    monkeypatch.setattr(supervisor, "_docker", fake_docker)
    user = User(id="user-12345678", username="beta", display_name="Beta", password_hash="x", role="beta_user")
    agent = Agent(
        id="agent-1",
        node_id="node-1",
        name="Agent",
        slug="agent",
        workspace_path="/tmp/agent",
    )
    container = RuntimeContainer(
        id="ctr-1",
        user_id=user.id,
        agent_id=agent.id,
        container_name="hermes-user1234-abcd1234",
        image=settings.runtime_container_image,
        endpoint_path="/runtime/hermes-user1234-abcd1234",
        api_server_key="secret-key",
    )

    await supervisor._run_container(container, user, agent, {"NOUS_API_KEY": "nous-key"})

    assert calls
    args = calls[0]
    assert args[:3] == ("run", "-d", "--name")
    assert "hermes_runtime" in args
    assert "headmaster-hermes-runtime:latest" == args[-1]
    assert "-p" not in args
    assert "API_SERVER_ENABLED=true" in args
    assert "API_SERVER_PORT=8080" in args
    assert "API_SERVER_KEY=secret-key" in args
    assert "NOUS_API_KEY=nous-key" in args
