from .base_classes import RendermanPropertyGroup
from .rib_helpers import rib
from bpy.props import *

''' Object Properties ''' 
class RendermanObjectSettings(RendermanPropertyGroup):
    ''' Object Properties, also handles ribgen for mesh data '''
    ### object specific properties ###

    # raytrace parameters
    raytrace_pixel_variance = FloatProperty(
        name="Relative Pixel Variance",
        description="Allows this object ot render to a different quality level than the main scene.  Actual pixel variance will be this number multiplied by the main pixel variance.",
        default=1.0)

    raytrace_maxdiffusedepth_override = BoolProperty(
        name="Diffuse Depth Override",
        description="Sets the diffuse bounces for this object separately from the scene default",
        default=False)

    raytrace_maxdiffusedepth = IntProperty(
        name="Max Diffuse Depth",
        description="Limit the number of diffuse bounces",
        default=0)

    raytrace_maxspeculardepth_override = BoolProperty(
        name="Specular Depth Override",
        description="Sets the specular bounces for this object separately from the scene default",
        default=False)

    raytrace_maxspeculardepth = IntProperty(
        name="Max Specular Depth",
        description="Limit the number of specular bounces",
        default=0)

    raytrace_tracedisplacements = BoolProperty(
        name="Trace Displacements",
        description="Ray Trace true displacement in rendered results",
        default=True)

    raytrace_intersectpriority = IntProperty(
        name="Intersection Priority",
        description="Dictates the priority used when using nested dielectrics (overlapping materials).  Objects with higher numbers will override lower ones",
        default=0)

    raytrace_ior = FloatProperty(
        name="Index of Refraction",
        description="When using nested dielectrics (overlapping materials), this should be set to the same value as the ior of your material",
        default=1.0)

    # shading parameters
    shading_override = BoolProperty(
        name="Override Default Shading Rate",
        description="Override the default shading rate for this object.",
        default=False)
    shadingrate = FloatProperty(
        name="Micropolygon Length",
        description="Maximum distance between displacement samples (lower = more detailed shading).",
        default=1.0)

    motion_segments_override = BoolProperty(
        name="Override Motion Samples",
        description="Override the global number of motion samples for this object.",
        default=False)

    motion_segments = IntProperty(
        name="Motion Samples",
        description="Number of motion samples to take for multi-segment motion blur.  This should be raised if you notice segment artifacts in blurs.",
        min=2, max=16, default=2)

    #visibility parameters
    visibility_camera = BoolProperty(
        name="Visible to Camera Rays",
        description="Object visibility to Camera Rays.",
        default=True)

    visibility_trace_indirect = BoolProperty(
        name="All Indirect Rays",
        description="Sets all the indirect transport modes at once (specular & diffuse).",
        default=True)

    visibility_trace_transmission = BoolProperty(
        name="Visible to Transmission Rays",
        description="Object visibility to Transmission Rays (eg. shadow() and transmission()).",
        default=True)

    matte = BoolProperty(
        name="Matte Object",
        description="Render the object as a matte cutout (alpha 0.0 in final frame).",
        default=False)

    MatteID0 = FloatVectorProperty(
        name="Matte ID 0",
        description="Matte ID 0 Color, you also need to add the PxrMatteID node to your bxdf",
        size=3,
        subtype='COLOR',
        default=[0.0, 0.0, 0.0], soft_min=0.0, soft_max=1.0)

    MatteID1 = FloatVectorProperty(
        name="Matte ID 1",
        description="Matte ID 1 Color, you also need to add the PxrMatteID node to your bxdf",
        size=3,
        subtype='COLOR',
        default=[0.0, 0.0, 0.0], soft_min=0.0, soft_max=1.0)

    MatteID2 = FloatVectorProperty(
        name="Matte ID 2",
        description="Matte ID 2 Color, you also need to add the PxrMatteID node to your bxdf",
        size=3,
        subtype='COLOR',
        default=[0.0, 0.0, 0.0], soft_min=0.0, soft_max=1.0)

    MatteID3 = FloatVectorProperty(
        name="Matte ID 3",
        description="Matte ID 3 Color, you also need to add the PxrMatteID node to your bxdf",
        size=3,
        subtype='COLOR',
        default=[0.0, 0.0, 0.0], soft_min=0.0, soft_max=1.0)

    MatteID4 = FloatVectorProperty(
        name="Matte ID 4",
        description="Matte ID 4 Color, you also need to add the PxrMatteID node to your bxdf",
        size=3,
        subtype='COLOR',
        default=[0.0, 0.0, 0.0], soft_min=0.0, soft_max=1.0)

    MatteID5 = FloatVectorProperty(
        name="Matte ID 5",
        description="Matte ID 5 Color, you also need to add the PxrMatteID node to your bxdf",
        size=3,
        subtype='COLOR',
        default=[0.0, 0.0, 0.0], soft_min=0.0, soft_max=1.0)

    MatteID6 = FloatVectorProperty(
        name="Matte ID 6",
        description="Matte ID 6 Color, you also need to add the PxrMatteID node to your bxdf",
        size=3,
        subtype='COLOR',
        default=[0.0, 0.0, 0.0], soft_min=0.0, soft_max=1.0)

    MatteID7 = FloatVectorProperty(
        name="Matte ID 7",
        description="Matte ID 7 Color, you also need to add the PxrMatteID node to your bxdf",
        size=3,
        subtype='COLOR',
        default=[0.0, 0.0, 0.0], soft_min=0.0, soft_max=1.0)

    ### overrides of base class methods ###
    def to_rib(self, ri, **kwargs):
        ''' creates an attribute block for the object, reads in the data archive(s)
            and recursively calls any children to_ribs''' 
        ob = self.id_data
        ri.AttributeBegin()
        ri.Attribute("identifier", {"string name": ob.name})

        m = ob.matrix_local
        ri.ConcatTransform(rib(m))

        for data in self.get_data_items():
            archive_name = data.renderman.get_archive_filename(paths=kwargs['paths'], ob=ob)
            if archive_name:
                ri.ReadArchive(archive_name)

        for child in ob.children:
            child.renderman.to_rib(ri, **kwargs)

        ri.AttributeEnd()

    def get_data_items(self):
        ''' Gets any data blocks on this object, such as mesh or particle systems '''
        ob = self.id_data
        if ob.type == 'MESH':
            return [ob.data]
        return []