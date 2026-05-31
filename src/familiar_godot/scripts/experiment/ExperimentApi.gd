extends Node

signal request_finished(action: String, success: bool, data: Variant, error: String)

const DEFAULT_BASE := "http://127.0.0.1:8000"

var mock_mode: bool = false
var _http: HTTPRequest
var _pending_action: String = ""
var _pending_body: Dictionary = {}


func _ready() -> void:
	_http = HTTPRequest.new()
	add_child(_http)
	_http.request_completed.connect(_on_request_completed)
	var env_mock: String = OS.get_environment("FAMILIAR_MOCK_API").strip_edges().to_lower()
	mock_mode = env_mock in ["1", "true", "yes"]


func base_url() -> String:
	var env := OS.get_environment("FAMILIAR_BACKEND_HTTP").strip_edges()
	if env.is_empty():
		env = DEFAULT_BASE
	return env.rstrip("/")


func post_raw_profile(payload: Dictionary) -> void:
	_post_json("/profiles/raw", payload, "post_raw")


func get_behavioral_profile(profile_id: String) -> void:
	var path := "/profiles/behavioral/%s" % profile_id.uri_encode()
	_get_json(path, "get_behavioral", {"profile_id": profile_id})


func list_profiles() -> void:
	_get_json("/profiles", "list_profiles")


func post_validation_generate_sample(profile_id: String, prompt: String) -> void:
	_post_json(
		"/profiles/validation/generate-sample",
		{"profile_id": profile_id, "prompt": prompt},
		"generate_sample"
	)


func post_validation(payload: Dictionary) -> void:
	_post_json("/profiles/validation", payload, "post_validation")


func post_experiment_chat(payload: Dictionary) -> void:
	_post_json("/experiment/chat", payload, "experiment_chat")


func interview_start(profile_id: String, modeled_user_alias: String) -> void:
	training_start(profile_id, modeled_user_alias, "interview_start")


func interview_turn(payload: Dictionary) -> void:
	training_answer(payload, "interview_turn")


func interview_save(payload: Dictionary) -> void:
	training_finalize(str(payload.get("profile_id", "")), "interview_save")


func interview_finish(profile_id: String) -> void:
	training_finish(profile_id, "interview_finish")


func training_start(profile_id: String, modeled_user_alias: String, action: String = "training_start") -> void:
	_post_json(
		"/profiles/training/start",
		{"profile_id": profile_id, "modeled_user_alias": modeled_user_alias},
		action
	)


func training_answer(payload: Dictionary, action: String = "training_answer") -> void:
	_post_json(
		"/profiles/training/answer",
		{
			"profile_id": payload.get("profile_id", ""),
			"user_message": payload.get("user_message", ""),
			"skip": payload.get("skip", false),
		},
		action
	)


func training_finalize(profile_id: String, action: String = "training_finalize") -> void:
	_post_json("/profiles/training/finalize", {"profile_id": profile_id}, action)


func training_finish(profile_id: String, action: String = "training_finish") -> void:
	_post_json("/profiles/training/finish", {"profile_id": profile_id}, action)


func validation_start(profile_id: String) -> void:
	_post_json("/profiles/validation/start", {"profile_id": profile_id}, "validation_start")


func validation_rating(payload: Dictionary) -> void:
	_post_json("/profiles/validation/rating", payload, "validation_rating")


func validation_finalize(profile_id: String) -> void:
	_post_json("/profiles/validation/finalize", {"profile_id": profile_id}, "validation_finalize")


const MOCK_INTERVIEW_QUESTIONS: Array[String] = [
	"Cuéntame brevemente cómo fue tu día.",
	"¿Qué sueles hacer después de trabajar o estudiar?",
	"Háblame de algo que te guste mucho últimamente.",
	"¿Qué opinas de tener que hacer trámites o tareas aburridas?",
	"¿Cómo reaccionarías si un amigo te cuenta una buena noticia?",
	"¿Cómo reaccionarías si algo pequeño pero molesto arruina tu día?",
	"Explícale a un amigo algo que sabes hacer bien.",
	"Dale un consejo casual a alguien que tuvo un día pesado.",
	"Responde de forma casual a alguien que te cuenta algo gracioso.",
	"Despídete como normalmente cerrarías una conversación.",
]


func _post_json(path: String, body: Dictionary, action: String) -> void:
	_pending_action = action
	_pending_body = body.duplicate(true)
	if mock_mode:
		call_deferred("_emit_mock", action, body)
		return
	var url := base_url() + path
	var headers := ["Content-Type: application/json"]
	var err := _http.request(url, headers, HTTPClient.METHOD_POST, JSON.stringify(body))
	if err != OK:
		request_finished.emit(action, false, {}, "http_request_failed:%s" % err)


func _get_json(path: String, action: String, body: Dictionary = {}) -> void:
	_pending_action = action
	_pending_body = body.duplicate(true)
	if mock_mode:
		call_deferred("_emit_mock", action, _pending_body)
		return
	var url := base_url() + path
	var err := _http.request(url)
	if err != OK:
		request_finished.emit(action, false, {}, "http_request_failed:%s" % err)


