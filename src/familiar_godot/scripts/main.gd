extends Control

@export var backend_ws: String = "ws://127.0.0.1:8000/ws/session"

const MAX_PACKETS_PER_FRAME := 8
const MAX_OUTPUT_CHARS := 12_000
const MAX_MP3_BYTES := 131072

var _peer: WebSocketPeer = WebSocketPeer.new()
var _session_ready: bool = false
var _turn_busy: bool = false
var _awaiting_tts_binary: bool = false
var _play_scheduled: bool = false

var _packet_backlog: Array[PackedByteArray] = []
var _audio_queue: Array[PackedByteArray] = []
var _pending_play_raw: PackedByteArray = PackedByteArray()

@onready var _input: LineEdit = %LineEdit
@onready var _send: Button = %SendButton
@onready var _out: RichTextLabel = %Output
@onready var _anim: Label = %AnimLabel
@onready var _status: Label = %StatusLabel
@onready var _player: AudioStreamPlayer = %AudioStreamPlayer


func _ready() -> void:
	_send.pressed.connect(_on_send)
	_input.text_submitted.connect(func(_t: String) -> void:
		_on_send()
	)
	if not _player.finished.is_connected(_on_audio_finished):
		_player.finished.connect(_on_audio_finished)
	_connect_ws()


func _connect_ws() -> void:
	var err: int = _peer.connect_to_url(backend_ws)
	if err != OK:
		_set_status("connect_to_url failed: %s" % err)


func _process(_delta: float) -> void:
	_peer.poll()
	var st: int = _peer.get_ready_state()
	if st == WebSocketPeer.STATE_OPEN:
		if not _session_ready:
			_session_ready = true
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
			_set_status("disconnected — stop and play again to reconnect")


func _dispatch_packet(pkt: PackedByteArray) -> void:
	if _awaiting_tts_binary:
		_awaiting_tts_binary = false
		_on_tts_binary(pkt)
		return
	_on_json_packet(pkt)


func _send_hello() -> void:
	var msg: Dictionary = {"v": 1, "type": "session.hello", "payload": {"client": "godot"}}
	_peer.send_text(JSON.stringify(msg))


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
	var msg: Dictionary = {
		"v": 1,
		"type": "turn.user_text",
		"payload": {"session_id": "default", "text": text},
	}
	_peer.send_text(JSON.stringify(msg))
	_input.clear()
	_out.append_text("\n[you] %s\n[buddy] " % text)


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
			_set_status("hello_ack model=%s" % payload.get("model", ""))
		"listening.state":
			_set_status("listening: %s" % payload.get("state", ""))
		"llm.delta":
			_append_output(String(payload.get("text", "")))
		"llm.done":
			_append_output("\n")
		"anim.command":
			_anim.text = "anim: %s (%.2fs)" % [payload.get("clip_id", ""), float(payload.get("blend_time", 0.2))]
		"tts.chunk_meta":
			var idx: int = int(payload.get("index", 0))
			var total: int = int(payload.get("total", 1))
			var nbytes: int = int(payload.get("bytes", 0))
			_set_status("audio %d/%d (%d KB)…" % [idx + 1, total, nbytes / 1024])
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
	var errors: Variant = payload.get("audio_errors", [])
	if payload.has("error") and str(payload.get("error", "")) != "":
		_set_status("error: %s" % payload.get("error", ""))
	elif errors is Array and not errors.is_empty():
		_set_status("ready (audio had %d errors)" % errors.size())
	else:
		_set_status("ready")


func _reset_turn_state() -> void:
	_turn_busy = false
	_send.disabled = false
	_awaiting_tts_binary = false
	_play_scheduled = false


func _append_output(text: String) -> void:
	if text.is_empty():
		return
	_out.append_text(text)
	if _out.text.length() > MAX_OUTPUT_CHARS:
		_out.text = _out.text.substr(-MAX_OUTPUT_CHARS)


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
	if _player.play() != OK:
		push_warning("AudioStreamPlayer.play() failed")
		call_deferred("_play_next_audio")


func _on_audio_finished() -> void:
	_play_next_audio()


func _set_status(t: String) -> void:
	_status.text = t
