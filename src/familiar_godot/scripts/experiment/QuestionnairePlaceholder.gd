extends Control

const MAIN_SCENE := "res://scenes/main.tscn"
const ORCHESTRATOR_SCENE := "res://scenes/experiment/ExperimentSessionMode.tscn"


func _ready() -> void:
	var after: int = ExperimentSessionManager.questionnaire_after_interaction
	var title: String
	var body: String
	var continue_label: String
	if after == 1:
		title = "Cuestionario — entre interacciones"
		body = (
			"Has completado la Interacción 1.\n\n"
			+ "[Marcador de posición] Aquí irán las preguntas del cuestionario "
			+ "entre la primera y la segunda interacción.\n\n"
			+ "Cuando termines, continúa con la Interacción 2."
		)
		continue_label = "Continuar a Interacción 2"
	else:
		title = "Cuestionario — final"
		body = (
			"Has completado la Interacción 2.\n\n"
			+ "[Marcador de posición] Aquí irán las preguntas del cuestionario "
			+ "final del experimento.\n\n"
			+ "Cuando termines, finaliza la sesión."
		)
		continue_label = "Finalizar prueba"

	var ui := ExperimentUI.setup_experiment_card(self, title)
	var content: VBoxContainer = ui["content"]
	var msg := Label.new()
	msg.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	msg.text = body
	content.add_child(msg)
	ExperimentScreenHelper.add_button(content, continue_label, func() -> void:
		if after == 1:
			_continue_to_interaction_2()
		else:
			_finish_test()
	)
	ExperimentScreenHelper.add_button(content, "Salir de la sesión", _confirm_exit_early)


func _continue_to_interaction_2() -> void:
	ExperimentSessionManager.log_run_event("questionnaire_mid_complete", {"interaction_index": 1})
	ExperimentSessionManager.begin_interaction(2)
	ExperimentSessionManager.log_run_event("interaction_start", {"interaction_index": 2})
	get_tree().change_scene_to_file(MAIN_SCENE)


func _finish_test() -> void:
	ExperimentSessionManager.complete_final_questionnaire()
	get_tree().change_scene_to_file(ORCHESTRATOR_SCENE)


func _confirm_exit_early() -> void:
	ExperimentExitHelper.confirm_exit(self, _exit_early)


func _exit_early() -> void:
	ExperimentSessionManager.exit_run_early("questionnaire_ui")
	get_tree().change_scene_to_file(ORCHESTRATOR_SCENE)
