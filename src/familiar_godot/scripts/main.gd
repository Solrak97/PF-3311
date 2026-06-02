extends Control

@export var backend_ws: String = "ws://127.0.0.1:8000/ws/session"
@export var participant_id: String = ""
@export var session_id: String = ""
@export_enum("A", "B") var condition: String = "B"
@export_enum("A-B", "B-A") var order_group: String = "A-B"
@export var session_duration_sec: int = 600

## LLM streaming can emit many small text frames; capping too low leaves TTS binary stuck in backlog (often ~3rd reply).
const MAX_WS_PACKETS_PER_FRAME := 256
const MAX_MP3_BYTES := 8 * 1024 * 1024
const WS_RECONNECT_DELAY_SEC := 2.0
const TTS_BUS_NAME := "TTS"
const TTS_LEVEL_GAIN := 12.0
const ORCHESTRATOR_SCENE := "res://scenes/experiment/ExperimentSessionMode.tscn"
const MAIN_MENU_SCENE := "res://scenes/experiment/ExperimentMenu.tscn"

## BuddyTTS lines in Godot Output — set false to silence.
@export var buddy_tts_log: bool = true

var _peer: WebSocketPeer = WebSocketPeer.new()
var _session_ready: bool = false
var _turn_busy: bool = false
var _play_scheduled: bool = false
var _turn_index: int = 0
var _seconds_left: int = 0
var _second_accumulator: float = 0.0
var _reconnect_in: float = 0.0
var _reconnect_when_idle: bool = false
var _expected_tts_chunks: int = 0
var _received_tts_chunks: int = 0
var _turn_end_pending: bool = false
var _buddy: Node3D

## Each entry: { "pkt": PackedByteArray, "is_text": bool } — route by WebSocket frame type, not order heuristics.
var _packet_backlog: Array = []
var _audio_queue: Array = []
var _pending_play_stream: Variant = null
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
@onready var _out: ChatBubbleLog = %Output
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
var _exit_early_button: Button
var _assistant_reply_buffer: String = ""
var _conversation_open_pending: bool = false
var _tts_http: HTTPRequest
var _tts_http_queue: Array[String] = []
var _tts_http_fetching: bool = false


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
	_conversation_open_pending = false


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
	_conversation_open_pending = false


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
		_exit_early_button = Button.new()
		_exit_early_button.text = "Salir"
		ExperimentUI.style_secondary_button(_exit_early_button)
		_exit_early_button.pressed.connect(_on_exit_early_pressed)
		_restart_experiment_button.get_parent().add_child(_exit_early_button)
		_restart_experiment_button.get_parent().move_child(_exit_early_button, 0)
		_restart_experiment_button.text = "Fin interacción"
		_condition_badge.text = ExperimentSessionManager.participant_interaction_label()
	else:
		_condition_badge.text = "Condición %s" % condition
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
	if not _player.finished.is_connected(_on_audio_finished):
		_player.finished.connect(_on_audio_finished)
	_tts_http = HTTPRequest.new()
	add_child(_tts_http)
	_tts_http.request_completed.connect(_on_tts_http_completed)
	_setup_tts_audio_bus()
	_setup_window_resize()
	_connect_ws()
	_send.focus_mode = Control.FOCUS_NONE
	call_deferred("_focus_chat_input")


func _setup_tts_audio_bus() -> void:
	_player.bus = &"Master"
	_player.volume_db = 0.0
	_player.volume_linear = 1.0
	_player.stream_paused = false
	_player.max_polyphony = 1
	var master_bus := AudioServer.get_bus_index(&"Master")
	if master_bus >= 0:
		AudioServer.set_bus_mute(master_bus, false)
	_tts_bus_index = AudioServer.get_bus_index(TTS_BUS_NAME)
	if _tts_bus_index >= 0:
		_tts_spectrum_idx = -1
		for i in range(AudioServer.get_bus_effect_count(_tts_bus_index)):
			if AudioServer.get_bus_effect(_tts_bus_index, i) is AudioEffectSpectrumAnalyzer:
				_tts_spectrum_idx = i
				break


