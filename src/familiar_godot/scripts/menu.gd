extends Control

const CHAT_A_SCENE := "res://scenes/chat_a.tscn"
const CHAT_B_SCENE := "res://scenes/chat_b.tscn"

@onready var _participant_id: LineEdit = %ParticipantIdEdit
@onready var _order_select: OptionButton = %OrderSelect
@onready var _start_a: Button = %StartAButton
@onready var _start_b: Button = %StartBButton
@onready var _quit: Button = %QuitButton


func _ready() -> void:
	ExperimentUI.apply(self)
	ExperimentUI.setup_menu_screen($Background, $Center/Card, _quit, $Center/Card/Margin/VBox/SettingsPanel)
	ExperimentUI.configure_window(get_window())
	_setup_order_select()
	_load_settings()
	_participant_id.text_changed.connect(_on_participant_id_changed)
	_order_select.item_selected.connect(_on_order_selected)
	_start_a.pressed.connect(func() -> void:
		_get_to_scene(CHAT_A_SCENE)
	)
	_start_b.pressed.connect(func() -> void:
		_get_to_scene(CHAT_B_SCENE)
	)
	_quit.pressed.connect(func() -> void:
		get_tree().quit()
	)


func _setup_order_select() -> void:
	_order_select.clear()
	_order_select.add_item("A-B", 0)
	_order_select.add_item("B-A", 1)


func _load_settings() -> void:
	var pid := ParticipantSettings.load_participant_id()
	if pid.is_empty():
		pid = "p-%s" % _random_token()
		ParticipantSettings.save_participant_id(pid)
	_participant_id.text = pid
	var order := ParticipantSettings.load_order_group()
	_order_select.select(0 if order == "A-B" else 1)


func _save_settings() -> void:
	var pid := _participant_id.text.strip_edges()
	if pid.is_empty():
		pid = "p-%s" % _random_token()
		_participant_id.text = pid
	ParticipantSettings.save_participant_id(pid)
	var order := "A-B" if _order_select.selected == 0 else "B-A"
	ParticipantSettings.save_order_group(order)


func _on_participant_id_changed(_text: String) -> void:
	_save_settings()


func _on_order_selected(_index: int) -> void:
	_save_settings()


func _get_to_scene(scene_path: String) -> void:
	_save_settings()
	var err := get_tree().change_scene_to_file(scene_path)
	if err != OK:
		push_error("Could not load scene: %s (%s)" % [scene_path, err])


func _random_token() -> String:
	return "%08x%08x" % [randi(), randi()]
