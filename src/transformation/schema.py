"""Unified output schema for all sources (JSON Lines)."""

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

SourceCredibility = Literal["high", "medium", "low"]
LabelMethod = Literal["human_expert", "community", "automated"]
Label = Literal["fake", "real"]


class ArticleMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_credibility: SourceCredibility
    has_image: bool
    label_method: LabelMethod


class Article(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    source: str
    title: str
    content: str
    image_url: str | None = None
    label: Label | None = None
    label_detail: str | None = None
    language: str = "en"
    domain: str | None = None
    collected_at: datetime
    metadata: ArticleMetadata

    def to_jsonl(self) -> str:
        return self.model_dump_json(exclude_none=False)
