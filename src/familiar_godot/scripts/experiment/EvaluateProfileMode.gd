extends Control

const SETUP_MENU := "res://scenes/experiment/ExperimentalSetupMenu.tscn"
const SUMMARY_MAX_HEIGHT := 160
const CHAT_MIN_HEIGHT := 220
const INPUT_MIN_LINES := 2
const INPUT_LINE_HEIGHT := 22

const RATING_LABELS: Dictionary = {
	"tone_similarity": "Tone similarity",
	"phrasing_similarity": "Phrasing similarity",
	"response_length_similarity": "Length similarity",
	"behavioral_consistency": "Behavioral consistency",
	"reminds_me_of_person": "Reminds me of the person",
	"naturalness": "Naturalness",
	"identity_leakage_absent": "Identity safety (no leakage)",
}

var _profile_select: OptionButton
var _status: Label
var _summary_scroll: ScrollContainer
var _summary: Label
var _chat: ChatBubbleLog
var _input: TextEdit
var _send: Button
var _clear_chat: Button
var _sliders: Dictionary = {}
var _ratings: Array[Dictionary] = []
var _conversation_history: Array = []
var _chat_busy: bool = false
var _pending_user_message: String = ""
var _loaded: bool = false
var _local_ids: Array[String] = []


func _ready() -> void:
	var ui := ExperimentUI.setup_experiment_card(self, "Evaluate Profile")
	_status = ui["status"]
	var content: VBoxContainer = ui["content"]
	_profile_select = ExperimentScreenHelper.add_labeled_option(content, "Profile")
	ExperimentScreenHelper.add_button(content, "Refresh profile list", _refresh_profile_list)
	ExperimentScreenHelper.add_button(content, "Load behavioral profile", _on_load)
	var summary_panel := PanelContainer.new()
	summary_panel.add_theme_stylebox_override("panel", ExperimentUI.viewport_panel())
	content.add_child(summary_panel)
	var summary_margin := MarginContainer.new()
	summary_margin.add_theme_constant_override("margin_left", 10)
	summary_margin.add_theme_constant_override("margin_top", 8)
	summary_margin.add_theme_constant_override("margin_right", 10)
	summary_margin.add_theme_constant_override("margin_bottom", 8)
	summary_panel.add_child(summary_margin)
	_summary_scroll = ScrollContainer.new()
	_summary_scroll.custom_minimum_size = Vector2(0, SUMMARY_MAX_HEIGHT)
	_summary_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_summary_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	summary_margin.add_child(_summary_scroll)
	_summary = Label.new()
	_summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_summary.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_summary_scroll.add_child(_summary)
	var chat_label := Label.new()
	chat_label.text = "Sample chat (condition A profile)"
	content.add_child(chat_label)
	_chat = ChatBubbleLog.new()
	_chat.custom_minimum_size = Vector2(0, CHAT_MIN_HEIGHT)
	_chat.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.add_child(_chat)
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
	_input.placeholder_text = "Message the profile… (Enter to send, Shift+Enter for new line)"
	_input.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	_input.custom_minimum_size = Vector2(0, INPUT_MIN_LINES * INPUT_LINE_HEIGHT)
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
	_clear_chat = ExperimentScreenHelper.add_button(content, "Clear chat", _on_clear_chat)
	for key in ExperimentPrompts.RATING_KEYS:
		content.add_child(_make_slider_row(key))
	ExperimentScreenHelper.add_button(content, "Add rating", _on_add_rating)
	ExperimentScreenHelper.add_button(content, "Finish evaluation", _on_finish)
	ExperimentScreenHelper.add_button(content, "Back", func() -> void:
		ExperimentScreenHelper.go_to(SETUP_MENU)
	)
	if not ExperimentApi.request_finished.is_connected(_on_api_finished):
		ExperimentApi.request_finished.connect(_on_api_finished)
	_set_chat_controls(false)
	_refresh_profile_list()
	call_deferred("_sync_layout_widths")


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED:
		call_deferred("_sync_layout_widths")


func _sync_layout_widths() -> void:
	if _summary_scroll != null and _summary != null:
		_summary.custom_minimum_size.x = maxf(_summary_scroll.size.x - 8.0, 320.0)
	if _chat != null:
		_chat._sync_bubble_widths()


func _selected_profile_id() -> String:
	return ProfileCatalog.selected_profile_id(_profile_select)


func _refresh_profile_list() -> void:
	_loaded = false
	_summary.text = ""
	_reset_chat()
	_local_ids = ProfileCatalog.list_local_raw_profile_ids()
	ProfileCatalog.populate_option(_profile_select, _local_ids)
	_status.text = "Loading profiles from backend…"
	ExperimentApi.list_profiles()


