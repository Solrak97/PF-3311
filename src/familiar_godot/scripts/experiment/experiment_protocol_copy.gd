class_name ExperimentProtocolCopy
extends RefCounted

const CONSENT_TEXT := (
	"Participación voluntaria en el estudio piloto Suena Familiar. "
	+ "Puedes retirarte en cualquier momento sin consecuencias. "
	+ "Las respuestas se guardan con un identificador anónimo. "
	+ "No se te revelará qué persona modela el perfil conductual del agente. "
	+ "Al marcar la casilla y continuar, confirmas que leíste esta información y aceptas participar."
)

const INSTRUCTIONS_TEXT := (
	"Vas a conversar de forma natural con un asistente virtual durante unos cinco minutos. "
	+ "Puedes escribir por texto (y usar voz si está disponible). "
	+ "No hay respuestas correctas ni incorrectas. "
	+ "No se te indicará si el agente usa un perfil especial ni quién podría estar modelado. "
	+ "Cuando termine el tiempo, pulsa «Fin interacción» o espera a que el temporizador termine."
)

const EXIT_INTERVIEW_QUESTIONS: Array[String] = [
	"¿Qué diferencias notaste entre las dos conversaciones?",
	"¿Alguna te resultó más natural que la otra? ¿Por qué?",
	"¿Detectaste señales de familiaridad en alguna de las charlas?",
	"¿Sentiste que el agente te conocía de antes en algún momento?",
	"¿Algo más que quieras comentar?",
]
