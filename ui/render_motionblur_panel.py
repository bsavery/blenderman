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

import bpy
from bpy.props import *
from bpy.types import Panel
from ..resources.icons.icons import load_icons


class RENDER_PT_renderman_motion_blur(PRManPanel, Panel):
    '''This panel covers the settings for Renderman's motion blur'''
    bl_context = "render"
    bl_label = "Motion Blur"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        rm = context.scene.renderman

        icon = 'DISCLOSURE_TRI_DOWN' if rm.advanced_timing else 'DISCLOSURE_TRI_RIGHT'

        layout = self.layout
        col = layout.column()
        col.prop(rm, "motion_blur")
        col = layout.column()
        col.enabled = rm.motion_blur
        col.prop(rm, "sample_motion_blur")
        col.prop(rm, "motion_segments")
        col.prop(rm, "shutter_timing")
        col.prop(rm, "shutter_angle")
        row = col.row(align=True)
        row.prop(rm, "shutter_efficiency_open")
        row.prop(rm, "shutter_efficiency_close")
        layout.separator()
        col = layout.column()
        col.prop(item, "show_advanced", icon=icon,
                 text="Advanced Shutter Timing", icon_only=True, emboss=False)
        if rm.advanced_timing:
            row = col.row(align=True)
            row.prop(rm, "c1")
            row.prop(rm, "c2")
            row.prop(rm, "d1")
            row.prop(rm, "d2")
            row = col.row(align=True)
            row.prop(rm, "e1")
            row.prop(rm, "e2")
            row.prop(rm, "f1")
            row.prop(rm, "f2")
