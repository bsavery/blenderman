from .rman_ui_base import _RManPanelHeader, CollectionPanel
from bl_ui.properties_particle import ParticleButtonsPanel
import bpy
from bpy.types import Panel

class PARTICLE_PT_renderman_particle(ParticleButtonsPanel, Panel, _RManPanelHeader):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "particle"
    bl_label = "Particle Attributes"

    def draw(self, context):
        layout = self.layout

        psys = context.particle_system
        rm = psys.settings.renderman
        is_rman_interactive_running = context.scene.renderman.is_rman_interactive_running

        col = layout.column()

        if psys.settings.type == 'EMITTER':
            if psys.settings.render_type != 'OBJECT':
                col.row().prop(rm, "constant_width", text="Override Width")
                col.row().prop(rm, "width")
                
        if psys.settings.render_type == 'OBJECT':
            col.prop(rm, 'override_instance_material')
            if rm.override_instance_material:
                col.prop(psys.settings, "material_slot")
       
        split = layout.split()
        col = split.column()

        if psys.settings.type == 'HAIR':
            ob = psys.id_data
            mesh = getattr(ob, 'data', None)

            col.prop(rm, 'export_scalp_st')
            if rm.export_scalp_st and mesh:
                col.prop_search(rm, "uv_name", mesh, "uv_layers", text="")
            col.separator()
            col.prop(rm, 'export_mcol')
            if rm.export_mcol and mesh:
                col.prop_search(rm, "mcol_name", mesh, "vertex_colors", text="")
            col.separator()                
            col.prop(rm, 'hair_index_name')

        col.prop(rm, 'do_velocity_blur')


class PARTICLE_PT_renderman_prim_vars(CollectionPanel, Panel):
    bl_context = "particle"
    bl_label = "Primitive Variables"

    def draw_item(self, layout, context, item):
        ob = context.object
        layout.prop(item, "name")

        row = layout.row()
        row.prop(item, "data_source", text="Source")

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        if not context.particle_system:
            return False
        return rd.engine == 'PRMAN_RENDER'

    def draw(self, context):
        layout = self.layout
        psys = context.particle_system
        rm = psys.settings.renderman

        self._draw_collection(context, layout, rm, "Primitive Variables:",
                              "collection.add_remove",
                              "particle_system.settings",
                              "prim_vars", "prim_vars_index")

        layout.prop(rm, "export_default_size")

classes = [
    PARTICLE_PT_renderman_prim_vars,
    PARTICLE_PT_renderman_particle
]

def register():
    from ..rfb_utils import register_utils

    register_utils.rman_register_classes(classes) 

def unregister():
    from ..rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes)      