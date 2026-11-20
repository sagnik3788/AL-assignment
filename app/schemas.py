from enum import StrEnum

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Action(StrEnum):
    STUDY_PLAN = "study_plan"
    EXPLAIN_TOPIC = "explain_topic"
    QUIZ = "quiz"
    EVALUATE_ANSWER = "evaluate_answer"
    CLARIFY = "clarify"


class IncomingMessage(BaseModel):
    content: str = Field(min_length=1, max_length=6000)


class PlannedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Action
    topic: str
    subject: str
    difficulty: Literal["beginner", "intermediate", "advanced"]
    days: int = Field(ge=1, le=30)
    minutes_per_day: int = Field(ge=1, le=1440)
    answer: str
    clarification: str
    rationale: str


class GeneratedQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    choices: list[str]
    answer: str
    explanation: str


class StudyDay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: int = Field(ge=1, le=30)
    goal: str
    estimated_minutes: int = Field(ge=0, le=1440)


class GeneratedToolOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    key_points: list[str]
    check_question: str
    questions: list[GeneratedQuestion]
    study_days: list[StudyDay]


class ToolResult(BaseModel):
    action: Action
    text: str
    data: dict = Field(default_factory=dict)
    rationale: str


class MessageResponse(BaseModel):
    session_id: str
    action: Action
    response: str
    data: dict = Field(default_factory=dict)
    rationale: str
    mode: str
