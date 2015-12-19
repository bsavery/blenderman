# ##### BEGIN MIT LICENSE BLOCK #####
#
# Copyright (c) 2015 Brian Savery
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
import sys
import os
from bpy.types import AddonPreferences
from bpy.props import CollectionProperty, BoolProperty, StringProperty
from bpy.props import IntProperty, PointerProperty

from .util import guess_rmantree


class RendermanPreferencePath(bpy.types.PropertyGroup):
    name = StringProperty(name="", subtype='DIR_PATH')


class RendermanEnvVarSettings(bpy.types.PropertyGroup):
    if sys.platform == ("win32"):
        outpath = os.path.join("C:", "Users", os.getlogin(), "Documents",
                               "PRMan")
        out = StringProperty(
            name="OUT (Output Root)",
            description="Default RIB export path root",
            subtype='DIR_PATH',
            default='$USERPROFILE\My Documents\prman_for_blender\{blend}')

    else:
        outpath = os.path.join(os.environ.get('HOME'), "Documents", "PRMan")
        out = StringProperty(
            name="OUT (Output Root)",
            description="Default RIB export path root",
            subtype='DIR_PATH',
            default='$HOME/Documents/prman_for_blender/{blend}')

    shd = StringProperty(
        name="SHD (Shadow Maps)",
        description="SHD environment variable",
        subtype='DIR_PATH',
        default=os.path.join('$OUT','shadowmaps'))

    ptc = StringProperty(
        name="PTC (Point Clouds)",
        description="PTC environment variable",
        subtype='DIR_PATH',
        default=os.path.join('$OUT','pointclouds'))

    arc = StringProperty(
        name="ARC (Archives)",
        description="ARC environment variable",
        subtype='DIR_PATH',
        default=os.path.join('$OUT','archives'))


class RendermanPreferences(AddonPreferences):
    bl_idname = __package__

    shader_paths = CollectionProperty(type=RendermanPreferencePath,
                                      name="Shader Paths")
    shader_paths_index = IntProperty(min=-1, default=-1)

    texture_paths = CollectionProperty(type=RendermanPreferencePath,
                                       name="Texture Paths")
    texture_paths_index = IntProperty(min=-1, default=-1)

    procedural_paths = CollectionProperty(type=RendermanPreferencePath,
                                          name="Procedural Paths")
    procedural_paths_index = IntProperty(min=-1, default=-1)

    archive_paths = CollectionProperty(type=RendermanPreferencePath,
                                       name="Archive Paths")
    archive_paths_index = IntProperty(min=-1, default=-1)

    use_default_paths = BoolProperty(
        name="Use PRMan default paths",
        description="Includes paths for default shaders etc. from RenderMan Pro\
            Server install",
        default=True)
    use_builtin_paths = BoolProperty(
        name="Use built in paths",
        description="Includes paths for default shaders etc. from PRMan\
            exporter",
        default=False)

    path_rmantree = StringProperty(
        name="RMANTREE Path",
        description="Path to RenderMan Pro Server installation folder",
        subtype='DIR_PATH',
        default=guess_rmantree())
    path_renderer = StringProperty(
        name="Renderer Path",
        description="Path to renderer executable",
        subtype='FILE_PATH',
        default="prman")
    path_shader_compiler = StringProperty(
        name="Shader Compiler Path",
        description="Path to shader compiler executable",
        subtype='FILE_PATH',
        default="shader")
    path_shader_info = StringProperty(
        name="Shader Info Path",
        description="Path to shaderinfo executable",
        subtype='FILE_PATH',
        default="sloinfo")
    path_texture_optimiser = StringProperty(
        name="Texture Optimiser Path",
        description="Path to tdlmake executable",
        subtype='FILE_PATH',
        default="txmake")

    env_vars = PointerProperty(
        type=RendermanEnvVarSettings,
        name="Environment Variable Settings")

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "use_default_paths")
        layout.prop(self, "use_builtin_paths")
        '''
        self._draw_collection(context, layout, self, "Shader Paths:", "collection.add_remove",
                                        "scene", "shader_paths", "shader_paths_index")
        self._draw_collection(context, layout, self, "Texture Paths:", "collection.add_remove",
                                        "scene", "texture_paths", "texture_paths_index")
        self._draw_collection(context, layout, self, "Procedural Paths:", "collection.add_remove",
                                        "scene", "procedural_paths", "procedural_paths_index")
        self._draw_collection(context, layout, self, "Archive Paths:", "collection.add_remove",
                                        "scene", "archive_paths", "archive_paths_index")
        '''
        layout.prop(self, "path_rmantree")
        layout.prop(self, "path_renderer")
        layout.prop(self, "path_shader_compiler")
        layout.prop(self, "path_shader_info")
        layout.prop(self, "path_texture_optimiser")

        env = self.env_vars
        layout.prop(env, "out")
        layout.prop(env, "shd")
        layout.prop(env, "ptc")
        layout.prop(env, "arc")


def register():
    bpy.utils.register_class(RendermanPreferencePath)
    bpy.utils.register_class(RendermanEnvVarSettings)
    bpy.utils.register_class(RendermanPreferences)


def unregister():
    bpy.utils.unregister_class(RendermanPreferences)
    bpy.utils.unregister_class(RendermanEnvVarSettings)
    bpy.utils.unregister_class(RendermanPreferencePath)
