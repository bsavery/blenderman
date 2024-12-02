from bpy.props import PointerProperty, StringProperty, BoolProperty, \
    EnumProperty, IntProperty, FloatProperty, \
    CollectionProperty

from ...rfb_utils.envconfig_utils import envconfig
from ...rfb_utils.prefs_utils import get_pref, using_qt
from ...rfb_logger import rfb_log
from ... import rman_bl_nodes
from ...rman_bl_nodes import rman_bl_nodes_props    
from ..rman_properties_misc import RendermanLightGroup, RendermanGroup, LightLinking, RendermanUserTokenGroup, RendermanVolumeAggregate
from ..rman_properties_renderlayers import RendermanRenderLayerSettings
from ... import rman_config
from ...rman_config import RmanBasePropertyGroup

import bpy
import os
import sys

class RendermanSceneSettings(RmanBasePropertyGroup, bpy.types.PropertyGroup):

    rman_config_name: StringProperty(name='rman_config_name',
                                    default='rman_properties_scene')
    
    light_groups: CollectionProperty(type=RendermanLightGroup,
                                      name='Light Groups')
    light_groups_index: IntProperty(min=-1, default=-1)

    light_mixer_groups: CollectionProperty(type=RendermanLightGroup,
                                      name='Light Mixer Groups')
    light_mixer_groups_index: IntProperty(min=-1, default=-1)    

    light_links: CollectionProperty(type=LightLinking,
                            name='Light Links')

    def update_light_link_index(self, context):
        scene = context.scene
        rm = scene.renderman
        if rm.light_links_index == -1 or rm.light_links_index >= len(rm.light_links):
            return
        light_links = rm.light_links[rm.light_links_index]
        light_ob = light_links.light_ob
        if light_ob is None or light_ob.name not in scene.objects:
            return
                
        if context.view_layer.objects.active:
            context.view_layer.objects.active.select_set(False)
        light_ob.select_set(True)
        context.view_layer.objects.active = light_ob    

    light_links_index: IntProperty(min=-1, default=-1, update=update_light_link_index)

    def update_scene_solo_light(self, context):
        from ... import rman_render
        rr = rman_render.RmanRender.get_rman_render()        
        if self.solo_light:
            rr.rman_scene_sync.update_solo_light(context)
        else:
            rr.rman_scene_sync.update_un_solo_light(context)

    solo_light: BoolProperty(name="Solo Light", update=update_scene_solo_light, default=False)

    render_selected_objects_only: BoolProperty(
        name="Only Render Selected",
        description="Render only the selected object(s)",
        default=False)

    external_animation: BoolProperty(
        name="Render Animation",
        description="Spool Animation",
        default=False)

    # Trace Sets 
    object_groups: CollectionProperty(
        type=RendermanGroup, name="Trace Sets")
    object_groups_index: IntProperty(min=-1, default=-1)

    # Volume aggregates
    vol_aggregates: CollectionProperty(
        type=RendermanVolumeAggregate, name="Volume Aggregates")
    vol_aggregates_index: IntProperty(min=-1, default=-1)    

    # Tokens
    version_token: IntProperty(name="version", default=1, min=1)
    take_token: IntProperty(name="take", default=1, min=1)
    blend_token: StringProperty(name="", default="")
    blenddir_token: StringProperty(name="", default="")
    user_tokens: CollectionProperty(type=RendermanUserTokenGroup, name="User Tokens")
    user_tokens_index: IntProperty(min=-1, max=10, default=-1)

    # txmanager
    txmanagerData: StringProperty(name="txmanagerData", default="")

    # Renderer Status properties
    def get_platform(self):
        if sys.platform == ("win32"):
            return 'windows'
        elif sys.platform == ("darwin"):
            return 'macOS'
        else:
            return 'linux'

    def get_is_ncr_license(self):
        return envconfig().is_ncr_license

    def get_has_xpu_license(self):
        return envconfig().has_xpu_license

    def get_has_stylized_license(self):
        return envconfig().has_stylized_license

    def get_is_rman_running(self):
        from ...rman_render import RmanRender
        rman_render = RmanRender.get_rman_render()
        return rman_render.rman_running            

    def get_is_rman_interactive_running(self):
        from ...rman_render import RmanRender
        from ...rfb_utils import scene_utils       
        rman_render = RmanRender.get_rman_render()
        is_shading = scene_utils.any_areas_shading()
        return (rman_render.rman_interactive_running or is_shading)

    def get_is_rman_swatch_render_running(self):
        from ...rman_render import RmanRender
        rman_render = RmanRender.get_rman_render()
        return rman_render.rman_swatch_render_running

    def get_is_rman_viewport_rendering(self):
        from ...rman_render import RmanRender
        from ...rfb_utils import scene_utils      
        rman_render = RmanRender.get_rman_render()
        is_shading = scene_utils.any_areas_shading()
        return (rman_render.rman_is_viewport_rendering or is_shading)        

    current_platform: StringProperty(get=get_platform)
    is_ncr_license: BoolProperty(get=get_is_ncr_license)
    has_xpu_license: BoolProperty(get=get_has_xpu_license)
    has_stylized_license: BoolProperty(get=get_has_stylized_license)
    is_rman_running: BoolProperty(get=get_is_rman_running)
    is_rman_interactive_running: BoolProperty(get=get_is_rman_interactive_running)         
    is_rman_swatch_render_running: BoolProperty(get=get_is_rman_swatch_render_running)  
    is_rman_viewport_rendering:  BoolProperty(get=get_is_rman_viewport_rendering)  

    # Roz Stats Properties
    def get_roz_stats_progress(self):
        from ...rman_render import RmanRender
        rman_render = RmanRender.get_rman_render()
        return rman_render.stats_mgr._progress

    def get_roz_stats_iterations(self):
        from ...rman_render import RmanRender
        stats_mgr = RmanRender.get_rman_render().stats_mgr
        itr = stats_mgr._iterations
        maxSamples = stats_mgr._maxSamples
        if maxSamples <= 0:
            return 0.0
        frac = itr/maxSamples
        return int(frac * 100)

    roz_stats_progress: IntProperty(name='Progress', subtype='PERCENTAGE', min=0, max=100, get=get_roz_stats_progress)
    roz_stats_iterations: IntProperty(name='Iterations', subtype='PERCENTAGE', min=0, max=100, get=get_roz_stats_iterations)

    renderman_version: StringProperty(name="RenderMan Version", default='')

classes = [         
    RendermanSceneSettings
]           

def register():
    from ...rfb_utils import register_utils  

    for cls in classes:
        cls._add_properties(cls, 'rman_properties_scene')
        register_utils.rman_register_class(cls)  

    bpy.types.Scene.renderman = PointerProperty(
        type=RendermanSceneSettings, name="Renderman Scene Settings")   

def unregister():

    del bpy.types.Scene.renderman

    from ...rfb_utils import register_utils  

    register_utils.rman_unregister_classes(classes)