func _tick_lip_sync_from_audio() -> void:
	if _avatar_ctl == null or not _avatar_ctl.has_method("update_lip_sync"):
		return
	var level := 0.0
	if _player.playing:
		level = _sample_tts_level()
	_avatar_ctl.call("update_lip_sync", level)


func _sample_tts_level() -> float:
	if _tts_bus_index >= 0 and _tts_spectrum_idx >= 0:
		var inst := AudioServer.get_bus_effect_instance(_tts_bus_index, _tts_spectrum_idx)
		if inst != null:
			var mag: Vector2 = inst.get_magnitude_for_frequency_range(180.0, 4500.0)
			var linear := (mag.x + mag.y) * 0.5
			var from_bus := linear * TTS_LEVEL_GAIN
			if from_bus > 0.05:
				return clampf(from_bus, 0.0, 1.0)
	# Fallback when TTS is on Master (no spectrum on that path).
	return 0.55 if _player.playing else 0.0


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
		_set_status("Error de conexión: %s" % err)
	else:
		_set_status("Conectando…")


func _schedule_reconnect() -> void:
	if _has_pending_audio_work():
		_reconnect_when_idle = true
		return
	_reconnect_when_idle = false
	_reconnect_in = WS_RECONNECT_DELAY_SEC
	_set_status("Desconectado — reconectando en %.0f s…" % WS_RECONNECT_DELAY_SEC)


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
			_reconnect_when_idle = false
			_set_status("Conectado")
			_send_hello()
		var recv_budget: int = MAX_WS_PACKETS_PER_FRAME
		while recv_budget > 0 and _peer.get_available_packet_count() > 0:
			_packet_backlog.append({
				"pkt": _peer.get_packet(),
				"is_text": _peer.was_string_packet(),
			})
			recv_budget -= 1
	_drain_packet_backlog()
	if st == WebSocketPeer.STATE_CLOSED:
		if _session_ready:
			var code := _peer.get_close_code()
			var reason := _peer.get_close_reason()
			_tts_log("WS CLOSED code=%s reason=%s backlog=%d queue=%d playing=%s" % [
				code, reason, _packet_backlog.size(), _audio_queue.size(), _player.playing
			])
			_session_ready = false
			_drain_packet_backlog()
			_reset_turn_state_after_disconnect()
			_schedule_reconnect()
	elif _reconnect_when_idle and not _has_pending_audio_work():
		_schedule_reconnect()


func _tick_reconnect(delta: float) -> void:
	if _reconnect_when_idle:
		return
	if _reconnect_in <= 0.0:
		return
	_reconnect_in -= delta
	if _reconnect_in > 0.0:
		return
	if _has_pending_audio_work():
		_reconnect_when_idle = true
		return
	if _peer.get_ready_state() == WebSocketPeer.STATE_OPEN:
		return
	_peer = WebSocketPeer.new()
	_connect_ws()


func _drain_packet_backlog() -> void:
	var budget: int = MAX_WS_PACKETS_PER_FRAME
	while budget > 0 and not _packet_backlog.is_empty():
		_dispatch_packet(_packet_backlog.pop_front())
		budget -= 1


func _has_pending_audio_work() -> bool:
	if _turn_end_pending and _received_tts_chunks < _expected_tts_chunks:
		return true
	if not _audio_queue.is_empty():
		return true
	if _player.playing:
		return true
	if _pending_play_stream != null:
		return true
	return false


func _begin_incoming_turn() -> void:
	_expected_tts_chunks = 0
	_received_tts_chunks = 0
	_turn_end_pending = false
	_tts_log("turn START (listening.processing)")


func _dispatch_packet(item: Variant) -> void:
	if typeof(item) != TYPE_DICTIONARY:
		return
	var pkt: PackedByteArray = item.get("pkt", PackedByteArray())
	if pkt.is_empty():
		return
	if bool(item.get("is_text", true)):
		_on_json_packet(pkt)
	else:
		_on_tts_binary(pkt)


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
		payload["scenario_id"] = ExperimentSessionManager.scenario_id_for_interaction()
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


