class_name ExperimentPrompts
extends RefCounted

const PROMPTS: Array[Dictionary] = [
	{
		"prompt_id": "p01",
		"category": "recent_day",
		"prompt": "Cuéntame brevemente cómo fue tu día.",
	},
	{
		"prompt_id": "p02",
		"category": "daily_routine",
		"prompt": "¿Qué sueles hacer después de trabajar o estudiar?",
	},
	{
		"prompt_id": "p03",
		"category": "preferences",
		"prompt": "Háblame de algo que te guste mucho últimamente.",
	},
	{
		"prompt_id": "p04",
		"category": "casual_opinion",
		"prompt": "¿Qué opinas de tener que hacer trámites o tareas aburridas?",
	},
	{
		"prompt_id": "p05",
		"category": "good_news_reaction",
		"prompt": "¿Cómo reaccionarías si un amigo te cuenta una buena noticia?",
	},
	{
		"prompt_id": "p06",
		"category": "annoying_situation_reaction",
		"prompt": "¿Cómo reaccionarías si algo pequeño pero molesto arruina tu día?",
	},
	{
		"prompt_id": "p07",
		"category": "explaining_to_friend",
		"prompt": "Explícale a un amigo algo que sabes hacer bien.",
	},
	{
		"prompt_id": "p08",
		"category": "giving_advice",
		"prompt": "Dale un consejo casual a alguien que tuvo un día pesado.",
	},
	{
		"prompt_id": "p09",
		"category": "casual_banter",
		"prompt": "Responde de forma casual a alguien que te cuenta algo gracioso.",
	},
	{
		"prompt_id": "p10",
		"category": "conversation_closing",
		"prompt": "Despídete como normalmente cerrarías una conversación.",
	},
]

const RATING_KEYS: Array[String] = [
	"tone_similarity",
	"phrasing_similarity",
	"response_length_similarity",
	"behavioral_consistency",
	"reminds_me_of_person",
	"naturalness",
	"identity_leakage_absent",
]
