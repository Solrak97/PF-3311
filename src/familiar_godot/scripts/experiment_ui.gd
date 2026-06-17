class_name ExperimentUI
extends RefCounted

const WINDOW_BG := Color(0.93, 0.93, 0.95, 1.0)
const SURFACE := Color(1.0, 1.0, 1.0, 1.0)
const BORDER := Color(0.9, 0.9, 0.93, 1.0)
const TEXT := Color(0.2, 0.22, 0.28, 1.0)
const MUTED := Color(0.55, 0.58, 0.64, 1.0)
const ACCENT := Color(0.9, 0.49, 0.27, 1.0)
const ACCENT_HOVER := Color(0.95, 0.55, 0.32, 1.0)
const ACCENT_PRESS := Color(0.82, 0.44, 0.24, 1.0)
const ACCENT_B := Color(0.45, 0.58, 0.85, 1.0)
const BUBBLE_USER_BG := Color(1.0, 0.93, 0.88, 1.0)
const BUBBLE_ASSISTANT_BG := Color(0.96, 0.97, 0.99, 1.0)
const BUBBLE_MIRROR_BG := Color(0.94, 0.91, 0.98, 1.0)
const BUBBLE_SKIP_BG := Color(0.97, 0.97, 0.98, 1.0)
const BUBBLE_SYSTEM_BG := Color(0.95, 0.96, 0.98, 1.0)
const BUBBLE_LABEL_MUTED := Color(0.54, 0.56, 0.62, 1.0)
const BUBBLE_MIRROR_LABEL := Color(0.36, 0.29, 0.48, 1.0)
const BUBBLE_SYSTEM_LABEL := Color(0.42, 0.46, 0.54, 1.0)
const BUBBLE_RADIUS := 16
const BUBBLE_GAP := 12
const BUBBLE_MAX_WIDTH_RATIO := 0.72
const BUBBLE_MARGIN_H := 14
const BUBBLE_MARGIN_V := 10
const PILL_PAD_H := 16
const PILL_PAD_V := 10


static func apply(root: Control) -> void:
	root.theme = build_theme()


static func configure_window(win: Window) -> void:
	if win == null:
		return
	win.mode = Window.MODE_MAXIMIZED


static func setup_main_screen(nodes: Dictionary) -> void:
	var bg: ColorRect = nodes.get("background")
	var avatar_panel: PanelContainer = nodes.get("avatar_panel")
	var chat_panel: PanelContainer = nodes.get("chat_panel")
	var condition_pill: PanelContainer = nodes.get("condition_pill")
	var top_row: HBoxContainer = nodes.get("top_row")
	var pill_sep: VSeparator = nodes.get("pill_sep")
	var condition_badge: Label = nodes.get("condition_badge")
	var timer_label: Label = nodes.get("timer_label")
	var new_chat_button: Button = nodes.get("new_chat_button")
	var menu_button: Button = nodes.get("menu_button")
	var send_button: Button = nodes.get("send_button")
	var output: ScrollContainer = nodes.get("output")
	var condition: String = String(nodes.get("condition", "A"))

	if bg != null:
		bg.color = WINDOW_BG
	if avatar_panel != null:
		avatar_panel.add_theme_stylebox_override("panel", viewport_panel())
	if chat_panel != null:
		chat_panel.add_theme_stylebox_override("panel", chat_panel_style())
	if condition_pill != null:
		condition_pill.add_theme_stylebox_override("panel", pill_panel())
		var margin: MarginContainer = condition_pill.get_node_or_null("PillMargin") as MarginContainer
		if margin != null:
			_apply_margin(margin, PILL_PAD_H, PILL_PAD_V)
	if top_row != null:
		style_overlay_row(top_row)
	if pill_sep != null:
		style_pill_separator(pill_sep)
	if condition_badge != null:
		style_condition_badge(condition_badge, condition)
	if timer_label != null:
		style_timer(timer_label)
	if new_chat_button != null:
		style_new_chat_button(new_chat_button)
	if menu_button != null:
		style_menu_button(menu_button)
	if send_button != null:
		style_send_button(send_button)
	if output != null:
		style_chat_log(output)


