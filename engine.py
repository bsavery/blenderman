# ##### BEGIN MIT LICENSE BLOCK #####
#
# Copyright (c) 2015 - 2017 Pixar
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
import bpy_types
import math
import os
import time
import subprocess
from subprocess import Popen, PIPE
import mathutils
from mathutils import Matrix, Vector, Quaternion
import re
import traceback
import glob

from . import bl_info

from .util import bpy_newer_257
from .util import BlenderVersionError
from .util import rib, rib_path, rib_ob_bounds
from .util import make_frame_path
from .util import init_exporter_env
from .util import get_sequence_path
from .util import user_path
from .util import get_path_list_converted, set_path
from .util import path_list_convert, guess_rmantree, set_pythonpath,\
    set_rmantree
from .util import get_real_path, find_it_path
from .util import debug
from .util import get_Selected_Objects
from .util import get_addon_prefs
from random import randint
import sys
from bpy.app.handlers import persistent

# global dictionaries
from .export import write_rib, write_preview_rib, get_texture_list,\
    issue_shader_edits, get_texture_list_preview, issue_transform_edits,\
    interactive_initial_rib, update_light_link, delete_light,\
    reset_light_illum, solo_light, mute_lights, issue_light_vis, update_crop_window

from .nodes import get_tex_file_name

addon_version = bl_info['version']

prman_inited = False
ipr_handle = None


def init_prman():
    # set pythonpath before importing prman
    set_rmantree(guess_rmantree())
    set_pythonpath(os.path.join(guess_rmantree(), 'bin'))
    it_dir = os.path.dirname(find_it_path()) if find_it_path() else None
    set_path([os.path.join(guess_rmantree(), 'bin'), it_dir])
    global prman
    import prman
    prman_inited = True

ipr = None


def init():
    pass


def is_ipr_running():
    if ipr is not None and ipr.is_interactive and ipr.is_interactive_ready:
        if ipr.is_prman_running():
            return True
        else:
            # shutdown IPR
            ipr.is_interactive_ready = False
            bpy.ops.lighting.start_interactive('INVOKE_DEFAULT')
            return False
    else:
        return False


def create(engine, data, scene, region=0, space_data=0, region_data=0):
    # TODO add support for regions (rerendering)
    engine.render_pass = RPass(scene, preview_render=engine.is_preview)


def free(engine):
    if hasattr(engine, 'render_pass'):
        if engine.render_pass.is_interactive and engine.render_pass.is_prman_running():
            engine.render_pass.end_interactive()
        if engine.render_pass:
            del engine.render_pass


def render(engine):
    if hasattr(engine, 'render_pass') and engine.render_pass.do_render:
        if engine.is_preview:
            if engine.render_pass.rib_done:
                engine.render_pass.preview_render(engine)
        else:
            engine.render_pass.render(engine)


def reset(engine, data, scene):
    del engine.render_pass.ri
    if prman:
        prman.Cleanup()
    engine.render_pass.ri = prman.Ri()
    engine.render_pass.set_scene(scene)
    engine.render_pass.update_frame_num(scene.frame_current)

def update(engine, data, scene):
    engine.render_pass.update_time = int(time.time())
    if engine.is_preview:
        try:
            engine.render_pass.gen_preview_rib()
        except Exception as err:
            engine.report({'ERROR'}, 'Rib gen error: ' +
                          traceback.format_exc())
    else:
        try:
            engine.render_pass.gen_rib(engine=engine)
        except Exception as err:
            engine.report({'ERROR'}, 'Rib gen error: ' +
                          traceback.format_exc())


# assumes you have already set the scene
def start_interactive(engine):
    engine.render_pass.start_interactive()


def update_interactive(engine, context):
    engine.render_pass.issue_edits(context)


# update the timestamp on an object
# note that this only logs the active object.  So it might not work say
# if a script updates objects.  We would need to iterate through all objects
@persistent
def update_timestamp(scene):
    active = scene.objects.active
    if active and (active.is_updated_data or (active.data and active.data.is_updated)):
        # mark object for update
        now = int(time.time())
        active.renderman.update_timestamp = now


