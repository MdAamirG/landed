"""Pydantic models for what the API sends and receives."""

from typing import Literal

from pydantic import BaseModel


class PingOut(BaseModel):
    status: Literal["ok"]


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["reachable", "unreachable"]