func _apply_profile_options(profile_ids: Array[String]) -> void:
	ProfileCatalog.populate_option(_profile_select, profile_ids)


func _reset_chat() -> void:
	_conversation_history.clear()
	_pending_user_message = ""
	_chat.clear_log()
	_input.clear()
	_chat_busy = false
	_set_chat_controls(_loaded)


func _set_chat_controls(active: bool) -> void:
	_input.editable = active and not _chat_busy
	_send.disabled = not active or _chat_busy
	_clear_chat.disabled = not active or _chat_busy


func _make_slider_row(key: String) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	var label := Label.new()
	label.text = RATING_LABELS.get(key, key)
	label.custom_minimum_size = Vector2(220, 0)
	row.add_child(label)
	var slider := HSlider.new()
	slider.min_value = 1
	slider.max_value = 7
	slider.step = 1
	slider.value = 4
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(slider)
	var val := Label.new()
	val.text = "4"
	val.custom_minimum_size = Vector2(24, 0)
	slider.value_changed.connect(func(v: float) -> void:
		val.text = str(int(v))
	)
	row.add_child(val)
	_sliders[key] = slider
	return row


func _on_load() -> void:
	var pid := _selected_profile_id()
	if pid.is_empty():
		_status.text = "Select a profile from the list."
		return
	_status.text = "Loading profile…"
	ExperimentApi.get_behavioral_profile(pid)
	ExperimentApi.validation_start(pid)


func _on_clear_chat() -> void:
	_reset_chat()
	_status.text = "Chat cleared — send a message to continue evaluating."


func _on_send() -> void:
	if not _loaded or _chat_busy:
		return
	var text := _input.text.strip_edges()
	if text.is_empty():
		_status.text = "Write a message to chat with the profile."
		return
	var pid := _selected_profile_id()
	_append_user(text)
	_input.clear()
	_pending_user_message = text
	_chat_busy = true
	_set_chat_controls(true)
	_status.text = "Agent thinking…"
	ExperimentApi.post_experiment_chat({
		"participant_id": "evaluator",
		"session_id": "evaluate-%s" % pid,
		"interaction_index": 1,
		"condition": "A",
		"profile_id": pid,
		"message": text,
		"conversation_history": _conversation_history,
	})


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


func _history_append(role: String, content: String) -> void:
	var text := content.strip_edges()
	if text.is_empty():
		return
	_conversation_history.append({"role": role, "content": text})


func _last_assistant_message() -> String:
	for i in range(_conversation_history.size() - 1, -1, -1):
		var item: Variant = _conversation_history[i]
		if item is Dictionary and str(item.get("role", "")) == "assistant":
			return str(item.get("content", "")).strip_edges()
	return ""


func _assistant_message_count() -> int:
	var count := 0
	for item in _conversation_history:
		if item is Dictionary and str(item.get("role", "")) == "assistant":
			count += 1
	return count


func _collect_ratings() -> Dictionary:
	var out: Dictionary = {}
	for key in ExperimentPrompts.RATING_KEYS:
		out[key] = int(_sliders[key].value)
	return out


func _on_add_rating() -> void:
	if _assistant_message_count() == 0:
		_status.text = "Chat with the profile before adding a rating."
		return
	var scores := _collect_ratings()
	var last_user := ""
	for i in range(_conversation_history.size() - 1, -1, -1):
		var item: Variant = _conversation_history[i]
		if item is Dictionary and str(item.get("role", "")) == "user":
			last_user = str(item.get("content", ""))
			break
	var last_agent := _last_assistant_message()
	_ratings.append({
		"kind": "sample_chat",
		"conversation": _conversation_history.duplicate(true),
		"agent_response": last_agent,
		"scores": scores,
	})
	var pid := _selected_profile_id()
	ExperimentApi.post_validation({
		"profile_id": pid,
		"validator_id": "godot-ui",
		"created_at": Time.get_datetime_string_from_system(true),
		"ratings": [_ratings.back()],
	})
	ExperimentApi.validation_rating({
		"profile_id": pid,
		"validator_id": "godot-ui",
		"prompt": last_user,
		"agent_response": last_agent,
		"scores": scores,
	})
	_status.text = "Rating %d recorded from sample chat." % _ratings.size()


