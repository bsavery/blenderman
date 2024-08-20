# ##### BEGIN MIT LICENSE BLOCK #####
#
# Copyright (c) 2015 - 2021 Pixar
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
import addon_utils

from .rfb_logger import rfb_log
from .rfb_utils.envconfig_utils import envconfig

bl_info = {
    "name": "RenderMan For Blender",
    "author": "Pixar",
    "version": (26, 2, 0),
    "blender": (2, 93, 0),
    "location": "Render Properties > Render Engine > RenderMan",
    "description": "RenderMan 26 integration",
    "doc_url": "https://rmanwiki.pixar.com/display/RFB",
    'warning': '',
    "category": "Render"}

__RMAN_ADDON_LOADED__ = False

def load_node_arrange():
    '''
    Make sure that the node_arrange addon is enabled
    '''

    if addon_utils.check('node_arrange')[1] is False:
        addon_utils.enable('node_arrange')

def load_addon():
    global __RMAN_ADDON_LOADED__

    if envconfig():
        from . import rman_config
        from . import rman_presets
        from . import rman_operators
        from . import rman_ui
        from . import rman_bl_nodes
        from . import rman_properties
        from . import rman_handlers
        from . import rfb_translations
        from . import rman_stats
        from . import rman_engine

        rman_config.register()
        rman_properties.pre_register() 
        rman_presets.register()        
        rman_operators.register()
        rman_bl_nodes.register()       
        rman_properties.register()   
        rman_ui.register()      
        rman_handlers.register()
        rfb_translations.register()
        rman_stats.register()
        rman_engine.register()

        __RMAN_ADDON_LOADED__ = True

    else:
        rfb_log().error(
            "Error loading addon.  Correct RMANTREE setting in addon preferences.")

def register():    
    from . import preferences
    preferences.register()
    load_addon()
    load_node_arrange()

def unregister():
    global __RMAN_ADDON_LOADED__

    from . import preferences
    preferences.unregister()

    if __RMAN_ADDON_LOADED__:
        rman_presets.unregister()
        rman_handlers.unregister()
        rman_bl_nodes.unregister()    
        rman_ui.unregister()
        rman_properties.unregister()
        rman_operators.unregister()    
        rfb_translations.unregister()
        rman_stats.unregister()
        rman_engine.unregister()
