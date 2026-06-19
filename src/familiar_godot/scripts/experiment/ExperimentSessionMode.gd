extends Control

const ORCHESTRATOR_SCENE := "res://scenes/experiment/ExperimentSessionMode.tscn"
const MAIN_SCENE := "res://scenes/main.tscn"
const RUN_MENU := "res://scenes/experiment/ExperimentalRunMenu.tscn"

var _content: VBoxContainer
var _status: Label
var _pending_participant_id: String = ""
var _exit_interview_fields: Array[TextEdit] = []


func _ready() -> void:
	if not ExperimentApi.request_finished.is_connected(_on_api_finished):
		ExperimentApi.request_finished.connect(_on_api_finished)
	if ExperimentApi.mock_mode:
		push_warning("FAMILIAR_MOCK_API activo: los cuestionarios no se guardan en SQLite.")
	match ExperimentSessionManager.phase:
		ExperimentSessionManager.Phase.SETUP:
			_show_setup()
		ExperimentSessionManager.Phase.INSTRUCTIONS:
			_show_instructions()
		ExperimentSessionManager.Phase.QUESTIONNAIRE:
			get_tree().change_scene_to_file(ExperimentSessionManager.QUESTIONNAIRE_SCENE)
		ExperimentSessionManager.Phase.EXIT_INTERVIEW:
			_show_exit_interview()
		ExperimentSessionManager.Phase.DONE:
			_show_end()
		ExperimentSessionManager.Phase.CHAT:
			_launch_chat()
		_:
			_show_setup()


func _mount(title: String) -> void:
	for child in get_children():
		child.queue_free()
	var ui := ExperimentUI.setup_experiment_card(self, title)
	_content = ui["content"]
	_status = ui["status"]


func _show_setup() -> void:
	_mount("Sesión experimental")
	ExperimentSessionManager.load_profile_config()
	var participant := ExperimentScreenHelper.add_labeled_line(_content, "ID del participante", "ej. P001")
	var saved_pid := ParticipantSettings.load_participant_id()
	if not saved_pid.is_empty():
		participant.text = saved_pid
	elif not ExperimentSessionManager.participant_id.is_empty():
		participant.text = ExperimentSessionManager.participant_id
	var profiles := Label.new()
	profiles.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	profiles.text = "Perfil A: %s\nControl (condición B): %s\nOrden: %s" % [
		_display_profile(ExperimentSessionManager.profile_a_id),
		ParticipantSettings.CONTROL_PROFILE_ID,
		"-".join(ExperimentSessionManager.order),
	]
	_content.add_child(profiles)
	if ExperimentApi.mock_mode:
		var mock_warn := Label.new()
		mock_warn.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		mock_warn.add_theme_color_override("font_color", Color(0.85, 0.45, 0.2))
		mock_warn.text = "Modo simulación API activo: no uses esto en sesiones reales."
		_content.add_child(mock_warn)
	var consent := CheckBox.new()
	consent.text = "Confirmo consentimiento informado"
	_content.add_child(consent)
	var consent_body := Label.new()
	consent_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	consent_body.add_theme_font_size_override("font_size", 13)
	consent_body.text = ExperimentProtocolCopy.CONSENT_TEXT
	_content.add_child(consent_body)
	ExperimentScreenHelper.add_button(_content, "Iniciar sesión", func() -> void:
		var pid := participant.text.strip_edges()
		if pid.is_empty():
			_status.text = "El ID del participante es obligatorio."
			return
		if not consent.button_pressed:
			_status.text = "Marca el consentimiento informado para continuar."
			return
		ParticipantSettings.save_participant_id(pid)
		if not ParticipantSettings.profile_a_configured():
			_status.text = "Asigna el Perfil A en Configuración experimental primero."
			return
		_pending_participant_id = pid
		_status.text = "Comprobando perfil en el servidor…"
		ExperimentApi.get_profile_status(ExperimentSessionManager.profile_a_id)
	)
	ExperimentScreenHelper.add_button(_content, "Salir de la sesión", _confirm_exit_early)
	ExperimentScreenHelper.add_button(_content, "Volver", func() -> void:
		ExperimentSessionManager.reset_run()
		ExperimentScreenHelper.go_to(RUN_MENU)
	)


func _show_instructions() -> void:
	_mount(ExperimentSessionManager.participant_interaction_label())
	var intro := Label.new()
	intro.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	intro.text = ExperimentSessionManager.participant_interaction_subtitle()
	_content.add_child(intro)
	var body := Label.new()
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.text = ExperimentProtocolCopy.INSTRUCTIONS_TEXT
	_content.add_child(body)
	ExperimentScreenHelper.add_button(_content, "Comenzar conversación", func() -> void:
		ExperimentSessionManager.enter_chat_after_instructions()
		ExperimentSessionManager.log_run_event("instructions_ack", {
			"interaction_index": ExperimentSessionManager.current_interaction_index,
		})
		get_tree().change_scene_to_file(MAIN_SCENE)
	)
	ExperimentScreenHelper.add_button(_content, "Salir de la sesión", _confirm_exit_early)


