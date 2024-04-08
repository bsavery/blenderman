from bpy.props import PointerProperty, IntProperty, CollectionProperty

from ...rfb_logger import rfb_log 
from ...rman_config import RmanBasePropertyGroup
from ..rman_properties_misc import RendermanMeshPrimVar, RendermanReferencePosePrimVars 

import bpy

class RendermanMeshGeometrySettings(RmanBasePropertyGroup, bpy.types.PropertyGroup):
    prim_vars: CollectionProperty(
        type=RendermanMeshPrimVar, name="Primitive Variables")
    prim_vars_index: IntProperty(min=-1, default=-1)

    reference_pose: CollectionProperty(
        type=RendermanReferencePosePrimVars, name=""
    )

classes = [         
    RendermanMeshGeometrySettings
]           

def register():

    from ...rfb_utils import register_utils

    for cls in classes:
        cls._add_properties(cls, 'rman_properties_mesh')
        register_utils.rman_register_class(cls)  

    bpy.types.Mesh.renderman = PointerProperty(
        type=RendermanMeshGeometrySettings,
        name="Renderman Mesh Geometry Settings")

def unregister():

    del bpy.types.Mesh.renderman

    from ...rfb_utils import register_utils
    register_utils.rman_unregister_classes(classes)