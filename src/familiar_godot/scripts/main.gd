extends Control

@export var backend_ws: String = "ws://127.0.0.1:8000/ws/session"
@export var participant_id: String = ""
@export var session_id: String = ""
@export_enum("A", "B") var condition: String = "B"
@export_enum("A-B", "B-A") var order_group: String = "A-B"
@export var session_duration_sec: int = 600

const MAX_PACKETS_PER_FRAME := 8
const MAX_OUTPUT_CHARS := 12_000
const MAX_MP3_BYTES := 8 * 1024 * 1024
const FACE_TEX_PATH := "res://landing/OrangeBot_FBX/OrangeBot_FBX/Textures/Faces.jpg"
const WS_RECONNECT_DELAY_SEC := 2.0
const TTS_BUS_NAME := "TTS"
const TTS_LEVEL_GAIN := 12.0
const ORCHESTRATOR_SCENE := "res://scenes/experiment/ExperimentSessionMode.tscn"
const MAIN_MENU_SCENE := "res://scenes/experiment/ExperimentMenu.tscn"

var _peer: WebSocketPeer = WebSocketPeer.new()
var _session_ready: bool = false
var _turn_busy: bool = false
var _awaiting_tts_binary: bool = false
var _play_scheduled: bool = false
var _turn_index: int = 0
var _seconds_left: int = 0
var _second_accumulator: float = 0.0
var _reconnect_in: float = 0.0
var _buddy: Node3D

var _packet_backlog: Array[PackedByteArray] = []
var _audio_queue: Array[PackedByteArray] = []
var _pending_play_raw: PackedByteArray = PackedByteArray()
var _buddy_reply_open: bool = false

@onready var _input: LineEdit = %LineEdit
@onready var _send: Button = %SendButton
@onready var _timer_label: Label = %TimerLabel
@onready var _new_chat_button: Button = %NewChatButton
@onready var _restart_experiment_button: Button = %RestartExperimentButton
@onready var _condition_badge: Label = %ConditionBadge
@onready var _background: ColorRect = $Background
@onready var _avatar_panel: PanelContainer = $Margin/VBox/AvatarPanel
@onready var _chat_panel: PanelContainer = $Margin/VBox/ChatPanel
@onready var _condition_pill: PanelContainer = %TopRow/ConditionPill
@onready var _top_row: HBoxContainer = %TopRow
@onready var _pill_sep: VSeparator = %TopRow/ConditionPill/PillMargin/PillPad/PillSep
@onready var _out: RichTextLabel = %Output
@onready var _anim: Label = %AnimLabel
@onready var _player: AudioStreamPlayer = %AudioStreamPlayer
@onready var _avatar_ctl: Node = $AvatarController

var _avatar_viewport: SubViewport
var _avatar_viewport_container: SubViewportContainer
var _tts_bus_index: int = -1
var _tts_spectrum_idx: int = -1
var _session_end_sent: bool = false
var _experiment_run: bool = false
var _experiment_returned: bool = false
var _assistant_reply_buffer: String = ""


func _apply_backend_from_env() -> void:
	var ws := OS.get_environment("FAMILIAR_BACKEND_WS").strip_edges()
	if not ws.is_empty():
		backend_ws = ws
	var pid := OS.get_environment("FAMILIAR_PARTICIPANT_ID").strip_edges()
	if not pid.is_empty():
		participant_id = pid


func _load_participant_settings() -> void:
	_apply_backend_from_env()
	if participant_id.is_empty():
		participant_id = ParticipantSettings.load_participant_id()
	order_group = ParticipantSettings.load_order_group()


func _begin_new_session() -> void:
	_ensure_participant_id()
	session_id = _new_session_id()
	_turn_index = 0
	_turn_busy = false
	_buddy_reply_open = false
	_session_end_sent = false
	_packet_backlog.clear()
	_audio_queue.clear()
	_reset_turn_state()


func _ensure_participant_id() -> void:
	if not participant_id.is_empty():
		return
	participant_id = ParticipantSettings.load_participant_id()
	if participant_id.is_empty():
		participant_id = "p-%s" % _random_token()
		ParticipantSettings.save_participant_id(participant_id)
	order_group = ParticipantSettings.load_order_group()


func _new_session_id() -> String:
	return "s-%s-%d-%s" % [condition.to_lower(), Time.get_unix_time_from_system(), _random_token()]