func _show_exit_interview() -> void:
	_mount("Entrevista breve")
	var hint := Label.new()
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.text = (
		"Gracias por completar ambas interacciones. "
		+ "Responde con tus propias palabras (puedes dejar en blanco lo que no aplique)."
	)
	_content.add_child(hint)
	_exit_interview_fields.clear()
	for question in ExperimentProtocolCopy.EXIT_INTERVIEW_QUESTIONS:
		var q := Label.new()
		q.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		q.text = question
		_content.add_child(q)
		var field := TextEdit.new()
		field.custom_minimum_size = Vector2(0, 72)
		field.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
		_content.add_child(field)
		_exit_interview_fields.append(field)
	ExperimentScreenHelper.add_button(_content, "Finalizar sesión", _submit_exit_interview)
	ExperimentScreenHelper.add_button(_content, "Salir sin guardar", _confirm_exit_early)


func _submit_exit_interview() -> void:
	var answers: Dictionary = {}
	for i in range(ExperimentProtocolCopy.EXIT_INTERVIEW_QUESTIONS.size()):
		var key := "q%d" % (i + 1)
		var text := ""
		if i < _exit_interview_fields.size():
			text = _exit_interview_fields[i].text.strip_edges()
		answers[key] = {
			"question": ExperimentProtocolCopy.EXIT_INTERVIEW_QUESTIONS[i],
			"answer": text,
		}
	ExperimentSessionManager.complete_exit_interview(answers)
	_show_end()


func _launch_chat() -> void:
	get_tree().change_scene_to_file(MAIN_SCENE)


func _confirm_exit_early() -> void:
	if not ExperimentSessionManager.is_run_active:
		ExperimentExitHelper.confirm_exit(self, func() -> void:
			ExperimentSessionManager.reset_run()
			ExperimentScreenHelper.go_to(RUN_MENU)
		)
		return
	ExperimentExitHelper.confirm_exit(self, _exit_early)


func _exit_early() -> void:
	ExperimentSessionManager.exit_run_early("orchestrator_ui")
	get_tree().change_scene_to_file(ORCHESTRATOR_SCENE)


func _show_end() -> void:
	_mount("Sesión finalizada")
	var msg := Label.new()
	msg.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	if ExperimentSessionManager.early_exit:
		msg.text = (
			"La sesión terminó antes de completar el protocolo. "
			+ "Avise al investigador."
		)
	else:
		msg.text = "La sesión ha finalizado. Gracias por participar."
	_content.add_child(msg)
	ExperimentScreenHelper.add_button(_content, "Menú principal", func() -> void:
		ExperimentSessionManager.reset_run()
		ExperimentScreenHelper.go_to(ExperimentScreenHelper.MENU_SCENE)
	)


func _on_api_finished(action: String, success: bool, data: Variant, error: String) -> void:
	if action != "profile_status":
		return
	if _pending_participant_id.is_empty():
		return
	if not success or not (data is Dictionary):
		_status.text = (
			"No se pudo verificar el perfil en el servidor (%s). "
			+ "¿Está el backend en marcha?"
		) % error
		return
	var has_profile := bool(data.get("has_behavioral")) or bool(data.get("has_yaml"))
	if not has_profile:
		_status.text = "El Perfil A no está en el servidor. Entrena/guarda el perfil antes del estudio."
		return
	if data.get("validation_passed") == false:
		_status.text = "La validación Fase 1 no aprobó este perfil. Corrige el perfil antes del estudio."
		_pending_participant_id = ""
		return
	if data.get("validation_passed") == null:
		push_warning("profile_without_validation: proceeding for pilot")
	ExperimentSessionManager.configure_run(
		_pending_participant_id,
		ExperimentSessionManager.order,
		with_consent = true,
	)
	ExperimentSessionManager.log_run_event("session_start", {"consent_confirmed": true})
	_pending_participant_id = ""
	_start_interaction(1)


func _start_interaction(index: int) -> void:
	ExperimentSessionManager.begin_interaction(index)
	ExperimentSessionManager.log_run_event("interaction_start", {"interaction_index": index})
	get_tree().change_scene_to_file(ORCHESTRATOR_SCENE)


func _display_profile(profile_id: String) -> String:
	return profile_id if not profile_id.is_empty() else "(sin asignar — usa Asignar perfiles)"
