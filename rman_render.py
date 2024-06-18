import time
import os
import rman
import ice
import bpy
import sys
from .rman_constants import RFB_VIEWPORT_MAX_BUCKETS, RMAN_RENDERMAN_BLUE, USE_GPU_MODULE, BLENDER_41
from .rman_scene import RmanScene
from .rman_scene_sync import RmanSceneSync
from. import rman_spool
from. import chatserver
from .rfb_logger import rfb_log
import socketserver
import threading
import subprocess
import ctypes
import numpy
import traceback

# for viewport buckets
import gpu
from gpu_extras.batch import batch_for_shader
from gpu_extras.presets import draw_texture_2d

# utils
from .rfb_utils.envconfig_utils import envconfig
from .rfb_utils import string_utils
from .rfb_utils import display_utils
from .rfb_utils import scene_utils
from .rfb_utils import transform_utils
from .rfb_utils.prefs_utils import get_pref
from .rfb_utils.timer_utils import time_this

# config
from .rman_config import __RFB_CONFIG_DICT__ as rfb_config

# roz stats
from .rman_stats import RfBStatsManager

# handlers
from .rman_handlers.rman_it_handlers import add_ipr_to_it_handlers, remove_ipr_to_it_handlers

__RMAN_RENDER__ = None
__RMAN_IT_PORT__ = -1
__BLENDER_DSPY_PLUGIN__ = None
__D_QUICKLYNOISELESS__ = None
__DRAW_THREAD__ = None
__RMAN_STATS_THREAD__ = None

# map Blender display file format
# to ice format
__BLENDER_TO_ICE_DSPY__ = {
    'TIFF': ice.constants.FMT_TIFFFLOAT, 
    'TARGA': ice.constants.FMT_TGA,
    'TARGA_RAW': ice.constants.FMT_TGA, 
    'JPEG': ice.constants.FMT_JPEG,
    'JPEG2000': ice.constants.FMT_JPEG,
    'OPEN_EXR': ice.constants.FMT_EXRFLOAT,
    'CINEON': ice.constants.FMT_CINEON,
    'PNG': ice.constants.FMT_PNG
}

# map ice format to a file extension
__ICE_EXT_MAP__ = {
    ice.constants.FMT_TIFFFLOAT: 'tif', 
    ice.constants.FMT_TGA: 'tga', 
    ice.constants.FMT_JPEG: 'jpg',
    ice.constants.FMT_EXRFLOAT: 'exr',
    ice.constants.FMT_CINEON: 'cin',
    ice.constants.FMT_PNG: 'png'
}

# map rman display to ice format
__RMAN_TO_ICE_DSPY__ = {
    'tiff': ice.constants.FMT_TIFFFLOAT, 
    'targa': ice.constants.FMT_TGA,
    'openexr': ice.constants.FMT_EXRFLOAT,    
    'png': ice.constants.FMT_PNG
}

def __update_areas__():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()

def __draw_callback__():
    # callback function for the display driver to call tag_redraw
    global __RMAN_RENDER__
    if __RMAN_RENDER__.rman_is_viewport_rendering and __RMAN_RENDER__.bl_engine:
        try:
            __RMAN_RENDER__.bl_engine.tag_redraw()
            pass
        except ReferenceError as e:
            return  False
        return True
    return False     

DRAWCALLBACK_FUNC = ctypes.CFUNCTYPE(ctypes.c_bool)
__CALLBACK_FUNC__ = DRAWCALLBACK_FUNC(__draw_callback__) 

class ItHandler(chatserver.ItBaseHandler):

    def dspyRender(self):
        global __RMAN_RENDER__
        if not __RMAN_RENDER__.is_running:                        
            bpy.ops.render.render(layer=bpy.context.view_layer.name)             

    def dspyIPR(self):
        global __RMAN_RENDER__
        if __RMAN_RENDER__.rman_interactive_running:
            crop = []
            for c in self.msg.getOpt('crop').split(' '):
                crop.append(float(c))
            if len(crop) == 4:
                __RMAN_RENDER__.rman_scene_sync.update_cropwindow(crop)

    def stopRender(self):
        global __RMAN_RENDER__
        rfb_log().debug("Stop Render Requested.")
        if __RMAN_RENDER__.rman_interactive_running:
            __RMAN_RENDER__.stop_render(stop_draw_thread=False)
        __RMAN_RENDER__.del_bl_engine() 

    def selectObjectById(self):
        global __RMAN_RENDER__

        obj_id = int(self.msg.getOpt('id', '0'))
        if obj_id < 0 or not (obj_id in __RMAN_RENDER__.rman_scene.obj_hash):
            return
        name = __RMAN_RENDER__.rman_scene.obj_hash[obj_id]
        rfb_log().debug('ID: %d Obj Name: %s' % (obj_id, name))
        obj = bpy.context.scene.objects[name]
        if obj:
            if bpy.context.view_layer.objects.active:
                bpy.context.view_layer.objects.active.select_set(False)
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj

    def selectSurfaceById(self):
        self.selectObjectById()
        window = bpy.context.window_manager.windows[0]
        if window.screen:
            for a in window.screen.areas:
                if a.type == "PROPERTIES":
                    for s in a.spaces:
                        if s.type == "PROPERTIES":
                            try:
                                s.context = "MATERIAL"
                            except:
                                pass
                            return

def start_cmd_server():

    global __RMAN_IT_PORT__

    if __RMAN_IT_PORT__ != -1:
        return __RMAN_IT_PORT__

    # zero port makes the OS pick one
    host, port = "localhost", 0

    # install handler
    chatserver.protocols['it'] = ItHandler

    # Create the server, binding to localhost on some port
    server = socketserver.TCPServer((host, port),
                                    chatserver.CommandHandler)
    ip, port = server.server_address

    thread = threading.Thread(target=server.serve_forever)

    # Exit the server thread when the main thread terminates
    thread.daemon = True
    thread.start()

    __RMAN_IT_PORT__ = port

    return __RMAN_IT_PORT__        

def draw_threading_func(db):
    refresh_rate = get_pref('rman_viewport_refresh_rate', default=0.01)
    while db.rman_is_live_rendering:
        if db.bl_viewport.shading.type != 'RENDERED':
            # if the viewport is not rendering, stop IPR
            db.del_bl_engine()
            break
        if db.xpu_slow_mode:
            if db.has_buffer_updated():
                try:
                    db.bl_engine.tag_redraw()
                    db.reset_buffer_updated()
                
                except ReferenceError as e:
                    # calling tag_redraw has failed. This might mean
                    # that there are no more view_3d areas that are shading. Try to
                    # stop IPR.
                    #rfb_log().debug("Error calling tag_redraw (%s). Aborting..." % str(e))
                    db.del_bl_engine()
                    return            
            time.sleep(refresh_rate)
        else:            
            time.sleep(1.0)

def call_stats_export_payloads(db):
    while db.rman_is_exporting:
        db.stats_mgr.update_payloads()
        time.sleep(0.1)  

def call_stats_update_payloads(db):
    while db.rman_running:
        if not db.bl_engine:
            break
        if db.rman_is_xpu and db.is_regular_rendering():
            # stop the render if we are rendering in XPU mode
            # and we've reached ~100%
            if float(db.stats_mgr._progress) > 98.0:
                db.rman_is_live_rendering = False
                break        
        db.stats_mgr.update_payloads()
        time.sleep(0.1)

def progress_cb(e, d, db):
    if not db.stats_mgr.is_connected():
        # set the progress in stats_mgr
        # we can at least get progress from the event callback
        # in case the stats listener is not connected
        db.stats_mgr._progress = int(d)
    if db.rman_is_live_rendering and int(d) == 100:
        db.rman_is_live_rendering = False

def bake_progress_cb(e, d, db): 
    if not db.stats_mgr.is_connected():
        db.stats_mgr._progress = int(d)      

