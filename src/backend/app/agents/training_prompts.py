from __future__ import annotations

CORE_TRAINING_PROMPTS: list[dict[str, str]] = [
    {"id": "daily_routine", "category": "routine", "text": "Cuéntame brevemente cómo fue tu día."},
    {"id": "after_work", "category": "routine", "text": "¿Qué sueles hacer después de trabajar o estudiar?"},
    {"id": "current_interest", "category": "preferences", "text": "Háblame de algo que te guste mucho últimamente."},
    {"id": "boring_tasks", "category": "opinion", "text": "¿Qué opinas de tener que hacer trámites o tareas aburridas?"},
    {"id": "good_news", "category": "emotional_reaction", "text": "¿Cómo reaccionarías si un amigo te cuenta una buena noticia?"},
    {"id": "annoying_situation", "category": "emotional_reaction", "text": "¿Cómo reaccionarías si algo pequeño pero molesto arruina tu día?"},
    {"id": "explain_to_friend", "category": "explanation", "text": "Explícale a un amigo algo que sabes hacer bien."},
    {"id": "advice", "category": "advice", "text": "Dale un consejo casual a alguien que tuvo un día pesado."},
    {"id": "banter", "category": "casual_banter", "text": "Responde de forma casual a alguien que te cuenta algo gracioso."},
    {"id": "closing", "category": "closing", "text": "Despídete como normalmente cerrarías una conversación."},
]

FOLLOW_UP_DIMENSIONS: tuple[str, ...] = (
    "tone",
    "recurring phrases",
    "emotional reaction style",
    "humor style",
    "storytelling structure",
    "conversational habits",
    "safe contextual facts",
)
