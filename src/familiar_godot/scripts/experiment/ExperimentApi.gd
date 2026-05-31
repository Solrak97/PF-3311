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
	_post_json(
		"/profiles/interview/start",
		{"profile_id": profile_id, "modeled_user_alias": modeled_user_alias},
		"interview_start"
	)


func interview_turn(payload: Dictionary) -> void:
	_post_json("/profiles/interview/turn", payload, "interview_turn")


func interview_save(payload: Dictionary) -> void:
	_post_json("/profiles/interview/save", payload, "interview_save")


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
			request_finished.emit(
				action,
				true,
				{
					"text": "[MOCK] Hola, estoy aquí para conversar contigo.",
					"metadata": {"condition": body.get("condition", "B"), "profile_used": false},
				},
				""
			)
		"interview_start":
			request_finished.emit(
				action,
				true,
				{
					"message": "[MOCK] Hola. Puedes saltar cualquier pregunta. " + MOCK_INTERVIEW_QUESTIONS[0],
					"prompt_index": 0,
					"total_prompts": MOCK_INTERVIEW_QUESTIONS.size(),
					"complete": false,
					"samples": [],
				},
				""
			)
		"interview_turn":
			request_finished.emit(action, true, _mock_interview_turn(body), "")
		"interview_save":
			request_finished.emit(action, true, {"ok": true, "profile_id": body.get("profile_id", "")}, "")
		_:
			request_finished.emit(action, false, {}, "unknown_mock_action")


func _mock_interview_turn(body: Dictionary) -> Dictionary:
	var idx := int(body.get("prompt_index", 0))
	var samples: Array = body.get("samples", [])
	if samples == null:
		samples = []
	var user_message := str(body.get("user_message", "")).strip_edges()
	var skip := bool(body.get("skip", false))
	var total := MOCK_INTERVIEW_QUESTIONS.size()
	if not skip and not user_message.is_empty() and idx >= 0 and idx < total:
		samples.append({
			"prompt_id": "mock_%d" % idx,
			"category": "mock",
			"prompt": MOCK_INTERVIEW_QUESTIONS[idx],
			"response": user_message,
			"timestamp": Time.get_datetime_string_from_system(true),
		})
	var next_idx := idx + 1
	var complete := next_idx >= total
	var message := "[MOCK] Gracias. Pulsa Guardar para crear el perfil."
	if not complete:
		message = "[MOCK] Entendido. " + MOCK_INTERVIEW_QUESTIONS[next_idx]
	return {
		"message": message,
		"prompt_index": next_idx,
		"total_prompts": total,
		"complete": complete,
		"samples": samples,
		"sample_saved": not skip and not user_message.is_empty(),
	}
