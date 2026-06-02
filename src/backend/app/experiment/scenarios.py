from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_SCENARIO_ID = "daily_conversation"


@dataclass(frozen=True)
class ConversationScenario:
    scenario_id: str
    name: str
    participant_facing_title: str
    description: str
    conversation_goal: str
    suggested_topics: tuple[str, ...]
    agent_behaviors: tuple[str, ...]
    avoid: tuple[str, ...]
    estimated_duration_minutes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "participant_facing_title": self.participant_facing_title,
            "description": self.description,
            "conversation_goal": self.conversation_goal,
            "suggested_topics": list(self.suggested_topics),
            "agent_behaviors": list(self.agent_behaviors),
            "avoid": list(self.avoid),
            "estimated_duration_minutes": self.estimated_duration_minutes,
        }


SCENARIOS: dict[str, ConversationScenario] = {
    "daily_conversation": ConversationScenario(
        scenario_id="daily_conversation",
        name="Conversación cotidiana guiada",
        participant_facing_title="Conversación cotidiana",
        description=(
            "A semi-guided casual conversation about the participant's day, recent activities, "
            "and everyday experiences."
        ),
        conversation_goal=(
            "Maintain a natural casual conversation that allows conversational style, follow-up "
            "behavior, and contextual reactions to emerge. The participant may later judge stylistic "
            "similarity — but you must not imply you already know them or that you spoke before this chat."
        ),
        suggested_topics=(
            "how the participant's day has been",
            "recent activities",
            "daily routine",
            "something interesting, tiring, funny, or unusual that happened recently",
            "hobbies, interests, or casual preferences",
        ),
        agent_behaviors=(
            "open with a soft, neutral prompt suited to a first contact in this chat",
            "ask natural follow-up questions only about what the user said in this conversation",
            "react briefly before asking another question",
            "avoid interrogating the participant",
            "allow the user to lead topic changes",
            "keep responses concise",
            "use the active behavioral profile for tone, phrasing, humor, and warmth — not for fake shared memories",
        ),
        avoid=(
            "asking directly whether the agent feels familiar",
            "asking who the agent sounds like",
            "mentioning the modeled person",
            "mentioning profile, clone, imitation, condition A, condition B, or experiment hypothesis",
            "forcing emotional disclosure",
            "collecting sensitive personal information",
        ),
        estimated_duration_minutes=5,
    ),
    "casual_support": ConversationScenario(
        scenario_id="casual_support",
        name="Conversación de soporte casual",
        participant_facing_title="Conversación casual",
        description=(
            "A semi-guided conversation where the participant may discuss a mildly positive, tiring, "
            "frustrating, or curious everyday situation."
        ),
        conversation_goal=(
            "Observe how the agent reacts to everyday emotional content, provides casual support, "
            "asks follow-up questions, and maintains a natural conversational tone."
        ),
        suggested_topics=(
            "something tiring that happened recently",
            "something mildly frustrating",
            "something positive or satisfying",
            "something funny or curious",
            "a small decision or casual concern",
        ),
        agent_behaviors=(
            "respond with light emotional acknowledgment",
            "avoid giving clinical or therapeutic advice",
            "ask one natural follow-up when appropriate",
            "provide casual support without exaggeration",
            "keep responses natural and conversational",
            "use the active behavioral profile to determine reaction style, phrasing, warmth, humor, and advice style",
        ),
        avoid=(
            "making the conversation feel like therapy",
            "asking for sensitive personal details",
            "exaggerating emotional intimacy",
            "diagnosing or giving serious mental health advice",
            "mentioning familiarity, profile, clone, imitation, or condition labels",
            "revealing the modeled person identity",
        ),
        estimated_duration_minutes=5,
    ),
}


def resolve_scenario_id(scenario_id: str | None) -> str:
    cleaned = (scenario_id or "").strip()
    if cleaned in SCENARIOS:
        return cleaned
    return DEFAULT_SCENARIO_ID


def get_scenario(scenario_id: str | None) -> ConversationScenario:
    return SCENARIOS[resolve_scenario_id(scenario_id)]


def list_scenarios() -> list[dict[str, Any]]:
    return [scenario.to_dict() for scenario in SCENARIOS.values()]
