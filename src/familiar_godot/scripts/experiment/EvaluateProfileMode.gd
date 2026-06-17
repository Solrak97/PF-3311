extends Control

const SETUP_MENU := "res://scenes/experiment/ExperimentalSetupMenu.tscn"
const SUMMARY_MAX_HEIGHT := 160
const CHAT_MIN_HEIGHT := 220
const INPUT_MIN_LINES := 2
const INPUT_LINE_HEIGHT := 22

const RATING_LABELS: Dictionary = {
	"tone_similarity": "Similitud de tono",
	"phrasing_similarity": "Similitud de formulación",
	"response_length_similarity": "Similitud de longitud",
	"behavioral_consistency": "Consistencia conductual",
	"reminds_me_of_person": "Me recuerda a la persona",
	"naturalness": "Naturalidad",
	"identity_leakage_absent": "Sin filtración de identidad",
}

var _profile_select: OptionButton
var _status: Label
var _summary_scroll: ScrollContainer
var _summary: Label
var _chat: ChatBubbleLog
var _input: TextEdit
var _send: Button
var _clear_chat: Button
var _sliders: Dictionary = {}
var _ratings: Array[Dictionary] = []
var _conversation_history: Array = []
var _chat_busy: bool = false
var _pending_user_message: String = ""
var _turn_counter: int = 0
var _active_profile_label: String = "Perfil"
var _loaded: bool = false
var _local_ids: Array[String] = []
var _pending_validation_start: bool = false
var _sync_local_queue: Array[String] = []
var _syncing_local: bool = false


func _ready() -> void:
	var ui := ExperimentUI.setup_experiment_card(self, "Evaluar perfil")
	_status = ui["status"]
	var content: VBoxContainer = ui["content"]
	_profile_select = ExperimentScreenHelper.add_labeled_option(content, "Perfil")
	ExperimentScreenHelper.add_button(content, "Actualizar lista de perfiles", _refresh_profile_list)
	ExperimentScreenHelper.add_button(content, "Cargar perfil conductual", _on_load)
	var summary_panel := PanelContainer.new()
	summary_panel.add_theme_stylebox_override("panel", ExperimentUI.viewport_panel())
	content.add_child(summary_panel)
	var summary_margin := MarginContainer.new()
	summary_margin.add_theme_constant_override("margin_left", 10)
	summary_margin.add_theme_constant_override("margin_top", 8)
	summary_margin.add_theme_constant_override("margin_right", 10)
	summary_margin.add_theme_constant_override("margin_bottom", 8)
	summary_panel.add_child(summary_margin)
	_summary_scroll = ScrollContainer.new()
	_summary_scroll.custom_minimum_size = Vector2(0, SUMMARY_MAX_HEIGHT)
	_summary_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_summary_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	summary_margin.add_child(_summary_scroll)
	_summary = Label.new()
	_summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_summary.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_summary_scroll.add_child(_summary)
	var chat_label := Label.new()
	chat_label.text = "Chat de prueba (condición A)"
	content.add_child(chat_label)
	var chat_panel := PanelContainer.new()
	chat_panel.custom_minimum_size = Vector2(0, CHAT_MIN_HEIGHT)
	chat_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	chat_panel.add_theme_stylebox_override("panel", ExperimentUI.chat_panel_style())
	content.add_child(chat_panel)
	var chat_margin := MarginContainer.new()
	chat_margin.add_theme_constant_override("margin_left", 12)
	chat_margin.add_theme_constant_override("margin_top", 10)
	chat_margin.add_theme_constant_override("margin_right", 12)
	chat_margin.add_theme_constant_override("margin_bottom", 10)
	chat_panel.add_child(chat_margin)
	_chat = ChatBubbleLog.new()
	_chat.size_flags_vertical = Control.SIZE_EXPAND_FILL
	chat_margin.add_child(_chat)
	var input_panel := PanelContainer.new()
	input_panel.add_theme_stylebox_override("panel", ExperimentUI.viewport_panel())
	content.add_child(input_panel)
	var input_margin := MarginContainer.new()
	input_margin.add_theme_constant_override("margin_left", 10)
	input_margin.add_theme_constant_override("margin_top", 8)
	input_margin.add_theme_constant_override("margin_right", 10)
	input_margin.add_theme_constant_override("margin_bottom", 8)
	input_panel.add_child(input_margin)
	var input_col := VBoxContainer.new()
	input_col.add_theme_constant_override("separation", 8)
	input_margin.add_child(input_col)
	_input = TextEdit.new()
	_input.placeholder_text = "Escribe al perfil… (Enter envía, Mayús+Enter nueva línea)"
	_input.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	_input.custom_minimum_size = Vector2(0, INPUT_MIN_LINES * INPUT_LINE_HEIGHT)
	_input.gui_input.connect(_on_input_gui_input)
	input_col.add_child(_input)
	var input_row := HBoxContainer.new()
	input_row.add_theme_constant_override("separation", 8)
	input_row.alignment = BoxContainer.ALIGNMENT_END
	input_col.add_child(input_row)
	_send = Button.new()
	_send.text = "Enviar"
	_send.pressed.connect(_on_send)
	input_row.add_child(_send)
	_clear_chat = ExperimentScreenHelper.add_button(content, "Limpiar chat", _on_clear_chat)
	for key in ExperimentPrompts.RATING_KEYS:
		content.add_child(_make_slider_row(key))
	ExperimentScreenHelper.add_button(content, "Añadir valoración", _on_add_rating)
	ExperimentScreenHelper.add_button(content, "Finalizar evaluación", _on_finish)
	ExperimentScreenHelper.add_button(content, "Volver", func() -> void:
		ExperimentScreenHelper.go_to(SETUP_MENU)
	)
	if not ExperimentApi.request_finished.is_connected(_on_api_finished):
		ExperimentApi.request_finished.connect(_on_api_finished)
	_set_chat_controls(false)
	_refresh_profile_list()
	call_deferred("_sync_layout_widths")


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED:
		call_deferred("_sync_layout_widths")


