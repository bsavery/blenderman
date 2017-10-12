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

from .. import util

# for panel icon
from .. icons import icons as ui_icons

import bpy
from .properties import RendermanPresetGroup, RendermanPreset

# for previews of assets
from . import icons

from bpy.props import StringProperty


# panel for the toolbar of node editor
class Renderman_Presets_UI_Panel(bpy.types.Panel):
    bl_idname = "renderman_presets_ui_panel"
    bl_label = "RenderMan Presets"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Renderman"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return rd.engine == 'PRMAN_RENDER'

    def draw_header(self, context):
        if util.get_addon_prefs().draw_panel_icon:
            rfb_icons = ui_icons.load_icons()
            rfb_icon = rfb_icons.get("rfb_panel")
            self.layout.label(text="", icon_value=rfb_icon.icon_id)
        else:
            pass

    # draws the panel
    def draw(self, context):
        scene = context.scene
        rm = scene.renderman
        layout = self.layout

        if context.scene.render.engine != "PRMAN_RENDER":
            return

        presets_library = util.get_addon_prefs().presets_library

        if presets_library.name == '':
            layout.operator("renderman.init_preset_library", text="Set up Library")
        else:
            layout = self.layout

            row = layout.row(align=True)
            row.context_pointer_set('renderman_preset', util.get_addon_prefs().presets_library)
            row.menu('renderman_presets_menu', text="Select Library")
            row.operator("renderman.init_preset_library", text="", icon="FILE_REFRESH")
            active = RendermanPresetGroup.get_active_library()

            if active:
                row = layout.row(align=True)
                row.prop(active, 'name', text='Library')
                row.operator('renderman.add_preset_library', text='', icon='ZOOMIN')
                row.operator('renderman.move_preset_library', text='', icon='MAN_TRANS').lib_path = active.path
                row.operator('renderman.remove_preset_library', text='', icon='X')
                current_preset = RendermanPreset.get_from_path(active.current_preset)

                if current_preset:
                    row = layout.row()
                    row.label("Current Preset:")
                    row.prop(active, 'current_preset', text='')
                    layout.template_icon_view(active, "current_preset")
                    # row of controls for preset
                    row = layout.row(align=True)
                    row.prop(current_preset, 'label', text="")
                    row.operator('renderman.move_preset', icon='MAN_TRANS', text="").preset_path = current_preset.path
                    row.operator('renderman.remove_preset', icon='X', text="").preset_path = current_preset.path

                    # add to scene
                    row = layout.row(align=True)
                    row.operator("renderman.load_asset_to_scene", text="Load to Scene", ).preset_path = current_preset.path
                    assign = row.operator("renderman.load_asset_to_scene", text="Assign to selected", )
                    assign.preset_path = current_preset.path
                    assign.assign = True

                # get from scene
                layout.separator()
                layout.operator("renderman.save_asset_to_library", text="Save Material to Library").lib_path = active.path

class Renderman_Presets_Menu(bpy.types.Menu):
    bl_idname = "renderman_presets_menu"
    bl_label = "RenderMan Presets Menu"

    path = StringProperty(default="")

    def draw(self, context):
        lib = context.renderman_preset
        prefix = "* " if lib.is_active() else ''
        self.layout.operator('renderman.set_active_preset_library',text=prefix + lib.name).lib_path = lib.path
        if len(lib.sub_groups) > 0:
            for key in sorted(lib.sub_groups.keys(), key=lambda k: k.lower()):
                sub = lib.sub_groups[key]
                self.layout.context_pointer_set('renderman_preset', sub)
                prefix = "* " if sub.is_active() else ''
                if len(sub.sub_groups):
                    self.layout.menu('renderman_presets_menu', text=prefix + sub.name)
                else:
                    prefix = "* " if sub.is_active() else ''
                    self.layout.operator('renderman.set_active_preset_library',text=prefix + sub.name).lib_path = sub.path


def register():
    try:
        bpy.utils.register_class(Renderman_Presets_Menu)
        bpy.utils.register_class(Renderman_Presets_UI_Panel)
    except:
        pass #allready registered

def unregister():
    bpy.utils.unregister_class(Renderman_Presets_Menu)
    bpy.utils.unregister_class(Renderman_Presets_UI_Panel)
