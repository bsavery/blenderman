import bpy
from bpy.props import PointerProperty, StringProperty, BoolProperty, \
    IntProperty, CollectionProperty
from ...rman_config import RmanBasePropertyGroup    
from ..rman_properties_misc import RendermanMeshPrimVar     


class RendermanCurveGeometrySettings(RmanBasePropertyGroup, bpy.types.PropertyGroup):
    prim_vars: CollectionProperty(
        type=RendermanMeshPrimVar, name="Primitive Variables")
    prim_vars_index: IntProperty(min=-1, default=-1)

classes = [         
    RendermanCurveGeometrySettings
]           

def register():
    from ...rfb_utils import register_utils

    for cls in classes:
        cls._add_properties(cls, 'rman_properties_curve')
        register_utils.rman_register_class(cls)

    bpy.types.Curve.renderman = PointerProperty(
        type=RendermanCurveGeometrySettings,
        name="Renderman Curve Geometry Settings")
    
    bpy.types.Curves.renderman = PointerProperty(
        type=RendermanCurveGeometrySettings,
        name="Renderman Curve Geometry Settings")    

def unregister():

    del bpy.types.Curve.renderman
    del bpy.types.Curves.renderman

    from ...rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes)