from bpy.props import PointerProperty, StringProperty, BoolProperty, \
    EnumProperty, IntProperty, FloatProperty, FloatVectorProperty, \
    CollectionProperty

from ... import rman_config
from ...rman_config import RmanBasePropertyGroup
from ..rman_properties_misc import RendermanLightPointer
from ...rfb_utils import shadergraph_utils
from ...rfb_utils import object_utils
from ...rfb_logger import rfb_log

import bpy

class RENDERMAN_UL_UserAttributes_List(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.name)

class RendermanUserAttributesGroup(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="", description="The name of your attribute. You can then look up these attributes in your shading network, using PxrAttribute. The attribute would be of the form 'namespace:name'. For example, if name is 'foo' and namespace is left blank, the name you use for PxrAttribute would be 'user:foo'.")
    namespace: StringProperty(name="Namespace", default="",
                              description="The namespace for your attribute. If left blank, we put these in the user namespace.  "
                              )
    type: EnumProperty(name="Type",
        items=[
              ('float', 'float', ''),
               ('int', 'int', ''),
               ('string', 'string', ''),
               ('color', 'color', ''),
               ('vector', 'vector', ''),
               ('normal', 'normal', ''),
               ('point', 'point', ''),
    ])

    value_float: FloatProperty(name="Value", default=0.0)
    value_int: IntProperty(name="Value", default=0)
    value_string: StringProperty(name="Value", default="")
    value_color: FloatVectorProperty(name="Value", size=3, subtype='COLOR', soft_min=0.0, soft_max=1.0, default=(1.0, 1.0, 1.0))
    value_vector: FloatVectorProperty(name="Value", size=3, subtype='XYZ', default=(0.0, 0.0, 0.0))
    value_normal: FloatVectorProperty(name="Value", size=3, subtype='XYZ', default=(0.0, 0.0, 0.0))
    value_point: FloatVectorProperty(name="Value", size=3, subtype='XYZ', default=(0.0, 0.0, 0.0))
    

class RendermanObjectSettings(RmanBasePropertyGroup, bpy.types.PropertyGroup):

    rman_config_name: StringProperty(name='rman_config_name',
                                    default='rman_properties_object')
 
    hide_primitive_type: BoolProperty(
        name="Hide Primitive Type",
        default=False
    )

    def matrial_override_update(self, context):
        if self.id_data:
            self.id_data.update_tag()

    rman_material_override: PointerProperty(
        name='Material',
        type=bpy.types.Material,
        description="Override the attached material. This is useful for attaching different materials to instances, or for objects that Blender doesn't allow for materials (ex: Empty).",
        update=matrial_override_update
    )    

    rman_lighting_excludesubset: CollectionProperty(
        name='lighting:excludesubset',
        type=RendermanLightPointer
    )

    rman_lightfilter_subset: CollectionProperty(
        name='lighting:excludesubset',
        type=RendermanLightPointer
    )

    export_archive_path: StringProperty(
        name="Archive Export Path",
        description="Path to automatically save this object as a RIB archive",
        subtype='FILE_PATH',
        default="")

    export_as_coordsys: BoolProperty(
        name="Export As CoordSys",
        description="Export this empty as a coordinate system.",
        default=False)      

    mute: BoolProperty(
        name="Mute",
        description="Turn off this light",
        default=False)        

    def update_solo(self, context):
        light = self.id_data
        scene = context.scene

        # if the scene solo is on already find the old one and turn off
        scene.renderman.solo_light = self.solo
        if self.solo:
            if scene.renderman.solo_light:
                for ob in scene.objects:
                    if shadergraph_utils.is_rman_light(ob, include_light_filters=False):
                        rm = ob.renderman
                        if rm != self and rm.solo:
                            rm.solo = False
                            break

    solo: BoolProperty(
        name="Solo",
        update=update_solo,
        description="Turn on only this light",
        default=False)        

    user_attributes: CollectionProperty(
        type=RendermanUserAttributesGroup, name="User Attributes")

    user_attributes_index: IntProperty(min=-1, default=-1)

    def get_object_type(self):
        if self.id_data:
            return object_utils._detect_primitive_(self.id_data)
        return ""        

    bl_object_type: StringProperty(
        get=get_object_type
    )

    def get_bake_mode(self):
        scene = bpy.context.scene
        return scene.renderman.rman_bake_mode

    rman_bake_mode: StringProperty(
        get=get_bake_mode
    )

rman_config_classes = [
    RendermanObjectSettings
]

classes = [       
    RENDERMAN_UL_UserAttributes_List,  
    RendermanUserAttributesGroup,
]           

def register():
    from ...rfb_utils import register_utils

    register_utils.rman_register_classes(classes) 

    for cls in rman_config_classes:
        cls._add_properties(cls, 'rman_properties_object')
        register_utils.rman_register_class(cls)  

    bpy.types.Object.renderman = PointerProperty(
        type=RendermanObjectSettings, name="Renderman Object Settings")

def unregister():

    del bpy.types.Object.renderman

    from ...rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes)