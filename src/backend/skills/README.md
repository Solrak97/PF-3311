# Backend skills

Skills follow a Cursor-style layout: each skill is a directory with a `skill.yaml` file.

| Skill | Path | Agent |
|-------|------|-------|
| Train profile | `train_profile/skill.yaml` | `app.agents.training_agent` |
| Converse with profile | `converse_with_profile/skill.yaml` | `app.agents.conversation_agent` |
| AI judge (testing) | `ai_judge/skill.yaml` | `app.agents.ai_judge` |
| Simulated participant | `simulated_participant/skill.yaml` | `app.agents.simulated_participant` |

## skill.yaml structure

```yaml
skill_id: my_skill
name: Human-readable name
description: What the skill does and when to use it.
templates:
  system: conversation_system.jinja2
memory:
  max_turns_ws: 8
  max_turns_http: 12
prompts: []   # training probes
cycles: []    # calibration cycles
safety_rules: []
```

Jinja templates live in `app/prompts/templates/`. Profiles are injected into templates as `profile_yaml`, `profile_style`, or `retrieval_snippets`.
