import json
import logging
from typing import Any

from app.config import Settings
from app.llm import LLMError, OpenRouter
from app.schemas import Action, GeneratedToolOutput, PlannedAction, ToolResult

logger = logging.getLogger(__name__)

ROUTER_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "action": {"type": "string", "enum": [a.value for a in Action]},
        "topic": {"type": "string"}, "subject": {"type": "string"},
        "difficulty": {"type": "string", "enum": ["beginner", "intermediate", "advanced"]},
        "days": {"type": "integer", "minimum": 1, "maximum": 30},
        "minutes_per_day": {"type": "integer", "minimum": 1, "maximum": 1440},
        "answer": {"type": "string"}, "clarification": {"type": "string"}, "rationale": {"type": "string"},
    },
    "required": ["action", "topic", "subject", "difficulty", "days", "minutes_per_day", "answer", "clarification", "rationale"],
}
TOOL_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "text": {"type": "string"},
        "key_points": {"type": "array", "items": {"type": "string"}},
        "check_question": {"type": "string"},
        "questions": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {
            "question": {"type": "string"}, "choices": {"type": "array", "items": {"type": "string"}},
            "answer": {"type": "string"}, "explanation": {"type": "string"},
        }, "required": ["question", "choices", "answer", "explanation"]}},
        "study_days": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {
            "day": {"type": "integer", "minimum": 1, "maximum": 30}, "goal": {"type": "string"},
            "estimated_minutes": {"type": "integer", "minimum": 0, "maximum": 1440},
        }, "required": ["day", "goal", "estimated_minutes"]}},
    },
    "required": ["text", "key_points", "check_question", "questions", "study_days"],
}