static func setup_experiment_card(root: Control, title: String) -> Dictionary:
	return ExperimentScreenHelper.mount(root, title)


static func setup_menu_screen(bg: ColorRect, card: PanelContainer, quit_btn: Button, settings_panel: PanelContainer = null) -> void:
	if bg != null:
		bg.color = WINDOW_BG
	if card != null:
		card.add_theme_stylebox_override("panel", viewport_panel())
	if settings_panel != null:
		settings_panel.add_theme_stylebox_override("panel", viewport_panel())
	if quit_btn != null:
		style_menu_button(quit_btn)
		quit_btn.text = "Salir"


static func build_theme() -> Theme:
	var t := Theme.new()
	var card := _panel(SURFACE, 16, BORDER, 0)
	var input_box := _panel(SURFACE, 12, BORDER, 14)
	var btn := _panel(ACCENT, 12, Color.TRANSPARENT, 8)
	var btn_hover := _panel(ACCENT_HOVER, 12, Color.TRANSPARENT, 8)
	var btn_press := _panel(ACCENT_PRESS, 12, Color.TRANSPARENT, 8)

	t.set_stylebox("panel", "PanelContainer", card)
	t.set_stylebox("normal", "Button", btn)
	t.set_stylebox("hover", "Button", btn_hover)
	t.set_stylebox("pressed", "Button", btn_press)
	t.set_stylebox("focus", "Button", btn_hover)
	t.set_stylebox("normal", "LineEdit", input_box)
	t.set_stylebox("focus", "LineEdit", _panel(SURFACE, 12, ACCENT, 14))
	t.set_color("font_color", "Button", Color(1, 1, 1, 1))
	t.set_color("font_color", "Label", TEXT)
	t.set_color("font_color", "LineEdit", TEXT)
	t.set_color("font_placeholder_color", "LineEdit", MUTED)
	t.set_font_size("font_size", "Button", 16)
	t.set_font_size("font_size", "Label", 15)
	t.set_font_size("font_size", "LineEdit", 16)
	t.set_constant("margin_left", "Button", 22)
	t.set_constant("margin_right", "Button", 22)
	t.set_constant("margin_top", "Button", 12)
	t.set_constant("margin_bottom", "Button", 12)
	t.set_constant("separation", "VBoxContainer", 12)
	t.set_constant("separation", "HBoxContainer", 10)
	return t


static func pill_panel() -> StyleBoxFlat:
	var s := _panel(Color(1, 1, 1, 0.98), 22, Color(0.9, 0.91, 0.93, 1), 0)
	s.shadow_size = 10
	s.shadow_color = Color(0, 0, 0, 0.08)
	s.shadow_offset = Vector2(0, 3)
	return s


static func viewport_panel() -> StyleBoxFlat:
	var s := _panel(SURFACE, 18, BORDER, 0)
	s.shadow_size = 6
	s.shadow_color = Color(0, 0, 0, 0.08)
	s.shadow_offset = Vector2(0, 2)
	return s


static func chat_panel_style() -> StyleBoxFlat:
	return viewport_panel()


static func style_secondary_button(btn: Button) -> void:
	style_menu_button(btn)


static func style_new_chat_button(btn: Button) -> void:
	_apply_compact_button(btn, SURFACE, TEXT, "＋  Nuevo chat", Vector2(132, 40))


static func style_menu_button(btn: Button) -> void:
	_apply_compact_button(btn, SURFACE, TEXT, "☰  Menú", Vector2(108, 40))


static func style_send_button(btn: Button) -> void:
	_apply_compact_button(btn, ACCENT, Color(1, 1, 1, 1), "➤  Enviar", Vector2(128, 48))
	var hover := _panel(ACCENT_HOVER, 12, Color.TRANSPARENT, 10)
	var press := _panel(ACCENT_PRESS, 12, Color.TRANSPARENT, 10)
	btn.add_theme_stylebox_override("hover", hover)
	btn.add_theme_stylebox_override("pressed", press)
	btn.add_theme_stylebox_override("focus", hover)


static func style_overlay_row(row: BoxContainer) -> void:
	row.add_theme_constant_override("separation", 12)
	row.alignment = BoxContainer.ALIGNMENT_BEGIN
	row.size_flags_vertical = Control.SIZE_SHRINK_BEGIN


