extends Node
## Cycles VRM expression clips (blend shapes) + body sway. No skeletal idle in this asset.
## Avoid look* / blink in idle loops — they morph or rotate eyes and can stick without RESET.

const VISEMES: PackedStringArray = ["aa", "ih", "ou", "oh", "ee"]
const VISEME_CLOSED: PackedStringArray = ["ih", "ee"]
const VISEME_MID: PackedStringArray = ["oh", "ou"]
const VISEME_OPEN: PackedStringArray = ["aa", "ou", "oh"]
const LIP_LEVEL_SMOOTH := 0.42
const LIP_CHANGE_MIN_SEC := 0.045

const IDLE_CLIP_MIN_SEC := 0.8
const IDLE_CLIP_MAX_SEC := 2.2
const BLINK_COOLDOWN_MIN_SEC := 3.5
const BLINK_COOLDOWN_MAX_SEC := 6.0

# Safe presets only (no lookLeft/Right/Down — eyes disappear when those stick).
const AMBIENT_CYCLE: PackedStringArray = ["neutral", "Smile"]
const THINK_CYCLE: PackedStringArray = ["neutral", "Smile", "relaxed"]

const REACTION_CLIPS: Dictionary = {
	"idle": ["neutral", "RESET"],
	"nod": ["Smile", "neutral"],
	"wave": ["Smile", "neutral"],
	"think": ["relaxed", "neutral"],
}

enum Mode { AMBIENT, THINKING, REACTION, LIPSYNC }

var _buddy: Node3D
var _anim: AnimationPlayer
var _body_base_rotation: Vector3 = Vector3.ZERO
var _body_tween: Tween
var _mode: Mode = Mode.AMBIENT
var _thinking: bool = false
var _reaction_busy: bool = false
var _lip_active: bool = false
var _lip_index: int = 0
var _lip_timer: float = 0.0
var _lip_level: float = 0.0
var _lip_level_smooth: float = 0.0
var _lip_change_timer: float = 0.0
var _last_viseme_clip: String = ""
var _viseme_clips: Dictionary = {}
var _idle_timer: float = 0.5
var _blink_timer: float = 4.0
var _known_clips: PackedStringArray = PackedStringArray()
var _neutral_return_tween: Tween
var _clip_reset: String = ""
var _clip_neutral: String = ""
var _clip_blink: String = ""

func setup(buddy: Node3D) -> void:
	_buddy = buddy
	if not is_instance_valid(_buddy):
		return
	_body_base_rotation = _buddy.rotation_degrees
	_anim = _find_animation_player(_buddy)
	if _anim == null:
		return
	_known_clips = _anim.get_animation_list()
	_cache_core_clips()
	if not _anim.animation_finished.is_connected(_on_animation_finished):
		_anim.animation_finished.connect(_on_animation_finished)
	_return_to_neutral(0.15)
	_idle_timer = 1.0
	_blink_timer = _rand_blink_cooldown()


func _process(delta: float) -> void:
	if _anim == null:
		return
	_tick_idle_scheduler(delta)
	_tick_blink(delta)
	_tick_lip_sync(delta)


func start_thinking() -> void:
	if _lip_active:
		return
	_thinking = true
	_reaction_busy = false
	_mode = Mode.THINKING
	_start_think_body_loop()
	_idle_timer = 0.2


func stop_thinking() -> void:
	_thinking = false
	if _lip_active or _reaction_busy:
		return
	_stop_body_tween()
	_mode = Mode.AMBIENT
	_return_to_neutral(0.2)
	_idle_timer = 0.3


func play_reaction(clip_id: String, blend: float) -> bool:
	if _anim == null:
		return false
	_reaction_busy = true
	_mode = Mode.REACTION
	_stop_body_tween()
	_cancel_neutral_return()
	var key := clip_id.to_lower()
	var candidates: Array = REACTION_CLIPS.get(key, ["neutral"])
	for candidate in candidates:
		var clip_name := _resolve_clip(String(candidate))
		if clip_name.is_empty():
			continue
		var hold := _clip_length(clip_name)
		_anim.play(clip_name, max(0.08, blend))
		_play_body_sway(key, blend)
		_schedule_neutral_return(hold + 0.1)
		get_tree().create_timer(hold + blend + 0.25).timeout.connect(_on_reaction_done)
		return true
	_reaction_busy = false
	_resume_idle_mode()
	return false


func start_lip_sync() -> void:
	if _anim == null:
		return
	_stop_body_tween()
	_reaction_busy = false
	_mode = Mode.LIPSYNC
	_lip_active = true
	_lip_index = 0
	_lip_timer = 0.0
	_lip_level = 0.0
	_lip_level_smooth = 0.0
	_lip_change_timer = 0.0
	_last_viseme_clip = ""
	_cancel_neutral_return()


