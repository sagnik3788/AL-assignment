from collections import deque

from app.agent import StudyAgent
from app.config import Settings
from app.llm import LLMError
from app.schemas import Action


class FakeLLM:
    enabled = True

    def __init__(self, *responses):
        self.responses = deque(responses)
        self.calls = []

    def complete_json(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.popleft()
        if isinstance(response, Exception):
            raise response
        return response


def planned(action="study_plan", topic="photosynthesis", **kwargs):
    return {"action": action, "topic": topic, "subject": "biology", "difficulty": "beginner", "days": 5, "minutes_per_day": 30, "answer": "", "clarification": "", "rationale": "The student explicitly asked for this action."} | kwargs


def tool(text="A useful response"):
    return {"text": text, "key_points": ["core idea"], "check_question": "What is the main idea?", "questions": [{"question": f"Question {i}", "choices": [], "answer": "answer", "explanation": "because"} for i in range(1, 4)], "study_days": [{"day": i, "goal": "Review", "estimated_minutes": 20} for i in range(1, 6)]}


def test_routes_to_plan_and_returns_structured_data():
    llm = FakeLLM(planned(), tool())
    result = StudyAgent(llm, Settings()).respond("Plan biology for five days", [], {})
    assert result.action == Action.STUDY_PLAN
    assert result.data["topic"] == "photosynthesis"
    assert result.data["key_points"] == ["core idea"]
    assert len(llm.calls) == 2


def test_quiz_text_includes_questions_and_answer_key():
    llm = FakeLLM(planned("quiz"), tool("Three questions"))
    result = StudyAgent(llm, Settings()).respond("Quiz me on biology", [], {})
    assert "Practice questions" in result.text
    assert "Question 1" in result.text
    assert "Answer key" in result.text
    assert "because" in result.text


def test_study_plan_text_includes_each_validated_day():
    llm = FakeLLM(planned(), tool("A useful plan"))
    result = StudyAgent(llm, Settings()).respond("Make a 5-day biology plan", [], {})
    assert result.text.count("Day ") == 5
    assert "Review (20 min)" in result.text


def test_ambiguous_request_clarifies_without_calling_tool():
    llm = FakeLLM(planned("clarify", clarification="Which topic should we study?"))
    result = StudyAgent(llm, Settings()).respond("Help me study", [], {})
    assert result.action == Action.CLARIFY
    assert result.text == "Which topic should we study?"
    assert len(llm.calls) == 1


def test_context_and_state_are_included_in_router_input():
    llm = FakeLLM(planned("quiz"), tool("Three questions"))
    history = [{"role": "assistant", "content": "We planned photosynthesis."}]
    result = StudyAgent(llm, Settings()).respond("Quiz me on that", history, {"last_topic": "photosynthesis"})
    assert result.action == Action.QUIZ
    assert "photosynthesis" in llm.calls[0]["user"]


def test_invalid_model_tool_output_fails_closed():
    llm = FakeLLM(planned("explain_topic"), {"text": 17, "key_points": [], "check_question": "", "questions": [], "study_days": []})
    result = StudyAgent(llm, Settings()).respond("Explain gravity", [], {})
    assert result.action == Action.CLARIFY
    assert "couldn't complete" in result.text


def test_study_plan_cannot_exceed_daily_budget():
    too_long = tool()
    too_long["study_days"][0]["estimated_minutes"] = 45
    llm = FakeLLM(planned("study_plan", days=5, minutes_per_day=30), too_long)
    result = StudyAgent(llm, Settings()).respond("Make a five-day plan, 30 minutes per day", [], {})
    assert result.action == Action.CLARIFY
    assert "couldn't complete" in result.text


def test_external_service_failure_returns_recoverable_message():
    llm = FakeLLM(LLMError("network timeout"))
    result = StudyAgent(llm, Settings()).respond("Explain gravity", [], {})
    assert result.action == Action.CLARIFY
    assert "try again" in result.text


def test_demo_mode_is_explicit_and_deterministic():
    class Disabled:
        enabled = False

    agent = StudyAgent(Disabled(), Settings())
    first = agent.respond("Quiz me on photosynthesis", [], {})
    second = agent.respond("Quiz me on photosynthesis", [], {})
    assert agent.mode == "demo"
    assert first == second
    assert first.action == Action.QUIZ
