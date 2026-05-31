class_name ExperimentScreenHelper
extends RefCounted

const MENU_SCENE := "res://scenes/experiment/ExperimentMenu.tscn"


static func mount(root: Control, title: String) -> Dictionary:
	ExperimentUI.apply(root)
	ExperimentUI.configure_window(root.get_window())
	var bg := ColorRect.new()
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = ExperimentUI.WINDOW_BG
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(bg)
	var page := MarginContainer.new()
	page.set_anchors_preset(Control.PRESET_FULL_RECT)
	page.add_theme_constant_override("margin_left", 24)
	page.add_theme_constant_override("margin_top", 24)
	page.add_theme_constant_override("margin_right", 24)
	page.add_theme_constant_override("margin_bottom", 24)
	root.add_child(page)
	var scroll := ScrollContainer.new()
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	page.add_child(scroll)
	var scroll_body := VBoxContainer.new()
	scroll_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(scroll_body)
	var center := CenterContainer.new()
	center.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll_body.add_child(center)
	var card := PanelContainer.new()
	center.add_child(card)
	card.add_theme_stylebox_override("panel", ExperimentUI.viewport_panel())
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 36)
	margin.add_theme_constant_override("margin_top", 36)
	margin.add_theme_constant_override("margin_right", 36)
	margin.add_theme_constant_override("margin_bottom", 36)
	card.add_child(margin)
	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 14)
	vbox.custom_minimum_size = Vector2(520, 0)
	margin.add_child(vbox)
	var title_label := Label.new()
	title_label.text = title
	title_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title_label.add_theme_font_size_override("font_size", 26)
	title_label.add_theme_color_override("font_color", Color(0.18, 0.2, 0.26))
	vbox.add_child(title_label)
	var status := Label.new()
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	status.add_theme_color_override("font_color", Color(0.45, 0.48, 0.55))
	vbox.add_child(status)
	var content := VBoxContainer.new()
	content.add_theme_constant_override("separation", 10)
	content.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_child(content)
	return {
		"content": content,
		"status": status,
		"vbox": vbox,
	}


static func add_labeled_option(parent: Control, label_text: String) -> OptionButton:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	var label := Label.new()
	label.text = label_text
	label.custom_minimum_size = Vector2(140, 0)
	row.add_child(label)
	var option := OptionButton.new()
	option.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(option)
	parent.add_child(row)
	return option


static func add_labeled_line(parent: Control, label_text: String, placeholder: String = "") -> LineEdit:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	var label := Label.new()
	label.text = label_text
	label.custom_minimum_size = Vector2(140, 0)
	row.add_child(label)
	var edit := LineEdit.new()
	edit.placeholder_text = placeholder
	edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(edit)
	parent.add_child(row)
	return edit


static func add_button(parent: Control, text: String, callback: Callable) -> Button:
	var btn := Button.new()
	btn.text = text
	btn.pressed.connect(callback)
	parent.add_child(btn)
	return btn


static func go_to(scene_path: String) -> void:
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null:
		return
	var err := tree.change_scene_to_file(scene_path)
	if err != OK:
		push_error("Scene change failed: %s (%s)" % [scene_path, err])
