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
from .base_classes import PRManPanel
from bpy.types import Panel


class RENDER_PT_renderman_sampling(PRManPanel, Panel):
    bl_label = "Sampling"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):

        layout = self.layout
        scene = context.scene
        rm = scene.renderman
        col = layout.column()
        row = col.row(align=True)
        row.menu("presets", text=bpy.types.presets.bl_label)
        row.operator("render.renderman_preset_add", text="", icon='ZOOMIN')
        row.operator("render.renderman_preset_add", text="",
                     icon='ZOOMOUT').remove_active = True
        col.prop(rm, "pixel_variance")
        row = col.row(align=True)
        row.prop(rm, "min_samples", text="Min Samples")
        row.prop(rm, "max_samples", text="Max Samples")
        row = col.row(align=True)
        row.prop(rm, "max_specular_depth", text="Specular Depth")
        row.prop(rm, "max_diffuse_depth", text="Diffuse Depth")
        row = col.row(align=True)
        row.prop(rm, 'incremental')
        row = col.row(align=True)
        layout.separator()
        col.prop(rm, "integrator")
        # find args for integrators here!
        integrator_settings = getattr(rm, "%s_settings" % rm.integrator)

        icon = 'DISCLOSURE_TRI_DOWN' if rm.show_integrator_settings \
            else 'DISCLOSURE_TRI_RIGHT'
        text = rm.integrator + " Settings:"

        row = col.row()
        row.prop(rm, "show_integrator_settings", icon=icon, text=text,
                 emboss=False)
        if rm.show_integrator_settings:
            draw_props(integrator_settings,
                       integrator_settings.prop_names, col)