func _send_conversation_open() -> void:
	if _turn_busy or _conversation_open_pending:
		return
	if _peer.get_ready_state() != WebSocketPeer.STATE_OPEN:
		return
	if not _out.is_empty():
		return
	_conversation_open_pending = true
	_turn_busy = true
	_send.disabled = true
	var turn_payload: Dictionary = {
		"participant_id": participant_id,
		"session_id": session_id,
		"condition": condition,
		"order_group": order_group,
		"turn_index": _turn_index,
	}
	if _experiment_run:
		turn_payload["experiment_mode"] = true
		turn_payload["profile_id"] = ExperimentSessionManager.active_profile_id()
		turn_payload["interaction_index"] = ExperimentSessionManager.current_interaction_index
		turn_payload["scenario_id"] = ExperimentSessionManager.scenario_id_for_interaction()
	else:
		_apply_profile_payload(turn_payload)
	var msg: Dictionary = {
		"v": 1,
		"type": "turn.conversation_open",
		"payload": turn_payload,
	}
	_peer.send_text(JSON.stringify(msg))
	_flush_ws_outbound()
	_buddy_reply_open = false
	_assistant_reply_buffer = ""
	_start_buddy_thinking()


func _on_send() -> void:
	if _turn_busy:
		_set_status("Espera a que Buddy termine…")
		return
	var text: String = _input.text.strip_edges()
	if text.is_empty():
		return
	if _peer.get_ready_state() != WebSocketPeer.STATE_OPEN:
		_set_status("Aún no hay conexión")
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
		turn_payload["scenario_id"] = ExperimentSessionManager.scenario_id_for_interaction()
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
	_out.append_user(text)
	_start_buddy_thinking()


func _clear_chat_log() -> void:
	_out.clear_log()


func _on_new_chat() -> void:
	if _turn_busy:
		_set_status("Espera a que Buddy termine antes de un chat nuevo")
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
		_set_status("Espera a que termine el turno actual antes de reiniciar")
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
		_set_status("No se pudo volver al menú: %s" % err)


func _on_exit_early_pressed() -> void:
	if _turn_busy:
		_set_status("Espera a que termine el turno actual antes de salir")
		return
	ExperimentExitHelper.confirm_exit(self, _complete_exit_early)


func _complete_exit_early() -> void:
	_send_session_end("early_exit")
	_flush_ws_outbound()
	_experiment_returned = true
	ExperimentSessionManager.exit_run_early("chat_ui")
	get_tree().change_scene_to_file(ORCHESTRATOR_SCENE)


func _return_to_orchestrator() -> void:
	ExperimentSessionManager.finish_interaction()
	if ExperimentSessionManager.phase == ExperimentSessionManager.Phase.QUESTIONNAIRE:
		get_tree().change_scene_to_file(ExperimentSessionManager.QUESTIONNAIRE_SCENE)
	else:
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
		_set_status("Se acabó el tiempo de la sesión")
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
			_set_status("Listo")
			_focus_chat_input()
			if _out.is_empty() and not _conversation_open_pending:
				call_deferred("_send_conversation_open")
		"listening.state":
			var listen_state := String(payload.get("state", ""))
			if listen_state == "processing":
				_begin_incoming_turn()
				_set_status("Pensando…")
				_start_buddy_thinking()
			else:
				_set_status("Escuchando: %s" % listen_state)
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
					{
						"text": _assistant_reply_buffer,
						"scenario_id": ExperimentSessionManager.scenario_id_for_interaction(),
					}
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
			_set_status("Audio %d/%d (%.1f KB)…" % [idx + 1, total, kb])
		"tts.audio_chunk":
			_ingest_tts_audio_payload(payload)
		"tts.error":
			_received_tts_chunks += 1
			_set_status("Error de audio: %s" % payload.get("error", ""))
			_try_unlock_turn_after_audio()
		"turn.end":
			_finish_turn(payload)
		_:
			pass


