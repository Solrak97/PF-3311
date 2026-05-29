# Familiar Godot client

Godot **4.6** UI + WebSocket client for the PF-3311 experiment.

## Avatar

**naivee friends** VRM (`landing/naivee-friends_Explorers_Published/`) — imported via [godot-vrm](https://github.com/V-Sekai/godot-vrm) in `addons/vrm` + `addons/Godot-MToon-Shader` (plugins enabled in `project.godot`).

### Editing camera, lights, and Buddy (important)

The buddy lives in a **SubViewport**, which is awkward to edit from `main.tscn`. Use the dedicated stage scene instead:

1. In **FileSystem**, open **`scenes/avatar_stage.tscn`** (double-click).
2. You get a normal **3D viewport** — move **Camera3D**, lights, and **Buddy** with the gizmos.
3. Press **F6** (*Run Current Scene*) to preview only the avatar stage.
4. Save — `main.tscn` instances this scene automatically inside the UI viewport.

Optional from `main.tscn`: select the **AvatarStage** node → click the **scene instance** icon (chain link) → **Open in Editor**.

Lighting / background / post-FX: edit `scenes/avatar_environment.tres` (SSAO, glow, color grading) or lights in `avatar_stage.tscn`.

**VSync** is on in `project.godot` (`display/window/vsync/vsync_mode=1`). Avatar SubViewport uses MSAA 4× + FXAA.

Each **Start Chat A / B** run creates a new `session_id` (fresh LLM context; turns stored under that id in SQLite). Use **＋ New chat** in the HUD anytime to clear the transcript and start another empty session without leaving the scene. Participant id is stable per machine (`user://familiar_participant_id.txt`) for research grouping only — it is not sent to the LLM as cross-session memory.

The game window starts **maximized** and UI uses `canvas_items` stretch (`aspect=expand`) so panels and chat scale with your display. The 3D avatar viewport resizes to fill the top card.

UI uses a shared warm gray palette via `scripts/experiment_ui.gd` (menu + chat). Edit colors there to retheme.

## Run (dev)

1. Start the backend (`src/backend` or Docker).
2. Open `project.godot` in Godot 4.6 (first open may reimport assets).
3. Press **F5** (`scenes/menu.tscn`).

Optional env before launch:

```powershell
$env:FAMILIAR_BACKEND_WS = "ws://127.0.0.1:8000/ws/session"
```

## Headless import (CI / fresh clone)

```powershell
& "C:\path\to\Godot_v4.exe" --headless --path "src\familiar_godot" --import
```

## Export

**Project → Export** → Windows Desktop. Ship with `FAMILIAR_BACKEND_WS` pointing at the lab server.

## License (naivee friends)

Non-commercial use; legal purchase from CubiCot / Booth. See `landing/naivee-friends_Explorers_Published/licenses/`.
