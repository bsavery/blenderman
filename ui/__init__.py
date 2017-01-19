""" This module has the RenderMan ui panels."""

from os.path import dirname, basename, isfile
import glob
import bpy

# load icons
import os

# get all .py files in directory
__all__ = [basename(f)[:-3] for f in glob.glob(dirname(__file__) + "/*.py")
           if isfile(f) and basename(f) != '__init__.py']

# try and reload modules if already loaded
import importlib as imp
for module in __all__:
    imp.import_module('.' + module, package=__name__)
