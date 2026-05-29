# Roadmap — Familiarity-Driven Agent Implementation

Last updated: 2026-05-28

This roadmap tracks implementation status for the experimental artifact (`src/`) and backend.

## 1. Core Conversation Loop
- [x] Godot client sends user message to backend.
- [x] Backend receives message with `participant_id`, `condition`, and conversation state fields.
- [ ] Backend calls Gemini for response generation.
- [x] Response is returned to Godot.
- [x] Godot displays agent text response.
- [x] Logs are stored per participant/session/condition (SQLite turn logs).

## 2. Experimental Conditions
- [ ] Implement Condition A: agent with familiarity behavioral profile.
- [ ] Implement Condition B: same agent with generic behavior.
- [x] Add condition switch: `A` or `B` (menu route to Chat A / Chat B).
- [x] Add order support: `A -> B` and `B -> A` payload field.
- [ ] Ensure same avatar, UI, voice, timing, and task across conditions (formalized and enforced).

## 3. Behavioral Profile System
- [ ] Define YAML schema for familiar user profile.
- [ ] Include fields: tone, formality, expressions, response length, humor, emotional expressiveness, pacing, topics/context facts.
- [ ] Load YAML profile in backend.
- [ ] Inject profile into prompt only in Condition A.
- [ ] Use generic prompt in Condition B.

## 4. Agentic Skill / Retrieval
- [ ] Add skill for retrieving familiar user info.
- [ ] Connect skill to profile data or Memoria.
- [ ] Allow retrieval of contextual facts during conversation.
- [ ] Prevent explicit identity leakage unless intentionally allowed.
- [ ] Log retrieval usage.

## 5. Memoria Integration
- [ ] Store conversation history by participant/session.
- [x] Store condition metadata (per turn logs).
- [ ] Store retrieved profile/context snippets.
- [x] Keep participant data anonymizable (ID-based logging).
- [ ] Separate experimental logs from development logs.

## 6. Voice Support
- [x] Implement text-only flow first.
- [ ] Add Whisper AI for STT in runtime path.
- [x] Add Edge-TTS for generated speech.
- [ ] Keep voice identical across A and B by explicit experiment guardrails.

## 7. Godot Agent Client
- [ ] Basic humanoid/generic avatar (currently UI + text/audio shell).
- [x] Text console/chat interface.
- [x] Optional talking/animation hint path (`anim.command`).
- [x] Audio playback with chunk queue.
- [x] Condition hidden from participant (main menu route; no inline A/B selector in chat scene).
- [x] Session timer (10 minutes in chat scene).

## 8. Experiment Logging
- [x] Save participant ID.
- [x] Save order group: `A-B` or `B-A`.
- [x] Save condition per interaction.
- [x] Save transcript (user + assistant text per turn).
- [x] Save agent response metadata (model + audio error count + timestamps).
- [ ] Save profile/retrieval usage flags from real profile/retrieval modules (currently placeholders).

## 9. Researcher Operations
- [x] Research dashboard to inspect sessions and turns.
- [x] Restart experiment flow from chat to menu.
- [x] Dockerized backend + Ollama compose stack.
- [ ] One-command bootstrap script for demo day (Windows + optional Linux/macOS variant).

## Next Recommended Milestone
1. Implement explicit Condition A/B prompt split.
2. Add YAML profile loader and schema.
3. Wire retrieval module and audit logs.
4. Enforce experiment invariants (voice/settings parity across A/B).
