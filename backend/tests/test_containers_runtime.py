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
        runtime_container_cpu="2",
        runtime_container_memory="4g",
        runtime_container_pids_limit=512,
        runtime_container_shm_size="1g",
        runtime_container_traefik_middleware="headmaster-forward-auth@docker",
        runtime_traefik_dynamic_config_path=None,
        forward_auth_url="http://127.0.0.1:18081/",
        forward_auth_hmac_secret="test-secret",
        forward_auth_token_ttl_seconds=86400,
        container_host_url="https://hermeshq.gcaplabs.com",
        public_base_url=None,
        run_domain=None,
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
    assert "PORT=3737" in args
    assert "GATEWAY_DEFAULT_AGENT=hermes" in args
    assert "NOUS_API_KEY=nous-key" in args
    assert "--cpus" in args
    assert "--memory" in args
    assert "--pids-limit" in args
    assert "--shm-size" in args


@pytest.mark.asyncio
async def test_run_container_adds_traefik_labels_when_run_domain_is_configured(monkeypatch) -> None:
    settings = SimpleNamespace(
        runtime_container_image="headmaster-hermes-runtime:latest",
        runtime_container_network="hermes_runtime",
        runtime_container_cpu="2",
        runtime_container_memory="4g",
        runtime_container_pids_limit=512,
        runtime_container_shm_size="1g",
        runtime_container_traefik_middleware="headmaster-forward-auth@docker",
        runtime_traefik_dynamic_config_path=None,
        forward_auth_url="http://127.0.0.1:18081/",
        forward_auth_hmac_secret="test-secret",
        forward_auth_token_ttl_seconds=86400,
        container_host_url=None,
        public_base_url="https://hq.gcaplabs.com",
        run_domain="run.gcaplabs.com",
    )
    supervisor = RuntimeContainerSupervisor(settings)
    calls: list[tuple[str, ...]] = []

    async def fake_docker(*args: str) -> str:
        calls.append(args)
        return "container-id"

    monkeypatch.setattr(supervisor, "_docker", fake_docker)
    user = User(id="user-12345678", username="beta", display_name="Beta", password_hash="x", role="beta_user")
    container = RuntimeContainer(
        id="abcdef1234567890",
        user_id=user.id,
        container_name="hermes-user1234-abcd1234",
        image=settings.runtime_container_image,
        endpoint_path="/",
        api_server_key="secret-key",
    )

    await supervisor._run_container(container, user, None, {})

    args = calls[0]
    assert supervisor.public_endpoint_url(container) == "https://hm-abcdef123456.run.gcaplabs.com"
    assert "traefik.enable=true" in args
    assert "traefik.http.routers.hm-abcdef123456.rule=Host(`hm-abcdef123456.run.gcaplabs.com`)" in args
    assert "traefik.http.services.hm-abcdef123456.loadbalancer.server.port=3737" in args
    assert (
        "traefik.http.middlewares.hm-abcdef123456-inject-id.headers.customrequestheaders.X-Headmaster-Container-Id=abcdef1234567890"
        in args
    )
    assert "traefik.http.middlewares.hm-abcdef123456-forward-auth.forwardauth.address=http://127.0.0.1:18081/" in args
    assert "traefik.http.routers.hm-abcdef123456.middlewares=hm-abcdef123456-inject-id,hm-abcdef123456-forward-auth" in args


@pytest.mark.asyncio
async def test_run_container_can_write_traefik_file_provider_route(monkeypatch, tmp_path) -> None:
    dynamic_config = tmp_path / "headmaster-runtimes.yml"
    settings = SimpleNamespace(
        runtime_container_image="headmaster-hermes-runtime:latest",
        runtime_container_network="hermes_runtime",
        runtime_container_cpu="2",
        runtime_container_memory="4g",
        runtime_container_pids_limit=512,
        runtime_container_shm_size="1g",
        runtime_container_traefik_middleware="headmaster-forward-auth@docker",
        runtime_traefik_dynamic_config_path=str(dynamic_config),
        forward_auth_url="http://127.0.0.1:18081/",
        forward_auth_hmac_secret="test-secret",
        forward_auth_token_ttl_seconds=86400,
        container_host_url=None,
        public_base_url="https://hq.gcaplabs.com",
        run_domain="run.gcaplabs.com",
    )
    supervisor = RuntimeContainerSupervisor(settings)
    calls: list[tuple[str, ...]] = []

    async def fake_docker(*args: str) -> str:
        calls.append(args)
        if args[:2] == ("inspect", "-f"):
            return "172.20.0.7"
        return "container-id"

    monkeypatch.setattr(supervisor, "_docker", fake_docker)
    user = User(id="user-12345678", username="beta", display_name="Beta", password_hash="x", role="beta_user")
    container = RuntimeContainer(
        id="abcdef1234567890",
        user_id=user.id,
        container_name="hermes-user1234-abcd1234",
        image=settings.runtime_container_image,
        endpoint_path="/",
        api_server_key="secret-key",
    )

    await supervisor._run_container(container, user, None, {})

    run_args = calls[0]
    assert "traefik.enable=true" not in run_args
    written = (dynamic_config.parent / "hm-abcdef123456.yml").read_text()
    assert "Host(`hm-abcdef123456.run.gcaplabs.com`)" in written
    assert "url: http://172.20.0.7:3737" in written
    assert "X-Headmaster-Container-Id: \"abcdef1234567890\"" in written
    assert "address: \"http://127.0.0.1:18081/\"" in written
