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
from .base_classes import PRManPanel
from ..resources.icons.icons import load_icons


class RENDER_PT_renderman_spooling(PRManPanel, Panel):

    '''this panel covers the options for spooling a render to an external queue manager'''
    bl_context = "render"
    bl_label = "External Rendering"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rm = scene.renderman

        # if external rendering is disabled, the panel will not appear
        row = layout.row()
        row.label(
            'Note:  External Rendering will render outside of Blender, images will not show up in the Image Editor.')

        row = layout.row()
        row.prop(rm, 'enable_external_rendering')
        if not rm.enable_external_rendering:
            return
        icons = load_icons()
        row = layout.row()
        rman_batch = icons.get("batch_render")
        row.operator("renderman.external_render",
                     text="Export", icon_value=rman_batch.icon_id)

        layout.separator()
        col = layout.column()
        col.prop(rm, "display_driver", text='Render To')

        layout.separator()
        split = layout.split(percentage=0.33)
        # do animation
        split.prop(rm, "external_animation")

        sub_row = split.row()
        sub_row.enabled = rm.external_animation
        sub_row.prop(scene, "frame_start", text="Start")
        sub_row.prop(scene, "frame_end", text="End")
        col = layout.column()
        col.enabled = rm.generate_alf
        col.prop(rm, 'external_denoise')
        row = col.row()
        row.enabled = rm.external_denoise and rm.external_animation
        row.prop(rm, 'crossframe_denoise')

        # render steps
        layout.separator()
        col = layout.column()
        icon_export = 'DISCLOSURE_TRI_DOWN' if rm.export_options else 'DISCLOSURE_TRI_RIGHT'
        col.prop(rm, "export_options", icon=icon_export,
                 text="Export Options:", emboss=False)
        if rm.export_options:
            col.prop(rm, "generate_rib")
            row = col.row()
            row.enabled = rm.generate_rib
            row.prop(rm, "generate_object_rib")
            col.prop(rm, "generate_alf")
            split = col.split(percentage=0.33)
            split.enabled = rm.generate_alf and rm.generate_render
            split.prop(rm, "do_render")
            sub_row = split.row()
            sub_row.enabled = rm.do_render and rm.generate_alf and rm.generate_render
            sub_row.prop(rm, "queuing_system")

        # options
        layout.separator()
        if rm.generate_alf:
            icon_alf = 'DISCLOSURE_TRI_DOWN' if rm.alf_options else 'DISCLOSURE_TRI_RIGHT'
            col = layout.column()
            col.prop(rm, "alf_options", icon=icon_alf, text="ALF Options:",
                     emboss=False)
            if rm.alf_options:
                col.prop(rm, 'custom_alfname')
                col.prop(rm, "convert_textures")
                col.prop(rm, "generate_render")
                row = col.row()
                row.enabled = rm.generate_render
                row.prop(rm, 'custom_cmd')
                split = col.split(percentage=0.33)
                split.enabled = rm.generate_render
                split.prop(rm, "override_threads")
                sub_row = split.row()
                sub_row.enabled = rm.override_threads
                sub_row.prop(rm, "external_threads")

                row = col.row()
                row.enabled = rm.external_denoise
                row.prop(rm, 'denoise_cmd')
                row = col.row()
                row.enabled = rm.external_denoise
                row.prop(rm, 'spool_denoise_aov')
                row = col.row()
                row.enabled = rm.external_denoise and not rm.spool_denoise_aov
                row.prop(rm, "denoise_gpu")

                col = layout.column()
                col.enabled = rm.generate_render
                row = col.row()
                row.prop(rm, 'recover')
                row = col.row()
                row.prop(rm, 'enable_checkpoint')
                row = col.row()
                row.enabled = rm.enable_checkpoint
                row.prop(rm, 'asfinal')
                row = col.row()
                row.enabled = rm.enable_checkpoint
                row.prop(rm, 'checkpoint_type')
                row = col.row(align=True)
                row.enabled = rm.enable_checkpoint
                row.prop(rm, 'checkpoint_interval')
                row.prop(rm, 'render_limit')