func _play_tts_audio_b64_list(parts: Variant) -> int:
	if not parts is Array:
		_tts_log("turn.end tts_audio_b64 missing or not array")
		return 0
	var played := 0
	for i in range(parts.size()):
		var b64 := String(parts[i])
		if b64.is_empty():
			_tts_log("  part %d empty b64" % i)
			continue
		var raw: PackedByteArray = Marshalls.base64_to_raw(b64)
		var magic := raw.slice(0, mini(4, raw.size())).get_string_from_ascii() if raw.size() >= 4 else "?"
		_tts_log("  part %d b64_len=%d raw=%d magic=%s" % [i, b64.length(), raw.size(), magic])
		if _enqueue_tts_bytes(raw):
			played += 1
	return played


func _ingest_tts_audio_payload(payload: Dictionary) -> void:
	var idx: int = int(payload.get("index", 0))
	var total: int = int(payload.get("total", 1))
	var b64 := String(payload.get("data_b64", ""))
	var nbytes: int = int(payload.get("bytes", 0))
	if nbytes <= 0 and not b64.is_empty():
		nbytes = int(b64.length() * 3 / 4)
	var kb := float(nbytes) / 1024.0
	_set_status("Audio %d/%d (%.1f KB)…" % [idx + 1, total, kb])
	if b64.is_empty():
		push_warning("tts.audio_chunk missing data_b64")
		_received_tts_chunks += 1
		_try_unlock_turn_after_audio()
		return
	var raw: PackedByteArray = Marshalls.base64_to_raw(b64)
	_tts_log("tts.audio_chunk legacy b64=%d raw=%d" % [b64.length(), raw.size()])
	if _enqueue_tts_bytes(raw):
		_received_tts_chunks += 1
	_try_unlock_turn_after_audio()


func _on_tts_binary(pkt: PackedByteArray) -> void:
	_tts_log("binary frame %d bytes (legacy)" % pkt.size())
	if _enqueue_tts_bytes(pkt):
		_received_tts_chunks += 1
	_try_unlock_turn_after_audio()


func _enqueue_tts_bytes(raw: PackedByteArray) -> bool:
	if raw.is_empty():
		_tts_log("enqueue SKIP empty")
		return false
	if raw.size() > MAX_MP3_BYTES:
		_tts_log("enqueue SKIP too large %d" % raw.size())
		return false
	var stream := _decode_tts_audio(raw)
	if stream == null:
		_tts_log("enqueue SKIP decode failed %d bytes" % raw.size())
		return false
	var dur := _estimate_stream_duration(stream)
	_enqueue_audio_stream(stream)
	_tts_log("enqueue OK raw=%d dur=%.2fs queue=%d player_playing=%s" % [
		raw.size(), dur, _audio_queue.size(), _player.playing
	])
	return true


func _tts_log(msg: String) -> void:
	if buddy_tts_log:
		print("[BuddyTTS] ", msg)


func _backend_http_base() -> String:
	var base := OS.get_environment("FAMILIAR_BACKEND_HTTP").strip_edges()
	if not base.is_empty():
		return base.rstrip("/")
	base = backend_ws.replace("wss://", "https://").replace("ws://", "http://")
	var ws_path := base.find("/ws/")
	if ws_path > 0:
		base = base.substr(0, ws_path)
	return base.rstrip("/")


func _queue_tts_http_urls(urls: Array) -> int:
	var n := 0
	for item in urls:
		var path := String(item)
		if path.is_empty():
			continue
		_tts_http_queue.append(path)
		n += 1
	if n > 0:
		_tts_log("queued %d TTS HTTP download(s)" % n)
		_kick_tts_http_fetch()
	return n


func _kick_tts_http_fetch() -> void:
	if _tts_http_fetching or _tts_http_queue.is_empty():
		return
	_tts_http_fetching = true
	var path: String = _tts_http_queue.pop_front()
	var url: String = _backend_http_base() + path
	_tts_log("HTTP GET %s" % url)
	_tts_http.request(url)