static func style_pill_separator(sep: VSeparator) -> void:
	sep.custom_minimum_size = Vector2(1, 18)
	sep.modulate = Color(0.82, 0.84, 0.88, 1)


static func style_condition_badge(label: Label, condition: String) -> void:
	var col := ACCENT if condition == "A" else ACCENT_B
	label.add_theme_color_override("font_color", col)
	label.add_theme_font_size_override("font_size", 15)
	label.size_flags_vertical = Control.SIZE_SHRINK_CENTER


static func style_timer(label: Label) -> void:
	label.add_theme_color_override("font_color", Color(0.28, 0.3, 0.36, 1))
	label.add_theme_font_size_override("font_size", 15)
	label.size_flags_vertical = Control.SIZE_SHRINK_CENTER


static func style_chat_log(chat_scroll: ScrollContainer) -> void:
	chat_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	chat_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO


static func style_chat_output(output: RichTextLabel) -> void:
	output.add_theme_constant_override("line_separation", 6)
	output.scroll_active = true
	output.context_menu_enabled = false


static func chat_placeholder() -> String:
	return ""


static func escape_bbcode(text: String) -> String:
	return _escape(text)


static func assistant_label_for_kind(kind: String, override_label: String = "") -> String:
	if not override_label.is_empty():
		return override_label
	match kind:
		"mirror":
			return "Intento de imitación"
		"profile":
			return "Perfil"
		"buddy":
			return "Buddy"
		"probe", "finish", "interview":
			return "Entrevistador"
		"system":
			return "Sistema"
		_:
			return "Asistente"


static func assistant_colors_for_kind(kind: String) -> Dictionary:
	match kind:
		"mirror":
			return {"bg": BUBBLE_MIRROR_BG, "label": BUBBLE_MIRROR_LABEL}
		"system":
			return {"bg": BUBBLE_SYSTEM_BG, "label": BUBBLE_SYSTEM_LABEL}
		_:
			return {"bg": BUBBLE_ASSISTANT_BG, "label": BUBBLE_LABEL_MUTED}


static func make_user_bubble(text: String, max_width: float, header: String = "Tú") -> Control:
	var bg := BUBBLE_SKIP_BG if header.contains("omitido") else BUBBLE_USER_BG
	return _make_bubble_row(
		_make_bubble_panel(header, text, bg, BUBBLE_LABEL_MUTED, max_width, true),
		true
	)


static func make_assistant_bubble(text: String, kind: String, max_width: float, header: String = "") -> Control:
	var colors := assistant_colors_for_kind(kind)
	var label := assistant_label_for_kind(kind, header)
	return _make_bubble_row(
		_make_bubble_panel(label, text, colors["bg"], colors["label"], max_width, false),
		false
	)


static func make_assistant_bubble_open(
	label: String,
	kind: String,
	max_width: float
) -> Dictionary:
	var colors := assistant_colors_for_kind(kind)
	var resolved_label := assistant_label_for_kind(kind, label)
	var panel := _make_bubble_panel(resolved_label, "", colors["bg"], colors["label"], max_width, false)
	var body := panel.get_meta("body") as Label
	return {"root": _make_bubble_row(panel, false), "body": body}


static func set_bubble_max_width(row: Control, max_width: float) -> void:
	var panel := row.get_meta("bubble_panel", null) as PanelContainer
	if panel == null:
		return
	var body := panel.get_meta("body") as Label
	if body == null:
		return
	var inner_w := maxf(max_width - float(BUBBLE_MARGIN_H * 2), 120.0)
	body.custom_minimum_size.x = inner_w


static func _make_bubble_row(panel: PanelContainer, align_right: bool) -> Control:
	panel.set_meta("bubble_panel", panel)
	var row := HBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.set_meta("bubble_panel", panel)
	if align_right:
		var spacer := Control.new()
		spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(spacer)
	row.add_child(panel)
	if not align_right:
		var spacer := Control.new()
		spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(spacer)
	return row


