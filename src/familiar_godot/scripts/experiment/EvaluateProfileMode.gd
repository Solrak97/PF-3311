extends Control

const SETUP_MENU := "res://scenes/experiment/ExperimentalSetupMenu.tscn"
const SUMMARY_MAX_HEIGHT := 200

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
var _sample_out: RichTextLabel
var _sliders: Dictionary = {}
var _ratings: Array[Dictionary] = []
var _current_prompt: String = ""
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
	ExperimentScreenHelper.add_button(content, "Generate sample response", _on_generate)
	_sample_out = RichTextLabel.new()
	_sample_out.custom_minimum_size = Vector2(0, 80)
	_sample_out.scroll_active = true
	content.add_child(_sample_out)
	for key in ExperimentPrompts.RATING_KEYS:
		content.add_child(_make_slider_row(key))
	ExperimentScreenHelper.add_button(content, "Add rating", _on_add_rating)
	ExperimentScreenHelper.add_button(content, "Finish evaluation", _on_finish)
	ExperimentScreenHelper.add_button(content, "Back", func() -> void:
		ExperimentScreenHelper.go_to(SETUP_MENU)
	)
	if not ExperimentApi.request_finished.is_connected(_on_api_finished):
		ExperimentApi.request_finished.connect(_on_api_finished)
	_refresh_profile_list()
	call_deferred("_sync_summary_width")


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED:
		call_deferred("_sync_summary_width")


func _sync_summary_width() -> void:
	if _summary_scroll == null or _summary == null:
		return
	_summary.custom_minimum_size.x = maxf(_summary_scroll.size.x - 8.0, 320.0)


func _selected_profile_id() -> String:
	return ProfileCatalog.selected_profile_id(_profile_select)


func _refresh_profile_list() -> void:
	_loaded = false
	_summary.text = ""
	_local_ids = ProfileCatalog.list_local_raw_profile_ids()
	ProfileCatalog.populate_option(_profile_select, _local_ids)
	_status.text = "Loading profiles from backend…"
	ExperimentApi.list_profiles()


func _apply_profile_options(profile_ids: Array[String]) -> void:
	ProfileCatalog.populate_option(_profile_select, profile_ids)


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


func _on_generate() -> void:
	var pid := _selected_profile_id()
	if pid.is_empty():
		_status.text = "Select a profile from the list."
		return
	if not _loaded:
		_status.text = "Load a behavioral profile first."
		return
	_current_prompt = String(ExperimentPrompts.PROMPTS[0].get("prompt", ""))
	_status.text = "Generating sample…"
	ExperimentApi.post_validation_generate_sample(pid, _current_prompt)


func _collect_ratings() -> Dictionary:
	var out: Dictionary = {}
	for key in ExperimentPrompts.RATING_KEYS:
		out[key] = int(_sliders[key].value)
	return out


func _on_add_rating() -> void:
	if _sample_out.text.strip_edges().is_empty():
		_status.text = "Generate a sample before rating."
		return
	_ratings.append({
		"prompt": _current_prompt,
		"agent_response": _sample_out.text,
		"scores": _collect_ratings(),
	})
	_status.text = "Rating %d recorded." % _ratings.size()
	_sample_out.text = ""


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
			call_deferred("_sync_summary_width")
			_status.text = "Behavioral profile loaded."
		"generate_sample":
			if not success or not (data is Dictionary):
				_status.text = "Sample generation failed (%s)." % error
				return
			_current_prompt = String(data.get("prompt", _current_prompt))
			_sample_out.text = String(data.get("agent_response", ""))
			_status.text = "Sample ready — adjust sliders and add rating."
		"post_validation":
			if success:
				_status.text = _status.text + "\nValidation submitted."
			else:
				_status.text = _status.text + "\nBackend submit failed (%s). Local copy saved." % error
