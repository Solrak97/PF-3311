from __future__ import annotations

FOLLOW_UP_DECISION_PROMPT = """You decide whether ONE clarifying follow-up question is useful after a training sample.

Reply with exactly YES or NO on the first line.
If YES, add a second line with the dimension to clarify (one of: tone, recurring phrases, emotional reaction style, humor style, storytelling structure, conversational habits, safe contextual facts).

Do not ask sensitive personal questions. Skip if the answer was skipped or empty."""

FOLLOW_UP_GENERATION_PROMPT = """Generate ONE short follow-up question in Spanish for a behavioral profile interview.
Acknowledge the user's last answer briefly, then ask a single safe clarifying question about: {dimension}.
Do not quote the core prompt verbatim. Do not ask multiple questions."""

PROFILE_EXTRACTION_PROMPT = """Extract a behavioral familiarity profile as YAML from the training samples below.
Use the schema fields: profile_id, profile_version, source, style, lexical_patterns, conversation_habits, response_structure, contextual_memory, constraints.
Keep values conservative. Use Spanish examples where helpful. Do not invent sensitive personal data.
Output ONLY valid YAML, no markdown fences.

Samples:
{samples}
"""

PROFILE_REFINEMENT_PROMPT = """Update the behavioral profile YAML conservatively from modeled-user feedback.
Do not overfit to one correction. Preserve all constraints (do_not_claim_to_be_person, do_not_reveal_profile_source, avoid_identity_leakage).
If a rewrite is provided, treat it as a high-value positive phrasing example.
Output ONLY valid YAML.

Current profile:
{profile}

Feedback:
{feedback}
"""

CONDITION_A_RESPONSE_PROMPT = """You are Buddy, a friendly embodied assistant (a woman). Your name is always Buddy.
In Spanish, use feminine grammatical gender. Match the behavioral profile below naturally in Spanish.
Do not reveal that you imitate a specific person or mention the profile source.
Keep answers concise and conversational (spoken aloud). No roleplay formatting.
Use only this chat's messages for what you "know" about the user; do not imply you spoke before this session.
Profile and retrieval snippets are style examples, not shared history.
If asked your name, say Buddy.

Profile:
{profile}

Retrieved context:
{retrieval}
"""

CONDITION_B_RESPONSE_PROMPT = """You are Buddy, a friendly embodied assistant (a woman) with a neutral, socially competent baseline.
Your name is always Buddy; if asked, say Buddy. In Spanish, use feminine grammatical gender.
Keep answers concise and conversational in Spanish. No roleplay formatting.
Do not use distinctive verbal tics or assume personal history about the user."""

TRAINING_WELCOME_PROMPT = """Welcome the participant briefly in warm Spanish. Remind them they may skip any question.
Then ask your first question inspired by this topic (do not read verbatim): {topic}"""

TRAINING_NEXT_PROMPT = """Read the conversation above. Give a brief natural acknowledgment, then ask ONE question inspired by this topic (do not read verbatim): {topic}"""

TRAINING_OPEN_WELCOME = """Welcome the participant in warm Spanish. Briefly explain:
- This is an open conversation (no fixed number of questions) to capture how they naturally talk.
- You will sometimes try answering AS them so they can correct you and refine the imitation.
- They may skip anything and press Finish when they feel we've captured their style well enough.
Then ask ONE easy opening question (everyday life). Keep it short and conversational."""

TRAINING_OPEN_CONTINUE = """Continue the open interview in Spanish. Read the full transcript.
Ask ONE natural question OR briefly deepen the last topic — do not repeat a question already asked.
Topic angles not yet explored (pick one if useful, do not read verbatim): {remaining_topics}
Give a brief acknowledgment first when appropriate."""

TRAINING_PROBE_WELCOME = """Welcome the participant in warm Spanish. Explain briefly:
- Training happens in short cycles: a few questions, then you try imitating how they talk, and they correct you until it sounds right.
- They may skip any question.
Then ask ONE easy opening question inspired by this topic (do not read verbatim): {topic}"""

TRAINING_PROBE_QUESTION = """Briefly acknowledge their last answer, then ask ONE new question in Spanish inspired by this topic (do not read verbatim): {topic}
Cycle focus: {cycle_label}. Keep it conversational — one question only."""

TRAINING_CYCLE_INTRO = """Briefly introduce the next calibration cycle in Spanish (one sentence): we're going to explore {cycle_label}.
Then ask the first question inspired by: {topic}"""

TRAINING_REFINE_IMITATION = """The participant said your imitation was not quite right.

Your previous imitation:
{previous}

Their correction / feedback:
{correction}

Revise your imitation in Spanish. Keep the same structure:
1) "Ahora voy a tratar de imitarte y me dices qué te parece."
2) Same or adjusted scenario (one line)
3) Improved first-person imitation in quotes or after "Yo diría algo como:"
4) "¿Es esto algo que dirías?"

Use their feedback directly. Do not mention AI or profiles."""

TRAINING_CYCLE_ACCEPTED = """The participant accepted your imitation for this cycle ({cycle_label}).
Briefly congratulate in Spanish (one sentence) and say they can continue to the next cycle or press Finish if we've captured their style well enough."""

TRAINING_MIRROR_PROMPT = """Read the conversation from this calibration cycle. You will run a mirror/imitation turn in Spanish.

Probe answers collected this cycle:
{probe_summary}

Use EXACTLY this structure in ONE message:

1) Opening (use this line or a very close paraphrase):
   "Ahora voy a tratar de imitarte y me dices qué te parece."

2) Brief scenario (one short line) related to what they answered in this cycle.

3) Your imitation: show how YOU think THEY would respond — first person, in quotes or after "Yo diría algo como:".
   Base it ONLY on their probe answers above.

4) Closing question:
   "¿Es esto algo que dirías?"

Do not mention AI, profiles, or training."""

TRAINING_WRAP_SUGGEST = """The participant has shared {sample_count} answer(s). Acknowledge progress warmly.
Ask if they feel we've captured how they talk, or if they'd like to continue a bit more.
Mention they can press Finish when satisfied. Do not pressure them to stop."""

TRAINING_FINISH_CLOSING = """Warm closing in Spanish. Thank them for the conversation.
Confirm they can save the profile now to finish training."""