class StudyAgent:
    def __init__(self, llm: OpenRouter, settings: Settings):
        self.llm = llm
        self.settings = settings

    @property
    def mode(self) -> str:
        return "openrouter" if self.llm.enabled else "demo"

    def respond(self, content: str, history: list[dict[str, str]], state: dict[str, Any]) -> ToolResult:
        if not self.llm.enabled:
            return self._demo_response(content, history, state)
        try:
            planned = self._route(content, history, state)
            if planned.action == Action.CLARIFY:
                return ToolResult(action=planned.action, text=planned.clarification or "What subject or topic should we work on?", rationale=planned.rationale or "The request lacks enough detail to choose a useful study action.")
            return self._run_tool(planned, content, history)
        except Exception as exc:
            logger.exception("Study workflow failed (%s)", type(exc).__name__)
            return ToolResult(action=Action.CLARIFY, text="I couldn't complete that reliably because the AI service returned an error. Please try again, or rephrase your request.", rationale=f"Workflow stopped safely after {type(exc).__name__}.")

    def _route(self, content: str, history: list[dict[str, str]], state: dict[str, Any]) -> PlannedAction:
        raw = self.llm.complete_json(
            system=("You are the intent router for a study assistant. Choose exactly one action. "
                    "Ask for clarification if the request is ambiguous or missing a topic. "
                    "Use conversation history and session state for follow-ups; never invent student preferences. "
                    "For study plans, extract explicit days and minutes per day; when the student gives no time budget, use a clearly disclosed 30-minute daily default. "
                    "Use evaluate_answer only when the student is responding to a quiz or question. "
                    "Do not answer the study request yourself. Include a short rationale tied to the wording or context."),
            user=json.dumps({"message": content, "recent_history": history, "session_state": state}),
            schema_name="study_action", schema=ROUTER_SCHEMA,
        )
        return PlannedAction.model_validate(raw)

    def _run_tool(self, planned: PlannedAction, content: str, history: list[dict[str, str]]) -> ToolResult:
        tools = {
            Action.STUDY_PLAN: self._study_plan_tool,
            Action.EXPLAIN_TOPIC: self._explain_topic_tool,
            Action.QUIZ: self._quiz_tool,
            Action.EVALUATE_ANSWER: self._evaluate_answer_tool,
        }
        return tools[planned.action](planned, content, history)

    def _study_plan_tool(self, planned, content, history):
        return self._generate_tool(planned, content, history, "Create exactly one plan entry per requested day. Keep each estimated_minutes at or below the requested daily budget; mention the 30-minute default if used. Populate study_days with day, goal, estimated_minutes. Use empty questions.")

    def _explain_topic_tool(self, planned, content, history):
        return self._generate_tool(planned, content, history, "Explain the topic at the requested level using an accurate example and one check question. Populate key_points; use empty questions and study_days.")

    def _quiz_tool(self, planned, content, history):
        return self._generate_tool(planned, content, history, "Create exactly three practice questions with choices (or empty choices), answer, and explanation. Put an answer key after questions. Match difficulty; use empty study_days.")

    def _evaluate_answer_tool(self, planned, content, history):
        return self._generate_tool(planned, content, history, "Evaluate fairly. Explain correct parts, improvements, and one next step. Do not invent a score. Use empty questions and study_days.")

    def _generate_tool(self, planned, content, history, instruction):
        raw = self.llm.complete_json(
            system=(instruction + " Return JSON with exactly: text, key_points, check_question, questions, and study_days. "
                    "Return all fields, using empty arrays for irrelevant action-specific fields. "
                    "Do not invent the student's age, ability, or preferences."),
            user=json.dumps({"request": content, "action": planned.model_dump(), "recent_history": history}),
            schema_name="study_result", schema=TOOL_SCHEMA,
        )
        output = GeneratedToolOutput.model_validate(raw)
        if planned.action == Action.QUIZ and len(output.questions) != 3:
            raise LLMError("Quiz tool must return exactly three questions")
        if planned.action == Action.STUDY_PLAN:
            if [day.day for day in output.study_days] != list(range(1, planned.days + 1)):
                raise LLMError("Study plan must contain one sequential entry for every requested day")
            if any(day.estimated_minutes > planned.minutes_per_day for day in output.study_days):
                raise LLMError("Study plan exceeds the requested daily time budget")
        data = {"topic": planned.topic, **output.model_dump(exclude={"text"})}
        return ToolResult(action=planned.action, text=self._format_tool_output(planned.action, output), data=data, rationale=planned.rationale or f"Selected {planned.action.value} based on the request and recent context.")

    @staticmethod
    def _format_tool_output(action: Action, output: GeneratedToolOutput) -> str:
        sections = [output.text.strip()]
        if action == Action.STUDY_PLAN and output.study_days:
            sections.append("Study plan\n" + "\n".join(
                f"Day {day.day} — {day.goal} ({day.estimated_minutes} min)" for day in output.study_days
            ))
        elif action == Action.QUIZ and output.questions:
            questions = []
            answers = []
            for index, question in enumerate(output.questions, 1):
                item = f"{index}. {question.question}"
                if question.choices:
                    item += "\n" + "\n".join(f"   {letter}. {choice}" for letter, choice in zip("ABCD", question.choices))
                questions.append(item)
                answers.append(f"{index}. {question.answer} — {question.explanation}")
            sections.append("Practice questions\n" + "\n".join(questions) + "\n\nAnswer key\n" + "\n".join(answers))
        elif action == Action.EXPLAIN_TOPIC:
            if output.key_points:
                sections.append("Key points\n" + "\n".join(f"• {point}" for point in output.key_points))
            if output.check_question:
                sections.append("Check your understanding\n" + output.check_question)
        elif action == Action.EVALUATE_ANSWER and output.key_points:
            sections.append("Next steps\n" + "\n".join(f"• {point}" for point in output.key_points))
        return "\n\n".join(section for section in sections if section)

    def _demo_response(self, content: str, history: list[dict[str, str]], state: dict[str, Any]) -> ToolResult:
        low = content.lower()
        if len(content.split()) < 3 and not history:
            return ToolResult(action=Action.CLARIFY, text="What subject or topic would you like help with? You can ask me to make a plan, explain a topic, or create a quiz.", rationale="The request is too vague to choose a useful study action.")
        topic = next((word for word in ["photosynthesis", "algebra", "gravity", "fractions", "python", "biology", "history"] if word in low), state.get("last_topic", "your topic"))
        if any(x in low for x in ["quiz", "practice question", "test me"]):
            action = Action.QUIZ
            text = f"Demo quiz on {topic}: 1) What is one key idea about {topic}? 2) Explain it in your own words. 3) Give a real-world example.\n\nReply with your answer and I’ll give feedback."
            data = {"topic": topic, "questions": [{"question": f"What is one key idea about {topic}?"}, {"question": f"Explain {topic} in your own words."}, {"question": f"Give an example of {topic}."}]}
        elif any(x in low for x in ["plan", "schedule", "study for"]):
            action = Action.STUDY_PLAN
            text = f"Demo 3-day plan for {topic}:\n1. Learn the core ideas (25 min).\n2. Work through examples (25 min).\n3. Review and self-test (25 min)."
            data = {"topic": topic, "days": [{"day": 1, "goal": "Learn core ideas"}, {"day": 2, "goal": "Practice examples"}, {"day": 3, "goal": "Review and self-test"}]}
        elif any(x in low for x in ["my answer", "i think", "because", "answer is"]):
            action = Action.EVALUATE_ANSWER
            text = "Demo feedback: You’ve shared an answer. Compare it with the key idea, then add a specific example to make your reasoning clearer."
            data = {"next_step": "Add a concrete example."}
        else:
            action = Action.EXPLAIN_TOPIC
            text = f"Demo explanation of {topic}: Start with the main idea, connect it to a concrete example, then explain the relationship in your own words. Configure OPENROUTER_API_KEY for generated topic-specific teaching."
            data = {"topic": topic, "check_question": f"Can you explain one key idea about {topic}?"}
        return ToolResult(action=action, text=text, data=data, rationale=f"Demo router selected {action.value} from the request wording; demo responses are deterministic and not model-generated.")
