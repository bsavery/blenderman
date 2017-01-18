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
from bpy.props import BoolProperty, StringProperty
from bpy.props import EnumProperty

from ..util.util import get_installed_rendermans,\
    rmantree_from_env, guess_rmantree

# get the out_path default based on os
OUT_PATH = 'C:/tmp/renderman_for_blender/{blend}' if sys.platform == ("win32") else \
    '/tmp/renderman_for_blender/{blend}'

class PRManAddonPrefs(AddonPreferences):
    ''' Addon prefences with it's own draw function'''
    bl_idname = __package__.split('.')[0] # to match upper addon name

    def find_installed_rendermans(self, context):
        ''' populate the enum for installed rendermans '''
        options = [('NEWEST', 'Newest Version Installed',
                    'Automatically updates when new version installed.')]
        for vers, path in get_installed_rendermans():
            options.append((path, vers, path))
        return options

    rmantree_choice = EnumProperty(
        name='RenderMan Version to use',
        description='Leaving as "Newest" will automatically update when you install a new RenderMan version',
        # default='NEWEST',
        items=find_installed_rendermans
    )

    rmantree_method = EnumProperty(
        name='RenderMan Location',
        description='How RenderMan should be detected.  Most users should leave to "Detect"',
        items=[('DETECT', 'Choose From Installed', 'This will scan for installed RenderMan locations to choose from'),
               ('ENV', 'Get From RMANTREE Environment Variable',
                'This will use the RMANTREE set in the enviornment variables'),
               ('MANUAL', 'Set Manually', 'Manually set the RenderMan installation (for expert users)')])

    path_rmantree = StringProperty(
        name="RMANTREE Path",
        description="Path to RenderMan Pro Server installation folder",
        subtype='DIR_PATH',
        default='')
    
    draw_ipr_text = BoolProperty(
        name="Draw IPR Text",
        description="Draw notice on View3D when IPR is active",
        default=True)

    path_main_image = StringProperty(
        name="Main Image path",
        description="Path for the rendered main image",
        subtype='FILE_PATH',
        default=os.path.join('{out}', 'images', '{scene}.####.{file_type}'))

    path_aov_image = StringProperty(
        name="AOV Image path",
        description="Path for the rendered aov images",
        subtype='FILE_PATH',
        default=os.path.join('{out}', 'images', '{scene}.{layer}.{pass}.####.{file_type}'))

    path_rib_output = StringProperty(
        name="RIB Output Path",
        description="Path to generated .rib files",
        subtype='FILE_PATH',
        default=os.path.join('{out}', '{scene}.####.rib'))

    path_object_archive_static = StringProperty(
        name="Object archive RIB Output Path",
        description="Path to generated rib file for a non-deforming objects' geometry",
        subtype='FILE_PATH',
        default=os.path.join('{out}', 'archives', 'static', '{object}.rib'))

    path_object_archive_animated = StringProperty(
        name="Object archive RIB Output Path",
        description="Path to generated rib file for an animated objects geometry",
        subtype='FILE_PATH',
        default=os.path.join('{out}', 'archives', '####', '{object}.rib'))

    path_texture_output = StringProperty(
        name="Teture Output Path",
        description="Path to generated .tex files",
        subtype='FILE_PATH',
        default=os.path.join('{out}', 'textures'))

    out = StringProperty(
        name="OUT (Output Root)",
        description="Default RIB export path root",
        subtype='DIR_PATH',
        default=OUT_PATH)

    def draw(self, context):
        layout = self.layout
        rmantree_sub = layout.box()
        rmantree_sub.label('RenderMan Location')
        rmantree_sub.prop(self, 'rmantree_method')
        if self.rmantree_method == 'DETECT':
            rmantree_sub.prop(self, 'rmantree_choice')
        elif self.rmantree_method == 'ENV':
            rmantree_sub.label(text="RMANTREE: %s " % rmantree_from_env())
        else:
            rmantree_sub.prop(self, "path_rmantree")
        if guess_rmantree() is None:
            row = rmantree_sub.row()
            row.alert = True
            row.label('Error in RMANTREE. Reload addon to reset.', icon='ERROR')

        paths_sub = layout.box()
        paths_sub.label('Paths')
        paths_sub.prop(self, 'out')
        paths_sub.prop(self, 'path_rib_output')
        paths_sub.prop(self, 'path_main_image')
        paths_sub.prop(self, 'path_aov_image')
        paths_sub.prop(self, 'path_texture_output')
        
        layout.prop(self, 'draw_ipr_text')
