from typing import Any, Literal

from pydantic import BaseModel, Field


RetrievalMode = Literal["all", "all_sources", "curated_only", "curated_trusted"]
AnswerStyle = Literal["Simple", "Technical", "Study Notes", "Article Draft", "Book Chapter Draft"]


class WorkbaseCreate(BaseModel):
    name: str
    description: str = ""


class WorkbasePatch(BaseModel):
    name: str | None = None
    description: str | None = None


class ChatCreate(BaseModel):
    title: str = "Research Chat"


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1)
    model: str | None = None
    technical_mode: bool | None = None
    retrieval_mode: RetrievalMode = "curated_trusted"
    answer_style: AnswerStyle = "Simple"
    document_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    advanced_mode: bool = False


class UrlIngestCreate(BaseModel):
    url: str
    title: str = ""
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    citation: dict[str, str] = Field(default_factory=dict)


class SourcePatch(BaseModel):
    workbase_id: str
    title: str | None = None
    tags: list[str] | None = None
    author: str | None = None
    year: str | None = None
    url: str | None = None


class SourceAskCreate(ChatMessageCreate):
    workbase_id: str


class ReportCreate(BaseModel):
    workbase_id: str | None = None
    title: str
    type: str = "Research Summary"
    content: str = ""
    sources: list[dict[str, Any]] = Field(default_factory=list)
    generate: Literal["none", "article", "chapter", "glossary"] = "none"
    topic: str = ""
    goal: str = ""
    audience: str = "Students"
    tone: str = "Clear and professional"
    length: str = "Medium"
    retrieval_mode: RetrievalMode = "curated_trusted"
    model: str | None = None


class ReportPatch(BaseModel):
    workbase_id: str
    title: str | None = None
    type: str | None = None
    content: str | None = None
    sources: list[dict[str, Any]] | None = None


class ExportCreate(BaseModel):
    title: str
    content: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    workbase_name: str = "SourceStack AI"


class SettingsPatch(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