func update_lip_sync(level: float) -> void:
	if not _lip_active or _anim == null:
		return
	_lip_level = clampf(level, 0.0, 1.0)


func stop_lip_sync() -> void:
	_lip_active = false
	_lip_level = 0.0
	_lip_level_smooth = 0.0
	_last_viseme_clip = ""
	_return_to_neutral(0.12)
	_resume_idle_mode()
	_idle_timer = 0.4
	_blink_timer = _rand_blink_cooldown()


func _cache_core_clips() -> void:
	_clip_reset = _resolve_clip("RESET")
	_clip_neutral = _resolve_clip("neutral")
	_clip_blink = _resolve_clip("blink")
	_viseme_clips.clear()
	for token in VISEMES:
		var clip_name := _resolve_clip(token)
		if not clip_name.is_empty():
			_viseme_clips[token] = clip_name


func _tick_idle_scheduler(delta: float) -> void:
	if _lip_active or _reaction_busy:
		return
	if _mode != Mode.AMBIENT and _mode != Mode.THINKING:
		return
	_idle_timer -= delta
	if _idle_timer > 0.0:
		return
	_queue_next_idle_clip(0.22)


func _tick_blink(delta: float) -> void:
	if _lip_active or _reaction_busy:
		return
	if _mode != Mode.AMBIENT and _mode != Mode.THINKING:
		return
	if _clip_blink.is_empty():
		return
	_blink_timer -= delta
	if _blink_timer > 0.0:
		return
	_blink_timer = _rand_blink_cooldown()
	_play_blink_once()


func _play_blink_once() -> void:
	if _anim == null or _clip_blink.is_empty() or _lip_active or _reaction_busy:
		return
	var hold := clampf(_clip_length(_clip_blink), 0.12, 0.35)
	_anim.play(_clip_blink, 0.1)
	_schedule_neutral_return(hold + 0.05)


func _queue_next_idle_clip(blend: float) -> void:
	if _anim == null or _lip_active or _reaction_busy:
		return
	var pool := THINK_CYCLE if _thinking else AMBIENT_CYCLE
	var token := pool[randi() % pool.size()]
	var clip_name := _resolve_clip(token)
	if clip_name.is_empty():
		_idle_timer = 0.8
		return
	if clip_name == _clip_neutral:
		_return_to_neutral(blend)
		_idle_timer = randf_range(IDLE_CLIP_MIN_SEC, IDLE_CLIP_MAX_SEC)
		return
	var hold := clampf(_clip_length(clip_name), IDLE_CLIP_MIN_SEC, IDLE_CLIP_MAX_SEC)
	_anim.play(clip_name, blend)
	_idle_timer = hold + randf_range(0.2, 0.5)
	_schedule_neutral_return(hold * 0.75)


func _return_to_neutral(blend: float = 0.2) -> void:
	if _anim == null:
		return
	if not _clip_reset.is_empty():
		_anim.play(_clip_reset, blend)
	elif not _clip_neutral.is_empty():
		_anim.play(_clip_neutral, blend)


func _schedule_neutral_return(delay_sec: float) -> void:
	_cancel_neutral_return()
	_neutral_return_tween = create_tween()
	_neutral_return_tween.tween_interval(max(0.05, delay_sec))
	_neutral_return_tween.tween_callback(func() -> void:
		if _lip_active or _reaction_busy:
			return
		_return_to_neutral(0.18)
	)


func _cancel_neutral_return() -> void:
	if is_instance_valid(_neutral_return_tween):
		_neutral_return_tween.kill()
	_neutral_return_tween = null


func _on_animation_finished(anim_name: StringName) -> void:
	if _lip_active or _reaction_busy:
		return
	if _mode != Mode.AMBIENT and _mode != Mode.THINKING:
		return
	var key := String(anim_name).to_lower()
	if key in ["neutral", "reset", "smile", "relaxed"]:
		return
	if key == "blink" or key.contains("blink"):
		_return_to_neutral(0.12)
		return
	_return_to_neutral(0.15)
	_idle_timer = 0.25


func _on_reaction_done() -> void:
	_reaction_busy = false
	_return_to_neutral(0.18)
	_resume_idle_mode()
	_idle_timer = 0.35


func _resume_idle_mode() -> void:
	_mode = Mode.THINKING if _thinking else Mode.AMBIENT
	if _thinking:
		_start_think_body_loop()
	else:
		_stop_body_tween()


func _tick_lip_sync(delta: float) -> void:
	if not _lip_active:
		return
	_lip_level_smooth = lerpf(_lip_level_smooth, _lip_level, LIP_LEVEL_SMOOTH)
	if _lip_level_smooth > 0.02:
		_lip_change_timer -= delta
		if _lip_change_timer <= 0.0:
			_lip_change_timer = LIP_CHANGE_MIN_SEC
			_play_viseme_for_level(_lip_level_smooth, false)
		return
	# Fallback jaw motion before/ between audio chunks (no spectrum signal yet).
	_lip_timer -= delta
	if _lip_timer > 0.0:
		return
	_lip_timer = randf_range(0.05, 0.085)
	_lip_index += 1
	var pool := VISEME_OPEN if _lip_index % 2 == 0 else VISEME_CLOSED
	var token: String = pool[randi() % pool.size()]
	_play_viseme_token(token, randf_range(0.07, 0.14))