func _on_finish() -> void:
	var pid := _selected_profile_id()
	if pid.is_empty() or _ratings.is_empty():
		_status.text = "Add at least one rating before finishing."
		return
	var payload := {
		"profile_id": pid,
		"validator_id": "godot-ui",
		"created_at": Time.get_datetime_string_from_system(true),
		"ratings": _ratings,
	}
	_save_local_validation(payload)
	var summary := _evaluate_thresholds()
	_status.text = summary
	ExperimentApi.post_validation(payload)
	ExperimentApi.validation_finalize(pid)


func _evaluate_thresholds() -> String:
	var last: Dictionary = _ratings.back()
	var scores: Dictionary = last.get("scores", {})
	var sim_keys := ["tone_similarity", "phrasing_similarity", "response_length_similarity"]
	var sim_sum := 0.0
	for k in sim_keys:
		sim_sum += float(scores.get(k, 0))
	var sim_avg := sim_sum / float(sim_keys.size())
	var natural := float(scores.get("naturalness", 0))
	var identity := float(scores.get("identity_leakage_absent", 0))
	var parts: PackedStringArray = []
	parts.append("Similarity avg: %.1f (need ≥ 4.5)" % sim_avg)
	parts.append("Naturalness: %.1f (need ≥ 4.0)" % natural)
	parts.append("Identity safety: %.1f (need ≥ 5.5)" % identity)
	if sim_avg >= 4.5 and natural >= 4.0 and identity >= 5.5:
		parts.append("Thresholds passed.")
	else:
		parts.append("Some thresholds not met.")
	return "\n".join(parts)


func _save_local_validation(payload: Dictionary) -> void:
	var dir := "user://experiment_logs/validation"
	DirAccess.make_dir_recursive_absolute(dir)
	var path := "%s/%s_%s.json" % [
		dir,
		payload.get("profile_id", "unknown"),
		Time.get_unix_time_from_system(),
	]
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(payload, "\t"))
		f.close()


func _append_user(text: String) -> void:
	_chat.append_user(text)
	_scroll_chat_to_bottom()


func _append_assistant(text: String) -> void:
	_chat.append_assistant(text, "profile")
	_scroll_chat_to_bottom()


func _scroll_chat_to_bottom() -> void:
	call_deferred("_scroll_chat_to_bottom_deferred")


func _scroll_chat_to_bottom_deferred() -> void:
	if _chat == null:
		return
	await get_tree().process_frame
	var bar := _chat.get_v_scroll_bar()
	if bar != null:
		bar.value = bar.max_value


func _on_api_finished(action: String, success: bool, data: Variant, error: String) -> void:
	match action:
		"list_profiles":
			var remote: Array = []
			if success and data is Dictionary:
				var raw_ids = data.get("profile_ids", [])
				if raw_ids is Array:
					remote = raw_ids
			var merged := ProfileCatalog.merge_profile_ids(remote, _local_ids)
			_apply_profile_options(merged)
			if merged.is_empty():
				_status.text = "No trained profiles found. Use Train Profile first."
			else:
				_status.text = "%d profile(s) available. Select one and load." % merged.size()
		"get_behavioral":
			if not success or not (data is Dictionary):
				_status.text = "Could not load profile (%s)." % error
				return
			_loaded = true
			_summary.text = String(data.get("style_summary", "(no summary)"))
			if data.get("yaml_profile") is Dictionary:
				var yaml := data.get("yaml_profile") as Dictionary
				if yaml.get("style") is Dictionary:
					_summary.text += "\n\n[YAML profile loaded]"
			_reset_chat()
			call_deferred("_sync_layout_widths")
			_status.text = "Profile loaded — send a message in the sample chat below."
		"experiment_chat":
			_chat_busy = false
			_set_chat_controls(_loaded)
			if not success or not (data is Dictionary):
				_status.text = "Chat failed (%s)." % error
				_pending_user_message = ""
				return
			var reply := str(data.get("text", "")).strip_edges()
			if reply.is_empty():
				_status.text = "Empty reply from agent."
				_pending_user_message = ""
				return
			if not _pending_user_message.is_empty():
				_history_append("user", _pending_user_message)
				_pending_user_message = ""
			_append_assistant(reply)
			_history_append("assistant", reply)
			_status.text = "Reply received — continue chatting or add a rating."
		"post_validation":
			if success:
				_status.text = _status.text + "\nValidation submitted."
			else:
				_status.text = _status.text + "\nBackend submit failed (%s). Local copy saved." % error
		"validation_finalize":
			if success and data is Dictionary:
				var passed := bool(data.get("passed", false))
				_status.text = _status.text + "\nValidation %s." % ("passed" if passed else "did not pass thresholds")
		"validation_rating":
			if not success:
				_status.text = "Validation rating failed (%s)." % error
