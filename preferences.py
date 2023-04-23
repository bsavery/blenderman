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

from enum import Enum
import bpy
import sys
import os
from bpy.types import AddonPreferences
from bpy.props import CollectionProperty, BoolProperty, StringProperty, FloatProperty
from bpy.props import IntProperty, PointerProperty, EnumProperty, FloatVectorProperty

from .rfb_utils import envconfig_utils
from .rfb_utils import register_utils
from . import rfb_logger
from . import rfb_icons

# Defaults for our preferences.
# Append to this dictionary whenever a new preference is added.
__DEFAULTS__ = {
    'rman_xpu_gpu_selection': -1,
    'rman_xpu_device': 'CPU',
    'rman_xpu_cpu_devices': [],
    'draw_panel_icon': True,
    'path_fallback_textures_path': os.path.join('<OUT>', 'textures'),        
    'path_fallback_textures_path_always': False,            
    'rman_txmanager_keep_extension': True,
    'rman_txmanager_workers': 2,       
    'rman_txmanager_tex_extensions': 'tex tx txr ptx ptex ies',
    'rman_scene_version_padding': 3,
    'rman_scene_take_padding': 2,      
    'rman_scene_version_increment': 'MANUALLY',
    'rman_scene_take_increment': 'MANUALLY',
    'rman_logging_level': 'WARNING',     
    'rman_logging_file': '',       
    'rman_do_preview_renders': False,
    'rman_preview_renders_minSamples': 0,
    'rman_preview_renders_maxSamples': 1,
    'rman_preview_renders_pixelVariance': 0.15,
    'rman_viewport_draw_lights_textured': True,
    'rman_viewport_lights_draw_wireframe': True,
    'rman_viewport_draw_bucket': True,
    'rman_viewport_draw_progress': True,
    'rman_viewport_crop_color': (0.0, 0.498, 1.0, 1.0),       
    'rman_viewport_bucket_color': (0.0, 0.498, 1.0, 1.0), 
    'rman_viewport_progress_color': (0.0, 0.498, 1.0, 1.0),        
    'rman_editor': '',
    'rman_invert_light_linking': False,
    'rman_show_cycles_convert': False,
    'rman_render_nurbs_as_mesh': True,
    'rman_emit_default_params': False,
    'rman_show_advanced_params': False,      
    'rman_config_dir': "",
    'rman_viewport_refresh_rate': 0.01,
    'rman_solo_collapse_nodes': True,
    'rman_use_blend_dir_token': True,          
    'rman_ui_framework': "NATIVE",
    'rpbConfigFile': '',
    'rpbUserLibraries': [],
    'rpbSelectedLibrary': '',
    'rpbSelectedCategory': '',
    'rpbSelectedPreset': '',
    'rpbStorageMode': 0,
    'rpbStorageKey': '',
    'rpbStoragePath': '',
    'rpbConvertToTex': 1,
    'rpbSwatchSize': 64,
    'rman_roz_logLevel': '3',     
    'rman_roz_grpcServer': True,  
    'rman_roz_webSocketServer': False,         
    'rman_roz_webSocketServer_Port': 0, 
    'rman_roz_stats_print_level': '1',
    'rman_enhance_zoom_factor': 5,
    'rman_parent_lightfilter': False,
    'rman_tractor_hostname': 'tractor-engine',
    'rman_tractor_port': 80,
    'rman_tractor_local_user': True,
    'rman_tractor_user': '',
    'rman_tractor_priority': 1.0,
    'rman_tractor_service': 'PixarRender',
    'rman_tractor_envkeys': '',
    'rman_tractor_after': '',
    'rman_tractor_crews': '',
    'rman_tractor_tier': '',
    'rman_tractor_projects': '',
    'rman_tractor_comment': '',
    'rman_tractor_metadata': '',
    'rman_tractor_whendone': '',
    'rman_tractor_whenerror': '',
    'rman_tractor_whenalways': '',
    'rman_tractor_dirmaps': []
}

class RendermanPreferencePath(bpy.types.PropertyGroup):
    path: StringProperty(name="", subtype='DIR_PATH')

