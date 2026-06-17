class_name QuestionnaireUIHelper
extends RefCounted

const CARD_WIDTH := 920
const SECTION_PAD := 22
const ITEM_SEP := 16


static func mount_questionnaire(root: Control, title: String, subtitle: String) -> Dictionary:
	ExperimentUI.apply(root)
	ExperimentUI.configure_window(root.get_window())
	var bg := ColorRect.new()
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = ExperimentUI.WINDOW_BG
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(bg)

	var page := MarginContainer.new()
	page.set_anchors_preset(Control.PRESET_FULL_RECT)
	page.add_theme_constant_override("margin_left", 32)
	page.add_theme_constant_override("margin_top", 28)
	page.add_theme_constant_override("margin_right", 32)
	page.add_theme_constant_override("margin_bottom", 28)
	root.add_child(page)

	var outer := VBoxContainer.new()
	outer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	outer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	outer.add_theme_constant_override("separation", 16)
	page.add_child(outer)

	var header := PanelContainer.new()
	header.add_theme_stylebox_override("panel", ExperimentUI.viewport_panel())
	outer.add_child(header)
	var header_margin := MarginContainer.new()
	_apply_margin(header_margin, 24, 20)
	header.add_child(header_margin)
	var header_col := VBoxContainer.new()
	header_col.add_theme_constant_override("separation", 8)
	header_margin.add_child(header_col)
	var title_label := Label.new()
	title_label.text = title
	title_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title_label.add_theme_font_size_override("font_size", 28)
	title_label.add_theme_color_override("font_color", Color(0.16, 0.18, 0.24))
	header_col.add_child(title_label)
	var subtitle_label := Label.new()
	subtitle_label.text = subtitle
	subtitle_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	subtitle_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	subtitle_label.add_theme_color_override("font_color", Color(0.42, 0.45, 0.52))
	subtitle_label.add_theme_font_size_override("font_size", 15)
	header_col.add_child(subtitle_label)

	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	outer.add_child(scroll)

	var center := CenterContainer.new()
	center.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(center)

	var content := VBoxContainer.new()
	content.custom_minimum_size.x = CARD_WIDTH
	content.add_theme_constant_override("separation", 24)
	center.add_child(content)

	var footer := HBoxContainer.new()
	footer.add_theme_constant_override("separation", 12)
	footer.alignment = BoxContainer.ALIGNMENT_END
	outer.add_child(footer)

	return {
		"content": content,
		"footer": footer,
		"subtitle": subtitle_label,
	}


static func add_section(parent: Control, title: String, description: String, construct_tag: String) -> VBoxContainer:
	var panel := PanelContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.add_theme_stylebox_override("panel", ExperimentUI.viewport_panel())
	parent.add_child(panel)

	var margin := MarginContainer.new()
	_apply_margin(margin, SECTION_PAD, SECTION_PAD)
	panel.add_child(margin)

	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", ITEM_SEP)
	margin.add_child(col)

	var head_row := HBoxContainer.new()
	head_row.add_theme_constant_override("separation", 10)
	col.add_child(head_row)

	var title_label := Label.new()
	title_label.text = title
	title_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title_label.add_theme_font_size_override("font_size", 20)
	title_label.add_theme_color_override("font_color", Color(0.2, 0.22, 0.28))
	head_row.add_child(title_label)

	if not construct_tag.is_empty():
		var tag := Label.new()
		tag.text = construct_tag
		tag.add_theme_font_size_override("font_size", 12)
		tag.add_theme_color_override("font_color", ExperimentUI.ACCENT)
		head_row.add_child(tag)

	if not description.is_empty():
		var desc := Label.new()
		desc.text = description
		desc.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		desc.add_theme_color_override("font_color", Color(0.45, 0.48, 0.55))
		desc.add_theme_font_size_override("font_size", 14)
		col.add_child(desc)

	return col


static func add_likert_item(parent: Control, item_id: String, text: String, sliders: Dictionary) -> void:
	var block := VBoxContainer.new()
	block.add_theme_constant_override("separation", 6)
	parent.add_child(block)

	var prompt := Label.new()
	prompt.text = text
	prompt.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	prompt.add_theme_font_size_override("font_size", 15)
	block.add_child(prompt)

	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	block.add_child(row)

	var low := Label.new()
	low.text = "1"
	low.custom_minimum_size = Vector2(18, 0)
	low.add_theme_color_override("font_color", ExperimentUI.MUTED)
	row.add_child(low)

	var slider := HSlider.new()
	slider.min_value = ExperimentQuestionnaireData.LIKERT_MIN
	slider.max_value = ExperimentQuestionnaireData.LIKERT_MAX
	slider.step = 1
	slider.value = 4
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	slider.custom_minimum_size.y = 28
	row.add_child(slider)

	var high := Label.new()
	high.text = "7"
	high.custom_minimum_size = Vector2(18, 0)
	high.add_theme_color_override("font_color", ExperimentUI.MUTED)
	row.add_child(high)

	var val := Label.new()
	val.text = "4"
	val.custom_minimum_size = Vector2(28, 0)
	val.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	val.add_theme_color_override("font_color", ExperimentUI.ACCENT)
	slider.value_changed.connect(func(v: float) -> void:
		val.text = str(int(v))
	)
	row.add_child(val)

	var hint := Label.new()
	hint.text = "Totalmente en desacuerdo — Totalmente de acuerdo"
	hint.add_theme_font_size_override("font_size", 12)
	hint.add_theme_color_override("font_color", ExperimentUI.MUTED)
	block.add_child(hint)

	sliders[item_id] = slider


