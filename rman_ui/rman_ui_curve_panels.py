from .rman_ui_base import _RManPanelHeader
from .rman_ui_base import CollectionPanel
from .rman_ui_base import PRManButtonsPanel
from ..rfb_utils.draw_utils import _draw_ui_from_rman_config
from ..rman_constants import NODE_LAYOUT_SPLIT
from ..rfb_utils import object_utils
from bpy.types import Panel
import bpy

class CURVE_PT_renderman_curve_attrs(CollectionPanel, Panel):
    bl_context = "data"
    bl_label = "Curve Attributes"

    @classmethod
    def poll(cls, context):
        if not context.curve and not context.curves:
            return False
        return CollectionPanel.poll(context)

    def draw(self, context):
        layout = self.layout
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False        
        curve = context.curve
        if curve is None:
            curve = context.curves
        rm = curve.renderman

        _draw_ui_from_rman_config('rman_properties_curve', 'CURVE_PT_renderman_curve_attrs', context, layout, rm)             

class CURVE_PT_renderman_prim_vars(CollectionPanel, Panel):
    bl_context = "data"
    bl_label = "Primitive Variables"

    def draw_item(self, layout, context, item):
        ob = context.object
        if context.curve:
            geo = context.curve
        elif context.curves:
            geo = context.curves
        layout.prop(item, "name")

        row = layout.row()
        row.prop(item, "data_source", text="Source")
        if item.data_source == 'VERTEX_COLOR':
            row.prop_search(item, "data_name", geo, "vertex_colors", text="")
        elif item.data_source == 'UV_TEXTURE':
            row.prop_search(item, "data_name", geo, "uv_textures", text="")
        elif item.data_source == 'VERTEX_GROUP':
            row.prop_search(item, "data_name", ob, "vertex_groups", text="")

    @classmethod
    def poll(cls, context):
        if not context.curve and not context.curves:
            return False
        return CollectionPanel.poll(context)

    def draw(self, context):
        layout = self.layout
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False           
        curve = context.curve
        if curve is None:
            curve = context.curves
        rm = curve.renderman

        self._draw_collection(context, layout, rm, "Primitive Variables:",
                              "collection.add_remove", "curve", "prim_vars",
                              "prim_vars_index")

        _draw_ui_from_rman_config('rman_properties_curve', 'CURVE_PT_renderman_prim_vars', context, layout, rm)             

classes = [
    CURVE_PT_renderman_curve_attrs,
    CURVE_PT_renderman_prim_vars  
]

def register():
    from ..rfb_utils import register_utils

    register_utils.rman_register_classes(classes) 

def unregister():
    from ..rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes) 