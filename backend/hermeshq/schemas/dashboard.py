from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ── Overview ──────────────────────────────────────────────────────────────────


class DashboardStatsRead(BaseModel):
    total_agents: int
    active_agents: int
    total_tasks: int
    queued_tasks: int


class DashboardActivityItemRead(BaseModel):
    id: str
    event_type: str
    message: Optional[str] = None
    severity: str
    created_at: datetime


class DashboardOverviewRead(BaseModel):
    stats: DashboardStatsRead
    activity: list[DashboardActivityItemRead]


# ── Agent summary ─────────────────────────────────────────────────────────────


class DashboardAgentSummaryRead(BaseModel):
    id: str
    name: str
    slug: str
    status: str
    model: str
    tokens: int
    tasks: int
    last_activity: Optional[datetime] = None


# ── Token stats ───────────────────────────────────────────────────────────────


class DashboardTokenByAgentRead(BaseModel):
    agent_id: str
    name: str
    tokens: int


class DashboardTokenStatsRead(BaseModel):
    total_tokens: int
    by_agent: list[DashboardTokenByAgentRead]


# ── Task stats ────────────────────────────────────────────────────────────────


class DashboardTaskStatsRead(BaseModel):
    counts: dict[str, int]
    total: int


# ── Channel ───────────────────────────────────────────────────────────────────


class DashboardChannelRead(BaseModel):
    agent_id: str
    agent_name: str
    agent_slug: str
    platform: str
    enabled: bool
    status: str
    paired_at: Optional[str] = None
    days_since_paired: Optional[int] = None


# ── Fleet health ──────────────────────────────────────────────────────────────


class DashboardRecentErrorRead(BaseModel):
    agent_id: Optional[str] = None
    agent_name: str
    message: Optional[str] = None
    timestamp: Optional[str] = None


class DashboardFleetHealthRead(BaseModel):
    status_breakdown: dict[str, int]
    task_summary: dict[str, int]
    recent_errors: list[DashboardRecentErrorRead]
    last_updated: str


# ── Analytics ─────────────────────────────────────────────────────────────────


class DashboardCompletionMetricsRead(BaseModel):
    avg_seconds: float
    p50_seconds: float
    p95_seconds: float


class DashboardAnalyticsTotalsRead(BaseModel):
    total: int
    failed: int
    success_rate: float


class DashboardTopFailingAgentRead(BaseModel):
    agent_id: str
    agent_name: str
    fail_count: int


class DashboardAnalyticsRead(BaseModel):
    time_series: dict[str, dict[str, int]]
    completion_metrics: DashboardCompletionMetricsRead
    totals: DashboardAnalyticsTotalsRead
    top_failing_agents: list[DashboardTopFailingAgentRead]
    period_days: int
