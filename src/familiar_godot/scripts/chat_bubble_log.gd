class_name ChatBubbleLog
extends ScrollContainer

const MAX_CHARS := 12_000

var _list: VBoxContainer
var _streaming_body: Label
var _char_count: int = 0


func _ready() -> void:
	horizontal_scroll_mode = SCROLL_MODE_DISABLED
	vertical_scroll_mode = SCROLL_MODE_AUTO
	ExperimentUI.style_chat_log(self)
	_ensure_list()
	resized.connect(_on_resized)


func _ensure_list() -> void:
	if _list != null:
		return
	_list = VBoxContainer.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_list.add_theme_constant_override("separation", ExperimentUI.BUBBLE_GAP)
	add_child(_list)


func _on_resized() -> void:
	_sync_bubble_widths()


func clear_log() -> void:
	_ensure_list()
	for child in _list.get_children():
		child.queue_free()
	_streaming_body = null
	_char_count = 0
	_scroll_to_bottom()


func is_empty() -> bool:
	_ensure_list()
	return _list.get_child_count() == 0 and _streaming_body == null


func append_user(text: String) -> void:
	_ensure_list()
	_finish_streaming()
	_list.add_child(ExperimentUI.make_user_bubble(text, _bubble_max_width()))
	_track_chars(text.length() + 24)
	_scroll_to_bottom()


func begin_assistant(label: String = "Buddy", kind: String = "buddy") -> void:
	_ensure_list()
	_finish_streaming()
	var bubble := ExperimentUI.make_assistant_bubble_open(label, kind, _bubble_max_width())
	_streaming_body = bubble["body"] as Label
	_list.add_child(bubble["root"] as Control)
	_scroll_to_bottom()


func append_assistant_delta(text: String) -> void:
	if text.is_empty():
		return
	if _streaming_body == null:
		begin_assistant()
	_streaming_body.text += text
	_track_chars(text.length())
	_scroll_to_bottom()


func finish_assistant() -> void:
	_streaming_body = null


func append_assistant(text: String, kind: String = "interview") -> void:
	_ensure_list()
	_finish_streaming()
	_list.add_child(ExperimentUI.make_assistant_bubble(text, kind, _bubble_max_width()))
	_track_chars(text.length() + 24)
	_scroll_to_bottom()


func _finish_streaming() -> void:
	_streaming_body = null


func _bubble_max_width() -> float:
	return maxf(size.x * ExperimentUI.BUBBLE_MAX_WIDTH_RATIO, 180.0)


func _sync_bubble_widths() -> void:
	if _list == null:
		return
	var max_w := _bubble_max_width()
	for child in _list.get_children():
		ExperimentUI.set_bubble_max_width(child, max_w)


func _scroll_to_bottom() -> void:
	call_deferred("_scroll_to_bottom_deferred")


func _scroll_to_bottom_deferred() -> void:
	await get_tree().process_frame
	var bar := get_v_scroll_bar()
	if bar != null:
		bar.value = bar.max_value


func _track_chars(n: int) -> void:
	_char_count += n
	while _char_count > MAX_CHARS and _list.get_child_count() > 1:
		_list.get_child(0).queue_free()
		_char_count = maxi(_char_count - 400, 0)