static func _make_bubble_panel(
	header_text: String,
	body_text: String,
	bg: Color,
	header_color: Color,
	max_width: float,
	align_right: bool
) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", bubble_panel_style(bg))
	panel.size_flags_horizontal = Control.SIZE_SHRINK_END if align_right else Control.SIZE_SHRINK_BEGIN
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", BUBBLE_MARGIN_H)
	margin.add_theme_constant_override("margin_top", BUBBLE_MARGIN_V)
	margin.add_theme_constant_override("margin_right", BUBBLE_MARGIN_H)
	margin.add_theme_constant_override("margin_bottom", BUBBLE_MARGIN_V)
	panel.add_child(margin)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 4)
	margin.add_child(col)
	var header := Label.new()
	header.text = header_text
	header.add_theme_color_override("font_color", header_color)
	header.add_theme_font_size_override("font_size", 12)
	col.add_child(header)
	var body := Label.new()
	body.text = body_text
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.add_theme_color_override("font_color", TEXT)
	body.add_theme_font_size_override("font_size", 15)
	body.custom_minimum_size.x = maxf(max_width - float(BUBBLE_MARGIN_H * 2), 120.0)
	col.add_child(body)
	panel.set_meta("body", body)
	panel.set_meta("bubble_panel", panel)
	return panel


static func bubble_panel_style(bg: Color) -> StyleBoxFlat:
	var s := _panel(bg, BUBBLE_RADIUS, Color(0.88, 0.89, 0.92, 1.0), 0)
	s.shadow_size = 2
	s.shadow_color = Color(0, 0, 0, 0.06)
	s.shadow_offset = Vector2(0, 1)
	return s


static func _color_hex(c: Color) -> String:
	return c.to_html(false)


static func _apply_compact_button(
	btn: Button,
	bg: Color,
	font_col: Color,
	label: String,
	min_size: Vector2
) -> void:
	var border_col := BORDER if bg == SURFACE else Color.TRANSPARENT
	var s := _panel(bg, 10, border_col, 10)
	var hover_bg := ACCENT_HOVER if bg == ACCENT else Color(0.99, 0.99, 1, 1)
	var press_bg := ACCENT_PRESS if bg == ACCENT else Color(0.96, 0.96, 0.98, 1)
	var h := _panel(hover_bg, 10, border_col, 10)
	var p := _panel(press_bg, 10, border_col, 10)
	btn.add_theme_stylebox_override("normal", s)
	btn.add_theme_stylebox_override("hover", h)
	btn.add_theme_stylebox_override("pressed", p)
	btn.add_theme_stylebox_override("focus", h)
	btn.add_theme_stylebox_override("disabled", s)
	btn.add_theme_color_override("font_color", font_col)
	btn.add_theme_color_override("font_hover_color", font_col)
	btn.add_theme_color_override("font_pressed_color", font_col)
	btn.add_theme_font_size_override("font_size", 14)
	btn.add_theme_constant_override("margin_left", 12)
	btn.add_theme_constant_override("margin_right", 12)
	btn.add_theme_constant_override("margin_top", 6)
	btn.add_theme_constant_override("margin_bottom", 6)
	btn.custom_minimum_size = min_size
	btn.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	btn.text = label


static func _apply_margin(margin: MarginContainer, h: int, v: int) -> void:
	margin.add_theme_constant_override("margin_left", h)
	margin.add_theme_constant_override("margin_top", v)
	margin.add_theme_constant_override("margin_right", h)
	margin.add_theme_constant_override("margin_bottom", v)


static func _escape(t: String) -> String:
	return t.replace("[", "[lb]")


static func _panel(
	bg: Color,
	radius: int,
	border: Color = Color.TRANSPARENT,
	content_margin: int = 0
) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.set_corner_radius_all(radius)
	if border.a > 0.0:
		s.border_color = border
		s.set_border_width_all(1)
	if content_margin > 0:
		s.set_content_margin(SIDE_LEFT, content_margin)
		s.set_content_margin(SIDE_RIGHT, content_margin)
		s.set_content_margin(SIDE_TOP, content_margin)
		s.set_content_margin(SIDE_BOTTOM, content_margin)
	s.shadow_color = Color(0, 0, 0, 0.05)
	s.shadow_size = 3
	s.shadow_offset = Vector2(0, 2)
	return s
