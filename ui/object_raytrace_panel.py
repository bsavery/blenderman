# ##### BEGIN MIT LICENSE BLOCK #####
#
# Copyright (c) 2015 - 2017 Pixar
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
#
# ##### END MIT LICENSE BLOCK #####

from .base_classes import PRManPanel
from bpy.types import Panel


class OBJECT_PT_renderman_object(PRManPanel, Panel):
    '''This panel allows the user to make modifications to the raytracing,
        shading and visibility parameters of each Blender object.  The override
        parameters are included in RIB output only when enabled
        '''
    bl_label = "Raytracing, Shading and Visibility"
    bl_context = "object"

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
        col.label("Raytracing Options:")
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
