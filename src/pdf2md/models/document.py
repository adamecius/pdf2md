from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class SourceRef(BaseModel):
    backend: str
    raw_id: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class Flag(BaseModel):
    code: str
    severity: Literal["low", "medium", "high"] = "low"
    message: str


class Block(BaseModel):
    id: str
    type: Literal["paragraph", "heading", "table", "formula", "image", "caption"]
    text: str | None = None
    level: int | None = Field(default=None, ge=1, le=6)
    bbox: BBox | None = None
    page_number: int = Field(ge=1)
    order: int = Field(ge=0)
    media_id: str | None = None
    source_refs: list[SourceRef] = Field(default_factory=list)
    flags: list[Flag] = Field(default_factory=list)


class Page(BaseModel):
    number: int = Field(ge=1)
    width: float | None = Field(default=None, gt=0)
    height: float | None = Field(default=None, gt=0)
    blocks: list[Block] = Field(default_factory=list)


class Document(BaseModel):
    id: str
    source_path: str | None = None
    pages: list[Page] = Field(default_factory=list)
    flags: list[Flag] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def ordered_blocks(self) -> list[Block]:
        return sorted(
            [block for page in self.pages for block in page.blocks],
            key=lambda b: (b.page_number, b.order),
        )
