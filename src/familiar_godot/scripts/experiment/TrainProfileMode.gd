extends Control

const SETUP_MENU := "res://scenes/experiment/ExperimentalSetupMenu.tscn"

var _profile_id: LineEdit
var _alias: LineEdit
var _status: Label
var _progress: Label
var _chat_scroll: ScrollContainer
var _chat: RichTextLabel
var _input: TextEdit
var _send: Button
var _save: Button
var _skip: Button
var _start: Button

const INPUT_MIN_LINES := 3
const INPUT_LINE_HEIGHT := 22
const CHAT_MIN_HEIGHT := 360

var _interview_active: bool = false
var _interview_busy: bool = false
var _interview_complete: bool = false
var _prompt_index: int = 0
var _total_prompts: int = 0
var _samples: Array = []
var _conversation_history: Array = []


func _ready() -> void:
	var ui := ExperimentUI.setup_experiment_card(self, "Train Profile")
	_status = ui["status"]
	var content: VBoxContainer = ui["content"]
	var hint := Label.new()
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.text = (
		"An LLM interviewer collects conversational samples to build a behavioral profile. "
		+ "Consent is handled offline by the research team."
	)
	content.add_child(hint)
	_profile_id = ExperimentScreenHelper.add_labeled_line(content, "Profile ID", "e.g. profile-001")
	_alias = ExperimentScreenHelper.add_labeled_line(content, "Alias", "optional")
	_progress = Label.new()
	_progress.text = "Interview not started."
	content.add_child(_progress)
	_chat_scroll = ScrollContainer.new()
	_chat_scroll.custom_minimum_size = Vector2(0, CHAT_MIN_HEIGHT)
	_chat_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_chat_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_chat_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	content.add_child(_chat_scroll)
	_chat = RichTextLabel.new()
	_chat.bbcode_enabled = true
	_chat.fit_content = true
	_chat.scroll_active = true
	_chat.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_chat.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_chat_scroll.add_child(_chat)
	var input_panel := PanelContainer.new()
	input_panel.add_theme_stylebox_override("panel", ExperimentUI.viewport_panel())
	content.add_child(input_panel)
	var input_margin := MarginContainer.new()
	input_margin.add_theme_constant_override("margin_left", 10)
	input_margin.add_theme_constant_override("margin_top", 8)
	input_margin.add_theme_constant_override("margin_right", 10)
	input_margin.add_theme_constant_override("margin_bottom", 8)
	input_panel.add_child(input_margin)
	var input_col := VBoxContainer.new()
	input_col.add_theme_constant_override("separation", 8)
	input_margin.add_child(input_col)
	_input = TextEdit.new()
	_input.placeholder_text = "Type your answer… (Shift+Enter for a new line, Enter to send)"
	_input.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	_input.scroll_fit_content_height = false
	_input.custom_minimum_size = Vector2(0, INPUT_MIN_LINES * INPUT_LINE_HEIGHT)
	_input.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_input.gui_input.connect(_on_input_gui_input)
	input_col.add_child(_input)
	var input_row := HBoxContainer.new()
	input_row.add_theme_constant_override("separation", 8)
	input_row.alignment = BoxContainer.ALIGNMENT_END
	input_col.add_child(input_row)
	_send = Button.new()
	_send.text = "Send"
	_send.pressed.connect(_on_send)
	input_row.add_child(_send)
	_start = ExperimentScreenHelper.add_button(content, "Start interview", _on_start)
	_skip = ExperimentScreenHelper.add_button(content, "Skip question", _on_skip)
	_save = ExperimentScreenHelper.add_button(content, "Save profile", _on_save)
	ExperimentScreenHelper.add_button(content, "Back", func() -> void:
		ExperimentScreenHelper.go_to(SETUP_MENU)
	)
	if not ExperimentApi.request_finished.is_connected(_on_api_finished):
		ExperimentApi.request_finished.connect(_on_api_finished)
	_set_interview_controls(false)
	call_deferred("_sync_chat_width")


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED:
		call_deferred("_sync_chat_width")


func _sync_chat_width() -> void:
	if _chat_scroll == null or _chat == null:
		return
	_chat.custom_minimum_size.x = maxf(_chat_scroll.size.x - 8.0, 320.0)


func _on_input_gui_input(event: InputEvent) -> void:
	if not _input.editable:
		return
	if event is InputEventKey:
		var key := event as InputEventKey
		if not key.pressed or key.echo:
			return
		if key.keycode == KEY_ENTER or key.keycode == KEY_KP_ENTER:
			if key.shift_pressed or key.ctrl_pressed:
				return
			get_viewport().set_input_as_handled()
			_on_send()


func _scroll_chat_to_bottom() -> void:
	call_deferred("_scroll_chat_to_bottom_deferred")


func _scroll_chat_to_bottom_deferred() -> void:
	if _chat_scroll == null:
		return
	await get_tree().process_frame
	var bar := _chat_scroll.get_v_scroll_bar()
	if bar != null:
		bar.value = bar.max_value


func _scroll_input_to_bottom() -> void:
	if _input == null:
		return
	var bar := _input.get_v_scroll_bar()
	if bar != null:
		bar.value = bar.max_value


func _focus_input() -> void:
	if _input == null or not _input.editable:
		return
	_input.grab_focus()
	_input.set_caret_line(maxi(_input.get_line_count() - 1, 0))
	_scroll_input_to_bottom()


