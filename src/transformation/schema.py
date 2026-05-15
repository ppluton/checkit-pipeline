"""Unified output schema for the processed dataset (JSON Lines).

Why a strict schema:
    The pipeline ingests heterogeneous sources (Fakeddit, The Guardian,
    Snopes, ...) and feeds a single multimodal classifier downstream.
    The model expects every record to expose the same shape; therefore
    every record produced by ``normalizer`` and accepted by
    ``validator`` must conform to ``Article``.

Why Pydantic v2:
    * Runtime validation at IO boundaries (file reads, API responses).
    * ``Literal`` types enforce a closed vocabulary on
      ``label``/``label_method``/``source_credibility`` so the dataset
      cannot silently drift.
    * ``extra="forbid"`` rejects unknown fields, preventing typos like
      ``label_dtail`` from leaking through.
    * ``model_dump_json`` produces the canonical JSON Lines line for
      ``data/processed/*.jsonl``.

Why ``label`` and ``label_detail`` are nullable:
    Some sources (The Guardian, raw NewsData) are unlabelled and serve
    as a high-credibility ``real`` baseline. The normalizer may decide
    to leave the binary ``label`` empty when there is no fact-checker
    verdict, while the model can still use ``source_credibility`` as a
    weak label signal.

Why ``label_detail`` is a free string:
    Snopes alone exposes verdicts like ``Mixture``, ``Mostly True``,
    ``Originated as Satire``, ``Correct Attribution``. Reducing them
    to ``fake`` vs ``real`` would destroy information the model needs.
    The string preserves the source's original nuance verbatim.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

SourceCredibility = Literal["high", "medium", "low"]
LabelMethod = Literal["human_expert", "community", "automated"]
Label = Literal["fake", "real"]


class ArticleMetadata(BaseModel):
    """Provenance and trustworthiness signals attached to every article.

    The model uses these as auxiliary features: an article from a
    ``high`` credibility source with ``human_expert`` labelling is far
    more reliable than a community-labelled one.
    """

    model_config = ConfigDict(extra="forbid")

    source_credibility: SourceCredibility
    has_image: bool
    label_method: LabelMethod


class Article(BaseModel):
    """One normalised article in the processed dataset.

    Produced by ``src/transformation/normalizer.py`` from raw records
    living in ``data/raw/<source>/``. Serialised one-per-line via
    ``to_jsonl()`` into ``data/processed/<batch>.jsonl``.
    """

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
        """Serialise as a single JSON Lines line (no trailing newline).

        Caller is responsible for writing the ``\\n`` separator so the
        method is composable with both file writes and streaming.
        """
        return self.model_dump_json(exclude_none=False)
