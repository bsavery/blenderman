import bpy
import os
import platform
import sys
import webbrowser
import re
from ..rfb_logger import rfb_log
from .prefs_utils import get_pref
from . import string_utils
from .. import rman_constants

def view_file(file_path):
    
    rman_editor = get_pref('rman_editor', '')

    if rman_editor:
        rman_editor = get_real_path(rman_editor)
        command = rman_editor + " " + file_path
        try:
            os.system(command)
            return
        except Exception:
            rfb_log().error("File or text editor not available. (Check and make sure text editor is in system path.)")        


    if sys.platform == ("win32"):
        try:
            os.startfile(file_path)
            return
        except:
            pass
    else:
        if sys.platform == ("darwin"):
            opener = 'open -t'
        else:
            opener = os.getenv('EDITOR', 'xdg-open')
            opener = os.getenv('VIEW', opener)
        try:
            command = opener + " " + file_path
            os.system(command)
            return
        except Exception as e:
            rfb_log().error("Open file command failed: %s" % command)
            pass
        
    # last resort, try webbrowser
    try:
        webbrowser.open(file_path)
    except Exception as e:
        rfb_log().error("Open file with web browser failed: %s" % str(e))    

def get_cycles_shader_path():
    # figure out the path to Cycles' shader path
    # hopefully, this won't change between versions
    path = ''
    version  = '%d.%d' % (bpy.app.version[0], bpy.app.version[1])
    binary_path = os.path.dirname(bpy.app.binary_path)
    rel_config_path = os.path.join(version, rman_constants.CYCLES_SHADERS_PATH)
    if sys.platform == ("win32"):
        path = os.path.join(binary_path, rel_config_path)
    elif sys.platform == ("darwin"):                
        path = os.path.join(binary_path, '..', 'Resources', rel_config_path )
    else:
        path = os.path.join(binary_path, rel_config_path)        

    return path

def get_token_blender_file_path(p):
    # Same as filesystem_path below, but substitutes the relative Blender path
    # with the <blend_dir> token
    if not get_pref('rman_use_blend_dir_token', True):
        return filesystem_path(p)
    if p.startswith('//'):
        pout = bpy.path.abspath(p)
        if p != pout:
            regex = r"^//"
            pout = re.sub(regex, '<blend_dir>/', p, 0, re.MULTILINE)
    else:
        blend_dir = string_utils.get_var('blend_dir')
        if blend_dir == '':
            pout = p
        elif blend_dir.endswith('/'):
            pout = p.replace(blend_dir, '<blend_dir>')
        else:    
            pout = p.replace(blend_dir, '<blend_dir>/')

    return pout.replace('\\', '/')
 
def filesystem_path(p):
    #Resolve a relative Blender path to a real filesystem path
    pout = p
    if pout.startswith('//'):
        pout = bpy.path.abspath(pout)

    if os.path.isabs(pout):
        pout = os.path.realpath(pout)

    return pout.replace('\\', '/')

def get_real_path(path):
    # This looks weird in that we're simply returning filesystem_path
    # However, originally the code for these two functions were slightly different
    # There's too many places that get_real_path is called, so just leave this as is
    return filesystem_path(path)
