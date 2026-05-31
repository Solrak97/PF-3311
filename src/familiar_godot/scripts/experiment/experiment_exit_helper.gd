extends RefCounted
class_name ExperimentExitHelper

const CONFIRM_TEXT := (
	"¿Salir de la sesión experimental antes de terminar?\n\n"
	+ "El investigador registrará que la sesión terminó antes de completar el protocolo."
)


static func confirm_exit(parent: Node, on_confirmed: Callable) -> void:
	var dlg := ConfirmationDialog.new()
	dlg.title = "Salir de la sesión"
	dlg.dialog_text = CONFIRM_TEXT
	dlg.ok_button_text = "Salir"
	dlg.cancel_button_text = "Continuar"
	dlg.confirmed.connect(func() -> void:
		on_confirmed.call()
		dlg.queue_free()
	)
	dlg.canceled.connect(func() -> void:
		dlg.queue_free()
	)
	parent.add_child(dlg)
	dlg.popup_centered()