def batch_progress_cb(e, d, db):
    # just tell the stats mgr to draw
    db.stats_mgr._progress = int(d)
    db.stats_mgr.draw_render_stats()    
    print("R90000 %4d%%" % int(d), file = sys.stderr )
    sys.stderr.flush()

def render_cb(e, d, db):
    if d == 0:
        rfb_log().debug("RenderMan has exited.")
        if db.rman_is_live_rendering:
            db.rman_is_live_rendering = False

def live_render_cb(e, d, db):
    if d == 0:
        db.rman_is_refining = False
    else:
        db.rman_is_refining = True

def preload_dsos(rman_render):
    """On linux there is a problem with std::call_once and
    blender, by default, being linked with a static libstdc++.
    The loader seems to not be able to get the right tls key
    for the __once_call global when libprman loads libxpu etc. By preloading
    we end up calling the proxy in the blender executable and
    that works.

    Arguments:
        rman_render (RmanRender) - instance of RmanRender where we want to store
                                   the ctypes.CDLL
    
    """    
    if sys.platform != 'linux':
        return

    plugins = [
        'lib/libxpu.so',
        'lib/plugins/impl_openvdb.so',
        'lib/plugins/d_blender.so',
        'lib/plugins/PxrSurface.so',
        'lib/plugins/PxrDisneyBsdf.so',
        'lib/libstats.so',
        'lib/plugins/d_quicklyNoiseless.so'
    ]

    tree = envconfig().rmantree    

    for plugin in plugins:
        plugin_path = os.path.join(tree, plugin)
        try:
            rman_render.preloaded_dsos.append(ctypes.CDLL(plugin_path))
        except OSError as error:
            rfb_log().debug('Failed to preload {0}: {1}'.format(plugin_path, error))

def preload_quicklynoiseless():
    global __D_QUICKLYNOISELESS__
    if __D_QUICKLYNOISELESS__ is None:
        if sys.platform != 'linux':
            return

        plugin = 'lib/plugins/d_quicklyNoiseless.so'
        tree = envconfig().rmantree    
        plugin_path = os.path.join(tree, plugin)
        try:
            __D_QUICKLYNOISELESS__ = ctypes.CDLL(plugin_path)
        except OSError as error:
            rfb_log().debug('Failed to preload {0}: {1}'.format(plugin_path, error))

class BlRenderResultHelper:
    def __init__(self, rman_render, bl_scene, dspy_dict):
        self.rman_render = rman_render
        self.bl_scene = bl_scene
        self.dspy_dict = dspy_dict
        self.width = -1
        self.height = -1
        self.size_x = -1
        self.size_y = -1
        self.bl_result = None
        self.bl_image_rps = dict()
        self.render = None
        self.render_view = None
        self.image_scale = -1
        self.write_aovs = False

    def register_passes(self):
        self.render = self.rman_render.rman_scene.bl_scene.render
        self.render_view = self.rman_render.bl_engine.active_view_get()
        self.image_scale = self.render.resolution_percentage * 0.01
        self.width = int(self.render.resolution_x * self.image_scale)
        self.height = int(self.render.resolution_y * self.image_scale)

        # register any AOV's as passes
        for i, dspy_nm in enumerate(self.dspy_dict['displays'].keys()):
            if i == 0:
                continue     

            num_channels = -1
            while num_channels == -1:
                num_channels = self.rman_render.get_numchannels(i)    

            dspy = self.dspy_dict['displays'][dspy_nm]
            dspy_chan = dspy['params']['displayChannels'][0]
            chan_info = self.dspy_dict['channels'][dspy_chan]
            chan_type = chan_info['channelType']['value']                        

            if num_channels == 4:
                self.rman_render.bl_engine.add_pass(dspy_nm, 4, 'RGBA')
            elif num_channels == 3:
                if chan_type == 'color':
                    self.rman_render.bl_engine.add_pass(dspy_nm, 3, 'RGB')
                else:
                    self.rman_render.bl_engine.add_pass(dspy_nm, 3, 'XYZ')
            elif num_channels == 2:
                self.rman_render.bl_engine.add_pass(dspy_nm, 2, 'XY')                        
            else:
                self.rman_render.bl_engine.add_pass(dspy_nm, 1, 'X')

        self.size_x = self.width
        self.size_y = self.height
        if self.render.use_border: 
            start_x = 0
            end_x = self.width
            start_y = 0
            end_y = self.height            
            if self.render.border_min_y > 0.0:
                start_y = round(self.height * self.render.border_min_y)-1
            if self.render.border_max_y > 0.0:                        
                end_y = round(self.height * self.render.border_max_y)-1 
            if self.render.border_min_x > 0.0:
                start_x = round(self.width * self.render.border_min_x)-1
            if self.render.border_max_x < 1.0:
                end_x = round(self.width * self.render.border_max_x)-2
            self.size_x = end_x - start_x
            self.size_y = end_y - start_y

        self.bl_result = self.rman_render.bl_engine.begin_result(0, 0,
                                    self.size_x,
                                    self.size_y,
                                    view=self.render_view)                        

        for i, dspy_nm in enumerate(self.dspy_dict['displays'].keys()):
            if i == 0:
                render_pass = self.bl_result.layers[0].passes.find_by_name("Combined", self.render_view)
            else:
                render_pass = self.bl_result.layers[0].passes.find_by_name(dspy_nm, self.render_view)
            self.bl_image_rps[i] = render_pass           

    def update_passes(self): 
        for i, rp in self.bl_image_rps.items():
            buffer = self.rman_render._get_buffer(self.width, self.height, image_num=i, 
                                        num_channels=rp.channels, 
                                        as_flat=False, 
                                        back_fill=False,
                                        render=self.render)
            if buffer is None:
                continue
            rp.rect = buffer

        if self.rman_render.bl_engine:
            self.rman_render.bl_engine.update_result(self.bl_result)

    def finish_passes(self):           
        if self.bl_result:
            if self.rman_render.bl_engine:
                self.rman_render.bl_engine.end_result(self.bl_result) 

            # check if we should write out the AOVs
            if self.write_aovs:
                use_ice = hasattr(ice, 'FromArray')
                for i, dspy_nm in enumerate(self.dspy_dict['displays'].keys()):
                    if dspy_nm in ['optix_denoiser_albedo', 'optix_denoiser_normal']:
                        # don't write out these displays; they're only for the opti
                        continue
                    filepath = self.dspy_dict['displays'][dspy_nm]['filePath']

                    if i == 0:
                        continue 

                        # write out the beauty with a 'raw' substring
                        toks = os.path.splitext(filepath)
                        filepath = '%s_beauty_raw.exr' % (toks[0])
                    
                    if use_ice:
                        buffer = self.rman_render._get_buffer(self.width, self.height, image_num=i, raw_buffer=True, as_flat=False)
                        if buffer is None:
                            continue

                        # use ice to save out the image
                        img = ice.FromArray(buffer)
                        img = img.Flip(False, True, False)
                        img_format = ice.constants.FMT_EXRFLOAT
                        if not display_utils.using_rman_displays():
                            img_format = __BLENDER_TO_ICE_DSPY__.get(self.bl_scene.render.image_settings.file_format, img_format)

                        # change file extension                            
                        toks = os.path.splitext(filepath)
                        ext = __ICE_EXT_MAP__.get(img_format)
                        filepath = '%s.%s' % (toks[0], ext)                            
                        img.Save(filepath, img_format)        

