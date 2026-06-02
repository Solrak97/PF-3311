extends Control

const ORCHESTRATOR_SCENE := "res://scenes/experiment/ExperimentSessionMode.tscn"
const MAIN_SCENE := "res://scenes/main.tscn"
const RUN_MENU := "res://scenes/experiment/ExperimentalRunMenu.tscn"

var _content: VBoxContainer
var _status: Label


func _ready() -> void:
	match ExperimentSessionManager.phase:
		ExperimentSessionManager.Phase.SETUP:
			_show_setup()
		ExperimentSessionManager.Phase.QUESTIONNAIRE:
			get_tree().change_scene_to_file(ExperimentSessionManager.QUESTIONNAIRE_SCENE)
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
	ExperimentScreenHelper.add_button(_content, "Iniciar sesión", func() -> void:
		var pid := participant.text.strip_edges()
		if pid.is_empty():
			_status.text = "El ID del participante es obligatorio."
			return
		ParticipantSettings.save_participant_id(pid)
		if not ParticipantSettings.profile_a_configured():
			_status.text = "Asigna el Perfil A en Configuración experimental primero."
			return
		ExperimentSessionManager.configure_run(pid, ExperimentSessionManager.order)
		ExperimentSessionManager.log_run_event("session_start")
		_start_interaction(1)
	)
	ExperimentScreenHelper.add_button(_content, "Salir de la sesión", _confirm_exit_early)
	ExperimentScreenHelper.add_button(_content, "Volver", func() -> void:
		ExperimentSessionManager.reset_run()
		ExperimentScreenHelper.go_to(RUN_MENU)
	)


func _start_interaction(index: int) -> void:
	ExperimentSessionManager.begin_interaction(index)
	ExperimentSessionManager.log_run_event("interaction_start", {"interaction_index": index})
	get_tree().change_scene_to_file(MAIN_SCENE)


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
		msg.text = "La sesión ha finalizado. Avise al investigador."
	_content.add_child(msg)
	ExperimentScreenHelper.add_button(_content, "Menú principal", func() -> void:
		ExperimentSessionManager.reset_run()
		ExperimentScreenHelper.go_to(ExperimentScreenHelper.MENU_SCENE)
	)


func _display_profile(profile_id: String) -> String:
	return profile_id if not profile_id.is_empty() else "(sin asignar — usa Asignar perfiles)"