func _random_token() -> String:
	return "%08x%08x" % [randi(), randi()]


func _active_profile_id() -> String:
	if _experiment_run:
		return ExperimentSessionManager.active_profile_id()
	return ParticipantSettings.profile_for_condition(condition)


func _apply_profile_payload(payload: Dictionary) -> void:
	payload["experiment_mode"] = true
	payload["profile_id"] = _active_profile_id()
	if _experiment_run:
		payload["interaction_index"] = ExperimentSessionManager.current_interaction_index


func _apply_experiment_run_config() -> void:
	participant_id = ExperimentSessionManager.participant_id
	condition = ExperimentSessionManager.current_condition
	order_group = ExperimentSessionManager.assigned_order_label
	session_duration_sec = ExperimentSessionManager.INTERACTION_SEC
	session_id = ExperimentSessionManager.interaction_session_id()
	_turn_index = 0
	_turn_busy = false
	_buddy_reply_open = false
	_session_end_sent = false
	_packet_backlog.clear()
	_audio_queue.clear()
	_reset_turn_state()


func _ready() -> void:
	_load_participant_settings()
	_experiment_run = (
		ExperimentSessionManager.is_run_active
		and ExperimentSessionManager.phase == ExperimentSessionManager.Phase.CHAT
	)
	if _experiment_run:
		_apply_experiment_run_config()
	else:
		_begin_new_session()
	ExperimentUI.apply(self)
	ExperimentUI.setup_main_screen({
		"background": _background,
		"avatar_panel": _avatar_panel,
		"chat_panel": _chat_panel,
		"condition_pill": _condition_pill,
		"top_row": _top_row,
		"pill_sep": _pill_sep,
		"condition_badge": _condition_badge,
		"timer_label": _timer_label,
		"new_chat_button": _new_chat_button,
		"menu_button": _restart_experiment_button,
		"send_button": _send,
		"output": _out,
		"condition": condition,
	})
	_apply_backend_from_env()
	_avatar_viewport = _resolve_viewport()
	_avatar_viewport_container = _resolve_viewport_container()
	if _experiment_run:
		_new_chat_button.visible = false
		_condition_badge.text = ExperimentSessionManager.participant_interaction_label()
	else:
		_condition_badge.text = "Condition %s" % condition
	_clear_chat_log()
	_send.pressed.connect(_on_send)
	_new_chat_button.pressed.connect(_on_new_chat)
	_restart_experiment_button.pressed.connect(_on_restart_experiment)
	_input.text_submitted.connect(func(_t: String) -> void:
		_on_send()
	)
	_seconds_left = session_duration_sec
	_update_timer_label()
	_buddy = _resolve_buddy()
	if is_instance_valid(_buddy):
		var presenter := get_node_or_null("AvatarPresenter")
		if presenter != null and presenter.has_method("apply"):
			presenter.call("apply", _buddy)
		if _avatar_ctl.has_method("setup"):
			_avatar_ctl.call("setup", _buddy)
			_anim.text = "anim: idle (expressions)"
	_patch_face_materials_if_orange_bot()
	if not _player.finished.is_connected(_on_audio_finished):
		_player.finished.connect(_on_audio_finished)
	_setup_tts_audio_bus()
	_setup_window_resize()
	_connect_ws()
	_send.focus_mode = Control.FOCUS_NONE
	call_deferred("_focus_chat_input")


func _setup_tts_audio_bus() -> void:
	_tts_bus_index = AudioServer.get_bus_index(TTS_BUS_NAME)
	if _tts_bus_index < 0:
		_tts_bus_index = AudioServer.bus_count
		AudioServer.add_bus(_tts_bus_index)
		AudioServer.set_bus_name(_tts_bus_index, TTS_BUS_NAME)
		AudioServer.set_bus_send(_tts_bus_index, &"Master")
	_tts_spectrum_idx = -1
	for i in range(AudioServer.get_bus_effect_count(_tts_bus_index)):
		if AudioServer.get_bus_effect(_tts_bus_index, i) is AudioEffectSpectrumAnalyzer:
			_tts_spectrum_idx = i
			break
	if _tts_spectrum_idx < 0:
		var spectrum := AudioEffectSpectrumAnalyzer.new()
		spectrum.buffer_length = 0.04
		spectrum.fft_size = AudioEffectSpectrumAnalyzer.FFT_SIZE_512
		_tts_spectrum_idx = AudioServer.get_bus_effect_count(_tts_bus_index)
		AudioServer.add_bus_effect(_tts_bus_index, spectrum)
	_player.bus = TTS_BUS_NAME


