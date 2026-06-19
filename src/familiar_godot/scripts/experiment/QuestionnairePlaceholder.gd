extends Control

const MAIN_SCENE := "res://scenes/main.tscn"
const ORCHESTRATOR_SCENE := "res://scenes/experiment/ExperimentSessionMode.tscn"

var _after_interaction: int = 1
var _sliders: Dictionary = {}
var _submitting: bool = false
var _continue_btn: Button
var _retry_btn: Button
var _status_label: Label
var _last_responses: Dictionary = {}


func _ready() -> void:
	_after_interaction = ExperimentSessionManager.questionnaire_after_interaction
	ExperimentSessionManager.log_run_event("questionnaire_start", {
		"questionnaire_after_interaction": _after_interaction,
	})
	if not ExperimentApi.request_finished.is_connected(_on_api_finished):
		ExperimentApi.request_finished.connect(_on_api_finished)

	var interaction_idx := _after_interaction
	var title := "Cuestionario post-interacción"
	var subtitle := _build_subtitle(interaction_idx)

	var ui := QuestionnaireUIHelper.mount_questionnaire(self, title, subtitle)
	var content: VBoxContainer = ui["content"]
	var footer: HBoxContainer = ui["footer"]

	_build_sam_section(content)
	_build_closeness_section(content)
	_build_godspeed_section(content)
	_build_familiarity_section(content)
	_build_context_section(content)

	_status_label = Label.new()
	_status_label.text = ""
	_status_label.add_theme_color_override("font_color", ExperimentUI.MUTED)
	_status_label.add_theme_font_size_override("font_size", 13)
	footer.add_child(_status_label)

	var continue_label := (
		"Continuar a Interacción 2"
		if _after_interaction == 1
		else "Continuar a entrevista final"
	)
	QuestionnaireUIHelper.add_footer_button(footer, "Salir de la sesión", false, _confirm_exit_early)
	_retry_btn = QuestionnaireUIHelper.add_footer_button(footer, "Reintentar guardado", false, _retry_submit)
	_retry_btn.visible = false
	_continue_btn = QuestionnaireUIHelper.add_footer_button(footer, continue_label, true, _on_submit)


func _build_subtitle(interaction_idx: int) -> String:
	var part := "Interacción %d completada." % interaction_idx
	var timing := (
		"Responde según la charla que acabas de tener. Luego continuarás con la segunda interacción."
		if interaction_idx == 1
		else "Responde según la segunda charla. Tus respuestas se guardan al continuar."
	)
	return "%s %s" % [part, timing]


func _build_sam_section(parent: Control) -> void:
	var section := QuestionnaireUIHelper.add_section(
		parent,
		"Estado emocional (SAM)",
		"Indica cómo te sentiste durante la charla con el agente (escala del 1 al 9). "
		+ "Se refiere a tu estado de ánimo y energía en ese momento, no a otros tipos de respuesta.",
		"RQ3",
	)
	for scale in ExperimentQuestionnaireData.SAM_SCALES:
		QuestionnaireUIHelper.add_sam_item(section, scale, _sliders)


func _build_closeness_section(parent: Control) -> void:
	var section := QuestionnaireUIHelper.add_section(
		parent,
		"Cercanía percibida",
		"Marca tu nivel de acuerdo con cada afirmación (1 = totalmente en desacuerdo, 7 = totalmente de acuerdo).",
		"RQ3",
	)
	for item in ExperimentQuestionnaireData.CLOSENESS_ITEMS:
		QuestionnaireUIHelper.add_likert_item(
			section,
			str(item.get("id", "")),
			str(item.get("text", "")),
			_sliders,
		)


func _build_godspeed_section(parent: Control) -> void:
	var section := QuestionnaireUIHelper.add_section(
		parent,
		"Godspeed — percepción del agente",
		"Para cada par de palabras, marca dónde ubicarías al agente (1 = izquierda, 5 = derecha).",
		"RQ2",
	)
	for gs_section in ExperimentQuestionnaireData.GODSPEED_SECTIONS:
		var sub := Label.new()
		sub.text = str(gs_section.get("title", ""))
		sub.add_theme_font_size_override("font_size", 17)
		sub.add_theme_color_override("font_color", Color(0.28, 0.3, 0.36))
		section.add_child(sub)
		for item in gs_section.get("items", []):
			if item is Dictionary:
				QuestionnaireUIHelper.add_semantic_item(
					section,
					str(item.get("id", "")),
					str(item.get("left", "")),
					str(item.get("right", "")),
					_sliders,
				)
		var spacer := Control.new()
		spacer.custom_minimum_size.y = 8
		section.add_child(spacer)


func _build_familiarity_section(parent: Control) -> void:
	var section := QuestionnaireUIHelper.add_section(
		parent,
		"Familiaridad conductual",
		"Sin pensar en quién podría estar detrás del agente, ¿qué tan familiar te resultó su forma de interactuar?",
		"RQ1",
	)
	for item in ExperimentQuestionnaireData.FAMILIARITY_ITEMS:
		QuestionnaireUIHelper.add_likert_item(
			section,
			str(item.get("id", "")),
			str(item.get("text", "")),
			_sliders,
		)


