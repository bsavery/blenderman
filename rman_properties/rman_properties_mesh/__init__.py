from bpy.props import PointerProperty, IntProperty, CollectionProperty, BoolProperty

from ...rfb_logger import rfb_log 
from ...rman_config import RmanBasePropertyGroup
from ...rman_constants import META_AS_MESH
from ..rman_properties_misc import RendermanMeshPrimVar, RendermanReferencePosePrimVars, RendermanReferencePoseNormalsPrimVars 

import bpy

class RendermanMeshGeometrySettings(RmanBasePropertyGroup, bpy.types.PropertyGroup):
    output_all_primvars: BoolProperty(
        name="Output All Attributes",
        default=True,
        description="Output all attributes as primitive variables. If you don't need all of them, turn this off and use the UI below. This can help speed up exporting of the scene."
    )
    prim_vars: CollectionProperty(
        type=RendermanMeshPrimVar, name="Primitive Variables")
    prim_vars_index: IntProperty(min=-1, default=-1)

    reference_pose: CollectionProperty(
        type=RendermanReferencePosePrimVars, name=""
    )

    reference_pose_normals: CollectionProperty(
        type=RendermanReferencePoseNormalsPrimVars, name=""
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
    
    # blender 3.6 provides us a mesh version
    # of metaballs, so we need to add a renderman
    # pointer property in order to use the rman_mesh_translator
    if META_AS_MESH:
        bpy.types.MetaBall.renderman = PointerProperty(
            type=RendermanMeshGeometrySettings,
            name="Renderman Mesh Geometry Settings")

def unregister():

    del bpy.types.Mesh.renderman

    from ...rfb_utils import register_utils
    register_utils.rman_unregister_classes(classes)