class PRMAN_OT_add_dirmap(bpy.types.Operator):
    bl_idname = "renderman.add_dirmap"
    bl_label = "Add Dirmap"
    bl_description = "Add a new dirmap"
    
    def execute(self, context):
        addon = context.preferences.addons[__package__]
        prefs = addon.preferences
        dirmap = prefs.rman_tractor_dirmaps.add()
        
        return {'FINISHED'}
    
class PRMAN_OT_remove_dirmap(bpy.types.Operator):
    bl_idname = "renderman.remove_dirmap"
    bl_label = "Remove Dirmap"
    bl_description = "Remove a dirmap"
    
    index: IntProperty(
        default=0
    )

    def execute(self, context):
        addon = context.preferences.addons[__package__]
        prefs = addon.preferences        
        if self.properties.index < len(prefs.rman_tractor_dirmaps):
            prefs.rman_tractor_dirmaps.remove(self.properties.index)

        return {'FINISHED'}    

class RendermanDirMap(bpy.types.PropertyGroup):
    from_path: StringProperty(name="From", description="")
    to_path: StringProperty(name="To", description="")
    zone: EnumProperty(
        name="Zone",
        description="The zone that this dirmap should apply to. UNC is for Windows; NFS is for linux and macOS.",
        default="NFS",
        items=[('NFS', 'NFS', ''),
               ('UNC', 'UNC', '')
               ]
    )

class RendermanDeviceDesc(bpy.types.PropertyGroup):
    name: StringProperty(name="", default="")
    id: IntProperty(default=-1)
    version_major: IntProperty(default=0)
    version_minor: IntProperty(default=0)
    use: BoolProperty(name="Use", default=False)

def fix_path(self, key):
    if key in self and self[key].startswith('//'): 
        self[key] = os.path.abspath(bpy.path.abspath(self[key]))     