func _sync_layout_widths() -> void:
	if _summary_scroll != null and _summary != null:
		_summary.custom_minimum_size.x = maxf(_summary_scroll.size.x - 8.0, 320.0)
	if _chat != null:
		_chat._sync_bubble_widths()


func _selected_profile_id() -> String:
	return ProfileCatalog.selected_profile_id(_profile_select)


func _refresh_profile_list() -> void:
	_loaded = false
	_summary.text = ""
	_reset_chat()
	_local_ids = ProfileCatalog.list_local_raw_profile_ids()
	ProfileCatalog.populate_option(_profile_select, _local_ids)
	_status.text = "Cargando perfiles del servidor…"
	ExperimentApi.list_profiles()


func _apply_profile_options(profile_ids: Array[String]) -> void:
	ProfileCatalog.populate_option(_profile_select, profile_ids)


func _reset_chat() -> void:
	_conversation_history.clear()
	_pending_user_message = ""
	_turn_counter = 0
	_chat.clear_log()
	_input.clear()
	_chat_busy = false
	_set_chat_controls(_loaded)


func _set_chat_controls(active: bool) -> void:
	_input.editable = active and not _chat_busy
	_send.disabled = not active or _chat_busy
	_clear_chat.disabled = not active or _chat_busy


func _make_slider_row(key: String) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	var label := Label.new()
	label.text = RATING_LABELS.get(key, key)
	label.custom_minimum_size = Vector2(220, 0)
	row.add_child(label)
	var slider := HSlider.new()
	slider.min_value = 1
	slider.max_value = 7
	slider.step = 1
	slider.value = 4
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(slider)
	var val := Label.new()
	val.text = "4"
	val.custom_minimum_size = Vector2(24, 0)
	slider.value_changed.connect(func(v: float) -> void:
		val.text = str(int(v))
	)
	row.add_child(val)
	_sliders[key] = slider
	return row


func _on_load() -> void:
	var pid := _selected_profile_id()
	if pid.is_empty():
		_status.text = "Selecciona un perfil de la lista."
		return
	_pending_validation_start = true
	_loaded = false
	_set_chat_controls(false)
	_status.text = "Cargando perfil…"
	ExperimentApi.get_behavioral_profile(pid)


