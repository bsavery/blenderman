from . import rman_operators_printer
from . import rman_operators_view3d
from . import rman_operators_render
from . import rman_operators_rib

def register():
    rman_operators_printer.register()
    rman_operators_view3d.register()
    rman_operators_render.register()
    rman_operators_rib.register()

def unregister():
    rman_operators_printer.unregister()
    rman_operators_view3d.unregister()
    rman_operators_render.unregister()
    rman_operators_rib.unregister()