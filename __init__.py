# ##### BEGIN MIT LICENSE BLOCK #####
#
# Copyright (c) 2011 Matt Ebb
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

""" Base module which loads the sub components and sets up app handlers """

bl_info = {
    "name": "RenderMan For Blender",
    "author": "Brian Savery",
    "version": (21, 2, 0),
    "blender": (2, 78, 0),
    "location": "Info Header, render engine menu",
    "description": "RenderMan 21.3 integration",
    "warning": "",
    "category": "Render"}

# list of modules to import to register.  Don't need to register util
#SUBMODULES = ['engine', 'operators', 'preferences', 'properties', 'ui']
SUBMODULES = ['engine', 'properties', 'preferences', 'ui']

import bpy
import importlib as imp
for module in SUBMODULES:
    imp.import_module('.' + module, package=__name__)

# register the module and subclasses
def register():
    bpy.utils.register_module(__name__)
    # add the pointer properties to things
    properties.add_properties()

def unregister():
    bpy.utils.unregister_module(__name__)