def format_seconds_to_hhmmss(seconds):
    hours = seconds // (60 * 60)
    seconds %= (60 * 60)
    minutes = seconds // 60
    seconds %= 60
    return "%02i:%02i:%02i" % (hours, minutes, seconds)


class RPass:

    def __init__(self, scene, interactive=False, external_render=False, preview_render=False, bake=False):
        self.rib_done = False
        self.scene = scene
        self.output_files = []
        # set the display driver
        if external_render:
            self.display_driver = scene.renderman.display_driver
        elif preview_render:
            self.display_driver = 'openexr'
        else:
            self.display_driver = 'it' if scene.renderman.render_into == 'it' else 'openexr'

        # pass addon prefs to init_envs
        addon = bpy.context.user_preferences.addons[__name__.split('.')[0]]
        init_exporter_env(addon.preferences)
        self.initialize_paths(scene)
        self.rm = scene.renderman
        self.external_render = external_render
        self.bake=bake
        self.do_render = (scene.renderman.output_action == 'EXPORT_RENDER')
        self.is_interactive = interactive
        self.is_interactive_ready = False
        self.options = []
        # check if prman is imported
        if not prman_inited:
            init_prman()

        if interactive:
            prman.Init(['-woff', 'A57001'])  # need to disable for interactive
        else:
            prman.Init()
        self.ri = prman.Ri()
        self.edit_num = 0
        self.update_time = None
        self.last_edit_mat = None

    def __del__(self):

        if self.is_interactive and self.is_prman_running():
            self.ri.EditWorldEnd()
            self.ri.End()
        del self.ri
        if prman:
            prman.Cleanup()

    def initialize_paths(self, scene):
        rm = scene.renderman
        self.paths = {}
        self.paths['rman_binary'] = rm.path_renderer
        self.paths['path_texture_optimiser'] = rm.path_texture_optimiser
        self.paths['rmantree'] = rm.path_rmantree

        self.paths['rib_output'] = user_path(rm.path_rib_output, scene=scene)
        self.paths['texture_output'] = user_path(rm.path_texture_output,
                                                 scene=scene)
        rib_dir = os.path.dirname(self.paths['rib_output'])
        self.paths['export_dir'] = user_path(rib_dir, scene=scene)

        if not os.path.exists(self.paths['export_dir']):
            os.makedirs(self.paths['export_dir'])

        addon_prefs = get_addon_prefs()
        self.paths['render_output'] = user_path(addon_prefs.path_display_driver_image,
                                                scene=scene, display_driver=self.display_driver)
        self.paths['aov_output'] = user_path(
            addon_prefs.path_aov_image, scene=scene, display_driver=self.display_driver)
        debug("info", self.paths)
        self.paths['shader'] = [user_path(rm.out_dir, scene=scene)] +\
            get_path_list_converted(rm, 'shader')
        self.paths['rixplugin'] = get_path_list_converted(rm, 'rixplugin')
        self.paths['texture'] = [self.paths['texture_output']]

        temp_archive_name = rm.path_object_archive_static
        static_archive_dir = os.path.dirname(user_path(temp_archive_name,
                                                       scene=scene))
        temp_archive_name = rm.path_object_archive_animated
        frame_archive_dir = os.path.dirname(user_path(temp_archive_name,
                                                      scene=scene))
        self.paths['static_archives'] = static_archive_dir
        self.paths['frame_archives'] = frame_archive_dir

        if not os.path.exists(self.paths['static_archives']):
            os.makedirs(self.paths['static_archives'])
        if not os.path.exists(self.paths['frame_archives']):
            os.makedirs(self.paths['frame_archives'])
        self.paths['archive'] = os.path.dirname(static_archive_dir)

    def update_frame_num(self, num):
        self.scene.frame_set(num)
        self.paths['rib_output'] = user_path(self.scene.renderman.path_rib_output,
                                             scene=self.scene)
        addon_prefs = get_addon_prefs()
        self.paths['render_output'] = user_path(addon_prefs.path_display_driver_image,
                                                scene=self.scene, display_driver=self.display_driver)
        self.paths['aov_output'] = user_path(
            addon_prefs.path_aov_image, scene=self.scene, display_driver=self.display_driver)
        temp_archive_name = self.scene.renderman.path_object_archive_animated
        frame_archive_dir = os.path.dirname(user_path(temp_archive_name,
                                                      scene=self.scene))
        self.paths['frame_archives'] = frame_archive_dir
        if not os.path.exists(self.paths['frame_archives']):
            os.makedirs(self.paths['frame_archives'])

    def preview_render(self, engine):
        render_output = self.paths['render_output']
        images_dir = os.path.split(render_output)[0]
        if not os.path.exists(images_dir):
            os.makedirs(images_dir)
        if os.path.exists(render_output):
            try:
                os.remove(render_output)  # so as not to load the old file
            except:
                debug("error", "Unable to remove previous render",
                      render_output)

        def update_image():
            render = self.scene.render
            image_scale = 100.0 / render.resolution_percentage
            result = engine.begin_result(0, 0,
                                         render.resolution_x * image_scale,
                                         render.resolution_y * image_scale)
            lay = result.layers[0]
            # possible the image wont load early on.
            try:
                lay.load_from_file(render_output)
            except:
                pass
            engine.end_result(result)

        # create command and start process
        options = self.options
        prman_executable = os.path.join(self.paths['rmantree'], 'bin',
                                        self.paths['rman_binary'])
        cmd = [prman_executable] + options + ["-t:%d" % self.rm.threads] + \
            [self.paths['rib_output']]
        cdir = os.path.dirname(self.paths['rib_output'])
        environ = os.environ.copy()
        environ['RMANTREE'] = self.paths['rmantree']

        # Launch the command to begin rendering.
        try:
            process = subprocess.Popen(cmd, cwd=cdir, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, env=environ)
            process.communicate()
            update_image()
        except:
            engine.report({"ERROR"},
                          "Problem launching RenderMan from %s." % prman_executable)
            isProblem = True

    def get_denoise_names(self):
        base, ext = self.paths['render_output'].rsplit('.', 1)
        # denoise data has the name .denoise.exr
        return (base + '.variance.' + 'exr', base + '.filtered.' + 'exr')

    def render(self, engine):
        DELAY = 1
        render_output = self.paths['render_output']
        aov_output = self.paths['aov_output']
        cdir = os.path.dirname(self.paths['rib_output'])
        update_frequency = 10 if not self.rm.do_denoise else 60

        images_dir = os.path.split(render_output)[0]
        aov_dir = os.path.split(aov_output)[0]
        if not os.path.exists(images_dir):
            os.makedirs(images_dir)
        if not os.path.exists(aov_dir):
            os.makedirs(aov_dir)
        if os.path.exists(render_output):
            try:
                os.remove(render_output)  # so as not to load the old file
            except:
                debug("error", "Unable to remove previous render",
                      render_output)

        if self.display_driver == 'it':
            it_path = find_it_path()
            if not it_path:
                engine.report({"ERROR"},
                              "Could not find 'it'. Install RenderMan Studio \
                              or use a different display driver.")
            else:
                environ = os.environ.copy()
                subprocess.Popen([it_path], env=environ, shell=True)

        def update_image():
            render = self.scene.render
            image_scale = 100.0 / render.resolution_percentage
            result = engine.begin_result(0, 0,
                                         render.resolution_x * image_scale,
                                         render.resolution_y * image_scale)
            lay = result.layers[0]
            # possible the image wont load early on.
            try:
                lay.load_from_file(render_output)
            except:
                pass
            engine.end_result(result)

        # create command and start process
        options = self.options + ['-Progress'] + ['-cwd', cdir] + \
            ['-woff', 'N02003']
        prman_executable = 'prman'
        if self.display_driver in ['openexr', 'tiff']:
            options = options + ['-checkpoint',
                                 "%ds" % update_frequency]
        cmd = [prman_executable] + options + ["-t:%d" % self.rm.threads] + \
            [self.paths['rib_output']]

        environ = os.environ.copy()
        environ['RMANTREE'] = self.paths['rmantree']
        environ['PATH'] = os.path.join(
            self.paths['rmantree'], 'bin') + os.pathsep + environ['PATH']

        # Launch the command to begin rendering.
        try:
            process = subprocess.Popen(cmd, cwd=cdir, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, env=environ)
            isProblem = False
        except:
            engine.report({"ERROR"},
                          "Problem launching RenderMan from %s." % prman_executable)
            isProblem = True

        if not isProblem:
            # Wait for the file to be created.
            t1 = time.time()
            s = '.'
            while not os.path.exists(render_output) and \
                    self.display_driver not in ['it']:
                engine.update_stats("", ("RenderMan: Starting Rendering" + s))
                if engine.test_break():
                    try:
                        process.kill()
                    except:
                        pass
                    break

                if process.poll() != None:
                    engine.report({"ERROR"}, "RenderMan: Exited")
                    break

                time.sleep(DELAY)
                s = s + '.'

            if os.path.exists(render_output) or self.display_driver in ['it']:

                if self.display_driver not in ['it']:
                    prev_mod_time = os.path.getmtime(render_output)
                engine.update_stats("", ("RenderMan: Rendering."))
                # Update while rendering

                while True:
                    line = process.stderr.readline()
                    if line and "R90000" in str(line):
                        # these come in as bytes
                        line = line.decode('utf8')
                        perc = line.rstrip(os.linesep).split()[1].strip("%%")
                        engine.update_progress(float(perc) / 100.0)
                    else:
                        if line and "ERROR" in str(line):
                            engine.report({"ERROR"}, "RenderMan: %s " %
                                          line.decode('utf8'))
                        elif line and "WARNING" in str(line):
                            engine.report({"WARNING"}, "RenderMan: %s " %
                                          line.decode('utf8'))
                        elif line and "SEVERE" in str(line):
                            engine.report({"ERROR"}, "RenderMan: %s " %
                                          line.decode('utf8'))

                    if process.poll() is not None:
                        if self.display_driver not in ['it']:
                            update_image()
                        t2 = time.time()
                        engine.report({"INFO"}, "RenderMan: Done Rendering." +
                                      " (elapsed time: " +
                                      format_seconds_to_hhmmss(t2 - t1) + ")")

                        break

                    # user exit
                    if engine.test_break():
                        try:
                            process.kill()
                            isProblem = True
                            engine.report({"INFO"},
                                          "RenderMan: Rendering Cancelled.")
                        except:
                            pass
                        break

                    # check if the file updated
                    if self.display_driver not in ['it']:
                        new_mod_time = os.path.getmtime(render_output)

                        if new_mod_time != prev_mod_time:
                            update_image()
                            prev_mod_time = new_mod_time

            else:
                debug("error", "Export path [" + render_output +
                      "] does not exist.")
        else:
            debug("error",
                  "Problem launching RenderMan from %s." % prman_executable)

        # launch the denoise process if turned on
        if self.rm.do_denoise and not isProblem:
            base, ext = render_output.rsplit('.', 1)
            denoise_options = []
            # denoise data has the name .denoise.exr
            denoise_options = ["-t%d" %
                               self.rm.threads] if self.rm.threads != 0 else []
            denoise_data, filtered_name = self.get_denoise_names()
            if os.path.exists(denoise_data):
                try:
                    # denoise to _filtered
                    cmd = [os.path.join(self.paths['rmantree'], 'bin',
                                        'denoise')] + denoise_options + [denoise_data]

                    engine.update_stats("", ("RenderMan: Denoising image"))
                    t1 = time.time()
                    process = subprocess.Popen(cmd, cwd=images_dir,
                                               stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE,
                                               env=environ)
                    process.wait()
                    t2 = time.time()
                    if os.path.exists(filtered_name):
                        engine.report({"INFO"}, "RenderMan: Done Denoising." +
                                      " (elapsed time: " +
                                      format_seconds_to_hhmmss(t2 - t1) + ")")
                        if self.display_driver != 'it':
                            render = self.scene.render
                            image_scale = 100.0 / \
                                self.scene.render.resolution_percentage
                            result = engine.begin_result(0, 0,
                                                         render.resolution_x *
                                                         image_scale,
                                                         render.resolution_y *
                                                         image_scale)
                            lay = result.layers[0]
                            # possible the image wont load early on.
                            try:
                                lay.load_from_file(filtered_name)
                            except:
                                pass
                            engine.end_result(result)
                        else:
                            # if using it just "sho" the result
                            environ['RMANFB'] = 'it'
                            cmd = [os.path.join(self.paths['rmantree'], 'bin',
                                                'sho'),
                                   '-native', filtered_name]
                            process = subprocess.Popen(cmd, cwd=images_dir,
                                                       stdout=subprocess.PIPE,
                                                       stderr=subprocess.PIPE,
                                                       env=environ)
                            process.wait()
                    else:
                        engine.report({"ERROR"}, "RenderMan: Error Denoising.")
                except:
                    engine.report({"ERROR"},
                                  "Problem launching denoise from %s." %
                                  prman_executable)
            else:
                engine.report({"ERROR"},
                              "Cannot denoise file %s. Does not exist" %
                              denoise_data)

        # Load all output images into image editor
        if self.rm.import_images and self.rm.render_into == 'blender':
            for image in self.output_files:
                try:
                    bpy.ops.image.open(filepath=image)
                except:
                    pass

    def set_scene(self, scene):
        self.scene = scene

    def is_prman_running(self):
        return prman.RicGetProgress() < 100

    def reset_filter_names(self):
        self.light_filter_map = {}
        for obj in self.scene.objects:
            if obj.type == 'LAMP':
                # add the filters to the filter ma
                for lf in obj.data.renderman.light_filters:
                    if lf.filter_name not in self.light_filter_map:
                        self.light_filter_map[lf.filter_name] = []
                    self.light_filter_map[lf.filter_name].append(
                        (obj.data.name, obj.name))

    # start the interactive session.  Basically the same as ribgen, only
    # save the file
    def start_interactive(self):
        rm = self.scene.renderman
        if find_it_path() is None:
            debug('error', "ERROR no 'it' installed.  \
                    Cannot start interactive rendering.")
            return

        if self.scene.camera is None:
            debug('error', "ERROR no Camera.  \
                    Cannot start interactive rendering.")
            self.end_interactive()
            return

        self.ri.Begin(self.paths['rib_output'])
        rib_options = {"string format": "binary"} if rm.rib_format == "binary" else {
            "string format": "ascii", "string asciistyle": "indented,wide"}
        if rm.rib_compression == "gzip":
            rib_options["string compression"] = "gzip"
        self.ri.Option("rib", rib_options)
        self.material_dict = {}
        self.instance_dict = {}
        self.lights = {}
        self.light_filter_map = {}
        self.current_solo_light = None
        self.muted_lights = []
        self.crop_window = (self.scene.render.border_min_x, self.scene.render.border_max_x,
                      1.0 - self.scene.render.border_min_y, 1.0 - self.scene.render.border_max_y)
        for obj in self.scene.objects:
            if obj.type == 'LAMP' and obj.name not in self.lights:
                # add the filters to the filter ma
                for lf in obj.data.renderman.light_filters:
                    if lf.filter_name not in self.light_filter_map:
                        self.light_filter_map[lf.filter_name] = []
                    self.light_filter_map[lf.filter_name].append(
                        (obj.data.name, obj.name))
                self.lights[obj.name] = obj.data.name
                if obj.data.renderman.solo:
                    self.current_solo_light = obj
                if obj.data.renderman.mute:
                    self.muted_lights.append(obj)
            for mat_slot in obj.material_slots:
                if mat_slot.material not in self.material_dict:
                    self.material_dict[mat_slot.material] = []
                self.material_dict[mat_slot.material].append(obj)

        # export rib and bake

        # Check if rendering select objects only.
        if(self.scene.renderman.render_selected_objects_only):
            visible_objects = get_Selected_Objects(self.scene)
        else:
            visible_objects = None
        write_rib(self, self.scene, self.ri, visible_objects)
        self.ri.End()
        self.convert_textures(get_texture_list(self.scene))

        if sys.platform == 'win32':
            filename = "launch:prman? -t:%d" % self.rm.threads + " -cwd \"%s\" -ctrl $ctrlin $ctrlout \
            -dspyserver it" % self.paths['export_dir']
        else:
            filename = "launch:prman? -t:%d" % self.rm.threads + " -cwd %s -ctrl $ctrlin $ctrlout \
            -dspyserver it" % self.paths['export_dir'].replace(' ', '%20')
        self.ri.Begin(filename)
        self.ri.Option("rib", {"string asciistyle": "indented,wide"})
        interactive_initial_rib(self, self.ri, self.scene, prman)

        while not self.is_prman_running():
            time.sleep(.1)

        self.ri.EditBegin('null', {})
        self.ri.EditEnd()
        self.is_interactive_ready = True
        return

    # find the changed object and send for edits
    def issue_transform_edits(self, scene):
        cw = (scene.render.border_min_x, scene.render.border_max_x,
                      1.0 - scene.render.border_min_y, 1.0 - scene.render.border_max_y)
        if cw != self.crop_window:
            self.crop_window = cw
            update_crop_window(self.ri, self, prman, cw)
            return

        active = scene.objects.active
        if (active and active.is_updated) or (active and active.type == 'LAMP' and active.is_updated_data):
            if is_ipr_running():
                issue_transform_edits(self, self.ri, active, prman)
            else:
                return
        # record the marker to rib and flush to that point
        # also do the camera in case the camera is locked to display.
        if scene.camera.name != active.name and scene.camera.is_updated:
            if is_ipr_running():
                issue_transform_edits(self, self.ri, scene.camera, prman)
            else:
                return
        # check for light deleted
        if not active and len(self.lights) > len([o for o in scene.objects if o.type == 'LAMP']):
            lights_deleted = []
            for light_name, data_name in self.lights.items():
                if light_name not in scene.objects:
                    if is_ipr_running():
                        delete_light(self, self.ri, data_name, prman)
                        lights_deleted.append(light_name)
                    else:
                        return

            for light_name in lights_deleted:
                self.lights.pop(light_name, None)

        if active and active.type in ['MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'LATTICE']:

            for mat_slot in active.material_slots:
                if mat_slot.material not in self.material_dict:
                    self.material_dict[mat_slot.material] = []
                if active not in self.material_dict[mat_slot.material]:
                    self.material_dict[mat_slot.material].append(active)
                    issue_shader_edits(self, self.ri, prman,
                                        nt=mat_slot.material.node_tree, ob=active)

    def update_illuminates(self):
        update_illuminates(self, self.ri, prman)

    def update_light_visibility(self, lamp):
        issue_light_vis(self, self.ri, lamp, prman)

    def solo_light(self):
        if self.current_solo_light:
            # if there was originally a solo light have to reset ALL
            lights = [
                light for light in self.scene.objects if light.type == 'LAMP']
            reset_light_illum(self, self.ri, prman, lights, do_solo=False)

        self.current_solo_light = solo_light(self, self.ri, prman)

    def un_solo_light(self):
        if self.current_solo_light:
            # if there was originally a solo light have to reset ALL
            lights = [
                light for light in self.scene.objects if light.type == 'LAMP']
            reset_light_illum(self, self.ri, prman, lights, do_solo=False)
            self.current_solo_light = None

    def mute_light(self):
        new_muted_lights = []
        un_muted_lights = []
        for obj in self.scene.objects:
            if obj.type == 'LAMP':
                if obj.data.renderman.mute and obj not in self.muted_lights:
                    new_muted_lights.append(obj)
                    self.muted_lights.append(obj)
                elif not obj.data.renderman.mute and obj in self.muted_lights:
                    un_muted_lights.append(obj)
                    self.muted_lights.remove(obj)

        if len(un_muted_lights):
            reset_light_illum(self, self.ri, prman, un_muted_lights)
        if len(new_muted_lights):
            mute_lights(self, self.ri, prman, new_muted_lights)

    def issue_shader_edits(self, nt=None, node=None):
        issue_shader_edits(self, self.ri, prman, nt=nt, node=node)

    def update_light_link(self, context, ll):
        update_light_link(self, self.ri, prman, ll)

    def remove_light_link(self, context, ll):
        update_light_link(self, self.ri, prman, ll, remove=True)

    # ri.end
    def end_interactive(self):
        self.is_interactive = False
        if self.is_prman_running():
            self.edit_num += 1
            # output a flush to stop rendering.
            self.ri.ArchiveRecord(
                "structure", self.ri.STREAMMARKER + "%d" % self.edit_num)
            prman.RicFlush("%d" % self.edit_num, 0, self.ri.SUSPENDRENDERING)
            self.ri.EditWorldEnd()
        self.ri.End()
        self.material_dict = {}
        self.lights = {}
        self.light_filter_map = {}
        self.instance_dict = {}
        pass

    def gen_rib(self, do_objects=True, engine=None, convert_textures=True):
        rm = self.scene.renderman
        if self.scene.camera is None:
            debug('error', "ERROR no Camera.  \
                    Cannot generate rib.")
            return
        time_start = time.time()
        if convert_textures:
            self.convert_textures(get_texture_list(self.scene))

        if engine:
            engine.report({"INFO"}, "Texture generation took %s" %
                          format_seconds_to_hhmmss(time.time() - time_start))
        self.scene.frame_set(self.scene.frame_current)
        time_start = time.time()
        rib_options = {"string format": "binary"} if rm.rib_format == "binary" else {
            "string format": "ascii", "string asciistyle": "indented,wide"}
        if rm.rib_compression == "gzip":
            rib_options["string compression"] = "gzip"
        self.ri.Option("rib", rib_options)
        self.ri.Begin(self.paths['rib_output'])

        # Check if rendering select objects only.
        if rm.render_selected_objects_only:
            visible_objects = get_Selected_Objects(self.scene)
        else:
            visible_objects = None
        write_rib(self, self.scene, self.ri, visible_objects, engine, do_objects)
        self.ri.End()
        if engine:
            engine.report({"INFO"}, "RIB generation took %s" %
                          format_seconds_to_hhmmss(time.time() - time_start))

    def gen_preview_rib(self):
        previewdir = os.path.join(self.paths['export_dir'], "preview")

        self.paths['rib_output'] = os.path.join(previewdir, "preview.rib")
        self.paths['render_output'] = os.path.join(previewdir, "preview.tif")
        self.paths['export_dir'] = os.path.dirname(self.paths['rib_output'])

        if not os.path.exists(previewdir):
            os.mkdir(previewdir)

        self.convert_textures(get_texture_list_preview(self.scene))

        self.ri.Begin(self.paths['rib_output'])
        self.ri.Option("rib", {"string asciistyle": "indented,wide"})
        self.rib_done = write_preview_rib(self, self.scene, self.ri)
        self.ri.End()

    def convert_textures(self, temp_texture_list):
        if not os.path.exists(self.paths['texture_output']):
            os.mkdir(self.paths['texture_output'])

        files_converted = []
        texture_list = []

        if not temp_texture_list:
            return

        # for UDIM textures
        for in_file, out_file, options in temp_texture_list:
            if '_MAPID_' in in_file:
                in_file = get_real_path(in_file)
                for udim_file in glob.glob(in_file.replace('_MAPID_', '*')):
                    texture_list.append(
                        (udim_file, get_tex_file_name(udim_file), options))
            else:
                texture_list.append((in_file, out_file, options))

        for in_file, out_file, options in texture_list:
            in_file = get_real_path(in_file)
            out_file_path = os.path.join(
                self.paths['texture_output'], out_file)

            if os.path.isfile(out_file_path) and os.path.exists(in_file) and\
                    self.rm.always_generate_textures is False and \
                    os.path.getmtime(in_file) <= \
                    os.path.getmtime(out_file_path):
                debug("info", "TEXTURE %s EXISTS (or is not dirty)!" %
                      out_file)
            else:
                cmd = [os.path.join(self.paths['rmantree'], 'bin',
                                    self.paths['path_texture_optimiser'])] + \
                    options + [in_file, out_file_path]
                debug("info", "TXMAKE STARTED!", cmd)

                Blendcdir = bpy.path.abspath("//")
                if not Blendcdir:
                    Blendcdir = None

                environ = os.environ.copy()
                environ['RMANTREE'] = self.paths['rmantree']
                process = subprocess.Popen(cmd, cwd=Blendcdir,
                                           stdout=subprocess.PIPE, env=environ)
                process.communicate()
                files_converted.append(out_file_path)

        return files_converted