func _tick_lip_sync_from_audio() -> void:
	if _avatar_ctl == null or not _avatar_ctl.has_method("update_lip_sync"):
		return
	var level := 0.0
	if _player.playing:
		level = _sample_tts_level()
	_avatar_ctl.call("update_lip_sync", level)


func _sample_tts_level() -> float:
	if _tts_bus_index < 0 or _tts_spectrum_idx < 0:
		return 0.0
	var inst := AudioServer.get_bus_effect_instance(_tts_bus_index, _tts_spectrum_idx)
	if inst == null:
		return 0.0
	var mag: Vector2 = inst.get_magnitude_for_frequency_range(180.0, 4500.0)
	var linear := (mag.x + mag.y) * 0.5
	return clampf(linear * TTS_LEVEL_GAIN, 0.0, 1.0)


func _setup_window_resize() -> void:
	var win := get_window()
	ExperimentUI.configure_window(win)
	if not win.size_changed.is_connected(_on_window_resized):
		win.size_changed.connect(_on_window_resized)
	if not get_viewport().size_changed.is_connected(_on_window_resized):
		get_viewport().size_changed.connect(_on_window_resized)
	_on_window_resized()


func _connect_ws() -> void:
	var err: int = _peer.connect_to_url(backend_ws)
	if err != OK:
		_set_status("connect_to_url failed: %s" % err)
	else:
		_set_status("connecting…")


func _schedule_reconnect() -> void:
	_reconnect_in = WS_RECONNECT_DELAY_SEC
	_set_status("disconnected — reconnecting in %.0fs…" % WS_RECONNECT_DELAY_SEC)


func _process(_delta: float) -> void:
	_sync_avatar_viewport_size()
	_tick_timer(_delta)
	_tick_reconnect(_delta)
	_tick_lip_sync_from_audio()
	_peer.poll()
	var st: int = _peer.get_ready_state()
	if st == WebSocketPeer.STATE_OPEN:
		if not _session_ready:
			_session_ready = true
			_reconnect_in = 0.0
			_set_status("connected")
			_send_hello()
		var budget: int = MAX_PACKETS_PER_FRAME
		while budget > 0 and _peer.get_available_packet_count() > 0:
			_packet_backlog.append(_peer.get_packet())
			budget -= 1
		var handle_budget: int = MAX_PACKETS_PER_FRAME
		while handle_budget > 0 and not _packet_backlog.is_empty():
			_dispatch_packet(_packet_backlog.pop_front())
			handle_budget -= 1
	elif st == WebSocketPeer.STATE_CLOSED:
		if _session_ready:
			_session_ready = false
			_reset_turn_state()
			_schedule_reconnect()


func _tick_reconnect(delta: float) -> void:
	if _reconnect_in <= 0.0:
		return
	_reconnect_in -= delta
	if _reconnect_in > 0.0:
		return
	if _peer.get_ready_state() == WebSocketPeer.STATE_OPEN:
		return
	_peer = WebSocketPeer.new()
	_connect_ws()


func _dispatch_packet(pkt: PackedByteArray) -> void:
	if _awaiting_tts_binary:
		_awaiting_tts_binary = false
		_on_tts_binary(pkt)
		return
	_on_json_packet(pkt)


func _send_hello() -> void:
	_send_session_event("session.hello")


func _send_session_new() -> void:
	_send_session_event("session.new")


func _send_session_event(event_type: String) -> void:
	if _peer.get_ready_state() != WebSocketPeer.STATE_OPEN:
		return
	var payload: Dictionary = {
		"client": "godot",
		"participant_id": participant_id,
		"session_id": session_id,
		"condition": condition,
		"order_group": order_group,
	}
	if _experiment_run:
		payload["experiment_mode"] = true
		payload["profile_id"] = ExperimentSessionManager.active_profile_id()
		payload["interaction_index"] = ExperimentSessionManager.current_interaction_index
	else:
		_apply_profile_payload(payload)
	var msg: Dictionary = {
		"v": 1,
		"type": event_type,
		"payload": payload,
	}
	_peer.send_text(JSON.stringify(msg))


func _flush_ws_outbound() -> void:
	if _peer.get_ready_state() != WebSocketPeer.STATE_OPEN:
		return
	for _i in range(6):
		_peer.poll()


