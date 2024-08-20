from .rman_ui_base import _RManPanelHeader
from .rman_ui_base import CollectionPanel
from .rman_ui_base import PRManButtonsPanel
from ..rfb_utils.draw_utils import _draw_ui_from_rman_config
from ..rman_constants import NODE_LAYOUT_SPLIT
from ..rfb_utils import object_utils
from bpy.types import Panel
import bpy

class MESH_PT_renderman_mesh_attrs(CollectionPanel, Panel):
    bl_context = "data"
    bl_label = "Mesh Attributes"

    @classmethod
    def poll(cls, context):
        if not context.mesh:
            return False
        return CollectionPanel.poll(context)

    def draw(self, context):
        layout = self.layout
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False        
        mesh = context.mesh
        rm = mesh.renderman

        _draw_ui_from_rman_config('rman_properties_mesh', 'MESH_PT_renderman_mesh_attrs', context, layout, rm)             

class MESH_PT_renderman_prim_vars(CollectionPanel, Panel):
    bl_context = "data"
    bl_label = "Primitive Variables"

    def draw_item(self, layout, context, item):
        ob = context.object
        if context.mesh:
            geo = context.mesh
        layout.prop(item, "name")

        row = layout.row()
        row.prop(item, "data_source", text="Source")
        if item.data_source == 'VERTEX_COLOR':
            row.prop_search(item, "data_name", geo, "vertex_colors", text="")
        elif item.data_source == 'UV_TEXTURE':
            row.prop_search(item, "data_name", geo, "uv_layers", text="")
            row = layout.row()
            row.prop(item, "export_tangents")
        elif item.data_source == 'VERTEX_GROUP':
            row.prop_search(item, "data_name", ob, "vertex_groups", text="")
        elif item.data_source == 'VERTEX_ATTR_COLOR':
            row.prop(item, "data_name", text="Attr")
    @classmethod
    def poll(cls, context):
        if not context.mesh:
            return False
        return CollectionPanel.poll(context)

    def draw(self, context):
        layout = self.layout
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False           
        mesh = context.mesh
        rm = mesh.renderman
        row = layout.row()

        row.prop(rm, 'output_all_primvars')
        row = layout.row()
        row.enabled = not rm.output_all_primvars
        self._draw_collection(context, row, rm, "Primitive Variables:",
                                "collection.add_remove", "mesh", "prim_vars",
                                "prim_vars_index")

        _draw_ui_from_rman_config('rman_properties_mesh', 'MESH_PT_renderman_prim_vars', context, layout, rm)


        row = layout.row()
        if len(rm.reference_pose) > 0 or len(rm.reference_pose_normals) > 0:
            row.operator('mesh.freeze_reference_pose', text='Re-Freeze Reference Pose')
        else:
            row.operator('mesh.freeze_reference_pose', text='Freeze Reference Pose')

classes = [
    MESH_PT_renderman_mesh_attrs,
    MESH_PT_renderman_prim_vars  
]

def register():
    from ..rfb_utils import register_utils

    register_utils.rman_register_classes(classes) 

def unregister():
    from ..rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes)   