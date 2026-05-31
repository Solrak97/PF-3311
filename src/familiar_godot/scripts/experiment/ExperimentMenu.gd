extends Control

const SETUP_SCENE := "res://scenes/experiment/ExperimentalSetupMenu.tscn"
const RUN_SCENE := "res://scenes/experiment/ExperimentalRunMenu.tscn"


func _ready() -> void:
	var ui := ExperimentUI.setup_experiment_card(self, "PF-3311")
	var content: VBoxContainer = ui["content"]
	ExperimentScreenHelper.add_button(content, "Experimental Setup", func() -> void:
		ExperimentScreenHelper.go_to(SETUP_SCENE)
	)
	ExperimentScreenHelper.add_button(content, "Experimental Run", func() -> void:
		ExperimentScreenHelper.go_to(RUN_SCENE)
	)
	ExperimentScreenHelper.add_button(content, "Quit", func() -> void:
		get_tree().quit()
	)
