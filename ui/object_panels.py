import bpy
from .base_classes import PRManPanel
from bpy.types import Panel
from ..resources.icons.icons import load_icons


class OBJECT_PT_renderman_object(PRManPanel, Panel):
	'''This panel allows the user to make modifications to the raytracing,
	shading and visibility parameters of each Blender object.  The override
	parameters are included in RIB output only when enabled
	'''
	bl_context = "object"
    bl_label = "Raytracing, Shading and Visibility"

    def draw(self, context):
        layout = self.layout
        ob = context.object
        rm = ob.renderman

        col = layout.column()
        col.label("Visibility Options:")
        row = col.row()
        row.prop(rm, "visibility_camera", text="Camera")
        row.prop(rm, "visibility_trace_indirect", text="Indirect")
        row = col.row()
        row.prop(rm, "visibility_trace_transmission", text="Transmission")
        row.prop(rm, "matte")
        col.prop(rm, 'MatteID0')
        col.prop(rm, 'MatteID1')
        col.prop(rm, 'MatteID2')
        col.prop(rm, 'MatteID3')
        col.prop(rm, 'MatteID4')
        col.prop(rm, 'MatteID5')
        col.prop(rm, 'MatteID6')
        col.prop(rm, 'MatteID7')

        col = layout.column()
        col.label("Shading Options:")
        row.prop(rm, 'shading_override')
        row = col.row()
        row.enabled = rm.shading_override
        row.prop(rm, "shadingrate")

        col = layout.column()
        col.label("Motion Segments Options:")
        row = col.row()
        row.prop(rm, "motion_segments_override")
        row = col.row()
        row.enabled = rm.motion_segments_override
        row.prop(rm, "motion_segments")

        col = layout.column()
        col.label("Raytracing Options":)
        row = col.row()
        row.label("Intersection Priority:")
        row.label("IOR:")
        row = col.row(align=True)
        row.prop(rm, "raytrace_intersectpriority")
        row.prop(rm, "raytrace_ior")
        col.prop(rm, "raytrace_pixel_variance")
        row = col.row()
        row.prop(rm, "raytrace_maxdiffusedepth_override")
        row.prop(rm, "raytrace_maxspeculardepth_override")
        col = row.column()
        col.enabled = rm.raytrace_maxdiffusedepth_override
        col.prop(rm, "raytrace_maxdiffusedepth")
        col = row.column()
        col.enabled = rm.raytrace_maxspeculardepth_override
        col.prop(rm, "raytrace_maxspeculardepth")
        col = layout.column()
        col.prop(rm, "raytrace_tracedisplacements")
