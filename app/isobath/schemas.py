from typing import Literal

from pydantic import BaseModel, Field


class AnswerIn(BaseModel):
    question_id: int = Field(ge=1)
    value: int = Field(ge=1, le=5)
    response_ms: int | None = Field(default=None, ge=0, le=3_600_000)


class AnswersIn(BaseModel):
    answers: list[AnswerIn] = Field(min_length=1, max_length=20)


class SessionCreate(BaseModel):
    kind: Literal["initial", "continuous"]


class ConsentIn(BaseModel):
    document: Literal["terms", "privacy", "research"]
    version: str = Field(max_length=16)


class ConsentsIn(BaseModel):
    consents: list[ConsentIn] = Field(min_length=1, max_length=3)


class ResearchParticipation(BaseModel):
    participating: bool
