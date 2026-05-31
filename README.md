# PF-3311 — Familiaridad conductual en agentes virtuales inteligentes

**Efecto de la familiaridad conductual en agentes conversacionales sobre la percepción del usuario**

| | |
|---|---|
| **Código** | PF-3311 |
| **Investigador principal** | Luis Carlos Quesada Rodríguez |
| **Unidad** | Escuela de Ciencias de la Computación e Informática, Universidad de Costa Rica |
| **Estado** | Investigación y prototipado |

---

## Resumen

Los agentes conversacionales actuales suelen sonar coherentes, pero poco **familiares** a nivel cognitivo: adaptan su estilo al usuario en el momento o usan patrones genéricos, sin apoyarse en **modelos mentales** que la persona ya tiene sobre alguien conocido.

Este proyecto explora si un agente puede inducir percepción de familiaridad alineando su **comportamiento comunicativo** (lenguaje, tono, ritmo, expresiones) con una persona de referencia — **sin** depender de la apariencia ni de revelar la identidad modelada. La familiaridad debería emerger del comportamiento, no del avatar.

```
Usuario → Agente con patrones de persona conocida → Se activa el modelo mental del usuario
```

En contraste con la alineación reactiva habitual:

```
Usuario → Agente se adapta al usuario → Estilo genérico o superficial
```

---

## Preguntas de investigación

| ID | Pregunta |
|----|----------|
| **RQ1** | ¿En qué medida los usuarios infieren familiaridad conductual sin indicaciones explícitas de identidad? |
| **RQ2** | ¿Cómo influyen esos patrones en naturalidad y presencia social percibidas? |
| **RQ3** | ¿Qué respuesta afectiva (valencia, cercanía) generan frente a un agente sin esos patrones? |
| **RQ4** | ¿El agente se percibe con conocimiento contextual previo sobre el usuario? |

Detalle metodológico e instrumentos: [`docs/protocolo_evaluacion.tex`](docs/protocolo_evaluacion.tex) (PDF: [`docs/protocolo_de_evaluacion.pdf`](docs/protocolo_de_evaluacion.pdf)).

---

## Diseño experimental

Estudio **intra-sujetos** con **contrabalanceo** de orden:

| Grupo | Orden |
|-------|--------|
| 1 | Condición A → Condición B |
| 2 | Condición B → Condición A |

- **Condición A (experimental):** mismo avatar y voz neutros; conversación con **patrones de familiaridad conductual** y recuperación contextual asociada al perfil modelado.
- **Condición B (control):** misma interfaz, avatar, voz y tarea; comportamiento conversacional **genérico**, sin perfil de familiaridad.

Cada sesión: conversación semi-estructurada (~5 min) sobre temas cotidianos. Tras cada interacción: Godspeed, SAM, Likert de familiaridad conductual e ítems de conocimiento contextual percibido. Al cierre: entrevista cualitativa breve.

**Guía operativa para el investigador en sala:** [`docs/guia_procedimiento.html`](docs/guia_procedimiento.html) (checklist, guiones, manejo de datos anonimizados).

---

## Arquitectura del sistema

### Visión (propuesta de investigación)

Dos capas desacopladas:

| Capa | Rol |
|------|-----|
| **Cliente (Godot)** | Única interfaz con el usuario: entrada texto/voz, embodiment 3D, animación, reproducción de audio |
| **Backend (Python)** | Orquestación, LLM, STT/TTS, memoria, perfiles conductuales (YAML + prompting) |

Componentes previstos en la propuesta ([`docs/proposal.tex`](docs/proposal.tex)):

| Módulo | Tecnología (objetivo) |
|--------|------------------------|
| Razonamiento | Gemini |
| STT | Whisper |
| TTS | Edge-TTS |
| Memoria a largo plazo | Memoria (estilo LLM-wiki / Karpathy) |
| Control conductual | Perfiles YAML + capa de comportamiento |

El avatar es **genérico** a propósito: no debe parecerse a la persona modelada; la hipótesis se prueba vía conducta, no identidad visual.

### Prototipo implementado (`src/`)

Implementación actual para desarrollo y pruebas locales del flujo **Buddy**:

