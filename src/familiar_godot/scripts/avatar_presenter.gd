extends Node
## Tints the single-surface MToon body: pulls white rope/cord regions toward warm tan.

# Multiplies albedo — whites become parchment/cord instead of stark white.
const ALBEDO_TINT := Color(0.9, 0.8, 0.68, 1.0)
const SHADE_TINT := Color(0.82, 0.72, 0.6, 1.0)
const RIM_TINT := Color(0.92, 0.72, 0.55, 1.0)

const MTOON_FLOAT_PARAMS: Dictionary = {
	"_RimLightingMix": 0.12,
	"_IndirectLightIntensity": 0.28,
	"_RimLift": 0.05,
}


func apply(root: Node3D) -> void:
	if not is_instance_valid(root):
		return
	_disable_extra_spring_bones(root)
	_tweak_recursive(root)


func _disable_extra_spring_bones(root: Node3D) -> void:
	# Editor-added head spring bones can wiggle white cord UVs on the scalp.
	if "spring_bones" in root:
		root.set("spring_bones", [])


func _tweak_recursive(node: Node) -> void:
	if node is MeshInstance3D:
		_tweak_mesh(node as MeshInstance3D)
	for child in node.get_children():
		_tweak_recursive(child)


func _tweak_mesh(mi: MeshInstance3D) -> void:
	var mesh := mi.mesh
	if mesh == null:
		return
	for i in range(mesh.get_surface_count()):
		var mat: Material = mi.get_surface_override_material(i)
		if mat == null:
			mat = mesh.surface_get_material(i)
		if mat == null:
			continue
		var tweaked := mat.duplicate()
		if tweaked is StandardMaterial3D:
			var std := tweaked as StandardMaterial3D
			std.albedo_color = std.albedo_color * ALBEDO_TINT
			std.roughness = clampf(std.roughness * 0.92, 0.0, 1.0)
			mi.set_surface_override_material(i, std)
		elif tweaked is ShaderMaterial:
			var sh := tweaked as ShaderMaterial
			if sh.shader == null:
				continue
			_set_color_param(sh, "_Color", ALBEDO_TINT)
			_set_color_param(sh, "_ShadeColor", SHADE_TINT)
			_set_color_param(sh, "_RimColor", RIM_TINT)
			for pname in MTOON_FLOAT_PARAMS:
				_add_float_param(sh, pname, float(MTOON_FLOAT_PARAMS[pname]))
			mi.set_surface_override_material(i, sh)


func _shader_uniform_names(shader_res: Shader) -> Array[StringName]:
	var out: Array[StringName] = []
	if not shader_res.has_method("get_shader_uniform_list"):
		return out
	for entry in shader_res.get_shader_uniform_list():
		if entry is Dictionary and entry.has("name"):
			out.append(StringName(String(entry["name"])))
	return out


func _resolve_param(sh: ShaderMaterial, pname: String) -> StringName:
	var want := StringName(pname)
	var shader_res := sh.shader
	if shader_res != null:
		for n in _shader_uniform_names(shader_res):
			if n == want:
				return n
	return want


func _set_color_param(sh: ShaderMaterial, pname: String, tint: Color) -> void:
	var key := _resolve_param(sh, pname)
	var c: Variant = sh.get_shader_parameter(key)
	if c is Color:
		var col := c as Color
		sh.set_shader_parameter(key, Color(
			clampf(col.r * tint.r, 0.0, 1.5),
			clampf(col.g * tint.g, 0.0, 1.5),
			clampf(col.b * tint.b, 0.0, 1.5),
			col.a
		))


func _add_float_param(sh: ShaderMaterial, pname: String, delta: float) -> void:
	var key := _resolve_param(sh, pname)
	var v: Variant = sh.get_shader_parameter(key)
	if typeof(v) == TYPE_FLOAT or typeof(v) == TYPE_INT:
		sh.set_shader_parameter(key, clampf(float(v) + delta, 0.0, 1.0))
