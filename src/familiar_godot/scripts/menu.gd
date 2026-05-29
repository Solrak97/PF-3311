extends Control

const CHAT_A_SCENE := "res://scenes/chat_a.tscn"
const CHAT_B_SCENE := "res://scenes/chat_b.tscn"

@onready var _start_a: Button = %StartAButton
@onready var _start_b: Button = %StartBButton
@onready var _quit: Button = %QuitButton


func _ready() -> void:
	ExperimentUI.apply(self)
	ExperimentUI.setup_menu_screen($Background, $Center/Card, _quit)
	ExperimentUI.configure_window(get_window())
	_start_a.pressed.connect(func() -> void:
		_get_to_scene(CHAT_A_SCENE)
	)
	_start_b.pressed.connect(func() -> void:
		_get_to_scene(CHAT_B_SCENE)
	)
	_quit.pressed.connect(func() -> void:
		get_tree().quit()
	)


func _get_to_scene(scene_path: String) -> void:
	var err := get_tree().change_scene_to_file(scene_path)
	if err != OK:
		push_error("Could not load scene: %s (%s)" % [scene_path, err])
