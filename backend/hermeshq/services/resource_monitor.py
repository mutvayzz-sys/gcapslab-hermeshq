"""Resource monitoring service for container/host resource detection."""

import logging
from pathlib import Path

import psutil

from hermeshq.config import get_settings

logger = logging.getLogger(__name__)


def _read_cgroup_memory_limit() -> int | None:
    """Read memory limit from cgroups (v1 or v2). Returns bytes or None."""
    # cgroup v2
    cgroup2 = Path("/sys/fs/cgroup/memory.max")
    if cgroup2.exists():
        try:
            raw = cgroup2.read_text().strip()
            if raw != "max":
                return int(raw)
        except (ValueError, OSError):
            pass

    # cgroup v1
    cgroup1 = Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")
    if cgroup1.exists():
        try:
            raw = cgroup1.read_text().strip()
            limit = int(raw)
            # cgroup v1 returns a very large number when unlimited
            if limit < (1 << 62):
                return limit
        except (ValueError, OSError):
            pass

    return None


def _read_cgroup_cpu_limit() -> float | None:
    """Read CPU limit from cgroups. Returns number of CPUs or None."""
    # cgroup v2
    cpu_max = Path("/sys/fs/cgroup/cpu.max")
    if cpu_max.exists():
        try:
            parts = cpu_max.read_text().strip().split()
            if parts[0] != "max":
                quota = int(parts[0])
                period = int(parts[1]) if len(parts) > 1 else 100000
                return quota / period
        except (ValueError, OSError):
            pass

    # cgroup v1
    quota_path = Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
    period_path = Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
    if quota_path.exists() and period_path.exists():
        try:
            quota = int(quota_path.read_text().strip())
            period = int(period_path.read_text().strip())
            if quota > 0 and period > 0:
                return quota / period
        except (ValueError, OSError):
            pass

    return None


class ResourceMonitor:
    """Provides container and system resource information."""

    def get_container_limits(self) -> dict:
        """Read cgroups for memory/CPU limits of the container."""
        memory_limit_bytes = _read_cgroup_memory_limit()
        cpu_limit = _read_cgroup_cpu_limit()

        return {
            "memory_limit_mb": round(memory_limit_bytes / 1024 / 1024) if memory_limit_bytes else None,
            "cpu_limit": round(cpu_limit, 2) if cpu_limit else None,
        }

    def get_container_usage(self) -> dict:
        """Current memory and CPU usage of the process."""
        process = psutil.Process()
        try:
            cpu_pct = process.cpu_percent(interval=0.1)
        except Exception:
            cpu_pct = 0.0

        return {
            "memory_mb": round(process.memory_info().rss / 1024 / 1024, 1),
            "cpu_pct": round(cpu_pct, 1),
            "num_threads": process.num_threads(),
            "num_children": len(process.children()),
        }

    def get_system_resources(self) -> dict:
        """Host system resources (may be limited by Docker)."""
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return {
            "total_ram_mb": round(mem.total / 1024 / 1024),
            "available_ram_mb": round(mem.available / 1024 / 1024),
            "cpu_cores": psutil.cpu_count(),
            "disk_available_gb": round(disk.free / 1024 / 1024 / 1024, 1),
        }

    def get_semaphore_info(self, active_task_count: int) -> dict:
        """Semaphore configuration and utilization."""
        settings = get_settings()
        current = settings.concurrency_semaphore
        max_tasks = current
        utilization_pct = round((active_task_count / max_tasks) * 100) if max_tasks > 0 else 0

        return {
            "current": current,
            "active_tasks": active_task_count,
            "max_tasks": max_tasks,
            "utilization_pct": utilization_pct,
        }

    def calculate_sizing(self, total_agents: int) -> dict:
        """Calculate recommended resource sizing for a given number of agents."""
        concurrent = max(1, total_agents // 2)
        semaphore = concurrent

        ram_backend_mb = semaphore * 50 + 500
        ram_postgres_mb = semaphore * 10 + 200
        cpu_needed = max(1, (semaphore // 6) + 1)
        disk_gb = total_agents * 3 // 2 + 5  # 1.5GB per agent + 5GB base

        return {
            "agents": total_agents,
            "concurrent": concurrent,
            "semaphore": semaphore,
            "ram_backend_mb": ram_backend_mb,
            "ram_postgres_mb": ram_postgres_mb,
            "cpu_needed": cpu_needed,
            "disk_gb": disk_gb,
        }


# Singleton instance
resource_monitor = ResourceMonitor()
