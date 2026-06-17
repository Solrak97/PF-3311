class_name ExperimentQuestionnaireData
extends RefCounted

## Post-interaction instruments mapped to research questions (methodology).

const LIKERT_MIN := 1
const LIKERT_MAX := 7
const GODSPEED_MIN := 1
const GODSPEED_MAX := 5
const SAM_MIN := 1
const SAM_MAX := 9

const SAM_SCALES: Array[Dictionary] = [
	{
		"id": "sam_valence",
		"construct": "RQ3",
		"title": "Valencia emocional",
		"left": "Muy desagradable",
		"right": "Muy agradable",
	},
	{
		"id": "sam_arousal",
		"construct": "RQ3",
		"title": "Nivel de activación",
		"left": "Muy calmado/a, con poca energía",
		"right": "Muy alerta, con mucha energía",
	},
	{
		"id": "sam_dominance",
		"construct": "RQ3",
		"title": "Sensación de control",
		"left": "Sin iniciativa en la conversación",
		"right": "Con iniciativa en la conversación",
	},
]

const CLOSENESS_ITEMS: Array[Dictionary] = [
	{"id": "closeness_warm", "text": "La interacción se sintió cercana y personal."},
	{"id": "closeness_connected", "text": "Me sentí conectado/a con el agente durante la charla."},
	{"id": "closeness_comfort", "text": "Me sentí cómodo/a hablando con el agente."},
]

const FAMILIARITY_ITEMS: Array[Dictionary] = [
	{"id": "fam_recognizable", "text": "La forma de hablar del agente me resultó reconocible."},
	{"id": "fam_familiar", "text": "El agente se sintió familiar (sin que me dijera quién imita)."},
	{"id": "fam_someone", "text": "El agente me recordó a alguien que conozco."},
	{"id": "fam_style", "text": "El estilo conversacional del agente parecía propio de una persona concreta."},
	{"id": "fam_implicit", "text": "Percibí señales de familiaridad aunque nadie me lo explicara."},
]

const CONTEXT_KNOWLEDGE_ITEMS: Array[Dictionary] = [
	{"id": "ctx_understood", "text": "El agente pareció entender mi situación y contexto."},
	{"id": "ctx_knew_me", "text": "El agente dio la impresión de conocerme de antes."},
	{"id": "ctx_trust", "text": "Confiaría en lo que el agente dijo en esta conversación."},
	{"id": "ctx_dependable", "text": "El agente se sintió predecible y coherente en cómo respondió."},
]

const GODSPEED_SECTIONS: Array[Dictionary] = [
	{
		"id": "godspeed_anthropomorphism",
		"title": "Antropomorfismo",
		"items": [
			{"id": "gs_anthro_fake", "left": "Artificial", "right": "Natural"},
			{"id": "gs_anthro_machine", "left": "Con aspecto de máquina", "right": "Con aspecto humano"},
			{"id": "gs_anthro_unconscious", "left": "Inconsciente", "right": "Consciente"},
			{"id": "gs_anthro_artificial", "left": "Artificial", "right": "Parece vivo"},
			{"id": "gs_anthro_rigid", "left": "Se mueve rígidamente", "right": "Se mueve con fluidez"},
		],
	},
	{
		"id": "godspeed_animacy",
		"title": "Animacidad",
		"items": [
			{"id": "gs_anim_dead", "left": "Muerto", "right": "Vivo"},
			{"id": "gs_anim_stagnant", "left": "Inactivo", "right": "Vivaz"},
			{"id": "gs_anim_mechanical", "left": "Mecánico", "right": "Orgánico"},
			{"id": "gs_anim_artificial", "left": "Artificial", "right": "Parece vivo"},
			{"id": "gs_anim_inert", "left": "Inerte", "right": "Interactivo"},
			{"id": "gs_anim_apathetic", "left": "Indiferente", "right": "Atento / responde"},
		],
	},
	{
		"id": "godspeed_likeability",
		"title": "Simpatía",
		"items": [
			{"id": "gs_like_dislike", "left": "No me gusta", "right": "Me gusta"},
			{"id": "gs_like_unfriendly", "left": "No amigable", "right": "Amigable"},
			{"id": "gs_like_unkind", "left": "Antipático", "right": "Amable"},
			{"id": "gs_like_unpleasant", "left": "Desagradable", "right": "Agradable"},
		],
	},
	{
		"id": "godspeed_intelligence",
		"title": "Inteligencia percibida",
		"items": [
			{"id": "gs_intel_incompetent", "left": "Incompetente", "right": "Competente"},
			{"id": "gs_intel_ignorant", "left": "Ignorante", "right": "Informado"},
			{"id": "gs_intel_irresponsible", "left": "Irresponsable", "right": "Responsable"},
			{"id": "gs_intel_unintelligent", "left": "Poco inteligente", "right": "Inteligente"},
			{"id": "gs_intel_foolish", "left": "Insensato", "right": "Sensato"},
		],
	},
	{
		"id": "godspeed_safety",
		"title": "Seguridad percibida (estado emocional)",
		"items": [
			{"id": "gs_safe_anxious", "left": "Ansioso/a", "right": "Relajado/a"},
			{"id": "gs_safe_agitated", "left": "Tranquilo/a", "right": "Agitado/a"},
			{"id": "gs_safe_quiescent", "left": "Sin sorpresas", "right": "Sorprendido/a"},
		],
	},
]
