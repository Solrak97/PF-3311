# PF-3311 — Agente conversacional con familiaridad conductual

**Proyecto de investigación — Universidad de Costa Rica (ECCI)**  
*Efecto de la familiaridad conductual en agentes conversacionales sobre la percepción del usuario*

| | |
|---|---|
| **Código** | PF-3311 |
| **Investigador** | Luis Carlos Quesada Rodríguez |
| **Estado** | Prototipo funcional (investigación + PoC) |
| **Demo** | [Vídeo en YouTube](https://youtu.be/jj2V7gkvOVU) |

---

## Demo

Grabación del prototipo en funcionamiento (avatar Buddy, chat, voz y flujo experimental): **[https://youtu.be/jj2V7gkvOVU](https://youtu.be/jj2V7gkvOVU)**

---

## ¿De qué trata?

Muchos chatbots suenan coherentes pero **poco familiares**: se adaptan en el momento o usan un estilo genérico, sin activar el **modelo mental** que el usuario ya tiene de alguien conocido.

Este repositorio implementa un **agente 3D (“Buddy”)** para estudiar si la **familiaridad puede emerger del comportamiento** (tono, frases, ritmo), **sin** parecerse visualmente a la persona modelada ni decir explícitamente quién es.

**Diseño experimental (resumen):**

| Condición | Qué hace el agente |
|-----------|-------------------|
| **A (experimental)** | Conversa con un **perfil conductual entrenado** (familiaridad modelada). |
| **B (control)** | Mismo avatar, voz e interfaz; comportamiento **genérico** (`generic_control_agent`). |

El participante ve dos interacciones (~5 min c/u) en orden contrabalanceado (A→B o B→A), cuestionarios post-interacción en la app, entrevista breve final y logging en SQLite. Flujo: consentimiento → instrucciones → chat → cuestionario (×2) → entrevista.

**Stack del prototipo:**

| Pieza | Tecnología |
|-------|------------|
| Cliente | **Godot 4.6** — avatar VRM, chat, menú experimental |
| Backend | **FastAPI** + **WebSocket** + **LangGraph** |
| LLM | **Ollama** (por defecto) u API **OpenAI-compatible** |
| Voz (salida) | **Edge-TTS** (requiere internet) |
| Datos | **SQLite** + logs locales en Godot (`user://`) |

> La propuesta original menciona Gemini y Memoria; **en código hoy** el LLM es Ollama/compatible y la memoria es por sesión + perfil YAML (sin Memoria vectorial). Ver [`docs/ROADMAP.md`](docs/ROADMAP.md).

---

## Requisitos

| Para | Necesitas |
|------|-----------|
| **Backend con Docker** (recomendado) | [Docker Desktop](https://www.docker.com/products/docker-desktop/) + Docker Compose |
| **Cliente Godot** | [Godot 4.6](https://godotengine.org/download) (editor; no va en Docker) |
| **Backend sin Docker** | [uv](https://docs.astral.sh/uv/) + [Ollama](https://ollama.com/) en el host |
| **TTS** | Conexión a internet (Edge-TTS) |

---

## Cómo ejecutar el proyecto

### Opción A — Docker (backend + Ollama) ← **recomendado**

Desde la **raíz del repo**:

```powershell
# 1. Levantar backend y Ollama
docker compose up --build -d

# 2. Descargar el modelo (solo la primera vez; tarda varios minutos)
docker exec -it pf3311-ollama ollama pull llama3.1:latest

# 3. Comprobar que responde
curl http://127.0.0.1:8000/healthz
```

Deberías ver JSON con `"status":"ok"` y el modelo configurado.

| URL | Para qué |
|-----|----------|
| http://127.0.0.1:8000/healthz | Salud del API |
| http://127.0.0.1:8000/research/dashboard | Logs de sesiones, perfiles, borrado de datos |

**Parar / limpiar contenedores:**

```powershell
docker compose down          # para servicios
docker compose down -v       # además borra volúmenes (SQLite + modelos Ollama en Docker)
```

**LLM en el host (sin contenedor Ollama):**

```powershell
copy .env.docker.example .env
# Editar LLM_BASE_URL (p. ej. http://host.docker.internal:11434) y LLM_MODEL
docker compose -f docker-compose.external-llm.yml up --build -d
```

Variables LLM en Docker (opcional, `.env` en la raíz):

| Variable | Ejemplo | Uso |
|----------|---------|-----|
| `LLM_PROVIDER` | `ollama` / `openai_compat` | Cliente nativo Ollama o API compatible |
| `LLM_BASE_URL` | `http://ollama:11434` | URL del modelo |
| `LLM_MODEL` | `llama3.1:latest` | Nombre del modelo |
| `LLM_API_KEY` | *(vacío en Ollama local)* | Token si usas API remota |

---

### Opción B — Backend local (sin Docker)

```powershell
# Terminal 1 — Ollama (si no lo tienes ya corriendo)
ollama pull llama3.2
ollama serve

# Terminal 2 — Backend
cd src\backend
uv sync
copy .env.example .env
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Dashboard: http://127.0.0.1:8000/research/dashboard

Prueba rápida por terminal:

```powershell
cd src\backend
uv run python scripts\test_ws_turn.py "Hola"
```

---

### Cliente Godot (siempre necesario para la UI)

1. Abre **`src/familiar_godot/project.godot`** en Godot **4.6**.
2. Pulsa **F5** (escena principal: menú experimental).

**Antes de una sesión de estudio:**

1. **Experimental Setup → Assign Profiles** — elige el perfil para condición A.
2. **Experimental Run** — orden A-B o B-A, ID de participante, iniciar.

**Conexión al backend** (por defecto apunta a localhost):

```powershell
$env:FAMILIAR_BACKEND_WS  = "ws://127.0.0.1:8000/ws/session"
$env:FAMILIAR_BACKEND_HTTP = "http://127.0.0.1:8000"
# Opcional: forzar respuestas mock si el backend no está
# $env:FAMILIAR_MOCK_API = "1"
```

Si el backend corre en otra máquina de la red, sustituye `127.0.0.1` por la IP del servidor.

Guía del cliente: [`src/familiar_godot/README.md`](src/familiar_godot/README.md).

### Servidor Windows + cliente Mac (día del experimento)

En el **PC Windows** (servidor con GPU/Ollama), desde PowerShell **como Administrador** (para reglas de firewall):

```powershell
cd C:\Users\luisc\dev\PF-3311

# Primera vez: modelos en Docker
.\scripts\experiment-server.ps1 -Action Start -PullModels

# Días siguientes
.\scripts\experiment-server.ps1 -Action Start

# Al terminar el día
.\scripts\experiment-server.ps1 -Action Stop

# Comprobar estado
.\scripts\experiment-server.ps1 -Status
```

El script: abre firewall (8000 + 11434), desactiva suspensión en AC, levanta `docker compose` con modelos **keep_alive 24h**, precalienta chat + embeddings, e imprime la IP LAN para el Mac.

En el **Mac** (antes de abrir Godot):

```bash
source scripts/mac-client-env.sh <IP-del-PC-Windows>
# o: export PF3311_SERVER=192.168.x.x && source scripts/mac-client-env.sh
```

Verifica: `curl http://<IP>:8000/healthz`

| Máquina | Rol |
|---------|-----|
| PC Windows | `experiment-server.ps1 -Action Start` |
| Mac | Godot + `FAMILIAR_BACKEND_*` apuntando al PC |
| Investigador | `http://<IP-PC>:8000/research/dashboard` |

### Exportar el cliente (PCs del laboratorio)

El juego **no** va en Docker. Para participantes sin el editor:

1. Godot → **Project → Export** → **Windows Desktop** (u otro SO).
2. Exporta p. ej. `dist/PF3311-Client.exe`.
3. En cada PC, antes de abrir el `.exe`:

   ```powershell
   $env:FAMILIAR_BACKEND_WS = "ws://<IP-servidor>:8000/ws/session"
   .\PF3311-Client.exe
   ```

### Setup típico en sala

| Máquina | Rol |
|---------|-----|
| 1 servidor | `docker compose up` (backend + Ollama) |
| N laptops participantes | Export Godot + `FAMILIAR_BACKEND_WS` apuntando al servidor |
| Investigador | `http://<IP-servidor>:8000/research/dashboard` |

---

## Flujo mínimo de verificación

1. `docker compose up -d` + `ollama pull` (o backend local con Ollama).
2. `curl http://127.0.0.1:8000/healthz` → OK.
3. Godot F5 → **Experimental Setup → Train Profile** (opcional) o asignar perfil existente.
4. **Experimental Run** → chat de prueba; deberías ver texto en streaming y oír TTS.
5. Abre el **dashboard** y confirma que aparece la sesión.

---

## Estructura del repositorio

```
PF-3311/
├── docker-compose.yml          # backend + Ollama
├── docker-compose.external-llm.yml
├── docs/                       # propuesta, protocolo, roadmap
├── src/
│   ├── analysis/               # notebooks, informes y figuras del estudio
│   ├── backend/                # FastAPI, LangGraph, perfiles, SQLite
│   └── familiar_godot/         # cliente Godot 4.6
└── README.md
```

---

## Documentación

| Documento | Contenido |
|-----------|-----------|
| [Demo (YouTube)](https://youtu.be/jj2V7gkvOVU) | Vídeo del prototipo en uso |
| [`docs/proposal.tex`](docs/proposal.tex) | Marco teórico y arquitectura objetivo |
| [`docs/protocolo_evaluacion.tex`](docs/protocolo_evaluacion.tex) | Diseño A/B, métricas del estudio |
| [`docs/protocolo_de_evaluacion.pdf`](docs/protocolo_de_evaluacion.pdf) | Protocolo (PDF) |
| [`docs/guia_procedimiento.html`](docs/guia_procedimiento.html) | Guía en sala para el investigador |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Implementado vs pendiente |
| [`src/README.md`](src/README.md) | Detalle técnico `src/` |
| [`src/backend/README.md`](src/backend/README.md) | API HTTP/WebSocket, perfiles, env |

---

## Preguntas de investigación

| ID | Pregunta |
|----|----------|
| **RQ1** | ¿En qué medida los usuarios infieren familiaridad conductual sin indicaciones explícitas de identidad? |
| **RQ2** | ¿Cómo influyen esos patrones en naturalidad y presencia social percibidas? |
| **RQ3** | ¿Qué respuesta afectiva (valencia, cercanía) generan frente a un agente sin esos patrones? |
| **RQ4** | ¿El agente se percibe con conocimiento contextual previo sobre el usuario? |

---

## Problemas frecuentes

| Síntoma | Qué revisar |
|---------|-------------|
| Godot no conecta | Backend en `8000`, `FAMILIAR_BACKEND_WS`, firewall |
| Sin voz | Edge-TTS necesita internet; revisa logs del backend |
| Respuestas `[MOCK]` | Backend caído o `FAMILIAR_MOCK_API=1`; el cliente hace fallback automático |
| `healthz` falla en Docker | `docker compose ps`; espera a que Ollama termine el `pull` |
| WebSocket se corta en dev | No uses `--reload`; reinicia el backend a mano (`scripts/run_dev.ps1`) |
| Modelo no encontrado | `docker exec -it pf3311-ollama ollama pull llama3.1:latest` (o el tag de `docker-compose.yml`) |

---

## Licencia y créditos

Proyecto académico UCR. Assets VRM de terceros bajo sus licencias en `src/familiar_godot/landing/`. Código del prototipo en `src/` para reproducibilidad del estudio.
