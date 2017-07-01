from .base_classes import RendermanPropertyGroup
from .rib_helpers import rib
from bpy.props import *
from mathutils import Matrix
from ..ui.base_classes import PRManPanel
from bpy.types import Panel
from ..resources.icons.icons import load_icons

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

    # visibility parameters
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
            archive_name = data.renderman.get_archive_filename(
                paths=kwargs['paths'], ob=ob)
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

    def get_updated_data_items(self):
        ''' Gets any data blocks on this object, such as mesh or particle systems '''
        return [data for data in self.get_data_items() if data.is_updated]

    def export_camera_matrix(self, ri, **kwargs):
        ''' Exports this objects matrix as a camera matrix '''
        mat = self.id_data.matrix_world
        loc = mat.translation
        rot = mat.to_euler()

        s = Matrix(([1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]))
        r = Matrix.Rotation(-rot[0], 4, 'X')
        r *= Matrix.Rotation(-rot[1], 4, 'Y')
        r *= Matrix.Rotation(-rot[2], 4, 'Z')
        l = Matrix.Translation(-loc)
        m = s * r * l

        ri.Transform(rib(m))


class OBJECT_PT_renderman_object_geometry(PRManPanel, Panel):
    bl_context = "object"
    bl_label = "Renderman Geometry"

    def draw(self, context):
        layout = self.layout
        ob = context.object
        rm = ob.renderman
        anim = rm.archive_anim_settings

        col = layout.column()
        col.prop(rm, "geometry_source")

        if rm.geometry_source in ('ARCHIVE', 'DELAYED_LOAD_ARCHIVE'):
            col.prop(rm, "path_archive")

            col.prop(anim, "animated_sequence")
            if anim.animated_sequence:
                col.prop(anim, "blender_start")
                row = col.row()
                row.prop(anim, "sequence_in")
                row.prop(anim, "sequence_out")

        elif rm.geometry_source == 'PROCEDURAL_RUN_PROGRAM':
            col.prop(rm, "path_runprogram")
            col.prop(rm, "path_runprogram_args")
        elif rm.geometry_source == 'DYNAMIC_LOAD_DSO':
            col.prop(rm, "path_dso")
            col.prop(rm, "path_dso_initial_data")

        if rm.geometry_source in ('DELAYED_LOAD_ARCHIVE',
                                  'PROCEDURAL_RUN_PROGRAM',
                                  'DYNAMIC_LOAD_DSO'):
            col.prop(rm, "procedural_bounds")

            if rm.procedural_bounds == 'MANUAL':
                colf = layout.column_flow()
                colf.prop(rm, "procedural_bounds_min")
                colf.prop(rm, "procedural_bounds_max")

        if rm.geometry_source == 'BLENDER_SCENE_DATA':
            col.prop(rm, "primitive")

            colf = layout.column_flow()

            if rm.primitive in ('CONE', 'DISK'):
                colf.prop(rm, "primitive_height")
            if rm.primitive in ('SPHERE', 'CYLINDER', 'CONE', 'DISK'):
                colf.prop(rm, "primitive_radius")
            if rm.primitive == 'TORUS':
                colf.prop(rm, "primitive_majorradius")
                colf.prop(rm, "primitive_minorradius")
                colf.prop(rm, "primitive_phimin")
                colf.prop(rm, "primitive_phimax")
            if rm.primitive in ('SPHERE', 'CYLINDER', 'CONE', 'TORUS'):
                colf.prop(rm, "primitive_sweepangle")
            if rm.primitive in ('SPHERE', 'CYLINDER'):
                colf.prop(rm, "primitive_zmin")
                colf.prop(rm, "primitive_zmax")
            if rm.primitive == 'POINTS':
                colf.prop(rm, "primitive_point_type")
                colf.prop(rm, "primitive_point_width")

            # col.prop(rm, "export_archive")
            # if rm.export_archive:
            #    col.prop(rm, "export_archive_path")

        rman_archive = load_icons().get("archive_RIB")
        col = layout.column()
        col.operator("export.export_rib_archive",
                     text="Export Object as RIB Archive.", icon_value=rman_archive.icon_id)

        col = layout.column()
        # col.prop(rm, "export_coordsys")

        row = col.row()
        row.prop(rm, "motion_segments_override", text="")
        sub = row.row()
        sub.active = rm.motion_segments_override
        sub.prop(rm, "motion_segments")
