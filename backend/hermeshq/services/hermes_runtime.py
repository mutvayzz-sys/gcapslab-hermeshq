import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hermeshq.models.agent import Agent
from hermeshq.models.secret import Secret
from hermeshq.models.task import Task
from hermeshq.services.hermes_installation import HermesInstallationManager
from hermeshq.services.provider_catalog import normalize_runtime_provider
from hermeshq.services.runtime_profiles import resolve_effective_toolsets
from hermeshq.services.secret_vault import SecretVault


@dataclass
class RuntimeExecutionResult:
    final_response: str
    messages: list[dict]
    tool_calls: list[dict]
    tokens_used: int
    iterations: int
    engine: str


class RuntimeExecutionError(RuntimeError):
    pass


class HermesRuntime:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        secret_vault: SecretVault,
        installation_manager: HermesInstallationManager,
    ) -> None:
        self.session_factory = session_factory
        self.secret_vault = secret_vault
        self.installation_manager = installation_manager

    @property
    def available(self) -> bool:
        return True

    async def execute(
        self,
        agent: Agent,
        task: Task,
        stream_callback,
        conversation_history: list[dict] | None = None,
        session_id: str | None = None,
    ) -> RuntimeExecutionResult:
        if not self._has_credentials(agent):
            raise RuntimeExecutionError("No runtime credentials configured for this agent")
        api_key = await self._resolve_api_key(agent.api_key_ref)
        await self.installation_manager.sync_agent_installation(agent)
        runtime_system_prompt = await self.installation_manager.get_runtime_system_prompt(agent)
        runtime_selection = await self.installation_manager.resolve_hermes_runtime(agent)
        try:
            return await self._run_real(
                agent,
                task,
                stream_callback,
                api_key,
                runtime_system_prompt,
                runtime_selection.python_bin,
                conversation_history=conversation_history,
                session_id=session_id,
            )
        except RuntimeExecutionError:
            # ── Fallback provider retry ────────────────────────────────
            if not self._has_fallback(agent):
                raise
            try:
                fallback_api_key = await self._resolve_api_key(agent.fallback_api_key_ref)
                return await self._run_real(
                    agent,
                    task,
                    stream_callback,
                    fallback_api_key,
                    runtime_system_prompt,
                    runtime_selection.python_bin,
                    conversation_history=conversation_history,
                    session_id=session_id,
                    fallback_override={
                        "model": agent.fallback_model,
                        "provider": agent.fallback_provider,
                        "base_url": agent.fallback_base_url,
                        "api_key": fallback_api_key,
                    },
                )
            except Exception:
                raise  # Fallback also failed — raise its error
        except Exception as exc:
            raise RuntimeExecutionError(str(exc)) from exc

    async def _run_real(
        self,
        agent: Agent,
        task: Task,
        stream_callback,
        api_key: str | None,
        runtime_system_prompt: str,
        runtime_python_bin: str,
        conversation_history: list[dict] | None = None,
        session_id: str | None = None,
        fallback_override: dict | None = None,
    ) -> RuntimeExecutionResult:
        workspace_path = self.installation_manager.resolve_workspace_path(agent.workspace_path)
        hermes_home = self.installation_manager.build_hermes_home(agent.workspace_path)
        process_env = await self.installation_manager.build_process_env(agent)
        if fallback_override:
            process_env = {**process_env, **self._fallback_env(agent, fallback_override.get("api_key"))}
        enabled_toolsets, disabled_toolsets = resolve_effective_toolsets(
            agent.runtime_profile,
            agent.enabled_toolsets,
            agent.disabled_toolsets,
        )
        runtime_provider = self.installation_manager._model_provider_for_agent(agent)
        effective_base_url = self.installation_manager._effective_provider_base_url(agent)
        payload = {
            "task_id": str(task.id),
            "prompt": task.prompt,
            "system_override": task.system_override,
            "model": agent.model,
            "provider": runtime_provider,
            "base_url": effective_base_url,
            "api_key": api_key,
            "enabled_toolsets": enabled_toolsets or None,
            "disabled_toolsets": disabled_toolsets or None,
            "max_iterations": agent.max_iterations,
            "system_prompt": runtime_system_prompt,
            "cwd": str(workspace_path),
            "hermes_home": str(hermes_home),
            "conversation_history": conversation_history or [],
            "session_id": session_id,
            "metadata": task.metadata_json or {},
        }

        if fallback_override:
            for key, value in fallback_override.items():
                if value is not None:
                    payload[key] = value

        process = await asyncio.create_subprocess_exec(
            runtime_python_bin,
            str(Path(__file__).resolve().parents[1] / "scripts" / "hermes_task_runner.py"),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=1024 * 1024,
            cwd=str(Path(__file__).resolve().parents[2]),
            env={**process_env, "HERMESHQ_TASK_PAYLOAD": json.dumps(payload)},
        )

        final_result: dict | None = None

        assert process.stdout is not None
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            try:
                event = json.loads(text)
            except json.JSONDecodeError:
                await stream_callback(text)
                continue

            if event.get("event") == "delta" and event.get("data"):
                await stream_callback(str(event["data"]))
            elif event.get("event") == "result":
                final_result = event
            elif event.get("event") == "error":
                raise RuntimeExecutionError(str(event.get("error") or "Hermes runtime process failed"))

        stderr_output = ""
        if process.stderr is not None:
            stderr_output = (await process.stderr.read()).decode("utf-8", errors="replace").strip()

        return_code = await process.wait()
        if return_code != 0 and not final_result:
            raise RuntimeExecutionError(stderr_output or "Hermes runtime process exited with an error")
        if not final_result:
            raise RuntimeExecutionError("Hermes runtime returned no result payload")

        raw_response = str(final_result.get("final_response") or "").strip()

        # ── Detect provider-level errors disguised as successful responses ──
        # hermes-agent catches API errors (429, timeout, auth) and returns
        # them as normal text responses instead of raising errors.
        _PROVIDER_ERROR_PATTERNS = (
            "API call failed",
            "rate limit",
            "Rate limit",
            "429",
            "401",
            "403",
            "Authentication",
            "timeout",
            "Connection",
            "service unavailable",
            "internal server error",
        )
        if any(p.lower() in raw_response.lower() for p in _PROVIDER_ERROR_PATTERNS) and len(raw_response) < 300:
            raise RuntimeExecutionError(raw_response)

        return RuntimeExecutionResult(
            final_response=raw_response,
            messages=list(final_result.get("messages") or []),
            tool_calls=list(final_result.get("tool_calls") or []),
            tokens_used=int(final_result.get("tokens_used") or 0),
            iterations=int(final_result.get("iterations") or 0),
            engine=str(final_result.get("engine") or "hermes-agent"),
        )

    async def _resolve_api_key(self, api_key_ref: str | None) -> str | None:
        if not api_key_ref:
            return None
        try:
            async with self.session_factory() as session:
                result = await session.execute(select(Secret).where(Secret.name == api_key_ref))
                secret = result.scalar_one_or_none()
            if not secret:
                raise RuntimeExecutionError(f"Secret '{api_key_ref}' was not found")
            return self.secret_vault.decrypt(secret.value_enc)
        except RuntimeExecutionError:
            raise
        except Exception as exc:
            raise RuntimeExecutionError(f"Could not resolve secret '{api_key_ref}'") from exc

    def _has_fallback(self, agent: Agent) -> bool:
        return bool(agent.fallback_provider or agent.fallback_model or agent.fallback_api_key_ref)

    def _fallback_env(self, agent: Agent, fallback_api_key: str | None) -> dict[str, str]:
        """Build extra env vars for the fallback provider."""
        env: dict[str, str] = {}
        if not agent.fallback_provider:
            return env
        provider = normalize_runtime_provider(agent.fallback_provider)
        for env_name in self.installation_manager._provider_env_names(provider):
            if fallback_api_key:
                env[env_name] = fallback_api_key
        if agent.fallback_base_url:
            base_env = self.installation_manager._provider_base_url_env_name(provider)
            if base_env:
                env[base_env] = agent.fallback_base_url
        return env

    def _has_credentials(self, agent: Agent) -> bool:
        if self._provider_uses_sdk_auth(normalize_runtime_provider(agent.provider)):
            return True
        if agent.api_key_ref:
            return True
        return any(
            os.getenv(env_name)
            for env_name in (
                "OPENROUTER_API_KEY",
                "OPENAI_API_KEY",
                "ANTHROPIC_API_KEY",
                "ANTHROPIC_TOKEN",
                "CLAUDE_CODE_OAUTH_TOKEN",
                "KIMI_API_KEY",
                "GEMINI_API_KEY",
                "GOOGLE_API_KEY",
                "GLM_API_KEY",
                "ZAI_API_KEY",
                "Z_AI_API_KEY",
            )
        )

    def _provider_uses_sdk_auth(self, provider: str | None) -> bool:
        if not provider:
            return False
        try:
            from hermes_cli.auth import PROVIDER_REGISTRY

            pconfig = PROVIDER_REGISTRY.get(provider)
            auth_type = getattr(pconfig, "auth_type", None) if pconfig else None
            return str(auth_type or "").strip().lower() == "aws_sdk"
        except Exception:
            pass
        return provider == "bedrock"

    def _extract_tool_calls(self, messages: list[dict]) -> list[dict]:
        extracted: list[dict] = []
        for message in messages:
            if message.get("role") != "assistant":
                continue
            for tool_call in message.get("tool_calls", []) or []:
                extracted.append(
                    {
                        "name": tool_call.get("function", {}).get("name", "tool"),
                        "status": "completed",
                        "payload": tool_call,
                    }
                )
        return extracted