static func add_semantic_item(
	parent: Control,
	item_id: String,
	left: String,
	right: String,
	sliders: Dictionary,
) -> void:
	var block := VBoxContainer.new()
	block.add_theme_constant_override("separation", 6)
	parent.add_child(block)

	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	block.add_child(row)

	var left_label := Label.new()
	left_label.text = left
	left_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	left_label.custom_minimum_size = Vector2(150, 0)
	left_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	left_label.add_theme_font_size_override("font_size", 14)
	left_label.add_theme_color_override("font_color", Color(0.38, 0.4, 0.46))
	row.add_child(left_label)

	var slider := HSlider.new()
	slider.min_value = ExperimentQuestionnaireData.GODSPEED_MIN
	slider.max_value = ExperimentQuestionnaireData.GODSPEED_MAX
	slider.step = 1
	slider.value = 3
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	slider.custom_minimum_size = Vector2(200, 28)
	row.add_child(slider)

	var right_label := Label.new()
	right_label.text = right
	right_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right_label.custom_minimum_size = Vector2(150, 0)
	right_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	right_label.add_theme_font_size_override("font_size", 14)
	right_label.add_theme_color_override("font_color", Color(0.38, 0.4, 0.46))
	row.add_child(right_label)

	var val_row := HBoxContainer.new()
	val_row.alignment = BoxContainer.ALIGNMENT_CENTER
	block.add_child(val_row)
	var val := Label.new()
	val.text = "3"
	val.add_theme_color_override("font_color", ExperimentUI.ACCENT_B)
	val.add_theme_font_size_override("font_size", 14)
	val_row.add_child(val)
	slider.value_changed.connect(func(v: float) -> void:
		val.text = str(int(v))
	)

	sliders[item_id] = slider


static func add_sam_item(parent: Control, scale: Dictionary, sliders: Dictionary) -> void:
	var block := VBoxContainer.new()
	block.add_theme_constant_override("separation", 8)
	parent.add_child(block)

	var title := Label.new()
	title.text = scale.get("title", "")
	title.add_theme_font_size_override("font_size", 16)
	title.add_theme_color_override("font_color", Color(0.22, 0.24, 0.3))
	block.add_child(title)

	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	block.add_child(row)

	var left := Label.new()
	left.text = str(scale.get("left", ""))
	left.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	left.custom_minimum_size = Vector2(160, 0)
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.add_theme_font_size_override("font_size", 13)
	left.add_theme_color_override("font_color", ExperimentUI.MUTED)
	row.add_child(left)

	var slider := HSlider.new()
	slider.min_value = ExperimentQuestionnaireData.SAM_MIN
	slider.max_value = ExperimentQuestionnaireData.SAM_MAX
	slider.step = 1
	slider.value = 5
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	slider.custom_minimum_size = Vector2(220, 32)
	row.add_child(slider)

	var right := Label.new()
	right.text = str(scale.get("right", ""))
	right.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right.custom_minimum_size = Vector2(160, 0)
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	right.add_theme_font_size_override("font_size", 13)
	right.add_theme_color_override("font_color", ExperimentUI.MUTED)
	row.add_child(right)

	var val_row := HBoxContainer.new()
	val_row.alignment = BoxContainer.ALIGNMENT_CENTER
	block.add_child(val_row)
	var val := Label.new()
	val.text = "5"
	val.add_theme_color_override("font_color", ExperimentUI.ACCENT)
	val_row.add_child(val)
	slider.value_changed.connect(func(v: float) -> void:
		val.text = str(int(v))
	)

	sliders[str(scale.get("id", ""))] = slider


static func add_footer_button(parent: Control, text: String, primary: bool, callback: Callable) -> Button:
	var btn := Button.new()
	btn.text = text
	btn.pressed.connect(callback)
	if primary:
		ExperimentUI.style_send_button(btn)
	else:
		ExperimentUI.style_secondary_button(btn)
	btn.custom_minimum_size = Vector2(200, 48)
	parent.add_child(btn)
	return btn


static func _apply_margin(margin: MarginContainer, h: int, v: int) -> void:
	margin.add_theme_constant_override("margin_left", h)
	margin.add_theme_constant_override("margin_right", h)
	margin.add_theme_constant_override("margin_top", v)
	margin.add_theme_constant_override("margin_bottom", v)
