extends Node

enum Phase { IDLE, SETUP, CHAT, QUESTIONNAIRE, DONE }

const INTERACTION_SEC := 300
const CHAT_SCENE := "res://scenes/main.tscn"
const ORCHESTRATOR_SCENE := "res://scenes/experiment/ExperimentSessionMode.tscn"

var is_run_active: bool = false
var phase: Phase = Phase.IDLE

var participant_id: String = ""
var session_id: String = ""
var profile_a_id: String = ""
var profile_b_id: String = ""
var order: Array[String] = ["A", "B"]
var current_interaction_index: int = 0
var current_condition: String = "B"
var assigned_order_label: String = ""

var conversation_history: Array[Dictionary] = []

signal interaction_finished(interaction_index: int)
signal run_finished()


func reset_run() -> void:
	is_run_active = false
	phase = Phase.IDLE
	participant_id = ""
	session_id = ""
	profile_a_id = ""
	profile_b_id = ""
	order = ["A", "B"]
	current_interaction_index = 0
	current_condition = "B"
	assigned_order_label = ""
	conversation_history.clear()


func load_profile_config() -> void:
	profile_a_id = ParticipantSettings.load_profile_a_id()
	profile_b_id = ParticipantSettings.CONTROL_PROFILE_ID


func profile_for_condition(cond: String) -> String:
	if cond.to_upper() == "B":
		return ParticipantSettings.CONTROL_PROFILE_ID
	return profile_a_id


func active_profile_id() -> String:
	return profile_for_condition(current_condition)


func configure_run(participant: String, order_ab: Array[String]) -> void:
	var chosen_order := order_ab.duplicate() if order_ab.size() >= 2 else ["A", "B"]
	reset_run()
	is_run_active = true
	phase = Phase.SETUP
	participant_id = participant.strip_edges()
	load_profile_config()
	order = chosen_order
	session_id = "exp-%s" % _token()
	assigned_order_label = "-".join(order)


func begin_interaction(index: int) -> void:
	current_interaction_index = index
	if index >= 1 and index <= order.size():
		current_condition = order[index - 1]
	else:
		current_condition = "B"
	conversation_history.clear()
	phase = Phase.CHAT


func finish_interaction() -> void:
	_log_run_event("interaction_end", {"interaction_index": current_interaction_index})
	if current_interaction_index >= 2:
		phase = Phase.DONE
		is_run_active = false
		run_finished.emit()
	else:
		phase = Phase.QUESTIONNAIRE
	interaction_finished.emit(current_interaction_index)


func participant_interaction_label() -> String:
	return "Interacción %d" % current_interaction_index


func participant_interaction_subtitle() -> String:
	return "Primera interacción" if current_interaction_index == 1 else "Segunda interacción"


func append_message(role: String, content: String) -> void:
	conversation_history.append({"role": role, "content": content})


func interaction_session_id() -> String:
	return "%s-i%d" % [session_id, current_interaction_index]


func _token() -> String:
	return "%08x%08x" % [randi(), randi()]


func log_run_event(event: String, extra: Dictionary = {}) -> void:
	_log_run_event(event, extra)


func _log_run_event(event: String, extra: Dictionary = {}) -> void:
	var dir := "user://experiment_logs/run"
	DirAccess.make_dir_recursive_absolute(dir)
	var path := "%s/%s.json" % [dir, session_id]
	var log_data: Dictionary = {
		"participant_id": participant_id,
		"session_id": session_id,
		"profile_a_id": profile_a_id,
		"profile_b_id": profile_b_id,
		"order": order,
		"events": [],
	}
	if FileAccess.file_exists(path):
		var f := FileAccess.open(path, FileAccess.READ)
		if f != null:
			var parsed: Variant = JSON.parse_string(f.get_as_text())
			f.close()
			if parsed is Dictionary:
				log_data = parsed
	var events: Array = log_data.get("events", [])
	var entry := {
		"event": event,
		"timestamp": Time.get_datetime_string_from_system(true),
		"interaction_index": current_interaction_index,
		"condition": current_condition,
		"profile_id": active_profile_id(),
	}
	for key in extra:
		entry[key] = extra[key]
	events.append(entry)
	log_data["events"] = events
	var w := FileAccess.open(path, FileAccess.WRITE)
	if w != null:
		w.store_string(JSON.stringify(log_data, "\t"))
		w.close()
