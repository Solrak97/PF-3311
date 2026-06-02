extends Node

enum Phase { IDLE, SETUP, CHAT, QUESTIONNAIRE, DONE }

const INTERACTION_SEC := 300
const CHAT_SCENE := "res://scenes/main.tscn"
const ORCHESTRATOR_SCENE := "res://scenes/experiment/ExperimentSessionMode.tscn"
const QUESTIONNAIRE_SCENE := "res://scenes/experiment/QuestionnairePlaceholder.tscn"
const DEFAULT_SCENARIO_ID := "daily_conversation"

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

var early_exit: bool = false
var early_exit_reason: String = ""

var conversation_history: Array[Dictionary] = []
var scenario_id_by_interaction: Dictionary = {1: DEFAULT_SCENARIO_ID, 2: DEFAULT_SCENARIO_ID}
## 1 = cuestionario tras interacción 1; 2 = cuestionario final tras interacción 2
var questionnaire_after_interaction: int = 0

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
	early_exit = false
	early_exit_reason = ""
	conversation_history.clear()
	scenario_id_by_interaction = {1: DEFAULT_SCENARIO_ID, 2: DEFAULT_SCENARIO_ID}
	questionnaire_after_interaction = 0


func load_profile_config() -> void:
	profile_a_id = ParticipantSettings.load_profile_a_id()
	profile_b_id = ParticipantSettings.CONTROL_PROFILE_ID
	scenario_id_by_interaction[1] = ParticipantSettings.load_scenario_for_interaction(1)
	scenario_id_by_interaction[2] = ParticipantSettings.load_scenario_for_interaction(2)


func scenario_id_for_interaction(index: int = 0) -> String:
	var idx := index if index > 0 else current_interaction_index
	var sid := str(scenario_id_by_interaction.get(idx, DEFAULT_SCENARIO_ID)).strip_edges()
	return sid if sid in ParticipantSettings.VALID_SCENARIO_IDS else DEFAULT_SCENARIO_ID


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
	questionnaire_after_interaction = current_interaction_index
	phase = Phase.QUESTIONNAIRE
	interaction_finished.emit(current_interaction_index)


func complete_final_questionnaire() -> void:
	_log_run_event("questionnaire_final_complete", {"interaction_index": 2})
	phase = Phase.DONE
	is_run_active = false
	run_finished.emit()


func exit_run_early(reason: String = "participant_request") -> void:
	if early_exit:
		return
	early_exit = true
	early_exit_reason = reason.strip_edges()
	_log_run_event("session_exit_early", {"reason": early_exit_reason})
	phase = Phase.DONE
	is_run_active = false
	run_finished.emit()


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
		"scenario_id": scenario_id_for_interaction(),
	}
	for key in extra:
		entry[key] = extra[key]
	events.append(entry)
	log_data["events"] = events
	var w := FileAccess.open(path, FileAccess.WRITE)
	if w != null:
		w.store_string(JSON.stringify(log_data, "\t"))
		w.close()