func _on_tts_http_completed(
	result: int,
	response_code: int,
	_headers: PackedStringArray,
	body: PackedByteArray
) -> void:
	_tts_http_fetching = false
	if result != HTTPRequest.RESULT_SUCCESS or response_code != 200:
		_tts_log("HTTP TTS FAIL result=%s code=%s bytes=%d" % [result, response_code, body.size()])
	else:
		if _enqueue_tts_bytes(body):
			_received_tts_chunks += 1
	_kick_tts_http_fetch()
	_try_unlock_turn_after_audio()


func _finish_turn(payload: Dictionary) -> void:
	var had_error := payload.has("error") and str(payload.get("error", "")) != ""
	if _conversation_open_pending:
		if had_error and _out.is_empty():
			_conversation_open_pending = false
		else:
			_conversation_open_pending = false
			_turn_index += 1
	var url_count := 0
	var urls: Variant = payload.get("tts_audio_urls", [])
	if urls is Array:
		url_count = _queue_tts_http_urls(urls)
	var b64_played := _play_tts_audio_b64_list(payload.get("tts_audio_b64", []))
	_expected_tts_chunks = maxi(int(payload.get("tts_chunk_count", 0)), url_count + b64_played)
	_received_tts_chunks = b64_played
	_tts_log(
		"turn.end expected=%d b64_played=%d http_queued=%d audio_errors=%s"
		% [_expected_tts_chunks, b64_played, url_count, str(payload.get("audio_errors", []))]
	)
	_turn_end_pending = true
	if payload.has("error") and str(payload.get("error", "")) != "":
		_expected_tts_chunks = 0
		_received_tts_chunks = 0
	_stop_buddy_thinking()
	_close_buddy_bubble()
	var errors: Variant = payload.get("audio_errors", [])
	if payload.has("error") and str(payload.get("error", "")) != "":
		_set_status("Error: %s" % payload.get("error", ""))
	elif errors is Array and not errors.is_empty():
		_set_status("Listo (audio con %d errores)" % errors.size())
	elif bool(payload.get("tts_truncated", false)):
		_set_status("Listo (voz recortada por longitud)")
	else:
		_set_status("Listo")
	_try_unlock_turn_after_audio()
	_drain_packet_backlog()
	_try_unlock_turn_after_audio()


func _try_unlock_turn_after_audio() -> void:
	if not _turn_end_pending:
		return
	if _received_tts_chunks < _expected_tts_chunks:
		return
	_turn_end_pending = false
	_turn_busy = false
	_send.disabled = false
	_focus_chat_input()


func _focus_chat_input() -> void:
	if not is_instance_valid(_input):
		return
	_input.grab_focus()


func _reset_turn_state() -> void:
	_turn_end_pending = false
	_expected_tts_chunks = 0
	_received_tts_chunks = 0
	_turn_busy = false
	_send.disabled = false
	_play_scheduled = false
	_tts_http_queue.clear()
	_tts_http_fetching = false
	if _avatar_ctl.has_method("stop_lip_sync"):
		_avatar_ctl.call("stop_lip_sync")


func _reset_turn_state_after_disconnect() -> void:
	_reset_turn_state()
	if not _audio_queue.is_empty() or _pending_play_stream != null:
		_play_scheduled = false
		call_deferred("_play_next_audio")


func _append_output(text: String) -> void:
	if text.is_empty():
		return
	if not _buddy_reply_open:
		_out.begin_assistant("Buddy", "buddy")
		_buddy_reply_open = true
	_out.append_assistant_delta(text)


func _close_buddy_bubble() -> void:
	if not _buddy_reply_open:
		return
	_out.finish_assistant()
	_buddy_reply_open = false


func _enqueue_audio_stream(stream: AudioStream) -> void:
	_audio_queue.append(stream)
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
	_pending_play_stream = _audio_queue.pop_front()
	call_deferred("_apply_pending_stream")


func _decode_tts_audio(raw: PackedByteArray) -> AudioStream:
	if raw.size() >= 4 and raw.slice(0, 4).get_string_from_ascii() == "RIFF":
		return _decode_wav(raw)
	if _looks_like_mp3(raw):
		return _decode_mp3(raw)
	return null


