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

import os
import os.path
import bpy
import time
import traceback
from ..util.util import get_addon_prefs, init_env, user_path, get_path_list_converted

PRMAN_INITED = False


def init_prman():
    ''' import prman and mark it as inited.  This is important to make sure we are not
    making calls from multiple threads to ri '''
    global prman
    import prman
    global PRMAN_INITED 
    PRMAN_INITED = True


class RenderManager(object):
    """ RenderManager takes care of all the actual work for rib gen,
    and has hooks to launch processes"""
    def __init__(self, scene, engine=None, is_interactive=False, external_render=False):
        ''' Instantiate the Render Manager and set the variables needed for it '''
        self.scene = scene
        self.engine = engine
        # set the display driver
        if external_render:
            self.display_driver = scene.renderman.display_driver
        elif engine and engine.is_preview:
            self.display_driver = 'openexr'
        else:
            self.display_driver = 'openexr'
            #self.display_driver = scene.renderman.render_into

        # pass addon prefs to init_envs
        init_env()

        self.is_preview = self.engine.is_preview if engine else False
        self.rm = scene.renderman
        self.initialize_paths(scene)
        self.external_render = external_render
        self.is_interactive = is_interactive
        self.is_interactive_ready = False
        self.options = []
        # check if prman is imported
        if not PRMAN_INITED:
            init_prman()
        self.ri = None

    def __del__(self):
        ''' Delete and cleanup prman if it's inited.  This is so there isn't threading issues.'''
        if self.is_interactive and self.is_prman_running():
            self.ri.EditWorldEnd()
            self.ri.End()
        if PRMAN_INITED:
            prman.Cleanup()

    def reset(self, scene):
        ''' Reset prman and reinstantiate it.'''
        if PRMAN_INITED:
            prman.Cleanup()
        self.scene = scene

    def write_rib(self):
        ''' set up ri context and Write out scene rib '''
        try:
            prman.Init()
            self.ri = prman.Ri()
            
            if self.is_preview:
                self.gen_preview_rib()
            else:
                self.gen_rib()
            del self.ri
            prman.Cleanup()

        except Exception as err:
            self.ri = None
            prman.Cleanup()
            self.engine.report({'ERROR'}, 'Rib gen error: ' + traceback.format_exc())
    

    def initialize_paths(self, scene):
        ''' Expands all the output paths for this pass and makes dirs for outputs '''
        rm = self.rm
        addon_prefs = get_addon_prefs()

        self.paths = {}
        out = user_path(addon_prefs.out, scene=scene)
        self.paths['scene_output_dir'] = out

        self.paths['frame_rib'] = user_path(addon_prefs.path_rib_output, scene=scene, out=out)
        self.paths['texture_output'] = user_path(addon_prefs.path_texture_output, scene=scene,
                                                 out=out)

        if not os.path.exists(self.paths['scene_output_dir']):
            os.makedirs(self.paths['scene_output_dir'])

        self.paths['main_image'] = user_path(addon_prefs.path_main_image, out=out,
                                             scene=scene, display_driver=self.display_driver)
        self.paths['aov_image_templ'] = user_path(addon_prefs.path_aov_image, scene=scene,
                                                  display_driver=self.display_driver, out=out)
        self.paths['shader'] = [out] + get_path_list_converted(rm, 'shader')
        self.paths['texture'] = [self.paths['texture_output']]

        if self.is_preview:
            previewdir = os.path.join(self.paths['scene_output_dir'], "preview")
            self.paths['frame_rib'] = os.path.join(previewdir, "preview.rib")
            self.paths['main_image'] = os.path.join(previewdir, "preview.tif")
            self.paths['scene_output_dir'] = os.path.dirname(self.paths['frame_rib'])
            if not os.path.exists(previewdir):
                os.mkdir(previewdir)

        static_archive_dir = os.path.dirname(user_path(addon_prefs.path_object_archive_static,
                                                       scene=scene, out=out))
        frame_archive_dir = os.path.dirname(user_path(addon_prefs.path_object_archive_animated,
                                                      scene=scene, out=out))

        self.paths['static_archives'] = static_archive_dir
        self.paths['frame_archives'] = frame_archive_dir

        if not os.path.exists(self.paths['static_archives']):
            os.makedirs(self.paths['static_archives'])
        if not os.path.exists(self.paths['frame_archives']):
            os.makedirs(self.paths['frame_archives'])
        self.paths['archive'] = os.path.dirname(static_archive_dir)

    def update_frame_num(self, num):
        ''' When rendering an animation we may need to use the same rpass to output multiple
            frames.  This will reset the frame number and reset paths'''
        self.scene.frame_set(num)
        self.initialize_paths(self.scene)

    def preview_render(self, engine):
        ''' For preview renders, simply render and load exr to blender swatch '''
        pass

    def render(self, engine):
        ''' Start the PRMan render process, and if rendering to Blender, setup display driver server 
            Also reports status
        '''
        pass

    def is_prman_running(self):
        ''' Uses Rix interfaces to get progress on running IPR or render '''
        return prman.RicGetProgress() < 100

    def gen_rib(self):
        ''' Does all the caching nescessary for generating a render rib, first caches motion blur 
            items, then outputs geometry caches, and also the frame rib.
        '''
        time_start = time.time()
        rib_options = {"string format": "ascii", "string asciistyle": "indented,wide"}
        self.ri.Option("rib", rib_options)

        # cache motion first and write out data archives
        self.rm.cache_motion(self.ri, self)
        for ob in self.scene.objects:
            items = ob.renderman.get_data_items()
            if items:
                for data in items:
                    data_rm = data.renderman
                    try:
                        archive_filename = data_rm.get_archive_filename(paths=self.paths, ob=ob)
                        if archive_filename:
                            self.ri.Begin(archive_filename)
                            data_rm.to_rib(self.ri, ob=ob, scene=self.scene)
                            self.ri.End()
                    except:
                        self.engine.report({'ERROR'}, 
                            'Rib gen error object %s data %s: ' % (ob.name, data.name) + 
                            traceback.format_exc())
        self.rm.clear_motion()

        self.ri.Begin(self.paths['frame_rib'])
        self.rm.to_rib(self.ri, paths=self.paths)
        self.ri.End()

        self.rm.clear_motion()

        if self.engine:
            self.engine.report({"INFO"}, "RIB generation took %s" % str(time.time() - time_start))

    def gen_preview_rib(self):
        ''' generates a preview rib file '''
        self.ri.Begin(self.paths['frame_rib'])
        self.rm.to_rib(self.ri, preview=True)
        self.ri.End()

    