func _session_elapsed_sec() -> int:
	return maxi(0, session_duration_sec - _seconds_left)


func _send_session_end(reason: String) -> void:
	if _session_end_sent or session_id.is_empty():
		return
	_session_end_sent = true
	if _peer.get_ready_state() != WebSocketPeer.STATE_OPEN:
		return
	var msg: Dictionary = {
		"v": 1,
		"type": "session.end",
		"payload": {
			"participant_id": participant_id,
			"session_id": session_id,
			"condition": condition,
			"order_group": order_group,
			"duration_sec": _session_elapsed_sec(),
			"message_count": _turn_index,
			"reason": reason,
		},
	}
	_peer.send_text(JSON.stringify(msg))
	_flush_ws_outbound()


func _on_send() -> void:
	if _turn_busy:
		_set_status("wait for buddy to finish…")
		return
	var text: String = _input.text.strip_edges()
	if text.is_empty():
		return
	if _peer.get_ready_state() != WebSocketPeer.STATE_OPEN:
		_set_status("not connected yet")
		return
	_turn_busy = true
	_send.disabled = true
	var turn_payload: Dictionary = {
		"participant_id": participant_id,
		"session_id": session_id,
		"condition": condition,
		"order_group": order_group,
		"turn_index": _turn_index,
		"text": text,
	}
	if _experiment_run:
		turn_payload["experiment_mode"] = true
		turn_payload["profile_id"] = ExperimentSessionManager.active_profile_id()
		turn_payload["interaction_index"] = ExperimentSessionManager.current_interaction_index
		ExperimentSessionManager.append_message("user", text)
		ExperimentSessionManager.log_run_event("user_message", {"text": text})
	else:
		_apply_profile_payload(turn_payload)
	var msg: Dictionary = {
		"v": 1,
		"type": "turn.user_text",
		"payload": turn_payload,
	}
	_turn_index += 1
	_peer.send_text(JSON.stringify(msg))
	_input.clear()
	_focus_chat_input()
	_buddy_reply_open = false
	_assistant_reply_buffer = ""
	_out.append_text(ExperimentUI.format_user_bubble(text))
	_start_buddy_thinking()


func _clear_chat_log() -> void:
	_out.text = ExperimentUI.chat_placeholder()


func _on_new_chat() -> void:
	if _turn_busy:
		_set_status("wait for buddy to finish before starting a new chat")
		return
	_player.stop()
	_stop_buddy_thinking()
	_send_session_end("new_chat")
	_begin_new_session()
	_clear_chat_log()
	_seconds_left = session_duration_sec
	_second_accumulator = 0.0
	_update_timer_label()
	_send.disabled = false
	if _peer.get_ready_state() == WebSocketPeer.STATE_OPEN:
		_send_session_new()
	_focus_chat_input()


func _on_restart_experiment() -> void:
	if _turn_busy:
		_set_status("wait for current turn to finish before restart")
		return
	_send_session_end("menu")
	_flush_ws_outbound()
	if _experiment_run:
		if not _experiment_returned:
			_experiment_returned = true
			_return_to_orchestrator()
		return
	var err := get_tree().change_scene_to_file(MAIN_MENU_SCENE)
	if err != OK:
		_set_status("could not return to menu: %s" % err)


func _return_to_orchestrator() -> void:
	ExperimentSessionManager.finish_interaction()
	get_tree().change_scene_to_file(ORCHESTRATOR_SCENE)


func _tick_timer(delta: float) -> void:
	if _seconds_left <= 0:
		return
	_second_accumulator += delta
	while _second_accumulator >= 1.0 and _seconds_left > 0:
		_second_accumulator -= 1.0
		_seconds_left -= 1
	_update_timer_label()
	if _seconds_left <= 0:
		_send.disabled = true
		_set_status("session time is over")
		_send_session_end("timer")
		if _experiment_run and not _experiment_returned:
			_experiment_returned = true
			call_deferred("_return_to_orchestrator")


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		_send_session_end("window_close")


func _exit_tree() -> void:
	_send_session_end("exit")


func _update_timer_label() -> void:
	var minutes := int(_seconds_left / 60.0)
	var seconds := _seconds_left % 60
	_timer_label.text = "%02d:%02d" % [minutes, seconds]