func _decode_mp3(raw: PackedByteArray) -> AudioStreamMP3:
	var stream := AudioStreamMP3.new()
	stream.data = raw
	stream.loop = false
	# Some builds decode more reliably after a disk round-trip.
	if stream.get_length() <= 0.01:
		var cache_path := "user://tts_cache.mp3"
		var file := FileAccess.open(cache_path, FileAccess.WRITE)
		if file != null:
			file.store_buffer(raw)
			file.close()
			var cached := FileAccess.get_file_as_bytes(cache_path)
			if not cached.is_empty():
				stream.data = cached
	return stream


func _decode_wav(raw: PackedByteArray) -> AudioStreamWAV:
	var info := _parse_wav_chunk(raw)
	if info.is_empty():
		return null
	var stream := AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = int(info["rate"])
	stream.stereo = int(info["channels"]) > 1
	var start: int = int(info["data_start"])
	var pcm_bytes: int = int(info["data_size"])
	stream.data = raw.slice(start, start + pcm_bytes)
	return stream


func _parse_wav_chunk(raw: PackedByteArray) -> Dictionary:
	if raw.size() < 44 or raw.slice(0, 4).get_string_from_ascii() != "RIFF":
		return {}
	var channels := 1
	var rate := 24000
	var data_start := -1
	var data_size := 0
	var pos := 12
	while pos + 8 <= raw.size():
		var chunk_id := raw.slice(pos, pos + 4).get_string_from_ascii()
		var chunk_size: int = raw.decode_u32(pos + 4)
		var body := pos + 8
		if chunk_id == "fmt " and body + 16 <= raw.size():
			channels = raw.decode_u16(body + 2)
			rate = raw.decode_u32(body + 4)
			if raw.decode_u16(body + 14) != 16:
				return {}
		elif chunk_id == "data":
			data_start = body
			data_size = mini(chunk_size, raw.size() - body)
			break
		pos = body + chunk_size + (chunk_size % 2)
	if data_start < 0 or data_size <= 0:
		return {}
	return {
		"channels": channels,
		"rate": rate,
		"data_start": data_start,
		"data_size": data_size,
	}


func _apply_pending_stream() -> void:
	if _pending_play_stream == null:
		_play_next_audio()
		return
	var stream: AudioStream = _pending_play_stream
	_pending_play_stream = null
	if _player.playing:
		_player.stop()
	_player.stream = stream
	_player.stream_paused = false
	_player.play()
	var duration := _estimate_stream_duration(stream)
	_tts_log(
		"PLAY len=%.2fs playing=%s bus=%s queue=%d"
		% [duration, _player.playing, _player.bus, _audio_queue.size()]
	)
	if _avatar_ctl.has_method("start_lip_sync"):
		_avatar_ctl.call("start_lip_sync")


func _estimate_stream_duration(stream: AudioStream) -> float:
	var duration := stream.get_length()
	if duration > 0.01:
		return duration
	if stream is AudioStreamWAV:
		var wav := stream as AudioStreamWAV
		var channels := 2 if wav.stereo else 1
		if wav.mix_rate > 0 and wav.data.size() > 0:
			return float(wav.data.size()) / float(wav.mix_rate * channels * 2)
	return 0.0


func _on_audio_finished() -> void:
	if _audio_queue.is_empty() and _avatar_ctl.has_method("stop_lip_sync"):
		_avatar_ctl.call("stop_lip_sync")
	_play_next_audio()


func _looks_like_mp3(data: PackedByteArray) -> bool:
	if data.size() < 3:
		return false
	# ID3 tag or MPEG sync (0xFF 0xE* / 0xFB / 0xFA)
	if data[0] == 0x49 and data[1] == 0x44 and data[2] == 0x33:
		return true
	if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
		return true
	return false


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
	return buddy


func _start_buddy_thinking() -> void:
	if _avatar_ctl.has_method("start_thinking"):
		_avatar_ctl.call("start_thinking")
		_anim.text = "anim: pensando…"


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
