extends Control

const ORCHESTRATOR_SCENE := "res://scenes/experiment/ExperimentSessionMode.tscn"
const EXP_MENU := "res://scenes/experiment/ExperimentMenu.tscn"


func _ready() -> void:
	var ui := ExperimentUI.setup_experiment_card(self, "Experimental Run")
	var content: VBoxContainer = ui["content"]
	var hint := Label.new()
	hint.text = "Choose counterbalancing order for Interacción 1 and 2."
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	content.add_child(hint)
	ExperimentScreenHelper.add_button(content, "Order A → B", func() -> void:
		_prepare_run(["A", "B"])
	)
	ExperimentScreenHelper.add_button(content, "Order B → A", func() -> void:
		_prepare_run(["B", "A"])
	)
	ExperimentScreenHelper.add_button(content, "Back", func() -> void:
		ExperimentScreenHelper.go_to(EXP_MENU)
	)


func _prepare_run(order: Array[String]) -> void:
	ExperimentSessionManager.reset_run()
	ExperimentSessionManager.order = order
	ExperimentSessionManager.phase = ExperimentSessionManager.Phase.SETUP
	ExperimentScreenHelper.go_to(ORCHESTRATOR_SCENE)
