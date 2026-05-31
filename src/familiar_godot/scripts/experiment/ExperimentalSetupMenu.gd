extends Control

const TRAIN_SCENE := "res://scenes/experiment/TrainProfileMode.tscn"
const EVAL_SCENE := "res://scenes/experiment/EvaluateProfileMode.tscn"
const ASSIGN_SCENE := "res://scenes/experiment/AssignProfilesMode.tscn"
const EXP_MENU := "res://scenes/experiment/ExperimentMenu.tscn"


func _ready() -> void:
	var ui := ExperimentUI.setup_experiment_card(self, "Experimental Setup")
	var content: VBoxContainer = ui["content"]
	ExperimentScreenHelper.add_button(content, "Assign Profiles (A / B)", func() -> void:
		ExperimentScreenHelper.go_to(ASSIGN_SCENE)
	)
	ExperimentScreenHelper.add_button(content, "Train Profile", func() -> void:
		ExperimentScreenHelper.go_to(TRAIN_SCENE)
	)
	ExperimentScreenHelper.add_button(content, "Evaluate Profile", func() -> void:
		ExperimentScreenHelper.go_to(EVAL_SCENE)
	)
	ExperimentScreenHelper.add_button(content, "Back", func() -> void:
		ExperimentScreenHelper.go_to(EXP_MENU)
	)