class RmanRender(object):
    '''
    RmanRender class. This class is responsible for starting and stopping
    the renderer. There should only be one instance of this class per session.

    Do not create an instance of this class directly. Use RmanRender.get_rman_render()
    '''

    def __init__(self):
        global __RMAN_RENDER__
        self.rictl = rman.RiCtl.Get()
        self.sgmngr = rman.SGManager.Get()
        self.rman = rman
        self.sg_scene = None
        self.rman_scene = RmanScene(rman_render=self)
        self.rman_scene_sync = RmanSceneSync(rman_render=self, rman_scene=self.rman_scene)
        self.bl_engine = None
        self.rman_running = False
        self.rman_is_exporting = False
        self.rman_interactive_running = False
        self.rman_swatch_render_running = False
        self.rman_is_live_rendering = False
        self.rman_is_viewport_rendering = False
        self.rman_is_xpu = False
        self.rman_is_refining = False
        self.rman_render_into = 'blender'
        self.rman_license_failed = False
        self.rman_license_failed_message = ''
        self.it_port = -1 
        self.rman_callbacks = dict()
        self.viewport_res_x = -1
        self.viewport_res_y = -1
        self.viewport_buckets = list()
        self._draw_viewport_buckets = False
        self.stats_mgr = RfBStatsManager(self)
        self.deleting_bl_engine = threading.Lock()
        self.stop_render_mtx = threading.Lock()
        self.bl_viewport = None
        self.xpu_slow_mode = False
        self.use_qn = False

        self._start_prman_begin()

        # hold onto this or python will unload it
        self.preloaded_dsos = list()

        preload_dsos(self)

    @classmethod
    def get_rman_render(self):
        global __RMAN_RENDER__
        if __RMAN_RENDER__ is None:
            __RMAN_RENDER__ = RmanRender()

        return __RMAN_RENDER__

    @property
    def bl_engine(self):
        return self.__bl_engine

    @bl_engine.setter
    def bl_engine(self, bl_engine):
        self.__bl_engine = bl_engine        

    def _start_prman_begin(self):
        argv = []
        argv.append("prman") 
        argv.append("-dspyserver")
        argv.append("%s" % envconfig().rman_it_path)

        woffs = ',' . join(rfb_config['woffs'])
        if woffs:
            argv.append('-woff')
            argv.append(woffs)
  
        self.rictl.PRManSystemBegin(argv)

    def __del__(self):   
        self.rictl.PRManSystemEnd()

    def _do_prman_render_begin(self):
        argv = []
        self.stats_mgr.stats_add_session()
        argv.append("-statssession")
        argv.append(self.stats_mgr.rman_stats_session_name)        
        err = self.rictl.PRManRenderBegin(argv)
        if err:
            rfb_log().error("Error initializing RenderMan")
        return err

    def _do_prman_render_end(self):
        self.rictl.PRManRenderEnd()
        self.stats_mgr.stats_remove_session()        

    def del_bl_engine(self):
        if not self.bl_engine:
            return
        if not self.deleting_bl_engine.acquire(timeout=2.0):
            return
        self.bl_engine = None
        self.deleting_bl_engine.release()
        
    def _append_render_cmd(self, render_cmd):
        return render_cmd

    def _dump_rib_(self, frame=1):
        if envconfig().getenv('RFB_DUMP_RIB'):
            rfb_log().debug("Writing to RIB...")
            rib_time_start = time.time()
            if sys.platform == ("win32"):
                self.sg_scene.Render("rib C:/tmp/blender.%04d.rib -format ascii -indent" % frame)
            else:
                self.sg_scene.Render("rib /var/tmp/blender.%04d.rib -format ascii -indent" % frame)     
            rfb_log().debug("Finished writing RIB. Time: %s" % string_utils._format_time_(time.time() - rib_time_start))            

    def _load_placeholder_image(self):   
        placeholder_image = os.path.join(envconfig().rmantree, 'lib', 'textures', 'placeholder.png')

        render = self.bl_scene.render
        image_scale = 100.0 / render.resolution_percentage
        result = self.bl_engine.begin_result(0, 0,
                                    render.resolution_x * image_scale,
                                    render.resolution_y * image_scale)
        lay = result.layers[0]
        try:
            lay.load_from_file(placeholder_image)
        except:
            pass
        self.bl_engine.end_result(result)               

    def _call_brickmake_for_selected(self):  
        rm = self.bl_scene.renderman
        ob = bpy.context.active_object
        if rm.external_animation:
            for frame in range(self.bl_scene.frame_start, self.bl_scene.frame_end + 1):        
                expanded_str = string_utils.expand_string(ob.renderman.bake_filename_attr, frame=self.bl_scene.frame_current) 
                ptc_file = '%s.ptc' % expanded_str            
                bkm_file = '%s.bkm' % expanded_str
                args = []
                args.append('%s/bin/brickmake' % envconfig().rmantree)
                args.append('-progress')
                args.append('2')
                args.append(ptc_file)
                args.append(bkm_file)
                subprocess.run(args)
        else:     
            expanded_str = string_utils.expand_string(ob.renderman.bake_filename_attr, frame=self.bl_scene.frame_current) 
            ptc_file = '%s.ptc' % expanded_str            
            bkm_file = '%s.bkm' % expanded_str
            args = []
            args.append('%s/bin/brickmake' % envconfig().rmantree)
            args.append('-progress')
            args.append('2')
            args.append(ptc_file)
            args.append(bkm_file)
            subprocess.run(args)   
        string_utils.update_frame_token(self.bl_scene.frame_current)

    def _check_prman_license(self):
        if not envconfig().is_valid_license:
            self.rman_license_failed = True
            self.rman_license_failed_message = 'Cannot find a valid RenderMan license. Aborting.'
        
        elif not envconfig().has_rps_license:
            self.rman_license_failed = True
            self.rman_license_failed_message = 'Cannot find RPS-%s license feature. Aborting.' % (envconfig().feature_version)
        else:
            # check for any available PhotoRealistic-RenderMan licenses
            status = envconfig().get_prman_license_status()
            if not(status.found and status.is_available):
                self.rman_license_failed = True
                self.rman_license_failed_message = 'No PhotoRealistic-RenderMan licenses available. Aborting.'
            elif status.is_expired():
                self.rman_license_failed = True
                self.rman_license_failed_message = 'PhotoRealistic-RenderMan licenses have expired (%s).' % str(status.exp_date)
       
        if self.rman_license_failed:
            rfb_log().error(self.rman_license_failed_message)
            if not self.rman_interactive_running:
                self.bl_engine.report({'ERROR'}, self.rman_license_failed_message)
                self.stop_render()
            return False

        return True     

    def is_regular_rendering(self):
        # return if we are doing a regular render and not interactive
        return (self.rman_running and not self.rman_interactive_running)   

    def is_ipr_to_it(self):
        return (self.rman_interactive_running and self.rman_scene.ipr_render_into == 'it')

    def do_draw_buckets(self):
        if self.use_qn:
            return False
        return get_pref('rman_viewport_draw_bucket', default=True) and self.rman_is_refining

    def do_draw_progressbar(self):
        return get_pref('rman_viewport_draw_progress') and self.stats_mgr.is_connected() and self.stats_mgr._progress < 100    

    def start_export_stats_thread(self): 
        # start an export stats thread
        global __RMAN_STATS_THREAD__       
        __RMAN_STATS_THREAD__ = threading.Thread(target=call_stats_export_payloads, args=(self, ))
        __RMAN_STATS_THREAD__.start()              

    def start_stats_thread(self): 
        # start a stats thread so we can periodically call update_payloads
        global __RMAN_STATS_THREAD__
        if __RMAN_STATS_THREAD__:
            __RMAN_STATS_THREAD__.join()
            __RMAN_STATS_THREAD__ = None
        __RMAN_STATS_THREAD__ = threading.Thread(target=call_stats_update_payloads, args=(self, ))
        if self.rman_is_xpu:
            # FIXME: for now, add a 1 second delay before starting the stats thread
            # for some reason, XPU doesn't seem to reset the progress between renders
            time.sleep(1.0)        
        self.stats_mgr.reset()
        __RMAN_STATS_THREAD__.start()         

    def reset(self):
        self.rman_license_failed = False
        self.rman_license_failed_message = ''
        self.rman_is_xpu = False
        self.rman_is_refining = False
        self.bl_viewport = None
        self.xpu_slow_mode = False
        self.use_qn = False 

    def create_scene(self, config, render_config):
        self.sg_scene = self.sgmngr.CreateScene(config, render_config, self.stats_mgr.rman_stats_session)
        return self.stats_mgr.attach()

    def start_render(self, depsgraph, for_background=False):
    
        self.reset()
        if self._do_prman_render_begin():
            return False
        self.bl_scene = depsgraph.scene_eval
        rm = self.bl_scene.renderman
        self.it_port = start_cmd_server()    
        rfb_log().info("Parsing scene...")
        time_start = time.time()

        if not self._check_prman_license():
            return False        

        self.rman_running = True
        do_persistent_data = rm.do_persistent_data
        use_compositor = scene_utils.should_use_bl_compositor(self.bl_scene)
        if for_background:
            self.rman_render_into = ''
            is_external = True
            if use_compositor:
                self.rman_render_into = 'blender'
                is_external = False
            self.rman_callbacks.clear()
            ec = rman.EventCallbacks.Get()
            ec.RegisterCallback("Render", render_cb, self)
            self.rman_callbacks["Render"] = render_cb  
            if envconfig().getenv('RFB_BATCH_NO_PROGRESS') is None:  
                ec.RegisterCallback("Progress", batch_progress_cb, self)
                self.rman_callbacks["Progress"] = batch_progress_cb               
            rman.Dspy.DisableDspyServer()       
        else:

            self.rman_render_into = rm.render_into
            is_external = False                    
            self.rman_callbacks.clear()
            ec = rman.EventCallbacks.Get()
            ec.RegisterCallback("Progress", progress_cb, self)
            self.rman_callbacks["Progress"] = progress_cb
            ec.RegisterCallback("Render", render_cb, self)
            self.rman_callbacks["Render"] = render_cb        
            
            try:
                if self.rman_render_into == 'it':
                    rman.Dspy.EnableDspyServer()
                else:
                    rman.Dspy.DisableDspyServer()
            except:
                pass

        config = rman.Types.RtParamList()
        render_config = rman.Types.RtParamList()
        rendervariant = scene_utils.get_render_variant(self.bl_scene)
        scene_utils.set_render_variant_config(self.bl_scene, config, render_config)
        self.rman_is_xpu = (rendervariant == 'xpu')

        boot_strapping = False
        bl_rr_helper = None
        if self.sg_scene is None:
            boot_strapping = True
            if not self.create_scene(config, render_config):
                self.bl_engine.report({'ERROR'}, 'Could not connect to the stats server. Aborting...' )
                self.stop_render(stop_draw_thread=False)
                self.del_bl_engine()
                return False

        # Export the scene
        try:
            bl_layer = depsgraph.view_layer
            self.rman_is_exporting = True
            self.start_export_stats_thread()
            if boot_strapping:
                # This is our first time exporting
                self.rman_scene.export_for_final_render(depsgraph, self.sg_scene, bl_layer, is_external=is_external)
            else:   
                # Scene still exists, which means we're in persistent data mode
                # Try to get the scene diffs.                    
                self.rman_scene_sync.batch_update_scene(bpy.context, depsgraph)
            self.rman_is_exporting = False
            self.stats_mgr.reset_progress()

            self._dump_rib_(self.bl_scene.frame_current)
            rfb_log().info("Finished parsing scene. Total time: %s" % string_utils._format_time_(time.time() - time_start)) 
            self.rman_is_live_rendering = True
        except Exception as e:      
            self.bl_engine.report({'ERROR'}, 'Export failed: %s' % str(e))
            rfb_log().error('Export Failed:\n%s' % traceback.format_exc())
            self.stop_render(stop_draw_thread=False)
            self.del_bl_engine()
            return False            
        
        # Start the render
        render_cmd = "prman -live"
        if self.rman_render_into == 'blender' or do_persistent_data:
            render_cmd = "prman -live"
        render_cmd = self._append_render_cmd(render_cmd)
        if boot_strapping:
            self.sg_scene.Render(render_cmd)
        if self.rman_render_into == 'blender':  
            dspy_dict = display_utils.get_dspy_dict(self.rman_scene, include_holdouts=False)
            bl_rr_helper = BlRenderResultHelper(self, self.bl_scene, dspy_dict)
            if for_background:
                bl_rr_helper.write_aovs = (use_compositor and rm.use_bl_compositor_write_aovs)
            else:
                bl_rr_helper.write_aovs = True
            bl_rr_helper.register_passes()
                              
        self.start_stats_thread()
        while self.bl_engine and not self.bl_engine.test_break() and self.rman_is_live_rendering:
            time.sleep(0.01)      
            if bl_rr_helper:
                bl_rr_helper.update_passes()
        if bl_rr_helper:
            bl_rr_helper.finish_passes()


        self.del_bl_engine()
        if not do_persistent_data:
            # If we're not in persistent data mode, stop the renderer immediately
            # If we are in persistent mode, we rely on the render_complete and
            # render_cancel handlers to stop the renderer (see rman_handlers/__init__.py)
            self.stop_render()

        return True   

    def start_external_render(self, depsgraph):  
        if self._do_prman_render_begin():
            return False        

        bl_scene = depsgraph.scene_eval
        rm = bl_scene.renderman

        self.rman_running = True
        self.rman_render_into = ''
        rib_options = ""
        if rm.rib_compression == "gzip":
            rib_options += " -compression gzip"
        rib_format = 'ascii'
        if rm.rib_format == 'binary':
            rib_format = 'binary' 
        rib_options += " -format %s" % rib_format
        if rib_format == "ascii":
            rib_options += " -indent"

        if rm.external_animation:
            original_frame = bl_scene.frame_current
            do_persistent_data = rm.do_persistent_data
            rfb_log().debug("Writing to RIB...")     
            time_start = time.time()

            if do_persistent_data:
                        
                for frame in range(bl_scene.frame_start, bl_scene.frame_end + 1, bl_scene.frame_step):
                    bl_view_layer = depsgraph.view_layer
                    config = rman.Types.RtParamList()
                    render_config = rman.Types.RtParamList()

                    if self.sg_scene is None:                        
                        self.create_scene(config, render_config)
                    try:
                        self.bl_engine.frame_set(frame, subframe=0.0)
                        rfb_log().debug("Frame: %d" % frame)
                        if frame == bl_scene.frame_start:
                            self.rman_is_exporting = True
                            self.rman_scene.export_for_final_render(depsgraph, self.sg_scene, bl_view_layer, is_external=True)
                            self.rman_is_exporting = False
                        else:
                            self.rman_scene_sync.batch_update_scene(bpy.context, depsgraph)
                            
                        rib_output = string_utils.expand_string(rm.path_rib_output, 
                                                                asFilePath=True)
                        self.sg_scene.Render("rib %s %s" % (rib_output, rib_options))                

                    except Exception as e:      
                        self.bl_engine.report({'ERROR'}, 'Export failed: %s' % str(e))
                        rfb_log().error('Export Failed:\n%s' % traceback.format_exc())
                        self.stop_render(stop_draw_thread=False)
                        self.del_bl_engine()
                        return False         

                self.sgmngr.DeleteScene(self.sg_scene) 
                self.sg_scene = None   
                self.rman_scene.reset()       
            else:     
                for frame in range(bl_scene.frame_start, bl_scene.frame_end + 1):
                    bl_view_layer = depsgraph.view_layer
                    config = rman.Types.RtParamList()
                    render_config = rman.Types.RtParamList()

                    self.create_scene(config, render_config)
                    try:
                        self.bl_engine.frame_set(frame, subframe=0.0)
                        rfb_log().debug("Frame: %d" % frame)
                        self.rman_is_exporting = True
                        self.rman_scene.export_for_final_render(depsgraph, self.sg_scene, bl_view_layer, is_external=True)
                        self.rman_is_exporting = False
                            
                        rib_output = string_utils.expand_string(rm.path_rib_output, 
                                                                asFilePath=True)
                        self.sg_scene.Render("rib %s %s" % (rib_output, rib_options))
                        self.sgmngr.DeleteScene(self.sg_scene) 
                        self.sg_scene = None   
                        self.rman_scene.reset()                     

                    except Exception as e:      
                        self.bl_engine.report({'ERROR'}, 'Export failed: %s' % str(e))
                        rfb_log().error('Export Failed:\n%s' % traceback.format_exc())
                        self.stop_render(stop_draw_thread=False)
                        self.del_bl_engine()
                        return False         

                if self.sg_scene:
                    self.sgmngr.DeleteScene(self.sg_scene) 
                    self.sg_scene = None   
                    self.rman_scene.reset()                                            
            rfb_log().info("Finished parsing scene. Total time: %s" % string_utils._format_time_(time.time() - time_start))
            self.bl_engine.frame_set(original_frame, subframe=0.0)
            

        else:
            config = rman.Types.RtParamList()
            render_config = rman.Types.RtParamList()

            if not self.create_scene(config, render_config):
                self.bl_engine.report({'ERROR'}, 'Could not connect to the stats server. Aborting...' )            
                self.stop_render(stop_draw_thread=False)
                self.del_bl_engine()
                return False
            try:
                time_start = time.time()
                        
                bl_view_layer = depsgraph.view_layer         
                rfb_log().info("Parsing scene...")      
                self.rman_is_exporting = True       
                self.rman_scene.export_for_final_render(depsgraph, self.sg_scene, bl_view_layer, is_external=True)
                self.rman_is_exporting = False
                rib_output = string_utils.expand_string(rm.path_rib_output, 
                                                        asFilePath=True)            

                rfb_log().debug("Writing to RIB: %s..." % rib_output)
                rib_time_start = time.time()
                self.sg_scene.Render("rib %s %s" % (rib_output, rib_options))     
                rfb_log().debug("Finished writing RIB. Time: %s" % string_utils._format_time_(time.time() - rib_time_start)) 
                rfb_log().info("Finished parsing scene. Total time: %s" % string_utils._format_time_(time.time() - time_start))
                self.sgmngr.DeleteScene(self.sg_scene)     
                self.sg_scene = None
                self.rman_scene.reset()                       
            except Exception as e:      
                self.bl_engine.report({'ERROR'}, 'Export failed: %s' % str(e))
                rfb_log().error('Export Failed:\n%s' % traceback.format_exc())
                self.stop_render(stop_draw_thread=False)
                self.del_bl_engine()
                return False                         

        if rm.queuing_system != 'none':
            spooler = rman_spool.RmanSpool(self, self.rman_scene, depsgraph)
            spooler.batch_render()
        self.rman_running = False
        self.del_bl_engine()
        self._do_prman_render_end()
        return True          

    def start_bake_render(self, depsgraph, for_background=False):
        self.reset()
        if self._do_prman_render_begin():
            return False        
        self.rman_running = True
        self.bl_scene = depsgraph.scene_eval
        rm = self.bl_scene.renderman
        self.it_port = start_cmd_server()    
        rfb_log().info("Parsing scene...")
        time_start = time.time()
        if not self._check_prman_license():
            return False             

        if for_background:
            is_external = True
            self.rman_callbacks.clear()
            ec = rman.EventCallbacks.Get()
            ec.RegisterCallback("Render", render_cb, self)
            self.rman_callbacks["Render"] = render_cb       
            rman.Dspy.DisableDspyServer()          
        else:
            is_external = False                    
            self.rman_callbacks.clear()
            ec = rman.EventCallbacks.Get()
            ec.RegisterCallback("Progress", bake_progress_cb, self)
            self.rman_callbacks["Progress"] = bake_progress_cb
            ec.RegisterCallback("Render", render_cb, self)
            self.rman_callbacks["Render"] = render_cb              

        self.rman_render_into = ''
        rman.Dspy.DisableDspyServer()
        config = rman.Types.RtParamList()
        render_config = rman.Types.RtParamList()

        if not self.create_scene(config, render_config):
            self.bl_engine.report({'ERROR'}, 'Could not connect to the stats server. Aborting...' )
            self.stop_render(stop_draw_thread=False)
            self.del_bl_engine()
            return False        
        try:
            bl_layer = depsgraph.view_layer
            self.rman_is_exporting = True
            self.start_export_stats_thread()
            self.rman_scene.export_for_bake_render(depsgraph, self.sg_scene, bl_layer, is_external=is_external)
            self.rman_is_exporting = False

            self._dump_rib_(self.bl_scene.frame_current)
            rfb_log().info("Finished parsing scene. Total time: %s" % string_utils._format_time_(time.time() - time_start)) 
            render_cmd = "prman -blocking"
            render_cmd = self._append_render_cmd(render_cmd)        
            self.sg_scene.Render(render_cmd)
            self.start_stats_thread()
        except Exception as e:      
            self.bl_engine.report({'ERROR'}, 'Export failed: %s' % str(e))
            rfb_log().error('Export Failed:\n%s' % traceback.format_exc())
            self.stop_render(stop_draw_thread=False)
            self.del_bl_engine()
            return False                  
        self.stop_render()
        if rm.hider_type == 'BAKE_BRICKMAP_SELECTED':
            self._call_brickmake_for_selected()
        self.del_bl_engine()
        return True        

    def start_external_bake_render(self, depsgraph):  
        if self._do_prman_render_begin():
            return False        

        bl_scene = depsgraph.scene_eval
        rm = bl_scene.renderman

        self.rman_running = True
        self.rman_render_into = ''
        rib_options = ""
        if rm.rib_compression == "gzip":
            rib_options += " -compression gzip"
        rib_format = 'ascii'
        if rm.rib_format == 'binary':
            rib_format = 'binary' 
        rib_options += " -format %s" % rib_format
        if rib_format == "ascii":
            rib_options += " -indent"

        if rm.external_animation:
            original_frame = bl_scene.frame_current
            rfb_log().debug("Writing to RIB...")             
            for frame in range(bl_scene.frame_start, bl_scene.frame_end + 1):
                bl_view_layer = depsgraph.view_layer
                config = rman.Types.RtParamList()
                render_config = rman.Types.RtParamList()

                self.create_scene(config, render_config)
                try:
                    self.bl_engine.frame_set(frame, subframe=0.0)
                    self.rman_is_exporting = True
                    self.rman_scene.export_for_bake_render(depsgraph, self.sg_scene, bl_view_layer, is_external=True)
                    self.rman_is_exporting = False
                    rib_output = string_utils.expand_string(rm.path_rib_output, 
                                                            asFilePath=True)                                                                            
                    self.sg_scene.Render("rib %s %s" % (rib_output, rib_options))
                except Exception as e:      
                    self.bl_engine.report({'ERROR'}, 'Export failed: %s' % str(e))
                    self.stop_render(stop_draw_thread=False)
                    self.del_bl_engine()
                    return False                         
                self.sgmngr.DeleteScene(self.sg_scene)  
                self.sg_scene = None
                self.rman_scene.reset()                     

            self.bl_engine.frame_set(original_frame, subframe=0.0)
            

        else:
            config = rman.Types.RtParamList()
            render_config = rman.Types.RtParamList()

            self.create_scene(config, render_config)

            try:
                time_start = time.time()
                        
                bl_view_layer = depsgraph.view_layer         
                rfb_log().info("Parsing scene...")
                self.rman_is_exporting = True             
                self.rman_scene.export_for_bake_render(depsgraph, self.sg_scene, bl_view_layer, is_external=True)
                self.rman_is_exporting = False
                rib_output = string_utils.expand_string(rm.path_rib_output, 
                                                        asFilePath=True)            

                rfb_log().debug("Writing to RIB: %s..." % rib_output)
                rib_time_start = time.time()
                self.sg_scene.Render("rib %s %s" % (rib_output, rib_options))     
                rfb_log().debug("Finished writing RIB. Time: %s" % string_utils._format_time_(time.time() - rib_time_start)) 
                rfb_log().info("Finished parsing scene. Total time: %s" % string_utils._format_time_(time.time() - time_start))
            except Exception as e:      
                self.bl_engine.report({'ERROR'}, 'Export failed: %s' % str(e))
                rfb_log().error('Export Failed:\n%s' % traceback.format_exc())
                self.stop_render(stop_draw_thread=False)
                self.del_bl_engine()
                return False                     

            self.sgmngr.DeleteScene(self.sg_scene)
            self.sg_scene = None
            self.rman_scene.reset()              

        if rm.queuing_system != 'none':
            spooler = rman_spool.RmanSpool(self, self.rman_scene, depsgraph)
            spooler.batch_render()
        self.rman_running = False
        self.del_bl_engine()
        self._do_prman_render_end()
        return True                  

    def start_interactive_render(self, context, depsgraph):

        global __DRAW_THREAD__
        self.reset()
        if self._do_prman_render_begin():
            return False        
        __update_areas__()
        self.rman_interactive_running = True
        if not self._check_prman_license():
            return False          
        self.rman_running = True            
        self.bl_scene = depsgraph.scene_eval
        rm = depsgraph.scene_eval.renderman
        self.it_port = start_cmd_server()    
        render_into_org = '' 
        self.rman_render_into = self.rman_scene.ipr_render_into
        self.bl_viewport = context.space_data
        self.use_qn = (self.bl_scene.renderman.blender_ipr_denoiser == display_utils.__RFB_DENOISER_AI__)
        
        self.rman_callbacks.clear()
        # register the blender display driver
        try:
            if self.rman_render_into == 'blender':
                # turn off dspyserver mode if we're not rendering to "it"
                self.rman_is_viewport_rendering = True    
                rman.Dspy.DisableDspyServer()             
                self.rman_callbacks.clear()
                ec = rman.EventCallbacks.Get()      
                ec.RegisterCallback("Render", live_render_cb, self)
                self.rman_callbacks["Render"] = live_render_cb                    
                self.viewport_buckets.clear()
                self._draw_viewport_buckets = True
            else:
                rman.Dspy.EnableDspyServer()
                add_ipr_to_it_handlers()
        except:
            # force rendering to 'it'
            rfb_log().error('Could not register Blender display driver. Rendering to "it".')
            render_into_org = rm.render_ipr_into
            rm.render_ipr_into = 'it'
            self.rman_render_into = 'it'
            rman.Dspy.EnableDspyServer()

        if self.use_qn:
            preload_quicklynoiseless()
            if self.rman_render_into == "blender":
                envconfig().set_qn_dspy("blender", immediate_close=True)
            else:
                # to be able to use quicklynoieless with "it", set RMAN_QN_DISPLAY to d_socket
                envconfig().set_qn_dspy("socket", immediate_close=True)  

        if not self._check_prman_license():
            return False
        time_start = time.time()      

        config = rman.Types.RtParamList()
        render_config = rman.Types.RtParamList()
        rendervariant = scene_utils.get_render_variant(self.bl_scene)
        scene_utils.set_render_variant_config(self.bl_scene, config, render_config)
        self.rman_is_xpu = (rendervariant == 'xpu')
        if self.rman_is_xpu:
            self.xpu_slow_mode = int(envconfig().getenv('RFB_XPU_SLOW_MODE', default=1))

        if not self.create_scene(config, render_config):
            self.bl_engine.report({'ERROR'}, 'Could not connect to the stats server. Aborting...' )
            self.stop_render(stop_draw_thread=False)
            self.del_bl_engine()
            return False

        try:
            self.rman_scene_sync.sg_scene = self.sg_scene
            rfb_log().info("Parsing scene...")        
            self.rman_is_exporting = True
            self.start_export_stats_thread()        
            self.rman_scene.export_for_interactive_render(context, depsgraph, self.sg_scene)
            self.rman_is_exporting = False

            self._dump_rib_(self.bl_scene.frame_current)
            rfb_log().info("Finished parsing scene. Total time: %s" % string_utils._format_time_(time.time() - time_start))      
            self.rman_is_live_rendering = True     
            render_cmd = "prman -live"   
            render_cmd = self._append_render_cmd(render_cmd)
            self.rman_scene_sync.reset() # reset the rman_scene_sync instance
            self.sg_scene.Render(render_cmd)
            self.start_stats_thread()

            rfb_log().info("RenderMan Viewport Render Started.")  

            if render_into_org != '':
                rm.render_ipr_into = render_into_org    
            
            if not self.xpu_slow_mode:
                self.set_redraw_func()
            else:
                rfb_log().debug("XPU slow mode enabled.")
            # start a thread to periodically call engine.tag_redraw()                
            __DRAW_THREAD__ = threading.Thread(target=draw_threading_func, args=(self, ))
            __DRAW_THREAD__.start()

            return True
        except Exception as e:      
            bpy.ops.renderman.printer('INVOKE_DEFAULT', level="ERROR", message='Export failed: %s' % str(e))
            rfb_log().error('Export Failed:\n%s' % traceback.format_exc())
            self.stop_render(stop_draw_thread=False)
            self.del_bl_engine()
            return False

    def start_swatch_render(self, depsgraph):
        self.reset()
        if self._do_prman_render_begin():
            return False        
        self.bl_scene = depsgraph.scene_eval

        rfb_log().debug("Parsing scene...")
        time_start = time.time()                
        self.rman_callbacks.clear()
        ec = rman.EventCallbacks.Get()
        rman.Dspy.DisableDspyServer()
        ec.RegisterCallback("Progress", progress_cb, self)
        self.rman_callbacks["Progress"] = progress_cb        
        ec.RegisterCallback("Render", render_cb, self)
        self.rman_callbacks["Render"] = render_cb        

        config = rman.Types.RtParamList()
        render_config = rman.Types.RtParamList()

        self.create_scene(config, render_config)
        self.rman_is_exporting = True
        self.rman_scene.export_for_swatch_render(depsgraph, self.sg_scene)
        self.rman_is_exporting = False

        self.rman_running = True
        self.rman_swatch_render_running = True
        self._dump_rib_()
        rfb_log().debug("Finished parsing scene. Total time: %s" % string_utils._format_time_(time.time() - time_start)) 
        if not self._check_prman_license():
            return False
        self.rman_is_live_rendering = True
        self.sg_scene.Render("prman")
        render = self.rman_scene.bl_scene.render
        render_view = self.bl_engine.active_view_get()
        image_scale = render.resolution_percentage / 100.0
        width = int(render.resolution_x * image_scale)
        height = int(render.resolution_y * image_scale)
        result = self.bl_engine.begin_result(0, 0,
                                    width,
                                    height,
                                    view=render_view)
        layer = result.layers[0].passes.find_by_name("Combined", render_view)        
        while not self.bl_engine.test_break() and self.rman_is_live_rendering:
            time.sleep(0.01)
            if layer:
                buffer = self._get_buffer(width, height, image_num=0, num_channels=4, as_flat=False)
                if buffer is None:
                    break
                else:
                    layer.rect = buffer
                    self.bl_engine.update_result(result)
        self.stop_render()              
        self.bl_engine.end_result(result)  
        self.del_bl_engine()         
       
        return True  

    def start_export_rib_selected(self, context, rib_path, export_materials=True, export_all_frames=False):

        self.rman_running = True  
        bl_scene = context.scene
        if self._do_prman_render_begin():
            return False              
        if export_all_frames:
            original_frame = bl_scene.frame_current
            rfb_log().debug("Writing to RIB...")             
            for frame in range(bl_scene.frame_start, bl_scene.frame_end + 1):        
                bl_scene.frame_set(frame, subframe=0.0)
                config = rman.Types.RtParamList()
                render_config = rman.Types.RtParamList()

                self.create_scene(config, render_config)
                try:
                    self.rman_is_exporting = True
                    self.rman_scene.export_for_rib_selection(context, self.sg_scene)
                    self.rman_is_exporting = False
                    rib_output = string_utils.expand_string(rib_path, 
                                                        asFilePath=True) 
                    cmd = 'rib ' + rib_output + ' -archive'                                                        
                    cmd = cmd + ' -bbox ' + transform_utils.get_world_bounding_box(context.selected_objects)
                    self.sg_scene.Render(cmd)
                except Exception as e:      
                    self.bl_engine.report({'ERROR'}, 'Export failed: %s' % str(e))
                    self.stop_render(stop_draw_thread=False)
                    self.del_bl_engine()
                    return False                    
                self.sgmngr.DeleteScene(self.sg_scene)     
                self.sg_scene = None
                self.rman_scene.reset()            
            bl_scene.frame_set(original_frame, subframe=0.0)    
        else:
            config = rman.Types.RtParamList()
            render_config = rman.Types.RtParamList()

            self.create_scene(config, render_config)
            try:
                self.rman_is_exporting = True
                self.rman_scene.export_for_rib_selection(context, self.sg_scene)
                self.rman_is_exporting = False
                rib_output = string_utils.expand_string(rib_path, 
                                                    asFilePath=True) 
                cmd = 'rib ' + rib_output + ' -archive'
                cmd = cmd + ' -bbox ' + transform_utils.get_world_bounding_box(context.selected_objects)
                self.sg_scene.Render(cmd)
            except Exception as e:      
                self.bl_engine.report({'ERROR'}, 'Export failed: %s' % str(e))
                rfb_log().error('Export Failed:\n%s' % traceback.format_exc())
                self.stop_render(stop_draw_thread=False)
                self.del_bl_engine()
                return False    
            self.sgmngr.DeleteScene(self.sg_scene)            
            self.sg_scene = None
            self.rman_scene.reset()  

        self.rman_running = False        
        self.del_bl_engine()
        self._do_prman_render_end()        
        return True                 

    def stop_render(self, stop_draw_thread=True):
        global __DRAW_THREAD__
        global __RMAN_STATS_THREAD__
        is_main_thread = (threading.current_thread() == threading.main_thread())
        self.reset_redraw_func()

        if is_main_thread:
            rfb_log().debug("Trying to acquire stop_render_mtx")
        if not self.stop_render_mtx.acquire(timeout=5.0):
            return
        
        if not self.rman_interactive_running and not self.rman_running:
            return

        self.rman_running = False
        self.rman_interactive_running = False  
        self.rman_swatch_render_running = False
        self.rman_is_viewport_rendering = False       
        self.rman_is_exporting = False     

        # Remove callbacks
        ec = rman.EventCallbacks.Get()
        if is_main_thread:
            rfb_log().debug("Unregister any callbacks")
        for k,v in self.rman_callbacks.items():
            ec.UnregisterCallback(k, v, self)
        self.rman_callbacks.clear()          
        remove_ipr_to_it_handlers()

        self.rman_is_live_rendering = False

        # wait for the drawing thread to finish
        # if we are told to.
        if stop_draw_thread and __DRAW_THREAD__:
            __DRAW_THREAD__.join()
            __DRAW_THREAD__ = None

        # stop retrieving stats
        if __RMAN_STATS_THREAD__:
            __RMAN_STATS_THREAD__.join()
            __RMAN_STATS_THREAD__ = None

        if is_main_thread:
            rfb_log().debug("Telling SceneGraph to stop.")    
        if self.sg_scene:    
            self.sg_scene.Stop()
            if is_main_thread:
                rfb_log().debug("Delete Scenegraph scene")
            self.sgmngr.DeleteScene(self.sg_scene)

        self._do_prman_render_end()

        self.sg_scene = None
        #self.stats_mgr.reset()
        self.rman_scene.reset()
        self.viewport_buckets.clear()
        self._draw_viewport_buckets = False                
        __update_areas__()
        self.stop_render_mtx.release()
        if is_main_thread:
            rfb_log().debug("RenderMan has Stopped.")

    def get_blender_dspy_plugin(self):
        global __BLENDER_DSPY_PLUGIN__
        if __BLENDER_DSPY_PLUGIN__ == None:
            # grab a pointer to the Blender display driver
            ext = '.so'
            if sys.platform == ("win32"):
                    ext = '.dll'
            __BLENDER_DSPY_PLUGIN__ = ctypes.CDLL(os.path.join(envconfig().rmantree, 'lib', 'plugins', 'd_blender%s' % ext))

        return __BLENDER_DSPY_PLUGIN__

    def set_redraw_func(self):
        # pass our callback function to the display driver
        dspy_plugin = self.get_blender_dspy_plugin()
        dspy_plugin.SetRedrawCallback(__CALLBACK_FUNC__)

    def reset_redraw_func(self):
        # pass our callback function to the display driver
        dspy_plugin = self.get_blender_dspy_plugin()
        dspy_plugin.SetRedrawCallback(None)        

    def has_buffer_updated(self):        
        dspy_plugin = self.get_blender_dspy_plugin()
        return dspy_plugin.HasBufferUpdated()      

    def reset_buffer_updated(self):
        dspy_plugin = self.get_blender_dspy_plugin()
        dspy_plugin.ResetBufferUpdated()        
                
    def draw_pixels(self, width, height):
        self.viewport_res_x = width
        self.viewport_res_y = height
        if self.rman_is_viewport_rendering is False:
            return
                 
        dspy_plugin = self.get_blender_dspy_plugin()

        if USE_GPU_MODULE:
            res_mult = self.rman_scene.viewport_render_res_mult
            width = int(self.viewport_res_x * res_mult)
            height = int(self.viewport_res_y * res_mult)
            buffer = self._get_buffer(width, height)
            if buffer is None:
                rfb_log().debug("Buffer is None")
                return
            pixels = gpu.types.Buffer('FLOAT', width * height * 4, buffer)

            texture = gpu.types.GPUTexture((width, height), format='RGBA32F', data=pixels)
            draw_texture_2d(texture, (0, 0), self.viewport_res_x, self.viewport_res_y)
        else:
            # (the driver will handle pixel scaling to the given viewport size)
            dspy_plugin.DrawBufferToBlender(ctypes.c_int(width), ctypes.c_int(height))            

        if BLENDER_41:
            uniform_color = 'UNIFORM_COLOR'
        else:
            uniform_color = '2D_UNIFORM_COLOR'

        if self.do_draw_buckets():
            # draw bucket indicator
            image_num = 0
            arXMin = ctypes.c_int(0)
            arXMax = ctypes.c_int(0)
            arYMin = ctypes.c_int(0)
            arYMax = ctypes.c_int(0)            
            dspy_plugin.GetActiveRegion(ctypes.c_size_t(image_num), ctypes.byref(arXMin), ctypes.byref(arXMax), ctypes.byref(arYMin), ctypes.byref(arYMax))
            if ( (arXMin.value + arXMax.value + arYMin.value + arYMax.value) > 0):
                yMin = height-1 - arYMin.value
                yMax = height-1 - arYMax.value
                xMin = arXMin.value
                xMax = arXMax.value
                if self.rman_scene.viewport_render_res_mult != 1.0:
                    # render resolution multiplier is set, we need to re-scale the bucket markers
                    scaled_width = width * self.rman_scene.viewport_render_res_mult
                    xMin = int(width * ((arXMin.value) / (scaled_width)))
                    xMax = int(width * ((arXMax.value) / (scaled_width)))

                    scaled_height = height * self.rman_scene.viewport_render_res_mult
                    yMin = height-1 - int(height * ((arYMin.value) / (scaled_height)))
                    yMax = height-1 - int(height * ((arYMax.value) / (scaled_height)))
                
                vertices = []
                c1 = (xMin, yMin)
                c2 = (xMax, yMin)
                c3 = (xMax, yMax)
                c4 = (xMin, yMax)
                vertices.append(c1)
                vertices.append(c2)
                vertices.append(c3)
                vertices.append(c4)
                indices = [(0, 1), (1, 2), (2,3), (3, 0)]

                # we've reach our max buckets, pop the oldest one off the list
                if len(self.viewport_buckets) > RFB_VIEWPORT_MAX_BUCKETS:
                    self.viewport_buckets.pop()
                self.viewport_buckets.insert(0,[vertices, indices])
                
            bucket_color = get_pref('rman_viewport_bucket_color', default=RMAN_RENDERMAN_BLUE)

            # draw from newest to oldest
            shader = gpu.shader.from_builtin(uniform_color)            
            shader.bind()
            shader.uniform_float("color", bucket_color)                   
            for v, i in (self.viewport_buckets):        
                batch = batch_for_shader(shader, 'LINES', {"pos": v}, indices=i)                 
                batch.draw(shader)   

        # draw progress bar at the bottom of the viewport
        if self.do_draw_progressbar():
            progress = self.stats_mgr._progress / 100.0 
            shader = gpu.shader.from_builtin(uniform_color)
            shader.bind()                
            progress_color = get_pref('rman_viewport_progress_color', default=RMAN_RENDERMAN_BLUE) 
            shader.uniform_float("color", progress_color)                       
            vtx = [(0, 1), (width * progress, 1)]
            batch = batch_for_shader(shader, 'LINES', {"pos": vtx})
            batch.draw(shader)   

    def get_numchannels(self, image_num):
        dspy_plugin = self.get_blender_dspy_plugin()
        num_channels = dspy_plugin.GetNumberOfChannels(ctypes.c_size_t(image_num))
        return num_channels

    def _get_buffer(self, width, height, image_num=0, num_channels=-1, raw_buffer=False, back_fill=True, as_flat=True, render=None):
        dspy_plugin = self.get_blender_dspy_plugin()
        if num_channels == -1:
            num_channels = self.get_numchannels(image_num)
            if num_channels > 4 or num_channels < 0:
                rfb_log().debug("Could not get buffer. Incorrect number of channels: %d" % num_channels)
                return None

        # code reference: https://asiffer.github.io/posts/numpy/
        RMAN_NUMPY_POINTER = numpy.ctypeslib.ndpointer(dtype=numpy.float32, 
                                      ndim=1,
                                      flags="C")
        f = dspy_plugin.GetFloatFramebuffer
        f.argtypes = [ctypes.c_size_t, ctypes.c_size_t, RMAN_NUMPY_POINTER]

        try:
            array_size = width * height * num_channels
            buffer = numpy.zeros(array_size, dtype=numpy.float32)
            f(ctypes.c_size_t(image_num), buffer.size, buffer)

            if raw_buffer:
                if not as_flat:
                    buffer.shape = (height, width, num_channels)
                return buffer

            if as_flat:
                if (num_channels == 4) or not back_fill:
                    return buffer
                else:
                    p_pos = 0
                    pixels = numpy.ones(width*height*4, dtype=numpy.float32)
                    for y in range(0, height):
                        i = (width * y * num_channels)
                        
                        for x in range(0, width):
                            j = i + (num_channels * x)
                            if num_channels == 3:
                                pixels[p_pos:p_pos+3] = buffer[j:j+3]
                            elif num_channels == 2:
                                pixels[p_pos:p_pos+2] = buffer[j:j+2]
                            elif num_channels == 1:
                                pixels[p_pos] = buffer[j]
                                pixels[p_pos+1] = buffer[j]
                                pixels[p_pos+2] = buffer[j]
                            p_pos += 4                                
                    return pixels
            else:
                if render and render.use_border:
                    start_x = 0
                    end_x = width
                    start_y = 0
                    end_y = height

                
                    if render.border_min_y > 0.0:
                        start_y = round(height * render.border_min_y)-1
                    if render.border_max_y > 0.0:                        
                        end_y = round(height * render.border_max_y)-1 
                    if render.border_min_x > 0.0:
                        start_x = round(width * render.border_min_x)-1
                    if render.border_max_x < 1.0:
                        end_x = round(width * render.border_max_x)-2

                    # return the buffer as a list of lists
                    if back_fill:
                        pixels = numpy.ones( ((end_x-start_x)*(end_y-start_y), 4), dtype=numpy.float32 )
                    else:
                        pixels = numpy.zeros( ((end_x-start_x)*(end_y-start_y), num_channels) )
                    p_pos = 0
                    for y in range(start_y, end_y):
                        i = (width * y * num_channels)

                        for x in range(start_x, end_x):
                            j = i + (num_channels * x)
                            if (num_channels==4) or not back_fill:
                                # just slice
                                pixels[p_pos] = buffer[j:j+num_channels]
                            else:
                                pixels[p_pos][0] = buffer[j]                             
                                if num_channels == 3:
                                    pixels[p_pos][1] = buffer[j+1]
                                    pixels[p_pos][2] = buffer[j+2]
                                elif num_channels == 2:
                                    pixels[p_pos][1] = buffer[j+1]
                                elif num_channels == 1:
                                    pixels[p_pos][1] = buffer[j]
                                    pixels[p_pos][2] = buffer[j]

                            p_pos += 1

                    return pixels
                else:
                    buffer.shape = (-1, num_channels)
                    return buffer
        except Exception as e:
            rfb_log().debug("Could not get buffer: %s" % str(e))
            return None                                     

    @time_this
    def save_viewport_snapshot(self):
        if not self.rman_is_viewport_rendering:
            return

        res_mult = self.rman_scene.viewport_render_res_mult
        width = int(self.viewport_res_x * res_mult)
        height = int(self.viewport_res_y * res_mult)

        nm = 'rman_viewport_snapshot_<F4>_%d.exr' % len(bpy.data.images)
        nm = string_utils.expand_string(nm)
        if hasattr(ice, 'FromArray'):
            buffer = self._get_buffer(width, height, as_flat=False, raw_buffer=True)  
            if buffer is None:
                rfb_log().error("Could not save snapshot.")
                return                  
            img = ice.FromArray(buffer)
            img = img.Flip(False, True, False)
            filepath = os.path.join(bpy.app.tempdir, nm)
            img.Save(filepath, ice.constants.FMT_EXRFLOAT)
            bpy.ops.image.open('EXEC_DEFAULT', filepath=filepath)
            bpy.data.images[-1].pack()
            os.remove(filepath)
        else:
            buffer = self._get_buffer(width, height)
            if buffer is None:
                rfb_log().error("Could not save snapshot.")
                return

            img = bpy.data.images.new(nm, width, height, float_buffer=True, alpha=True) 
            if isinstance(buffer, numpy.ndarray):
                buffer = buffer.tolist()               
            img.pixels.foreach_set(buffer)
            img.update()            
       
    def update_scene(self, context, depsgraph):
        if self.rman_interactive_running:
            self.rman_scene_sync.update_scene(context, depsgraph)

    def update_view(self, context, depsgraph):
        if self.rman_interactive_running:
            self.rman_scene_sync.update_view(context, depsgraph)
