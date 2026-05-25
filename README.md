# Familiarity-Driven AI Agent

## Overview

This project explores a novel approach to human-agent interaction based on behavioral familiarity.

Modern AI agents are capable of generating coherent and context-aware responses, but they often fail to produce interactions that feel personally meaningful, natural, or familiar to users. This project investigates whether it is possible to improve user perception by aligning agent behavior with mental models that users already possess about known individuals.

Instead of adapting to the current user dynamically, the agent is designed to behave as if it were a familiar person, leveraging patterns of communication associated with that individual.

---

## Research Motivation

Human social interaction relies heavily on mental models of other people. These models allow us to:

- Predict behavior
- Interpret intentions
- Infer emotional states
- Reduce uncertainty in communication

Familiarity plays a key role in this process.

However, current AI agents:

- Adapt reactively to user input
- Use generic conversational styles
- Do not leverage pre-existing social knowledge

This project proposes that:

> Familiarity can be induced by aligning agent behavior with a known individual, triggering existing mental models in the user.

---

## Core Idea

Instead of:
User → Agent adapts to User (reactive alignment)


We explore:


User → Agent behaves like Known Person → User activates mental model


This shifts the interaction from:

- reactive adaptation  
to  
- model-driven perception

---

## System Architecture

The system is divided into two main layers:

### 1. Client Application (Godot)

- Handles all user interaction
- Displays the agent (visual embodiment)
- Captures input (text / voice)
- Renders responses (text, voice, animation)

> Godot is the only layer that directly interacts with the user.

---

### 2. AI Backend

The backend processes requests and generates responses.

#### Components:

- **Orchestration Layer**
  - Coordinates all modules
  - Builds structured responses

- **LLM (Gemini)**
  - Core reasoning and response generation

- **Speech-to-Text (Whisper AI)**
  - Converts voice input into text

- **Text-to-Speech (Edge-TTS)**
  - Generates voice output

- **Memory System (Memoria)**
  - Stores long-term interaction data
  - Provides context beyond the current conversation

- **Skill System (YAML-based)**
  - Defines structured behaviors and rules

---

### 3. Behavioral Control Module

This is the key component of the project.

It modifies the agent’s behavior to reflect:

- Language style
- Tone
- Expression patterns
- Conversational structure

based on a **known individual**.

Unlike traditional approaches:

| Approach         | Behavior Source        |
|----------------|----------------------|
| Alignment       | Current user          |
| Mimicry         | Observed signals      |
| This project    | Pre-existing mental model |

---

## Interaction Flow

1. User provides input (text or voice)
2. Godot sends request to backend
3. Backend processes:
   - Context
   - Memory
   - Behavioral profile
4. LLM generates response
5. Behavioral module adjusts output
6. Response returned to Godot
7. Agent displays:
   - Text
   - Voice
   - Animation

---

## Embodiment Strategy

The agent includes a generic visual representation, but:

- It does NOT resemble the target person
- It avoids identity-based cues

This ensures that:

> Familiarity emerges from behavior, not appearance

---

## Research Questions

The system is designed to evaluate:

- Does behavioral familiarity increase perceived naturalness?
- Can users detect familiarity without explicit cues?
- What emotional responses are triggered?
- Is the agent perceived as having prior knowledge?

---

## Goals

- Explore familiarity as a controllable design variable
- Move beyond reactive adaptation in AI systems
- Build agents that feel more socially meaningful

---

## Tech Stack

| Component | Technology |
|----------|--------|
| Client | Godot Engine |
| LLM | Gemini (proposal) / **Ollama** (local prototype in `src/backend`) |
| STT | Whisper AI |
| TTS | Edge-TTS |
| Memory | Memoria |
| Behavior | YAML + Prompting |

---

## Local prototype (`src/`)

An interactive **Buddy** loop lives under [`src/`](src/README.md): a Godot client talks to a Python backend over **WebSocket** (streaming assistant text, animation hints, and **Edge-TTS** audio). See [`src/README.md`](src/README.md) for setup and run commands.

---

## Status

This project is currently in the research and prototyping phase.

---

## Future Work

- User studies and evaluation
- Behavioral profile refinement
- Multi-person modeling
- Cross-domain applications

---

## Author

Developed as part of a research proposal on familiarity-driven interaction in AI agents.