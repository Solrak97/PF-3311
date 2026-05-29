# Landing assets

| Path | Use |
|------|-----|
| `naivee-friends_Explorers_Published/naivee-friends_Explorers_published.vrm` | **Active avatar** (naivee friends, CubiCot) |
| `naivee-friends_Explorers_Published/licenses/` | License PDFs (renamed from zip typo `licesnses`) |
| `OrangeBot_*` | Legacy robot (unused in `main.tscn`; kept for reference) |

Large archives (`*.zip`, `*.unitypackage`) are gitignored; keep the extracted `.vrm` for the project.

First clone: open the project in Godot 4.6+ (VRM plugins are in `addons/`) or run:

```bash
Godot_v4.exe --headless --path . --import
```