func _on_json_packet(pkt: PackedByteArray) -> void:
	var s: String = pkt.get_string_from_utf8()
	var parsed: Variant = JSON.parse_string(s)
	if typeof(parsed) != TYPE_DICTIONARY:
		return
	var data: Dictionary = parsed
	var typ: String = String(data.get("type", ""))
	var payload: Dictionary = data.get("payload", {})
	if typeof(payload) != TYPE_DICTIONARY:
		payload = {}
	match typ:
		"session.hello_ack":
			_set_status("ready")
			_focus_chat_input()
		"listening.state":
			var listen_state := String(payload.get("state", ""))
			if listen_state == "processing":
				_set_status("thinking…")
				_start_buddy_thinking()
			else:
				_set_status("listening: %s" % listen_state)
		"llm.delta":
			_stop_buddy_thinking()
			var delta := String(payload.get("text", ""))
			_assistant_reply_buffer += delta
			_append_output(delta)
		"llm.done":
			_close_buddy_bubble()
			if _experiment_run and not _assistant_reply_buffer.is_empty():
				ExperimentSessionManager.append_message("assistant", _assistant_reply_buffer)
				ExperimentSessionManager.log_run_event(
					"assistant_message",
					{"text": _assistant_reply_buffer}
				)
				_assistant_reply_buffer = ""
		"anim.command":
			var clip_id := String(payload.get("clip_id", "idle"))
			var blend := float(payload.get("blend_time", 0.2))
			_anim.text = "anim: %s (%.2fs)" % [clip_id, blend]
			_apply_bot_animation(clip_id, blend)
		"tts.chunk_meta":
			var idx: int = int(payload.get("index", 0))
			var total: int = int(payload.get("total", 1))
			var nbytes: int = int(payload.get("bytes", 0))
			var kb := float(nbytes) / 1024.0
			_set_status("audio %d/%d (%.1f KB)…" % [idx + 1, total, kb])
			_awaiting_tts_binary = true
		"tts.error":
			_set_status("audio error: %s" % payload.get("error", ""))
		"turn.end":
			_finish_turn(payload)
		_:
			pass


func _on_tts_binary(pkt: PackedByteArray) -> void:
	if pkt.is_empty():
		_set_status("audio: empty chunk")
		return
	if pkt.size() > MAX_MP3_BYTES:
		push_warning("TTS chunk too large (%d bytes), skipped" % pkt.size())
		_set_status("audio chunk too large, skipped")
		return
	_enqueue_audio(pkt)


func _finish_turn(payload: Dictionary) -> void:
	_turn_busy = false
	_send.disabled = false
	_awaiting_tts_binary = false
	_stop_buddy_thinking()
	_close_buddy_bubble()
	var errors: Variant = payload.get("audio_errors", [])
	if payload.has("error") and str(payload.get("error", "")) != "":
		_set_status("error: %s" % payload.get("error", ""))
	elif errors is Array and not errors.is_empty():
		_set_status("ready (audio had %d errors)" % errors.size())
	elif bool(payload.get("tts_truncated", false)):
		_set_status("ready (speech truncated for length)")
	else:
		_set_status("ready")
	_focus_chat_input()


func _focus_chat_input() -> void:
	if not is_instance_valid(_input):
		return
	_input.grab_focus()


func _reset_turn_state() -> void:
	_turn_busy = false
	_send.disabled = false
	_awaiting_tts_binary = false
	_play_scheduled = false
	if _avatar_ctl.has_method("stop_lip_sync"):
		_avatar_ctl.call("stop_lip_sync")


func _append_output(text: String) -> void:
	if text.is_empty():
		return
	if not _buddy_reply_open:
		_out.append_text(ExperimentUI.format_assistant_open())
		_buddy_reply_open = true
	_out.append_text(ExperimentUI.escape_bbcode(text))
	if _out.text.length() > MAX_OUTPUT_CHARS:
		_out.text = _out.text.substr(-MAX_OUTPUT_CHARS)


func _close_buddy_bubble() -> void:
	if not _buddy_reply_open:
		return
	_out.append_text(ExperimentUI.format_assistant_close())
	_buddy_reply_open = false


func _enqueue_audio(raw: PackedByteArray) -> void:
	_audio_queue.append(raw)
	if not _player.playing and not _play_scheduled:
		_play_scheduled = true
		call_deferred("_play_next_audio")


