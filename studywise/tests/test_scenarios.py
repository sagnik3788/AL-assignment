from collections import deque

from app.agent import StudyAgent
from app.config import Settings
from app.llm import LLMError
from app.schemas import Action


def route(action, topic="photosynthesis", clarification=""):
    return {"action": action, "topic": topic, "subject": "biology", "difficulty": "beginner", "days": 5, "minutes_per_day": 30, "answer": "", "clarification": clarification, "rationale": "The student asked for this based on the current conversation."}


def generated(text):
    return {"text": text, "key_points": ["key idea"], "check_question": "What is the key idea?", "questions": [{"question": f"Question {i}", "choices": [], "answer": "answer", "explanation": "because"} for i in range(1, 4)], "study_days": [{"day": i, "goal": "Review", "estimated_minutes": 20} for i in range(1, 6)]}


class ScriptedLLM:
    enabled = True

    def __init__(self, *replies):
        self.replies = deque(replies)
        self.router_payloads = []

    def complete_json(self, **kwargs):
        if kwargs["schema_name"] == "study_action":
            self.router_payloads.append(kwargs["user"])
        reply = self.replies.popleft()
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_scenario_plan_then_quiz_then_feedback_uses_context():
    llm = ScriptedLLM(route("study_plan"), generated("Five-day plan"), route("quiz"), generated("Three questions and an answer key"), route("evaluate_answer"), generated("Correct core idea; add an example."))
    agent = StudyAgent(llm, Settings())
    history, state = [], {}
    outputs = []
    for message in ["Plan for my biology exam in five days", "Quiz me on the topic we planned", "My answer is that plants use light to make sugars"]:
        result = agent.respond(message, history, state)
        outputs.append(result)
        if result.data.get("topic"):
            state["last_topic"] = result.data["topic"]
        history.extend([{"role": "user", "content": message}, {"role": "assistant", "content": result.text}])
    assert [r.action for r in outputs] == [Action.STUDY_PLAN, Action.QUIZ, Action.EVALUATE_ANSWER]
    assert "photosynthesis" in llm.router_payloads[1]
    assert "photosynthesis" in llm.router_payloads[2]


def test_scenario_clarifies_then_acts_after_student_adds_context():
    llm = ScriptedLLM(route("clarify", topic="", clarification="Which subject and test date should I plan for?"), route("study_plan", topic="algebra"), generated("A short algebra plan"))
    agent = StudyAgent(llm, Settings())
    first = agent.respond("Help me prepare for my test", [], {})
    second = agent.respond("Algebra, next Friday; 20 minutes daily", [{"role": "assistant", "content": first.text}], {})
    assert first.action == Action.CLARIFY
    assert second.action == Action.STUDY_PLAN


def test_scenario_provider_failure_then_user_retry_recovers():
    llm = ScriptedLLM(LLMError("timeout"), route("explain_topic"), generated("Gravity attracts masses."))
    agent = StudyAgent(llm, Settings())
    failed = agent.respond("Explain gravity", [], {})
    recovered = agent.respond("Please try again: explain gravity", [], {})
    assert failed.action == Action.CLARIFY
    assert "try again" in failed.text
    assert recovered.action == Action.EXPLAIN_TOPIC
