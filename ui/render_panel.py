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
from ..resources.icons.icons import load_icons

'''This file defines the panels that appear in the Render ui tab'''


class RENDER_PT_renderman_render(PRManPanel, Panel):
    '''This panel covers the settings for Renderman's motion blur'''
    bl_context = "render"
    bl_label = "Render"

    def draw(self, context):
        # icons = load_icons()
        layout = self.layout
        rd = context.scene.render
        rm = context.scene.renderman

        # # Render
        # row = layout.row(align=True)
        # rman_render = icons.get("render")
        # row.operator("render.render", text="Render",
        #              icon_value=rman_render.icon_id)

        # # IPR
        # if engine.ipr:
        #     # Stop IPR
        #     rman_batch_cancel = icons.get("stop_ipr")
        #     row.operator('lighting.start_interactive',
        #                  text="Stop IPR", icon_value=rman_batch_cancel.icon_id)
        # else:
        #     # Start IPR
        #     rman_rerender_controls = icons.get("start_ipr")
        #     row.operator('lighting.start_interactive', text="Start IPR",
        #                  icon_value=rman_rerender_controls.icon_id)

        # # Batch Render
        # rman_batch = icons.get("batch_render")
        # row.operator("render.render", text="Render Animation",
        #              icon_value=rman_batch.icon_id).animation = True

        # layout.separator()

        split = layout.split(percentage=0.33)

        split.label(text="Display:")
        row = split.row(align=True)
        row.prop(rd, "display_mode", text="")
        row.prop(rd, "use_lock_interface", icon_only=True)
        col = layout.column()
        row = col.row()
        row.prop(rm, "render_into", text="Render To")

        # layout.separator()
        # col = layout.column()
        # col.prop(context.scene.renderman, "render_selected_objects_only")
        # col.prop(rm, "do_denoise")
