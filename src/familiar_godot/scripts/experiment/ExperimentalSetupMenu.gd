extends Control

const TRAIN_SCENE := "res://scenes/experiment/TrainProfileMode.tscn"
const EVAL_SCENE := "res://scenes/experiment/EvaluateProfileMode.tscn"
const ASSIGN_SCENE := "res://scenes/experiment/AssignProfilesMode.tscn"
const EXP_MENU := "res://scenes/experiment/ExperimentMenu.tscn"

const _SCENARIO_LABELS := {
	"daily_conversation": "Conversación cotidiana",
	"casual_support": "Soporte casual",
}


func _ready() -> void:
	var ui := ExperimentUI.setup_experiment_card(self, "Configuración experimental")
	var content: VBoxContainer = ui["content"]
	_add_scenario_selectors(content)
	ExperimentScreenHelper.add_button(content, "Asignar perfiles (A / B)", func() -> void:
		ExperimentScreenHelper.go_to(ASSIGN_SCENE)
	)
	ExperimentScreenHelper.add_button(content, "Entrenar perfil", func() -> void:
		ExperimentScreenHelper.go_to(TRAIN_SCENE)
	)
	ExperimentScreenHelper.add_button(content, "Evaluar perfil", func() -> void:
		ExperimentScreenHelper.go_to(EVAL_SCENE)
	)
	ExperimentScreenHelper.add_button(content, "Volver", func() -> void:
		ExperimentScreenHelper.go_to(EXP_MENU)
	)


func _add_scenario_selectors(content: VBoxContainer) -> void:
	var hint := Label.new()
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.text = (
		"Escenarios conversacionales (solo investigador). "
		+ "Se aplican igual en condiciones A y B para cada interacción."
	)
	content.add_child(hint)
	_make_scenario_row(content, "Interacción 1", 1, ParticipantSettings.load_scenario_for_interaction(1))
	_make_scenario_row(content, "Interacción 2", 2, ParticipantSettings.load_scenario_for_interaction(2))


func _make_scenario_row(
	parent: VBoxContainer,
	label_text: String,
	interaction_index: int,
	selected_id: String
) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	var label := Label.new()
	label.text = label_text
	label.custom_minimum_size = Vector2(140, 0)
	row.add_child(label)
	var select := OptionButton.new()
	select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var selected_idx := 0
	for scenario_id in ParticipantSettings.VALID_SCENARIO_IDS:
		var title: String = _SCENARIO_LABELS.get(scenario_id, scenario_id)
		select.add_item(title)
		var idx := select.item_count - 1
		select.set_item_metadata(idx, scenario_id)
		if scenario_id == selected_id:
			selected_idx = idx
	select.select(selected_idx)
	select.item_selected.connect(func(_idx: int) -> void:
		var sid := str(select.get_item_metadata(select.selected))
		ParticipantSettings.save_scenario_for_interaction(interaction_index, sid)
	)
	parent.add_child(row)