func _set_interview_controls(active: bool) -> void:
	_interview_active = active
	_input.editable = active and not _interview_busy
	_send.disabled = not active or _interview_busy
	_skip.disabled = not active or _interview_busy or _interview_complete
	_start.disabled = active and not _interview_complete
	_save.disabled = not _interview_complete or _interview_busy
	_profile_id.editable = not active
	_alias.editable = not active


func _on_start() -> void:
	var pid := _profile_id.text.strip_edges()
	if pid.is_empty():
		_status.text = "Profile ID is required."
		return
	_chat.clear()
	_samples.clear()
	_conversation_history.clear()
	_prompt_index = 0
	_total_prompts = 0
	_interview_complete = false
	_progress.text = "Starting interview…"
	_status.text = "Connecting to interviewer…"
	_interview_busy = true
	_set_interview_controls(true)
	ExperimentApi.interview_start(pid, _alias.text.strip_edges())


func _on_send() -> void:
	if not _interview_active or _interview_busy or _interview_complete:
		return
	var text := _input.text.strip_edges()
	if text.is_empty():
		_status.text = "Write an answer or use Skip question."
		return
	_submit_turn(text, false)


func _on_skip() -> void:
	if not _interview_active or _interview_busy or _interview_complete:
		return
	_submit_turn("", true)


func _history_append(role: String, content: String) -> void:
	var text := content.strip_edges()
	if text.is_empty():
		return
	_conversation_history.append({"role": role, "content": text})


func _submit_turn(user_message: String, skip: bool) -> void:
	var display := user_message if not skip else "(skipped)"
	_append_user(display)
	if skip:
		_history_append("user", "[skipped]")
	else:
		_history_append("user", user_message)
	_input.clear()
	_scroll_input_to_bottom()
	_interview_busy = true
	_send.disabled = true
	_skip.disabled = true
	_status.text = "Interviewer thinking…"
	ExperimentApi.interview_turn({
		"profile_id": _profile_id.text.strip_edges(),
		"modeled_user_alias": _alias.text.strip_edges(),
		"prompt_index": _prompt_index,
		"user_message": user_message,
		"skip": skip,
		"samples": _samples,
		"conversation_history": _conversation_history,
	})


func _on_save() -> void:
	if _samples.is_empty():
		_status.text = "Complete the interview before saving."
		return
	var payload := {
		"profile_id": _profile_id.text.strip_edges(),
		"modeled_user_alias": _alias.text.strip_edges(),
		"created_at": Time.get_datetime_string_from_system(true),
		"consent_confirmed": true,
		"samples": _samples,
		"interview_transcript": _conversation_history,
	}
	_save_local_raw(payload)
	_interview_busy = true
	_save.disabled = true
	_status.text = "Saving profile…"
	ExperimentApi.interview_save(payload)


func _apply_interview_state(data: Dictionary) -> void:
	_prompt_index = int(data.get("prompt_index", _prompt_index))
	_total_prompts = int(data.get("total_prompts", _total_prompts))
	_interview_complete = bool(data.get("complete", false))
	var incoming = data.get("samples", null)
	if incoming is Array:
		_samples = incoming
	var message := str(data.get("message", "")).strip_edges()
	if not message.is_empty():
		_append_assistant(message)
		_history_append("assistant", message)
	if _total_prompts > 0:
		var shown := mini(_prompt_index + 1, _total_prompts) if not _interview_complete else _total_prompts
		_progress.text = "Interview %d/%d — %d sample(s) collected" % [
			shown,
			_total_prompts,
			_samples.size(),
		]
	else:
		_progress.text = "%d sample(s) collected" % _samples.size()
	if _interview_complete:
		_progress.text += " — ready to save"
		_status.text = "Interview complete. Press Save profile."
	_set_interview_controls(true)
	_focus_input()


func _append_user(text: String) -> void:
	_chat.append_text(ExperimentUI.format_user_bubble(text))
	_scroll_chat_to_bottom()


func _append_assistant(text: String) -> void:
	_chat.append_text(ExperimentUI.format_assistant_open())
	_chat.append_text(ExperimentUI.escape_bbcode(text))
	_chat.append_text(ExperimentUI.format_assistant_close())
	_scroll_chat_to_bottom()


func _save_local_raw(payload: Dictionary) -> void:
	var dir := "user://profiles/raw"
	DirAccess.make_dir_recursive_absolute(dir)
	var path := "%s/%s.json" % [dir, payload.get("profile_id", "unknown")]
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(payload, "\t"))
		f.close()


func _on_api_finished(action: String, success: bool, data: Variant, error: String) -> void:
	match action:
		"interview_start":
			_interview_busy = false
			if not success or not (data is Dictionary):
				_status.text = "Could not start interview (%s)." % error
				_set_interview_controls(false)
				return
			_apply_interview_state(data)
			_status.text = "Interview in progress."
		"interview_turn":
			_interview_busy = false
			if not success or not (data is Dictionary):
				_status.text = "Interview step failed (%s)." % error
				_set_interview_controls(_interview_active)
				return
			_apply_interview_state(data)
			_status.text = "Interview complete." if _interview_complete else "Answer recorded."
		"interview_save", "post_raw":
			_interview_busy = false
			if success:
				_status.text = "Training session saved successfully."
			else:
				_status.text = "Backend save failed (%s). Local copy kept in user://profiles/raw/." % error
			_set_interview_controls(_interview_active)