class RendermanPreferences(AddonPreferences):
    bl_idname = __package__
        
    def find_xpu_cpu_devices(self):
        # for now, there's only one CPU
        if len(self.rman_xpu_cpu_devices) < 1:
            device = self.rman_xpu_cpu_devices.add()
            device.name = "CPU 0"
            device.id = 0
            device.use = True

    def find_xpu_gpu_devices(self):
        try:
            import rman

            count = rman.pxrcore.GetGpgpuCount(rman.pxrcore.k_cuda)
            gpu_device_names = list()

            # try and add ones that we don't know about
            for i in range(count):
                desc = rman.pxrcore.GpgpuDescriptor()
                rman.pxrcore.GetGpgpuDescriptor(rman.pxrcore.k_cuda, i, desc)
                gpu_device_names.append(desc.name)

                found = False
                for device in self.rman_xpu_gpu_devices:
                    if device.name == desc.name:
                        found = True
                        break

                if not found:
                    device = self.rman_xpu_gpu_devices.add()
                    device.name = desc.name
                    device.version_major = desc.major
                    device.version_minor = desc.minor
                    device.id = i
                    if len(self.rman_xpu_gpu_devices) == 1:
                        # always use the first one, if this is our first time adding
                        # gpus
                        device.use = True

            # now, try and remove devices that no longer exist
            name_list = [device.name for device in self.rman_xpu_gpu_devices]
            for nm in name_list:
                if nm not in gpu_device_names:
                    self.rman_xpu_gpu_devices.remove(self.rman_xpu_gpu_devices.find(nm))

        except Exception as e:
            rfb_logger.rfb_log().debug("Exception when getting GPU devices: %s" % str(e))
            pass

    def find_xpu_devices(self):
        self.find_xpu_cpu_devices()
        self.find_xpu_gpu_devices()


    # find the renderman options installed
    def find_installed_rendermans(self, context):
        options = [('NEWEST', 'Newest Version Installed',
                    'Automatically updates when new version installed. NB: If an RMANTREE environment variable is set, this will always take precedence.')]
        for vers, path in envconfig_utils.get_installed_rendermans():
            options.append((path, vers, path))
        return options

    rman_xpu_cpu_devices: bpy.props.CollectionProperty(type=RendermanDeviceDesc)
    rman_xpu_gpu_devices: bpy.props.CollectionProperty(type=RendermanDeviceDesc)

    def fill_gpu_devices(self, context):
        items = []
        items.append(('-1', 'None', ''))
        for device in self.rman_xpu_gpu_devices:
            items.append(('%d' % device.id, '%s (%d.%d)' % (device.name, device.version_major, device.version_minor), ''))
                  
        return items

    rman_xpu_gpu_selection: EnumProperty(name="GPU Device",
                                        items=fill_gpu_devices
                                        )

    rman_xpu_device: EnumProperty(name="Devices",
                                description="Select category",
                                items=[
                                    ("CPU", "CPU", ""),
                                    ("GPU", "GPU", "")
                                ]
                                )
    def reload_rmantree(self, context):
        envconfig_utils.reload_envconfig()

    rmantree_choice: EnumProperty(
        name='RenderMan Version to use',
        description='Leaving as "Newest" will automatically update when you install a new RenderMan version',
        # default='NEWEST',
        items=find_installed_rendermans,
        update=reload_rmantree        
    )

    rmantree_method: EnumProperty(
        name='RenderMan Location',
        description='''How RenderMan should be detected.  Most users should leave to "Detect". 
                    Users should restart Blender after making a change.
                    ''',
        items=[('ENV', 'Get From RMANTREE Environment Variable',
                'This will use the RMANTREE set in the enviornment variables'),
                ('DETECT', 'Choose From Installed', 
                '''This will scan for installed RenderMan locations to choose from.'''),
                ('MANUAL', 'Set Manually', 'Manually set the RenderMan installation (for expert users)')],
        default='ENV',
        update=reload_rmantree)

    path_rmantree: StringProperty(
        name="RMANTREE Path",
        description="Path to RenderMan Pro Server installation folder",
        subtype='DIR_PATH',
        default='',
        update=lambda s,c: fix_path(s, 'path_rmantree')
    )

    draw_panel_icon: BoolProperty(
        name="Draw Panel Icon",
        description="Draw an icon on RenderMan Panels",
        default=True)

    path_fallback_textures_path: StringProperty(
        name="Fallback Texture Path",
        description="Fallback path for textures, when the current directory is not writable",
        subtype='FILE_PATH',
        default=os.path.join('<OUT>', 'textures'),
        update=lambda s,c: fix_path(s, 'path_rmantree')
    )        

    path_fallback_textures_path_always: BoolProperty(
        name="Always Fallback",
        description="Always use the fallback texture path regardless",
        default=False)            

    rman_txmanager_keep_extension: BoolProperty(
        name='Keep original extension',
        default=True,
        description="If on, keep the original extension of the input image."
    )  

    rman_txmanager_workers: IntProperty(
        name='Number of processes',
        description="Number of txmake processes to launch in parallel. Default to 2 (assuming a typical 4-cores computer). You should only increase this if you have more than 8 physical cores.",
        default=2,
        min=1,max=32
    )  

    rman_txmanager_tex_extensions: StringProperty(
        name='Texture Extensions',
        description="Any file with one of these extensions will not be converted by the texture manager and used as-is. Entries should be space-delimited.",
        default='tex tx txr ptx ptex ies',
    )      

    rman_scene_version_padding: IntProperty(
        name="Version Padding",
        description="The number of zeros to pad the version token",
        default=3,
        min=1, max=4
    )
    rman_scene_take_padding: IntProperty(
        name="Take Padding",
        description="The number of zeros to pad the take token",
        default=2,
        min=1, max=4
    )    

    rman_scene_version_increment: EnumProperty(
        name="Increment Version",
        description="The version number can be set to automatically increment each time you render",
        items=[
            ('MANUALLY', 'Manually', ''),
            ('RENDER', 'On Render', ''),
            ('BATCH RENDER', 'On Batch Render', '')
        ],
        default='MANUALLY'
    )

    rman_scene_take_increment: EnumProperty(
        name="Increment Take",
        description="The take number can be set to automatically increment each time you render",
        items=[
            ('MANUALLY', 'Manually', ''),
            ('RENDER', 'On Render', ''),
            ('BATCH RENDER', 'On Batch Render', '')
        ],        
        default='MANUALLY'
    )    

    def update_rman_logging_level(self, context):
        level = rfb_logger.__LOG_LEVELS__[self.rman_logging_level]
        rfb_logger.set_logger_level(level)

    rman_logging_level: EnumProperty(
        name='Logging Level',
        description='''Log level verbosity. Advanced: Setting the RFB_LOG_LEVEL environment variable will override this preference. Requires a restart.
                    ''',
        items=[('CRITICAL', 'Critical', ''),
                ('ERROR', 'Error', ''),
                ('WARNING', 'Warning', ''),
                ('INFO', 'Info', ''),
                ('VERBOSE', 'Verbose', ''),
                ('DEBUG', 'Debug', ''),
        ],
        default='WARNING',
        update=update_rman_logging_level)

    rman_logging_file: StringProperty(
        name='Logging File',
        description='''A file to write logging to. This will always write at DEBUG level. Setting the RFB_LOG_FILE environment variable will override this preference. Requires a restart.''',
        default = '',
        subtype='FILE_PATH',
        update=lambda s,c: fix_path(s, 'rman_logging_file')
    )

    rman_do_preview_renders: BoolProperty(
        name="Render Previews",
        description="Enable rendering of material previews. This is considered a WIP.",
        default=False)

    rman_preview_renders_minSamples: IntProperty(
        name="Preview Min Samples",
        description="Minimum samples for preview renders",
        default=0,
        min=0, soft_max=4,
    )
    rman_preview_renders_maxSamples: IntProperty(
        name="Preview Max Samples",
        description="Maximum samples for preview renders",
        default=1,
        min=1, soft_max=4,
    )  
    rman_preview_renders_pixelVariance: FloatProperty(
        name="Pixel Variance",
        description="Maximum samples for preview renders",
        default=0.15,
        min=0.001, soft_max=0.5,
    )        

    rman_viewport_draw_lights_textured: BoolProperty(
        name="Draw Textured Lights",    
        description="Draw textured versions for RenderMan lights. This is automatically turned off when in IPR.",
        default=True
    )         

    rman_viewport_lights_draw_wireframe: BoolProperty(
        name="Draw Light Wireframes",    
        description="Draw the wireframe for RenderMan lights. Note, we still draw the wireframe when the light is selected, even if this is off.",
        default=True
    )             

    rman_viewport_draw_bucket: BoolProperty(
        name="Draw Bucket Marker",    
        description="Unchechk this if you do not want the bucket markers in the viewport",
        default=True
    )

    rman_viewport_draw_progress: BoolProperty(
        name="Draw Progress Bar",    
        description="Unchechk this if you do not want the progress bar in the viewport",
        default=True
    )    

    rman_viewport_crop_color: FloatVectorProperty(
        name="CropWindow Color",
        description="Color of the cropwindow border in the viewport when in IPR.",
        default=(0.0, 0.498, 1.0, 1.0), 
        size=4,
        subtype="COLOR")     

    rman_viewport_bucket_color: FloatVectorProperty(
        name="Bucket Marker Color",
        description="Color of the bucket markers in the viewport when in IPR.",
        default=(0.0, 0.498, 1.0, 1.0), 
        size=4,
        subtype="COLOR")  

    rman_viewport_progress_color: FloatVectorProperty(
        name="Progress Bar Color",
        description="Color of the progress bar in the viewport when in IPR.",
        default=(0.0, 0.498, 1.0, 1.0), 
        size=4,
        subtype="COLOR")                

    rman_editor: StringProperty(
        name="Editor",
        subtype='FILE_PATH',
        description="Text editor excutable you want to use to view RIB.",
        default="",
        update=lambda s,c: fix_path(s, 'rman_editor')
    )

    rman_invert_light_linking: BoolProperty(
        name="Invert Light Linking",
        default=False,
        description="Invert the behavior of light linking (only applies if UI framework is set to Native). Only objects linked to the light in the light linking editor will be illuminated. Changing this requires an IPR restart.",
    )    

    rman_show_cycles_convert: BoolProperty(
        name="Convert Cycles Nodes",
        default=False,
        description="Add convert Cycles Networks buttons to the material properties panel. N.B.: This isn't guaranteed to fully convert Cycles networks successfully. Also, because of differences in OSL implementations, converted networks may cause stability problems when rendering."

    )

    rman_render_nurbs_as_mesh: BoolProperty(
        name="NURBS as Mesh",
        default=True,
        description="Render all NURBS surfaces as meshes."
    )

    rman_emit_default_params: BoolProperty(
        name="Emit Default Params",
        default=False,
        description="Controls whether or not parameters that are not changed from their defaults should be emitted to RenderMan. Turning this on is only useful for debugging purposes."
    )

    rman_show_advanced_params: BoolProperty(
        name="Show Advanced",
        default=False,
        description="Show advanced preferences"
    )

    rman_config_dir: StringProperty(
        name="Config Directory",
        subtype='DIR_PATH',
        description="Path to JSON configuration files. Requires a restart.",
        default="",
        update=lambda s,c: fix_path(s, 'rman_config_dir')
    )    

    rman_viewport_refresh_rate: FloatProperty(
        name="Viewport Refresh Rate",
        description="The number of seconds to wait before the viewport refreshes during IPR.",
        default=0.01,
        precision=6,
        min=0.000001,
        max=0.1
    )    

    rman_solo_collapse_nodes: BoolProperty(
        name="Collapse Non-Solo Nodes",
        default=True,
        description="If on, when soloing a node, all other nodes in the network will be collapsed."
    )    

    rman_use_blend_dir_token: BoolProperty(
        name="Use blend_dir token",
        default=True,
        description="For relative file paths, we add a <blend_dir> token to the path to represent the path where the current blend file is in. Turning this off will use the real path instead"
    )        

    rman_ui_framework: EnumProperty(
        name="UI Framework",
        default="NATIVE",
        description="Which UI framework to use. Qt is currently experimental and requires PySide2 to be installed. Changes to this requires a restart.",
        items=[('NATIVE', 'Native', ''),
                ("QT", "Qt", '')
            ]
    )

    rman_show_wip_qt: BoolProperty(
        name="Show WIP UI",
        default=False,
        description="Show WIP Qt UI. Not all of our UI have been completely converted to Qt. Turn this option off to go back to the native version, even if UI Framework is set to Qt."
    )

    # For the preset browser
    rpbConfigFile: StringProperty(default='')
    rpbUserLibraries: CollectionProperty(type=RendermanPreferencePath)
    rpbSelectedLibrary: StringProperty(default='')
    rpbSelectedCategory: StringProperty(default='')
    rpbSelectedPreset: StringProperty(default='')
    rpbStorageMode: IntProperty(default=0)
    rpbStorageKey: StringProperty(default='')
    rpbStoragePath: StringProperty(default='')
    rpbConvertToTex: IntProperty(default=1)    
    rpbSwatchSize: IntProperty(default=64)

    def update_stats_config(self, context):
        bpy.ops.renderman.update_stats_config('INVOKE_DEFAULT')

    # For roz stats
    rman_roz_logLevel: EnumProperty(
                        name="Log Level",
                        default='3',        
                        items=[('0', 'None', ''),
                                ('1', 'Severe', ''),
                                ('2', 'Error', ''),
                                ('3', 'Warning', ''),
                                ('4', 'Info', ''),
                                ('5', 'Debug', ''),
                            ],
                        description="Change the logging level for the live statistics system.",
                        update=update_stats_config
                        )
    rman_roz_grpcServer: BoolProperty(name="Send Stats to 'it' HUD", default=True, 
                                        description="(DEPRECATED) Turn this off if you don't want stats to be sent to the 'it' HUD.",
                                        update=update_stats_config)
    rman_roz_webSocketServer: BoolProperty(name="Enable Live Stats", default=False, 
                                        description="(DEPRECATED) Turning this off will disable the live statistics system in RfB.",
                                        update=update_stats_config)
    rman_roz_liveStatsEnabled: BoolProperty(name="Enable Live Stats", default=True, 
                                        description="Turning this off will disable the live statistics system in RfB.",
                                        update=update_stats_config)                                        
    rman_roz_webSocketServer_Port: IntProperty(name="Port", default=0, 
                                        min=0,
                                        description="Port number of the live stats server to use. Setting to 0 will randomly select an open port.",
                                        update=update_stats_config)      

    rman_roz_stats_print_level: EnumProperty(
                    name="Stats Print Level",
                    default = '1',
                    items=[('0', 'None', ''),
                            ('1', 'Basic', ''),
                            ('2', 'Moderate', ''),
                            ('3', 'Most', ''),
                            ('4', 'All', ''),
                        ],
                    description="How much live stats to print",
                    update=update_stats_config
    )

    rman_enhance_zoom_factor: IntProperty(
        name="Enhance Zoom Factor",
        description="How much to zoom in when using the Enhance operator",
        default=5,
        min=2,
        max=10
    )    

    rman_parent_lightfilter: BoolProperty(
        name="Parent Filter to Light",
        default=False,
        description="If on, and a light is selected, attaching a light filter will parent the light filter to the selected light."
    )                      

    # Tractor preferences
    rman_tractor_hostname: StringProperty(
        name="Hostname",
        default="tractor-engine",
        description="Hostname of the Tractor engine to use to submit batch render jobs"
    )               

    rman_tractor_port: IntProperty(
        name="Port",
        default=80,
        description="Port number that the Tractor engine is listening on"
    )

    rman_tractor_local_user: BoolProperty(
        name="Use Local User",
        default=True,
        description="Use the current logged in user to submit the tractor job"
    )

    rman_tractor_user: StringProperty(
        name="Username",
        default="",
        description="Username to use to submit the tractor job"
    )

    rman_tractor_priority: FloatProperty(
        name="Priority",
        default=1.0,
        description="Priority of your job"
    )

    rman_tractor_service: StringProperty(
        name="Service",
        default="PixarRender",
        description="Service keys for your job"
    )

    rman_tractor_envkeys: StringProperty(
        name="Environment Keys",
        default="",
        description="Multiple keys can be specified and should be space separated.",
    )

    rman_tractor_after: StringProperty(
        name="After",
        default="",
        description="Delay start of job processing until given time\nFormat: MONTH/DAY HOUR:MINUTES\nEx: 11/24 13:45"
    )

    rman_tractor_crews: StringProperty(
        name="Crews",
        default="",
        description="List of crews. See 'Crews' in the Tractor documentation",
    )

    rman_tractor_tier: StringProperty(
        name="Tier",
        default="",
        description="Dispatching tier that the job belongs to. See 'Scheduling Modes' in the Tractor documentation"
    )

    rman_tractor_projects: StringProperty(
        name="Projects",
        default="",
        description="Dispatching tier that the job belongs to. See 'Limits Configuration' in the Tractor documentation"
    )

    rman_tractor_comment: StringProperty(
        name="Comments",
        default="",
        description="Additional comment about the job."
    )

    rman_tractor_metadata: StringProperty(
        name="Meta Data",
        default="",
        description= "Meta data to add to the job."
    )

    rman_tractor_whendone: StringProperty(
        name='When Done Command',
        default='',
        description="Command to run when job completes withour error."
    )

    rman_tractor_whenerror: StringProperty(
        name='When Error Command', 
        default='',
        description="Command to run if there is an error executing the job."
    )

    rman_tractor_whenalways: StringProperty( 
        name='When Always Command',
        default='',
        description="Command to run regardless if job completes with or without errors."
    )

    rman_tractor_dirmaps: bpy.props.CollectionProperty(type=RendermanDirMap)

    def draw_xpu_devices(self, context, layout):
        if self.rman_xpu_device == 'CPU':
            device = self.rman_xpu_cpu_devices[0]
            layout.prop(device, 'use', text='%s' % device.name)
        else:
            if len(self.rman_xpu_gpu_devices) < 1:
                layout.label(text="No compatible GPU devices found.", icon='INFO')
            else:
                '''
                ## TODO: For when XPU can support multiple gpu devices...
                for device in self.rman_xpu_gpu_devices:
                    layout.prop(device, 'use', text='%s (%d.%d)' % (device.name, device.version_major, device.version_minor))
                '''

                # Else, we only can select one GPU
                layout.prop(self, 'rman_xpu_gpu_selection')

                

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False        
        layout = self.layout

        rman_r_icon = rfb_icons.get_icon("rman_blender")

        row = layout.row()
        row.use_property_split = False
        col = row.column()
        col.prop(self, 'rmantree_method')

         # Check if Blender is using newer version of python than 3.9. This can be removed when renderman supports python 3.10.
        if sys.version_info[1] > 9:
            row = layout.row()
            row.alert = True
            row.label(text='This version of Blender is not supported. We support Blender versions up to 3.0.x.', icon='ERROR')
            return

        if self.rmantree_method == 'MANUAL':
            col.prop(self, "path_rmantree")
            if envconfig_utils.envconfig() is None:
                row = layout.row()
                row.alert = True
                row.label(text='Error in RMANTREE. Reload addon to reset.', icon='ERROR')
                return
        else:
            if self.rmantree_method == 'DETECT':  
                col.prop(self, 'rmantree_choice')
            if envconfig_utils.envconfig() is None:
                row = layout.row()
                row.alert = True
                row.label(text='Error in RMANTREE. Reload addon to reset.', icon='ERROR')
                return                
            col.label(text="RMANTREE: %s" % envconfig_utils.envconfig().rmantree)    

        # Behavior Prefs
        row = layout.row()
        row.label(text='Behavior', icon_value=rman_r_icon.icon_id)
        row = layout.row()
        col = row.column()
        #col.prop(self, 'rman_do_preview_renders')  
        col.prop(self, 'rman_render_nurbs_as_mesh')
        col.prop(self, 'rman_show_cycles_convert')     
        col.prop(self, 'rman_emit_default_params')    
        col.prop(self, 'rman_invert_light_linking')
        col.prop(self, 'rman_solo_collapse_nodes')
        col.prop(self, 'rman_use_blend_dir_token')
        col.prop(self, 'rman_parent_lightfilter')
        col.prop(self, 'rman_editor')      
        col.prop(self, 'rman_enhance_zoom_factor')

        # XPU Prefs
        if sys.platform != ("darwin") and envconfig_utils.envconfig().has_xpu_license:
            row = layout.row()
            row.label(text='XPU', icon_value=rman_r_icon.icon_id)
            row = layout.row()
            row.use_property_split = False
            row.prop(self, 'rman_xpu_device', expand=True)
            row = layout.row()
            row.use_property_split = False
            self.find_xpu_devices()
            col = row.column()      
            box = col.box()  
            self.draw_xpu_devices(context, box)

        # Workspace
        row = layout.row()
        row.label(text='Workspace', icon_value=rman_r_icon.icon_id)
        row = layout.row()
        col = row.column()
        col.prop(self, "rman_scene_version_padding")
        col.prop(self, "rman_scene_take_padding")
        col.prop(self, "rman_scene_version_increment")
        col.prop(self, "rman_scene_take_increment")

        # TxManager
        row = layout.row()
        row.label(text='Texture Manager', icon_value=rman_r_icon.icon_id)
        row = layout.row()
        col = row.column()
        col.prop(self, 'path_fallback_textures_path')
        col.prop(self, 'path_fallback_textures_path_always')
        col.prop(self, "rman_txmanager_workers")
        col.prop(self, "rman_txmanager_keep_extension")
        col.prop(self, "rman_txmanager_tex_extensions")

        # UI Prefs
        row = layout.row()
        row.label(text='UI', icon_value=rman_r_icon.icon_id)
        row = layout.row()
        col = row.column()
        col.prop(self, 'rman_viewport_draw_lights_textured')
        col.prop(self, 'rman_viewport_lights_draw_wireframe')
        col.prop(self, 'rman_viewport_crop_color')
        col.prop(self, 'rman_viewport_draw_bucket')
        if self.rman_viewport_draw_bucket:
            col.prop(self, 'rman_viewport_bucket_color')   
        col.prop(self, 'rman_viewport_draw_progress')
        if self.rman_viewport_draw_progress:
            col.prop(self, 'rman_viewport_progress_color')                
        col.prop(self, 'draw_panel_icon')
        col.prop(self, 'rman_ui_framework')
        if self.rman_ui_framework == 'QT':
            col.prop(self, 'rman_show_wip_qt')

        # Logging
        row = layout.row()
        row.label(text='Logging', icon_value=rman_r_icon.icon_id)
        row = layout.row()
        col = row.column()
        col.prop(self, 'rman_logging_level')
        col.prop(self, 'rman_logging_file')

        # Batch Rendering
        row = layout.row()
        row.label(text='Batch Rendering', icon_value=rman_r_icon.icon_id)
        row = layout.row()
        col = row.column()        
        col.prop(self, 'rman_tractor_hostname')
        col.prop(self, 'rman_tractor_port')
        col.prop(self, 'rman_tractor_local_user')
        if not self.rman_tractor_local_user:
            col.prop(self, 'rman_tractor_user')
        col.prop(self, 'rman_tractor_priority')
        col.prop(self, 'rman_tractor_service')
        col.prop(self, 'rman_tractor_envkeys')
        col.prop(self, 'rman_tractor_after')
        col.prop(self, 'rman_tractor_crews')
        col.prop(self, 'rman_tractor_tier')
        col.prop(self, 'rman_tractor_projects')
        col.prop(self, 'rman_tractor_comment')
        col.prop(self, 'rman_tractor_metadata')
        col.prop(self, 'rman_tractor_whendone')
        col.prop(self, 'rman_tractor_whenerror')
        col.prop(self, 'rman_tractor_whenalways')

        row = layout.row()
        row.label(text='Directory Maps')
        row = layout.row()
        col = row.column()   
        col.operator('renderman.add_dirmap', text='+')
        for i, dirmap in enumerate(self.rman_tractor_dirmaps):
            dirmap_row = col.row()
            dirmap_row.use_property_split = False
            dirmap_row.use_property_decorate = True             
            dirmap_row.prop(dirmap, 'from_path')
            dirmap_row.prop(dirmap, 'to_path')
            dirmap_row.prop(dirmap, 'zone')
            op = dirmap_row.operator('renderman.remove_dirmap', text='X')
            op.index = i

        # Advanced
        row = layout.row()      
        row.use_property_split = False
        row.use_property_decorate = True          
        row.prop(self, 'rman_show_advanced_params')              

        row = layout.row()
        col = row.column() 
        ui_open = getattr(self, 'rman_show_advanced_params')
        if ui_open:
            col.label(text='Live Statistics', icon_value=rman_r_icon.icon_id)
            row = col.row()
            col = row.column()
            col.prop(self, 'rman_roz_logLevel')  
            col.prop(self, 'rman_roz_liveStatsEnabled')    

            if self.rman_roz_liveStatsEnabled:     
                try:
                    from .rman_stats import RfBStatsManager
                    stats_mgr = RfBStatsManager.get_stats_manager()
                    split = layout.split()
                    row = split.row()
                    col.prop(self, 'rman_roz_webSocketServer_Port', slider=False)
                    col = row.column()
                    col.label(text='')
                    col = row.column()
                    if stats_mgr:
                        if stats_mgr.is_connected():
                            col.operator('renderman.disconnect_stats_render')
                        else:
                            col.operator('renderman.attach_stats_render')
                        col.label(text='              Web Socket Status: %s' % stats_mgr.get_status())   
           
                except Exception as e:
                    rfb_logger.rfb_log().debug("Could not import rman_stats: %s" % str(e))
                    pass                         

            row = layout.row()
            col = row.column()
            col.label(text='Other', icon_value=rman_r_icon.icon_id)

            col.prop(self, 'rman_viewport_refresh_rate')  
            col.prop(self, 'rman_config_dir')   
            if self.rman_do_preview_renders:
                col.prop(self, 'rman_preview_renders_minSamples')
                col.prop(self, 'rman_preview_renders_maxSamples')
                col.prop(self, 'rman_preview_renders_pixelVariance') 

classes = [
    RendermanPreferencePath,
    RendermanDeviceDesc,
    PRMAN_OT_add_dirmap,
    PRMAN_OT_remove_dirmap,
    RendermanDirMap,
    RendermanPreferences
]

def register():
    register_utils.rman_register_classes(classes)
    
def unregister():
    register_utils.rman_unregister_classes(classes)

