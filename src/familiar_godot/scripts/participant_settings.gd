class_name ParticipantSettings
extends RefCounted

const PARTICIPANT_PATH := "user://familiar_participant_id.txt"
const ORDER_PATH := "user://familiar_order_group.txt"
const PROFILE_A_PATH := "user://familiar_profile_a_id.txt"
const PROFILE_B_PATH := "user://familiar_profile_b_id.txt"
const CONTROL_PROFILE_ID := "generic_control_agent"
const VALID_ORDERS := ["A-B", "B-A"]


static func load_participant_id() -> String:
	return _read_text(PARTICIPANT_PATH)


static func save_participant_id(participant_id: String) -> void:
	_write_text(PARTICIPANT_PATH, participant_id.strip_edges())


static func load_order_group() -> String:
	var raw := _read_text(ORDER_PATH)
	return raw if raw in VALID_ORDERS else "A-B"


static func save_order_group(order_group: String) -> String:
	var normalized := order_group.strip_edges()
	if normalized not in VALID_ORDERS:
		normalized = "A-B"
	_write_text(ORDER_PATH, normalized)
	return normalized


static func load_profile_a_id() -> String:
	return _read_text(PROFILE_A_PATH)


static func load_profile_b_id() -> String:
	return _read_text(PROFILE_B_PATH)


static func save_profile_ids(profile_a_id: String, profile_b_id: String) -> void:
	_write_text(PROFILE_A_PATH, profile_a_id.strip_edges())
	_write_text(PROFILE_B_PATH, profile_b_id.strip_edges())


static func profile_for_condition(condition: String) -> String:
	if condition.to_upper() == "B":
		return CONTROL_PROFILE_ID
	return load_profile_a_id()


static func profiles_configured() -> bool:
	return not load_profile_a_id().is_empty()


static func profile_a_configured() -> bool:
	return not load_profile_a_id().is_empty()


static func _read_text(path: String) -> String:
	if not FileAccess.file_exists(path):
		return ""
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return ""
	var text := f.get_as_text().strip_edges()
	f.close()
	return text


static func _write_text(path: String, text: String) -> void:
	var w := FileAccess.open(path, FileAccess.WRITE)
	if w == null:
		return
	w.store_string(text)
	w.close()