func _play_next_audio() -> void:
	_play_scheduled = false
	if _audio_queue.is_empty():
		return
	if _player.playing:
		_play_scheduled = true
		call_deferred("_play_next_audio")
		return
	var raw: PackedByteArray = _audio_queue.pop_front()
	_pending_play_raw = raw
	call_deferred("_apply_pending_mp3")


func _apply_pending_mp3() -> void:
	if _pending_play_raw.is_empty():
		_play_next_audio()
		return
	var raw: PackedByteArray = _pending_play_raw
	_pending_play_raw = PackedByteArray()
	var stream := AudioStreamMP3.new()
	stream.data = raw
	_player.stream = stream
	_player.play()
	if _avatar_ctl.has_method("start_lip_sync"):
		_avatar_ctl.call("start_lip_sync")


func _on_audio_finished() -> void:
	if _audio_queue.is_empty() and _avatar_ctl.has_method("stop_lip_sync"):
		_avatar_ctl.call("stop_lip_sync")
	_play_next_audio()


func _resolve_viewport() -> SubViewport:
	var node := get_node_or_null("%AvatarViewport") as SubViewport
	if node != null:
		return node
	return find_child("AvatarViewport", true, false) as SubViewport


func _resolve_viewport_container() -> SubViewportContainer:
	var node := get_node_or_null("%AvatarViewportContainer") as SubViewportContainer
	if node != null:
		return node
	return find_child("AvatarViewportContainer", true, false) as SubViewportContainer


func _resolve_buddy() -> Node3D:
	var buddy := get_node_or_null("%Buddy") as Node3D
	if buddy != null:
		return buddy
	buddy = find_child("Buddy", true, false) as Node3D
	if buddy != null:
		return buddy
	return get_node_or_null("%OrangeBot") as Node3D


func _patch_face_materials_if_orange_bot() -> void:
	if not is_instance_valid(_buddy):
		return
	if _buddy.name != "OrangeBot" and not String(_buddy.scene_file_path).contains("OrangeBot"):
		return
	var face_tex := load(FACE_TEX_PATH) as Texture2D
	if face_tex == null:
		push_warning("Face texture not found: %s" % FACE_TEX_PATH)
		return
	_apply_face_texture_recursive(_buddy, face_tex)


func _apply_face_texture_recursive(root: Node, face_tex: Texture2D) -> void:
	if root is MeshInstance3D:
		var mi := root as MeshInstance3D
		var mesh := mi.mesh
		if mesh != null:
			for i in range(mesh.get_surface_count()):
				var mat := mi.get_active_material(i)
				if mat == null:
					mat = mesh.surface_get_material(i)
				if mat == null:
					continue
				var mat_name := String(mat.resource_name).to_lower()
				if not (mat_name.contains("face") or mat_name.contains("screen")):
					continue
				var base := mat as BaseMaterial3D
				var patched := base.duplicate() if base != null else StandardMaterial3D.new()
				if patched is BaseMaterial3D:
					var p := patched as BaseMaterial3D
					p.albedo_texture = face_tex
					p.emission_enabled = true
					p.emission_texture = face_tex
					p.emission_energy_multiplier = 0.5
				mi.set_surface_override_material(i, patched)
	for child in root.get_children():
		_apply_face_texture_recursive(child, face_tex)


func _start_buddy_thinking() -> void:
	if _avatar_ctl.has_method("start_thinking"):
		_avatar_ctl.call("start_thinking")
		_anim.text = "anim: thinking…"


func _stop_buddy_thinking() -> void:
	if _avatar_ctl.has_method("stop_thinking"):
		_avatar_ctl.call("stop_thinking")


func _apply_bot_animation(clip_id: String, blend: float) -> void:
	_stop_buddy_thinking()
	if _avatar_ctl.has_method("play_reaction"):
		_avatar_ctl.call("play_reaction", clip_id, blend)


func _set_status(_t: String) -> void:
	pass


func _on_window_resized() -> void:
	call_deferred("_sync_avatar_viewport_size")


func _sync_avatar_viewport_size() -> void:
	var vp := _resolve_viewport()
	var vpc := _resolve_viewport_container()
	if not is_instance_valid(vp) or not is_instance_valid(vpc):
		return
	var s := vpc.get_rect().size
	if s.x < 1.0 or s.y < 1.0:
		s = vpc.size
	var target := Vector2i(max(1, int(round(s.x))), max(1, int(round(s.y))))
	if vp.size != target:
		vp.size = target
