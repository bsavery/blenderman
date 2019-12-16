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
import os
import shutil
import bpy
from bpy.props import StringProperty, EnumProperty, BoolProperty
from .properties import RendermanPresetGroup, RendermanPreset
from . import icons
import json
from bpy.types import NodeTree

# update the tree structure from disk file
def refresh_presets_libraries(disk_lib, preset_library):
    dirs = os.listdir(disk_lib)
    for dir in dirs:
        cdir = os.path.join(disk_lib, dir)
        # skip if not a dir
        if not os.path.isdir(cdir):
            continue
        
        is_asset = '.rma' in dir
        path = os.path.join(disk_lib, dir)

        if is_asset:
            preset = preset_library.presets.get(dir, None)
            if not preset:
                preset = preset_library.presets.add()
            

            preset.name = dir
            json_path = os.path.join(path, 'asset.json')
            data = json.load(open(json_path))
            preset.label = data['RenderManAsset']['label']
            preset.path = path
            preset.json_path = os.path.join(path, 'asset.json')

        else:
            sub_group = preset_library.sub_groups.get(dir, None)
            if not sub_group:
                sub_group = preset_library.sub_groups.add()
            sub_group.name = dir
            sub_group.path = path

            refresh_presets_libraries(cdir, sub_group)

    for i,sub_group in enumerate(preset_library.sub_groups):
        if sub_group.name not in dirs:
            preset_library.sub_groups.remove(i)
    for i,preset in enumerate(preset_library.presets):
        if preset.name not in dirs:
            preset_library.presets.remove(i)


# if the library isn't present copy it from rmantree to the path in addon prefs
class init_preset_library(bpy.types.Operator):
    bl_idname = "renderman.init_preset_library"
    bl_label = "Init RenderMan Preset Library"
    bl_description = "Copies the Preset Library from RMANTREE to the library path if not present\n Or refreshes if changed on disk."

    def invoke(self, context, event):
        presets_library = util.get_addon_prefs().presets_library
        presets_path = util.get_addon_prefs().presets_path
        
        if not os.path.exists(presets_path):
            rmantree_lib_path = os.path.join(util.guess_rmantree(), 'lib', 'RenderManAssetLibrary')
            shutil.copytree(rmantree_lib_path, presets_path)
            
        presets_library.name = 'Library'
        presets_library.path = presets_path
        refresh_presets_libraries(presets_path, presets_library)
        bpy.ops.wm.save_userpref()
        return {'FINISHED'}

# if the library isn't present copy it from rmantree to the path in addon prefs
class load_asset_to_scene(bpy.types.Operator):
    bl_idname = "renderman.load_asset_to_scene"
    bl_label = "Load Asset to Scene"
    bl_description = "Load the Asset to scene"

    preset_path: StringProperty(default='')
    assign: BoolProperty(default=False)

    def invoke(self, context, event):
        preset = RendermanPreset.get_from_path(self.properties.preset_path)
        from . import rmanAssetsBlender
        mat = rmanAssetsBlender.importAsset(preset.json_path)
        if self.properties.assign and mat and type(mat) == bpy.types.Material:
            for ob in context.selected_objects:
                ob.active_material = mat

        return {'FINISHED'}


# save the current material to the library
class save_asset_to_lib(bpy.types.Operator):
    bl_idname = "renderman.save_asset_to_library"
    bl_label = "Save Asset to Library"
    bl_description = "Save Asset to Library"

    lib_path: StringProperty(default='')

    def invoke(self, context, event):
        presets_path = util.get_addon_prefs().presets_library.path
        path = os.path.relpath(self.properties.lib_path, presets_path)
        library = RendermanPresetGroup.get_from_path(self.properties.lib_path)
        ob = context.active_object
        mat = ob.active_material
        nt = mat.node_tree
        if nt:
            from . import rmanAssetsBlender
            os.environ['RMAN_ASSET_LIBRARY'] = presets_path
            rmanAssetsBlender.exportAsset(nt, 'nodeGraph', 
                                          {'label':mat.name,
                                           'author': '',
                                           'version': ''},
                                           path
                                           )
        refresh_presets_libraries(library.path, library)
        bpy.ops.wm.save_userpref()
        return {'FINISHED'}


# if the library isn't present copy it from rmantree to the path in addon prefs
class set_active_preset_library(bpy.types.Operator):
    bl_idname = "renderman.set_active_preset_library"
    bl_label = "Set active RenderMan Preset Library"
    bl_description = "Sets the clicked library active"

    lib_path: StringProperty(default='')

    def execute(self, context):
        lib_path = self.properties.lib_path
        if lib_path:
            util.get_addon_prefs().active_presets_path = lib_path
        return {'FINISHED'}

# if the library isn't present copy it from rmantree to the path in addon prefs
class add_preset_library(bpy.types.Operator):
    bl_idname = "renderman.add_preset_library"
    bl_label = "Add RenderMan Preset Library"
    bl_description = "Adds a new library"

    new_name: StringProperty(default="")
    
    def execute(self, context):
        active = RendermanPresetGroup.get_active_library()
        lib_path = active.path
        new_folder = self.properties.new_name
        if lib_path and new_folder:
            path = os.path.join(lib_path, new_folder)
            os.mkdir(path)
            sub_group = active.sub_groups.add()
            sub_group.name = new_folder
            sub_group.path = path

            util.get_addon_prefs().active_presets_path = path
        bpy.ops.wm.save_userpref()
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        row = self.layout
        row.prop(self, "new_name", text="New Folder Name:")