func _play_viseme_for_level(level: float, force: bool) -> void:
	var token := _pick_viseme_token(level)
	_play_viseme_token(token, lerpf(0.07, 0.16, level), force)


func _pick_viseme_token(level: float) -> String:
	if level < 0.14:
		return VISEME_CLOSED[randi() % VISEME_CLOSED.size()]
	if level < 0.38:
		return VISEME_MID[randi() % VISEME_MID.size()]
	if level < 0.62:
		return VISEME_OPEN[randi() % VISEME_OPEN.size()]
	return "aa"


func _play_viseme_token(token: String, blend: float, force: bool = false) -> void:
	var clip_name: String = String(_viseme_clips.get(token, ""))
	if clip_name.is_empty():
		clip_name = _resolve_clip(token)
	if clip_name.is_empty():
		return
	if not force and clip_name == _last_viseme_clip:
		var alt := _pick_alternate_viseme(token)
		if not alt.is_empty():
			clip_name = alt
	_anim.play(clip_name, blend)
	_last_viseme_clip = clip_name


func _pick_alternate_viseme(current_token: String) -> String:
	var pool: PackedStringArray = VISEME_MID
	var key := current_token.to_lower()
	if key in ["ih", "ee"]:
		pool = VISEME_CLOSED
	elif key == "aa":
		pool = VISEME_OPEN
	elif key in ["oh", "ou"]:
		pool = VISEME_MID
	for token in pool:
		var clip_name: String = String(_viseme_clips.get(token, ""))
		if clip_name.is_empty() or clip_name == _last_viseme_clip:
			continue
		return clip_name
	return ""


func _start_think_body_loop() -> void:
	if not is_instance_valid(_buddy):
		return
	_stop_body_tween()
	var base := _body_base_rotation
	_body_tween = create_tween().set_loops()
	_body_tween.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	_body_tween.tween_property(_buddy, "rotation_degrees", base + Vector3(4, -7, 2), 1.1)
	_body_tween.tween_property(_buddy, "rotation_degrees", base + Vector3(-3, 5, -1), 1.1)
	_body_tween.tween_property(_buddy, "rotation_degrees", base + Vector3(2, -4, 1), 0.9)


func _play_body_sway(clip_id: String, blend: float) -> void:
	if not is_instance_valid(_buddy):
		return
	_stop_body_tween()
	var base := _body_base_rotation
	var d: float = max(0.12, blend)
	_body_tween = create_tween()
	_body_tween.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	match clip_id:
		"nod":
			_body_tween.tween_property(_buddy, "rotation_degrees", base + Vector3(10, 0, 0), d * 0.45)
			_body_tween.tween_property(_buddy, "rotation_degrees", base, d * 0.45)
		"wave":
			_body_tween.tween_property(_buddy, "rotation_degrees", base + Vector3(0, 12, 0), d * 0.4)
			_body_tween.tween_property(_buddy, "rotation_degrees", base + Vector3(0, -10, 0), d * 0.4)
			_body_tween.tween_property(_buddy, "rotation_degrees", base, d * 0.35)
		"think":
			_body_tween.tween_property(_buddy, "rotation_degrees", base + Vector3(5, -8, 2), d * 0.55)
			_body_tween.tween_property(_buddy, "rotation_degrees", base, d * 0.55)
		_:
			_body_tween.tween_property(_buddy, "rotation_degrees", base, d * 0.4)


func _stop_body_tween() -> void:
	if is_instance_valid(_body_tween):
		_body_tween.kill()
	_body_tween = null


func _clip_length(clip_name: String) -> float:
	if _anim == null:
		return 0.6
	var anim := _anim.get_animation(clip_name)
	if anim == null:
		return 0.6
	return maxf(anim.length, 0.2)


func _resolve_clip(token: String) -> String:
	var want := token.to_lower()
	for anim_name in _known_clips:
		if String(anim_name).to_lower() == want:
			return String(anim_name)
	return ""


func _has_clip(token: String) -> bool:
	return not _resolve_clip(token).is_empty()


func _rand_blink_cooldown() -> float:
	return randf_range(BLINK_COOLDOWN_MIN_SEC, BLINK_COOLDOWN_MAX_SEC)


func _find_animation_player(root: Node) -> AnimationPlayer:
	if root is AnimationPlayer:
		return root as AnimationPlayer
	for child in root.get_children():
		var found := _find_animation_player(child)
		if found != null:
			return found
	return null
