from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class RegistrationIn(ConsentsIn):
    model_config = ConfigDict(extra="forbid")
    birth_year: int = Field(strict=True, ge=1, le=9999)
    birth_month: int = Field(strict=True, ge=1, le=12)
    gender: Literal["male", "female", "neither", "prefer_not_to_say"]
    adult_confirmed: bool = Field(strict=True)
    non_diagnostic_confirmed: bool = Field(strict=True)

    @model_validator(mode="after")
    def validate_registration(self):
        current = datetime.now(ZoneInfo("Asia/Tokyo"))
        if (self.birth_year, self.birth_month) > (current.year, current.month):
            raise ValueError("future birth month")
        if not self.adult_confirmed or not self.non_diagnostic_confirmed:
            raise ValueError("registration confirmations required")
        return self
