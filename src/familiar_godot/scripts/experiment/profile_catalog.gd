class_name ProfileCatalog
extends RefCounted

const LOCAL_RAW_DIR := "user://profiles/raw"
const EMPTY_LABEL := "(no profiles — train one first)"


static func list_local_raw_profile_ids() -> Array[String]:
	var ids: Array[String] = []
	if not DirAccess.dir_exists_absolute(LOCAL_RAW_DIR):
		return ids
	var dir := DirAccess.open(LOCAL_RAW_DIR)
	if dir == null:
		return ids
	for file_name in dir.get_files():
		if file_name.ends_with(".json"):
			ids.append(file_name.get_basename())
	ids.sort()
	return ids


static func merge_profile_ids(remote: Array, local: Array[String]) -> Array[String]:
	var seen: Dictionary = {}
	var out: Array[String] = []
	for source in [remote, local]:
		for item in source:
			var id := str(item).strip_edges()
			if id.is_empty() or seen.has(id):
				continue
			seen[id] = true
			out.append(id)
	out.sort()
	return out


static func populate_option(select: OptionButton, profile_ids: Array[String]) -> void:
	select.clear()
	if profile_ids.is_empty():
		select.add_item(EMPTY_LABEL)
		select.disabled = true
		return
	select.disabled = false
	for i in range(profile_ids.size()):
		select.add_item(profile_ids[i], i)


static func selected_profile_id(select: OptionButton) -> String:
	if select.disabled or select.item_count == 0:
		return ""
	var text := select.get_item_text(select.selected).strip_edges()
	if text.begins_with("("):
		return ""
	return text


static func select_profile_id(select: OptionButton, profile_id: String) -> void:
	if profile_id.is_empty() or select.item_count == 0:
		return
	for i in range(select.item_count):
		if select.get_item_text(i) == profile_id:
			select.select(i)
			return
