extends Control

const SETUP_MENU := "res://scenes/experiment/ExperimentalSetupMenu.tscn"

var _profile_a: OptionButton
var _status: Label
var _local_ids: Array[String] = []


func _ready() -> void:
	var ui := ExperimentUI.setup_experiment_card(self, "Assign Profiles")
	_status = ui["status"]
	var content: VBoxContainer = ui["content"]
	var hint := Label.new()
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.text = (
		"Condition A uses your trained behavioral profile (Profile A).\n"
		+ "Condition B always uses the built-in control baseline: generic_control_agent."
	)
	content.add_child(hint)
	_profile_a = ExperimentScreenHelper.add_labeled_option(content, "Profile A")
	var control_note := Label.new()
	control_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	control_note.text = "Profile B (control): %s (fixed on backend)" % ParticipantSettings.CONTROL_PROFILE_ID
	content.add_child(control_note)
	ExperimentScreenHelper.add_button(content, "Refresh profile list", _refresh_profile_list)
	ExperimentScreenHelper.add_button(content, "Save assignment", _on_save)
	ExperimentScreenHelper.add_button(content, "Back", func() -> void:
		ExperimentScreenHelper.go_to(SETUP_MENU)
	)
	if not ExperimentApi.request_finished.is_connected(_on_api_finished):
		ExperimentApi.request_finished.connect(_on_api_finished)
	_refresh_profile_list()


func _refresh_profile_list() -> void:
	_local_ids = ProfileCatalog.list_local_raw_profile_ids()
	_apply_profile_options(_local_ids)
	ProfileCatalog.select_profile_id(_profile_a, ParticipantSettings.load_profile_a_id())
	_status.text = "Loading profiles from backend…"
	ExperimentApi.list_profiles()


func _apply_profile_options(profile_ids: Array[String]) -> void:
	ProfileCatalog.populate_option(_profile_a, profile_ids)
	ProfileCatalog.select_profile_id(_profile_a, ParticipantSettings.load_profile_a_id())


func _on_api_finished(action: String, success: bool, data: Variant, _error: String) -> void:
	if action != "list_profiles":
		return
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
		_status.text = "%d profile(s) available." % merged.size()


func _on_save() -> void:
	var a := ProfileCatalog.selected_profile_id(_profile_a)
	if a.is_empty():
		_status.text = "Select Profile A for Condition A."
		return
	ParticipantSettings.save_profile_ids(a, ParticipantSettings.CONTROL_PROFILE_ID)
	ExperimentSessionManager.load_profile_config()
	_status.text = "Saved. Condition A → %s. Condition B → %s." % [
		a,
		ParticipantSettings.CONTROL_PROFILE_ID,
	]