func _build_context_section(parent: Control) -> void:
	var section := QuestionnaireUIHelper.add_section(
		parent,
		"Conocimiento contextual percibido",
		"¿En qué medida el agente pareció conocer tu contexto o situación?",
		"RQ4",
	)
	for item in ExperimentQuestionnaireData.CONTEXT_KNOWLEDGE_ITEMS:
		QuestionnaireUIHelper.add_likert_item(
			section,
			str(item.get("id", "")),
			str(item.get("text", "")),
			_sliders,
		)


func _collect_responses() -> Dictionary:
	var out: Dictionary = {}
	for key in _sliders:
		var slider: HSlider = _sliders[key]
		out[key] = int(slider.value)
	return out


func _questionnaire_api_payload(responses: Dictionary) -> Dictionary:
	return {
		"run_session_id": ExperimentSessionManager.session_id,
		"session_id": ExperimentSessionManager.interaction_session_id(),
		"participant_id": ExperimentSessionManager.participant_id,
		"condition": ExperimentSessionManager.current_condition,
		"order_group": ExperimentSessionManager.assigned_order_label,
		"interaction_index": _after_interaction,
		"questionnaire_after_interaction": _after_interaction,
		"profile_id": ExperimentSessionManager.active_profile_id(),
		"scenario_id": ExperimentSessionManager.scenario_id_for_interaction(_after_interaction),
		"responses": responses,
	}


func _save_questionnaire_local(responses: Dictionary) -> void:
	var dir := "user://experiment_logs/questionnaires"
	DirAccess.make_dir_recursive_absolute(dir)
	var path := "%s/%s-i%d.json" % [
		dir,
		ExperimentSessionManager.session_id,
		_after_interaction,
	]
	var payload := _questionnaire_api_payload(responses)
	payload["saved_at"] = Time.get_datetime_string_from_system(true)
	payload["backend_synced"] = false
	var w := FileAccess.open(path, FileAccess.WRITE)
	if w != null:
		w.store_string(JSON.stringify(payload, "\t"))
		w.close()


func _mark_questionnaire_local_synced() -> void:
	var path := "user://experiment_logs/questionnaires/%s-i%d.json" % [
		ExperimentSessionManager.session_id,
		_after_interaction,
	]
	if not FileAccess.file_exists(path):
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if parsed is Dictionary:
		parsed["backend_synced"] = true
		var w := FileAccess.open(path, FileAccess.WRITE)
		if w != null:
			w.store_string(JSON.stringify(parsed, "\t"))
			w.close()


func _set_submitting(active: bool) -> void:
	_submitting = active
	if _continue_btn != null:
		_continue_btn.disabled = active
	if _retry_btn != null:
		_retry_btn.disabled = active
	if _status_label != null and active:
		_status_label.text = "Guardando respuestas…"


func _on_submit() -> void:
	if _submitting:
		return
	var responses := _collect_responses()
	_last_responses = responses
	var local_payload := {
		"questionnaire_after_interaction": _after_interaction,
		"interaction_index": _after_interaction,
		"responses": responses,
	}
	_save_questionnaire_local(responses)
	ExperimentSessionManager.log_run_event("questionnaire_responses", local_payload)
	_set_submitting(true)
	if _retry_btn != null:
		_retry_btn.visible = false
	ExperimentApi.post_questionnaire(_questionnaire_api_payload(responses))


func _retry_submit() -> void:
	if _last_responses.is_empty():
		_on_submit()
		return
	_set_submitting(true)
	ExperimentApi.post_questionnaire(_questionnaire_api_payload(_last_responses))


func _on_api_finished(action: String, success: bool, _data: Variant, error: String) -> void:
	if action != "questionnaire" or not _submitting:
		return
	_set_submitting(false)
	if not success:
		if _status_label != null:
			_status_label.text = (
				"No se pudo guardar en el servidor (%s). "
				+ "Copia local guardada — pulsa Reintentar."
			) % error
		if _retry_btn != null:
			_retry_btn.visible = true
		push_warning("questionnaire_save_failed: %s" % error)
		return
	_mark_questionnaire_local_synced()
	if _after_interaction == 1:
		_continue_to_interaction_2()
	else:
		_finish_test()


func _continue_to_interaction_2() -> void:
	ExperimentSessionManager.log_run_event("questionnaire_mid_complete", {"interaction_index": 1})
	ExperimentSessionManager.begin_interaction(2)
	ExperimentSessionManager.log_run_event("interaction_start", {"interaction_index": 2})
	get_tree().change_scene_to_file(ORCHESTRATOR_SCENE)


func _finish_test() -> void:
	ExperimentSessionManager.complete_final_questionnaire()
	get_tree().change_scene_to_file(ORCHESTRATOR_SCENE)


func _confirm_exit_early() -> void:
	ExperimentExitHelper.confirm_exit(self, _exit_early)


func _exit_early() -> void:
	ExperimentSessionManager.exit_run_early("questionnaire_ui")
	get_tree().change_scene_to_file(ORCHESTRATOR_SCENE)
