class_name ParticipantSettings
extends RefCounted

const PARTICIPANT_PATH := "user://familiar_participant_id.txt"
const ORDER_PATH := "user://familiar_order_group.txt"
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
