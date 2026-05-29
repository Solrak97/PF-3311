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
	var output: RichTextLabel = nodes.get("output")
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
		style_chat_output(output)


static func setup_menu_screen(bg: ColorRect, card: PanelContainer, quit_btn: Button) -> void:
	if bg != null:
		bg.color = WINDOW_BG
	if card != null:
		card.add_theme_stylebox_override("panel", viewport_panel())
	if quit_btn != null:
		style_menu_button(quit_btn)
		quit_btn.text = "Quit"


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
	_apply_compact_button(btn, SURFACE, TEXT, "＋  New chat", Vector2(132, 40))


static func style_menu_button(btn: Button) -> void:
	_apply_compact_button(btn, SURFACE, TEXT, "☰  Menu", Vector2(108, 40))


static func style_send_button(btn: Button) -> void:
	_apply_compact_button(btn, ACCENT, Color(1, 1, 1, 1), "➤  Send", Vector2(128, 48))
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


static func style_chat_output(output: RichTextLabel) -> void:
	output.add_theme_constant_override("line_separation", 6)
	output.scroll_active = true
	output.context_menu_enabled = false


static func chat_placeholder() -> String:
	return ""


static func escape_bbcode(text: String) -> String:
	return _escape(text)


static func format_user_bubble(text: String) -> String:
	var esc := _escape(text)
	return "\n[right][color=#1f2430][font_size=15]%s[/font_size][/color][/right]\n" % esc


static func format_assistant_open() -> String:
	# Left-aligned by default; only [color] and [font_size] (must close in reverse order).
	return "\n[color=#1f2430][font_size=15]"


static func format_assistant_close() -> String:
	return "[/font_size][/color]\n"


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