func _on_request_completed(
	result: int,
	response_code: int,
	_headers: PackedStringArray,
	body: PackedByteArray
) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or response_code < 200 or response_code >= 300:
		if not mock_mode:
			mock_mode = true
			_emit_mock(_pending_action, _pending_body)
			return
		request_finished.emit(_pending_action, false, {}, "http_%s" % response_code)
		return
	var parsed: Variant = JSON.parse_string(body.get_string_from_utf8())
	if parsed == null:
		request_finished.emit(_pending_action, false, {}, "invalid_json")
		return
	request_finished.emit(_pending_action, true, parsed, "")


func _emit_mock(action: String, body: Dictionary) -> void:
	match action:
		"post_raw":
			request_finished.emit(action, true, {"ok": true, "profile_id": body.get("profile_id", "")}, "")
		"get_behavioral":
			request_finished.emit(
				action,
				true,
				{
					"profile_id": body.get("profile_id", "demo"),
					"style_summary": "Mock behavioral profile for UI testing.",
					"samples": [],
				},
				""
			)
		"list_profiles":
			request_finished.emit(
				action,
				true,
				{"profile_ids": ProfileCatalog.list_local_raw_profile_ids()},
				""
			)
		"generate_sample":
			request_finished.emit(
				action,
				true,
				{
					"prompt": body.get("prompt", ""),
					"agent_response": "[MOCK] Gracias por contarme — suena interesante, cuéntame más.",
					"metadata": {"profile_used": true, "retrieval_used": false},
				},
				""
			)
		"post_validation":
			request_finished.emit(action, true, {"ok": true}, "")
		"experiment_chat":
			var history: Array = body.get("conversation_history", [])
			var user_msg := str(body.get("message", "")).strip_edges()
			var reply := "[MOCK] Entendido"
			if not user_msg.is_empty():
				reply = "[MOCK] (%s) Suena interesante — cuéntame un poco más." % user_msg.left(40)
			if history is Array and history.size() > 0:
				reply = "[MOCK] Sigo aquí contigo. " + reply
			request_finished.emit(
				action,
				true,
				{
					"text": reply,
					"metadata": {
						"condition": "A",
						"profile_id": body.get("profile_id", ""),
						"profile_used": true,
						"retrieval_used": false,
					},
				},
				""
			)
		"interview_start", "training_start":
			request_finished.emit(
				action,
				true,
				{
					"message": "[MOCK] Hola. Conversación abierta — sin número fijo de preguntas. Cuéntame, ¿cómo va tu día?",
					"prompt_index": 0,
					"total_prompts": 0,
					"open_ended": true,
					"complete": false,
					"samples": [],
					"sample_count": 0,
					"min_samples_to_finish": 3,
					"turn_mode": "interview",
					"conversation_history": [],
				},
				""
			)
		"interview_turn", "training_answer":
			request_finished.emit(action, true, _mock_interview_turn(body), "")
		"interview_finish", "training_finish":
			request_finished.emit(
				action,
				true,
				{
					"message": "[MOCK] Perfecto. Ya puedes guardar el perfil.",
					"complete": true,
					"total_prompts": 0,
					"open_ended": true,
					"turn_mode": "finish",
					"samples": [],
					"sample_count": 3,
					"min_samples_to_finish": 3,
				},
				""
			)
		"interview_save", "training_finalize":
			request_finished.emit(action, true, {"ok": true, "profile_id": body.get("profile_id", "")}, "")
		"validation_finalize":
			request_finished.emit(
				action,
				true,
				{
					"profile_id": body.get("profile_id", ""),
					"passed": true,
					"mean_similarity": 5.0,
					"mean_naturalness": 5.0,
					"mean_identity_safety": 6.0,
				},
				""
			)
		_:
			request_finished.emit(action, false, {}, "unknown_mock_action")


func _mock_interview_turn(body: Dictionary) -> Dictionary:
	var user_message := str(body.get("user_message", "")).strip_edges()
	var skip := bool(body.get("skip", false))
	var samples: Array = []
	if not skip and not user_message.is_empty():
		samples.append({
			"prompt_id": "mock_turn",
			"category": "open",
			"prompt": "[MOCK] Previous question",
			"response": user_message,
			"timestamp": Time.get_datetime_string_from_system(true),
		})
	var count := samples.size()
	var message := "[MOCK] Entendido."
	if count > 0 and count % 2 == 0:
		message = (
			"[MOCK] Ahora voy a tratar de imitarte y me dices qué te parece.\n\n"
			+ "Imagina que un amigo te pregunta cómo te fue el día.\n\n"
			+ "Yo diría algo como: «%s»\n\n"
			+ "¿Es esto algo que dirías?"
		) % user_message.left(60)
	elif count > 0:
		message = "[MOCK] Gracias. Cuéntame algo más sobre cómo sueles reaccionar ante noticias."
	return {
		"message": message,
		"prompt_index": count,
		"total_prompts": 0,
		"open_ended": true,
		"complete": false,
		"samples": samples,
		"sample_count": count,
		"min_samples_to_finish": 3,
		"sample_saved": not skip and not user_message.is_empty(),
		"turn_mode": "mirror" if count > 0 and count % 2 == 0 else "interview",
		"conversation_history": [],
	}