class remove_preset_library(bpy.types.Operator):
    bl_idname = "renderman.remove_preset_library"
    bl_label = "Remove RenderMan Preset Library"
    bl_description = "Remove a library"

    def execute(self, context):
        active = RendermanPresetGroup.get_active_library()
        lib_path = active.path
        if lib_path:
            parent_path = os.path.split(active.path)[0]
            parent = RendermanPresetGroup.get_from_path(parent_path)
            util.get_addon_prefs().active_presets_path = parent_path
            
            shutil.rmtree(active.path)

            refresh_presets_libraries(parent.path, parent)
        bpy.ops.wm.save_userpref()  
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

class remove_preset(bpy.types.Operator):
    bl_idname = "renderman.remove_preset"
    bl_label = "Remove RenderMan Preset"
    bl_description = "Remove a Preset"

    preset_path: StringProperty()

    def execute(self, context):
        preset_path = self.properties.preset_path
        active = RendermanPreset.get_from_path(preset_path)
        if active:
            parent_path = os.path.split(preset_path)[0]
            parent = RendermanPresetGroup.get_from_path(parent_path)
            
            shutil.rmtree(active.path)

            refresh_presets_libraries(parent.path, parent)
        bpy.ops.wm.save_userpref()   
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

class move_preset(bpy.types.Operator):
    bl_idname = "renderman.move_preset"
    bl_label = "Move RenderMan Preset"
    bl_description = "Move a Preset"

    def get_libraries(self, context):
        def get_libs(parent_lib):
            enum = [(parent_lib.path, parent_lib.name, '')]
            for lib in parent_lib.sub_groups:
                enum.extend(get_libs(lib))
            return enum
        return get_libs(util.get_addon_prefs().presets_library)

    preset_path: StringProperty(default='')
    new_library: EnumProperty(items=get_libraries, description='New Library', name="New Library")

    def execute(self, context):
        new_parent_path = self.properties.new_library
        active = RendermanPreset.get_from_path(self.properties.preset_path)
        if active:
            old_parent_path = os.path.split(active.path)[0]
            old_parent = RendermanPresetGroup.get_from_path(old_parent_path)
            new_parent = RendermanPresetGroup.get_from_path(new_parent_path)

            shutil.move(active.path, new_parent_path)
            
            refresh_presets_libraries(old_parent.path, old_parent)
            refresh_presets_libraries(new_parent.path, new_parent)
        bpy.ops.wm.save_userpref()
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        row = self.layout
        row.prop(self, "new_library", text="New Library")

class move_preset_library(bpy.types.Operator):
    bl_idname = "renderman.move_preset_library"
    bl_label = "Move RenderMan Preset Group"
    bl_description = "Move a Preset Group"

    def get_libraries(self, context):
        def get_libs(parent_lib):
            enum = [(parent_lib.path, parent_lib.name, '')]
            for lib in parent_lib.sub_groups:
                enum.extend(get_libs(lib))
            return enum

        return get_libs(util.get_addon_prefs().presets_library)

    lib_path: StringProperty(default='')
    new_library: EnumProperty(items=get_libraries, description='New Library', name="New Library")

    def execute(self, context):
        new_parent_path = self.properties.new_library
        active = RendermanPresetGroup.get_from_path(self.properties.lib_path)
        if active:
            old_parent_path = os.path.split(active.path)[0]
            old_parent = RendermanPresetGroup.get_from_path(old_parent_path)
            new_parent = RendermanPresetGroup.get_from_path(new_parent_path)

            shutil.move(active.path, new_parent_path)
            
            refresh_presets_libraries(old_parent.path, old_parent)
            refresh_presets_libraries(new_parent.path, new_parent)
        bpy.ops.wm.save_userpref()
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        row = self.layout
        row.prop(self, "new_library", text="New Parent")
        
def register():
    try:
        bpy.utils.register_class(init_preset_library)
        bpy.utils.register_class(set_active_preset_library)
        bpy.utils.register_class(load_asset_to_scene)
        bpy.utils.register_class(save_asset_to_lib)
        bpy.utils.register_class(add_preset_library)
        bpy.utils.register_class(remove_preset_library)
        bpy.utils.register_class(move_preset_library)
        bpy.utils.register_class(move_preset)
        bpy.utils.register_class(remove_preset)
    except:
        pass #allready registered

def unregister():
    bpy.utils.unregister_class(init_preset_library)
    bpy.utils.unregister_class(set_active_preset_library)
    bpy.utils.unregister_class(load_asset_to_scene)
    bpy.utils.unregister_class(save_asset_to_lib)
    bpy.utils.unregister_class(add_preset_library)
    bpy.utils.unregister_class(remove_preset_library)
    bpy.utils.unregister_class(move_preset_library)
    bpy.utils.unregister_class(move_preset)
    bpy.utils.unregister_class(remove_preset)