| Componente | Implementación actual |
|------------|------------------------|
| Cliente | Godot 4.6 — [`src/familiar_godot/`](src/familiar_godot/) |
| Backend | FastAPI + WebSocket — [`src/backend/`](src/backend/) |
| LLM | **Ollama** (local; intercambiable por API compatible) |
| TTS | **Edge-TTS** (audio MP3 por frames binarios en WebSocket) |
| STT / VAD | Interfaces + Whisper (`faster-whisper`); mic en roadmap |
| Logging | SQLite (`turns` + `sessions`) — dashboard en `/research/dashboard` |
| Memoria / perfiles YAML | Pendiente |

Flujo del prototipo:

1. En Godot: configurar **Participant ID** y **Order** en el menú; iniciar Chat A o B.
2. El usuario escribe; cada turno se guarda (mensaje + respuesta) en SQLite.
3. WebSocket → backend: streaming de texto (Ollama), animación, TTS en segmentos.
4. Godot muestra el texto, reproduce audio y refleja `clip_id`. Al cerrar sesión, el cliente envía duración y conteo de mensajes.
5. Investigador: revisar o borrar datos en `http://127.0.0.1:8000/research/dashboard`.

Instrucciones de ejecución: [`src/README.md`](src/README.md).

---

## Estructura del repositorio

```
PF-3311/
├── docs/
│   ├── proposal.tex              # Propuesta de investigación
│   ├── protocolo_evaluacion.tex  # Diseño metodológico y condiciones A/B
│   ├── protocolo_de_evaluacion.pdf
│   ├── guia_procedimiento.html   # Guía del investigador en sesión
│   └── references.bib
├── src/
│   ├── familiar_godot/           # Cliente Godot
│   └── backend/                  # Servicio Python (uv)
└── README.md
```

---

## Inicio rápido (prototipo)

Requisitos: [Ollama](https://ollama.com/), [uv](https://docs.astral.sh/uv/), Godot 4.6+, red para Edge-TTS.

```bash
# 1. Modelo local (ajuste OLLAMA_MODEL en .env si usa otro tag)
ollama pull llama3.1

# 2. Backend
cd src/backend
uv sync
copy .env.example .env   # Windows; en Unix: cp .env.example .env
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 3. Godot: abrir src/familiar_godot/project.godot, F5 (menú). Configurar Participant ID y Order antes de Chat A/B.

# Dashboard (mismos datos que SQLite en src/backend/data/experiment.db):
# http://127.0.0.1:8000/research/dashboard
```

Prueba por terminal:

```bash
cd src/backend
uv run python scripts/test_ws_turn.py "Hola, ¿cómo estás?"
```

---

## Documentación

| Documento | Contenido |
|-----------|-----------|
| [`docs/proposal.tex`](docs/proposal.tex) | Marco teórico, problema, arquitectura objetivo, RQs |
| [`docs/protocolo_evaluacion.tex`](docs/protocolo_evaluacion.tex) | Condiciones A/B, diseño, matriz metodológica |
| [`docs/guia_procedimiento.html`](docs/guia_procedimiento.html) | Protocolo en sala, consentimiento, cuestionarios, cierre |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Estado de implementación y siguientes hitos técnicos |
| [`src/README.md`](src/README.md) | Detalle técnico del prototipo |
| [`src/backend/README.md`](src/backend/README.md) | API, variables de entorno, dependencias |

---

## Obetivos del proyecto

- Tratar la **familiaridad como variable de diseño** controlable en agentes conversacionales.
- Ir más allá de la adaptación reactiva superficial hacia la **activación de modelos mentales preexistentes**.
- Construir un banco experimental (agente + protocolo + instrumentos) para estudios con usuarios en condiciones A/B.

---

## Trabajo en curso

- [ ] Perfiles conductuales (YAML) y capa de comportamiento sobre el LLM
- [ ] Integración de memoria contextual (Memoria o equivalente)
- [ ] Entrada por voz (Whisper + endpointing / VAD)
- [x] Logging de sesiones y mensajes + dashboard de investigación
- [x] Participant ID y orden A-B / B-A en menú Godot
- [ ] Modo experimental A/B conmutables desde configuración (condiciones ya separadas en escenas)
- [ ] Estudios con participantes según [`docs/guia_procedimiento.html`](docs/guia_procedimiento.html)

---

## Referencia

Proyecto de investigación — Universidad de Costa Rica. Propuesta y protocolo en `docs/`; implementación de referencia en `src/`.
