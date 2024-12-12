from bpy.props import PointerProperty, StringProperty, BoolProperty, \
    EnumProperty, IntProperty, FloatProperty, \
    CollectionProperty

from ...rfb_logger import rfb_log

import bpy

class RendermanParticlePrimVar(bpy.types.PropertyGroup):
    name: StringProperty(
        name="Variable Name",
        description="Name of the exported renderman primitive variable")
    data_source: EnumProperty(
        name="Data Source",
        description="Blender data type to export as the primitive variable",
        items=[('SIZE', 'Size', ''),
               ('VELOCITY', 'Velocity', ''),
               ('ANGULAR_VELOCITY', 'Angular Velocity', ''),
               ('AGE', 'Age', ''),
               ('BIRTH_TIME', 'Birth Time', ''),
               ('DIE_TIME', 'Die Time', ''),
               ('LIFE_TIME', 'Lifetime', ''),
               ('ID', 'ID', '')
               ]   # XXX: Would be nice to have particle ID, needs adding in RNA
    )


class RendermanParticleSettings(bpy.types.PropertyGroup):

    particle_type_items = [('particle', 'Particle', 'Point primitive'),
                           ('blobby', 'Blobby',
                            'Implicit Surface (metaballs)'),
                           ('sphere', 'Sphere', 'Two-sided sphere primitive'),
                           ('disk', 'Disk', 'One-sided disk primitive'),
                           ('OBJECT', 'Object',
                            'Instanced objects at each point')
                           ]

    def update_psys(self, context):
        active = context.active_object
        active.update_tag(refresh={'DATA'})

    def update_point_type(self, context):
        return

    particle_type: EnumProperty(
        name="Point Type",
        description="Geometric primitive for points to be rendered as",
        items=particle_type_items,
        default='particle',
        update=update_point_type)

    particle_instance_object: StringProperty(
        name="Instance Object",
        description="Object to instance on every particle",
        default="")

    round_hair: BoolProperty(
        name="Round Hair",
        description="Render curves as round cylinders or ribbons.  Round is faster and recommended for hair",
        default=True)

    constant_width: BoolProperty(
        name="Constant Width",
        description="Override particle sizes with constant width value",
        update=update_psys,
        default=False)

    width: FloatProperty(
        name="Width",
        description="With used for constant width across all particles",
        update=update_psys,
        precision=4,
        default=0.01)

    export_default_size: BoolProperty(
        name="Export Default size",
        description="Export the particle size as the default 'width' primitive variable",
        default=True)

    export_scalp_st: BoolProperty(
        name="Export Emitter UV",
        description="On hair, export the u/v from the emitter where the hair originates.  Use the variable 'scalpST' in your manifold node",
        update=update_psys,
        default=True
    )

    uv_name: StringProperty(
        name="UV",
        description="Which UV map to use for scalpST. Default is to use the current active UV map",
        update=update_psys
    )

    export_mcol: BoolProperty(
        name="Export Vertex Color",
        description="For hair, export the vertex color from the emitter where the hair originates.  Use the variable 'Cs' in your shading network.",
        update=update_psys,
        default=True
    )    

    mcol_name: StringProperty(
        name="Vertex Color",
        description="Which vertex colors to use for hair. Default is to use the current active vertex color, if available",
        update=update_psys
    )    

    hair_index_name: StringProperty(
        name="Hair Index Name",
        description="The name of the index primvar used for each hair curve.",
        default="index",
        update=update_psys
    )

    do_velocity_blur: BoolProperty(
        name="Velocity Blur",
        description="By default, we do velocity based motion blur for particle systems. Uncheck this if you don't want any blur",
        default=True,
        update=update_psys
    )

    override_instance_material: BoolProperty(
        name='Override Instance Material',
        description='Override the material that is attached to the instance object',
        default=False
    ) 

    prim_vars: CollectionProperty(
        type=RendermanParticlePrimVar, name="Primitive Variables")
    prim_vars_index: IntProperty(min=-1, default=-1)

classes = [
    RendermanParticlePrimVar,
    RendermanParticleSettings
]

def register():

    from ...rfb_utils import register_utils

    register_utils.rman_register_classes(classes)

    bpy.types.ParticleSettings.renderman = PointerProperty(
        type=RendermanParticleSettings, name="Renderman Particle Settings")

def unregister(): 

    del bpy.types.ParticleSettings.renderman

    from ...rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes)