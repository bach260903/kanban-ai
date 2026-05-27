"""Pydantic schemas for GitHub integration (US7 / T102)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GitHubConfigResponse(BaseModel):
    repo_full_name: str
    default_base_branch: str
    enabled: bool


class GitHubConfigUpsert(BaseModel):
    repo_full_name: str = Field(..., min_length=3, max_length=200)
    pat: str = Field(..., min_length=1)
    default_base_branch: str = Field(default="main", min_length=1, max_length=100)