func _on_clear_chat() -> void:
	_reset_chat()
	if _loaded:
		_request_conversation_open()
	else:
		_status.text = "Chat limpiado — carga un perfil para evaluar."


func _request_conversation_open() -> void:
	if not _loaded or _chat_busy:
		return
	if not _conversation_history.is_empty():
		return
	_chat_busy = true
	_set_chat_controls(true)
	_status.text = "Buddy va a iniciar la conversación…"
	var pid := _selected_profile_id()
	ExperimentApi.post_experiment_chat({
		"participant_id": "evaluator",
		"session_id": "evaluate-%s" % pid,
		"interaction_index": 1,
		"condition": "A",
		"profile_id": pid,
		"scenario_id": ParticipantSettings.DEFAULT_SCENARIO_ID,
		"conversation_open": true,
		"conversation_history": [],
	})


func _on_send() -> void:
	if not _loaded or _chat_busy:
		return
	var text := _input.text.strip_edges()
	if text.is_empty():
		_status.text = "Escribe un mensaje para chatear con el perfil."
		return
	var pid := _selected_profile_id()
	_append_user(text)
	_input.clear()
	_pending_user_message = text
	_chat_busy = true
	_set_chat_controls(true)
	_status.text = "El agente está pensando…"
	ExperimentApi.post_experiment_chat({
		"participant_id": "evaluator",
		"session_id": "evaluate-%s" % pid,
		"interaction_index": 1,
		"condition": "A",
		"profile_id": pid,
		"scenario_id": ParticipantSettings.DEFAULT_SCENARIO_ID,
		"message": text,
		"conversation_history": _conversation_history,
	})


func _on_input_gui_input(event: InputEvent) -> void:
	if not _input.editable:
		return
	if event is InputEventKey:
		var key := event as InputEventKey
		if not key.pressed or key.echo:
			return
		if key.keycode == KEY_ENTER or key.keycode == KEY_KP_ENTER:
			if key.shift_pressed or key.ctrl_pressed:
				return
			get_viewport().set_input_as_handled()
			_on_send()


func _history_append(role: String, content: String) -> void:
	var text := content.strip_edges()
	if text.is_empty():
		return
	_conversation_history.append({"role": role, "content": text})


func _last_assistant_message() -> String:
	for i in range(_conversation_history.size() - 1, -1, -1):
		var item: Variant = _conversation_history[i]
		if item is Dictionary and str(item.get("role", "")) == "assistant":
			return str(item.get("content", "")).strip_edges()
	return ""


func _assistant_message_count() -> int:
	var count := 0
	for item in _conversation_history:
		if item is Dictionary and str(item.get("role", "")) == "assistant":
			count += 1
	return count


func _collect_ratings() -> Dictionary:
	var out: Dictionary = {}
	for key in ExperimentPrompts.RATING_KEYS:
		out[key] = int(_sliders[key].value)
	return out


func _on_add_rating() -> void:
	if _assistant_message_count() == 0:
		_status.text = "Chatea con el perfil antes de añadir una valoración."
		return
	var scores := _collect_ratings()
	var last_user := ""
	for i in range(_conversation_history.size() - 1, -1, -1):
		var item: Variant = _conversation_history[i]
		if item is Dictionary and str(item.get("role", "")) == "user":
			last_user = str(item.get("content", ""))
			break
	var last_agent := _last_assistant_message()
	_ratings.append({
		"kind": "sample_chat",
		"conversation": _conversation_history.duplicate(true),
		"agent_response": last_agent,
		"scores": scores,
	})
	var pid := _selected_profile_id()
	ExperimentApi.post_validation({
		"profile_id": pid,
		"validator_id": "godot-ui",
		"created_at": Time.get_datetime_string_from_system(true),
		"ratings": [_ratings.back()],
	})
	ExperimentApi.validation_rating({
		"profile_id": pid,
		"validator_id": "godot-ui",
		"prompt": last_user,
		"agent_response": last_agent,
		"scores": scores,
	})
	_status.text = "Valoración %d registrada del chat de prueba." % _ratings.size()


