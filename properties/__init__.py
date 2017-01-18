""" This module has the RenderMan properties which are added to things like the scene,
    and objects.  Properties Classes handle rib gen as well as holding data."""

from os.path import dirname, basename, isfile
import glob
import bpy
from bpy.props import PointerProperty

# get all .py files in directory
__all__ = [basename(f)[:-3] for f in glob.glob(dirname(__file__)+"/*.py") \
           if isfile(f) and basename(f) != '__init__.py']

# try and reload modules if already loaded
import importlib as imp
for module in __all__:
    imp.import_module('.' + module, package=__name__)

# attach the properties to their respective ID in blender
def add_properties():
    bpy.types.Scene.renderman = PointerProperty(type=scene.RendermanSceneSettings, 
                                                name="Renderman Scene Settings")

    bpy.types.Object.renderman = PointerProperty(type=object.RendermanObjectSettings, 
                                                name="Renderman Object Settings")

    bpy.types.Mesh.renderman = PointerProperty(type=mesh.RendermanMeshSettings, 
                                                name="Renderman Mesh Settings")