func _on_finish() -> void:
	var pid := _selected_profile_id()
	if pid.is_empty() or _ratings.is_empty():
		_status.text = "Añade al menos una valoración antes de finalizar."
		return
	var payload := {
		"profile_id": pid,
		"validator_id": "godot-ui",
		"created_at": Time.get_datetime_string_from_system(true),
		"ratings": _ratings,
	}
	_save_local_validation(payload)
	var summary := _evaluate_thresholds()
	_status.text = summary
	ExperimentApi.post_validation(payload)
	ExperimentApi.validation_finalize(pid)


func _evaluate_thresholds() -> String:
	var last: Dictionary = _ratings.back()
	var scores: Dictionary = last.get("scores", {})
	var sim_keys := ["tone_similarity", "phrasing_similarity", "response_length_similarity"]
	var sim_sum := 0.0
	for k in sim_keys:
		sim_sum += float(scores.get(k, 0))
	var sim_avg := sim_sum / float(sim_keys.size())
	var natural := float(scores.get("naturalness", 0))
	var identity := float(scores.get("identity_leakage_absent", 0))
	var parts: PackedStringArray = []
	parts.append("Media de similitud: %.1f (se requiere ≥ 4.5)" % sim_avg)
	parts.append("Naturalidad: %.1f (se requiere ≥ 4.0)" % natural)
	parts.append("Seguridad de identidad: %.1f (se requiere ≥ 5.5)" % identity)
	if sim_avg >= 4.5 and natural >= 4.0 and identity >= 5.5:
		parts.append("Umbrales cumplidos.")
	else:
		parts.append("Algunos umbrales no se cumplieron.")
	return "\n".join(parts)


func _save_local_validation(payload: Dictionary) -> void:
	var dir := "user://experiment_logs/validation"
	DirAccess.make_dir_recursive_absolute(dir)
	var path := "%s/%s_%s.json" % [
		dir,
		payload.get("profile_id", "unknown"),
		Time.get_unix_time_from_system(),
	]
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(payload, "\t"))
		f.close()


func _append_user(text: String) -> void:
	_turn_counter += 1
	_chat.append_user(text, "Tú · turno %d" % _turn_counter)
	_scroll_chat_to_bottom()


func _append_assistant(text: String) -> void:
	_turn_counter += 1
	var header := "%s · turno %d" % [_active_profile_label, _turn_counter]
	_chat.append_assistant(text, "profile", header)
	_scroll_chat_to_bottom()


func _scroll_chat_to_bottom() -> void:
	call_deferred("_scroll_chat_to_bottom_deferred")


func _scroll_chat_to_bottom_deferred() -> void:
	if _chat == null:
		return
	await get_tree().process_frame
	var bar := _chat.get_v_scroll_bar()
	if bar != null:
		bar.value = bar.max_value


func _start_sync_local_profiles(remote: Array) -> void:
	var missing := ProfileCatalog.ids_missing_from_remote(remote, _local_ids)
	if missing.is_empty():
		return
	_sync_local_queue = missing
	_syncing_local = true
	_status.text = "Subiendo %d perfil(es) local(es) al servidor…" % missing.size()
	_sync_next_local_profile()


func _sync_next_local_profile() -> void:
	if _sync_local_queue.is_empty():
		_syncing_local = false
		_status.text = "Perfiles locales sincronizados. Actualizando lista…"
		ExperimentApi.list_profiles()
		return
	var pid: String = _sync_local_queue.pop_front()
	var payload := ProfileCatalog.load_local_raw_profile(pid)
	if payload.is_empty():
		call_deferred("_sync_next_local_profile")
		return
	if not bool(payload.get("consent_confirmed", false)):
		payload["consent_confirmed"] = true
	ExperimentApi.post_raw_profile(payload)


func _on_api_finished(action: String, success: bool, data: Variant, error: String) -> void:
	match action:
		"list_profiles":
			if _syncing_local:
				return
			var remote: Array = []
			if success and data is Dictionary:
				var raw_ids = data.get("profile_ids", [])
				if raw_ids is Array:
					remote = raw_ids
			var missing := ProfileCatalog.ids_missing_from_remote(remote, _local_ids)
			if not missing.is_empty() and success:
				_start_sync_local_profiles(remote)
				var merged := ProfileCatalog.merge_profile_ids(remote, _local_ids)
				_apply_profile_options(merged)
				return
			var merged := ProfileCatalog.merge_profile_ids(remote, _local_ids)
			_apply_profile_options(merged)
			if not success:
				if merged.is_empty():
					_status.text = "Servidor no disponible (%s). No hay perfiles locales." % error
				else:
					_status.text = (
						"Servidor no disponible (%s). Mostrando %d perfil(es) local(es); la carga puede fallar hasta que el servidor esté activo."
						% [error, merged.size()]
					)
			elif merged.is_empty():
				_status.text = "No hay perfiles entrenados. Usa «Entrenar perfil» primero."
			else:
				_status.text = "%d perfil(es) disponible(s). Selecciona uno y cárgalo." % merged.size()
		"post_raw":
			if _syncing_local:
				call_deferred("_sync_next_local_profile")
				return
			if _pending_validation_start:
				var pid := _selected_profile_id()
				if not success:
					_pending_validation_start = false
					_status.text = "No se pudo subir el perfil local (%s)." % error
					return
				_status.text = "Perfil subido. Cargando…"
				ExperimentApi.get_behavioral_profile(pid)
				return
		"get_behavioral":
			if not success or not (data is Dictionary):
				_pending_validation_start = false
				var pid := _selected_profile_id()
				var local := ProfileCatalog.load_local_raw_profile(pid)
				if not local.is_empty():
					_status.text = "Perfil no está en el servidor — subiendo copia local…"
					if not bool(local.get("consent_confirmed", false)):
						local["consent_confirmed"] = true
					_pending_validation_start = true
					ExperimentApi.post_raw_profile(local)
					return
				_status.text = "No se pudo cargar el perfil (%s)." % error
				return
			_loaded = true
			_active_profile_label = _selected_profile_id()
			if _active_profile_label.is_empty():
				_active_profile_label = "Perfil"
			_summary.text = String(data.get("style_summary", "(sin resumen)"))
			if data.get("yaml_profile") is Dictionary:
				var yaml := data.get("yaml_profile") as Dictionary
				if yaml.get("style") is Dictionary:
					_summary.text += "\n\n[Perfil YAML cargado]"
			_reset_chat()
			call_deferred("_sync_layout_widths")
			if _pending_validation_start:
				_pending_validation_start = false
				ExperimentApi.validation_start(_selected_profile_id())
			_status.text = "Perfil cargado — Buddy iniciará la conversación."
			_request_conversation_open()
		"experiment_chat":
			_chat_busy = false
			_set_chat_controls(_loaded)
			if not success or not (data is Dictionary):
				_status.text = "Falló el chat (%s)." % error
				_pending_user_message = ""
				return
			var reply := str(data.get("text", "")).strip_edges()
			if reply.is_empty():
				_status.text = "Respuesta vacía del agente."
				_pending_user_message = ""
				return
			if not _pending_user_message.is_empty():
				_history_append("user", _pending_user_message)
				_pending_user_message = ""
			_append_assistant(reply)
			_history_append("assistant", reply)
			_status.text = "Respuesta recibida — sigue chateando o añade una valoración."
		"post_validation":
			if success:
				_status.text = _status.text + "\nValidación enviada."
			else:
				_status.text = _status.text + "\nFalló el envío al servidor (%s). Copia local guardada." % error
		"validation_finalize":
			if success and data is Dictionary:
				var passed := bool(data.get("passed", false))
				_status.text = _status.text + "\nValidación %s." % (
					"aprobada" if passed else "no cumple los umbrales"
				)
		"validation_start":
			if not success:
				_status.text = "Falló la sesión de validación (%s)." % error
		"validation_rating":
			if not success:
				_status.text = "Falló el registro de valoración (%s)." % error
