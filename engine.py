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
from random import randint
import sys
from bpy.app.handlers import persistent

# global dictionaries
from .export import write_rib, write_preview_rib, get_texture_list,\
    issue_shader_edits, get_texture_list_preview, issue_transform_edits,\
    interactive_initial_rib, update_light_link, delete_light

from .nodes import get_tex_file_name

addon_version = bl_info['version']

# set pythonpath before importing prman
set_rmantree(guess_rmantree())
set_pythonpath(os.path.join(guess_rmantree(), 'bin'))
it_dir = os.path.dirname(find_it_path()) if find_it_path() else None
set_path([os.path.join(guess_rmantree(), 'bin'), it_dir])
import prman

ipr = None


def init():
    pass


def create(engine, data, scene, region=0, space_data=0, region_data=0):
    # TODO add support for regions (rerendering)
    engine.render_pass = RPass(scene)


def free(engine):
    if hasattr(engine, 'render_pass'):
        if engine.render_pass.is_interactive_running:
            engine.render_pass.end_interactive()
        if engine.render_pass:
            del engine.render_pass


def render(engine):
    if hasattr(engine, 'render_pass') and engine.render_pass.do_render:
        if engine.is_preview:
            engine.render_pass.preview_render(engine)
        else:
            engine.render_pass.render(engine)


def reset(engine, data, scene):
    engine.render_pass.set_scene(scene)


def update(engine, data, scene):
    engine.render_pass.update_time = int(time.time())
    if engine.is_preview:
        engine.render_pass.display_driver = 'tif'
        try:
            engine.render_pass.gen_preview_rib()
        except Exception as err:
            engine.report({'ERROR'}, 'Rib gen error: ' + traceback.format_exc())
    else:
        engine.render_pass.display_driver = scene.renderman.display_driver
        try:
            engine.render_pass.gen_rib(engine=engine)
        except Exception as err:
            engine.report({'ERROR'}, 'Rib gen error: ' + traceback.format_exc())


# assumes you have already set the scene
def start_interactive(engine):
    engine.render_pass.start_interactive()


def update_interactive(engine, context):
    engine.render_pass.issue_edits(context)


# update the timestamp on an object
# note that this only logs the active object.  So it might not work say
# if a script updates objects.  We would need to iterate through all objects
def update_timestamp(scene):
    active = scene.objects.active
    if active and active.is_updated_data:
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

    def __init__(self, scene, interactive=False):
        self.scene = scene
        # pass addon prefs to init_envs
        addon = bpy.context.user_preferences.addons[__name__.split('.')[0]]
        init_exporter_env(addon.preferences)
        self.initialize_paths(scene)
        self.rm = scene.renderman

        self.do_render = (scene.renderman.output_action == 'EXPORT_RENDER')
        self.is_interactive_running = False
        self.is_interactive = interactive
        self.options = []
        if interactive:
            prman.Init(['-woff', 'A57001']) #need to disable for interactive
        else:
            prman.Init()
        self.ri = prman.Ri()
        self.edit_num = 0
        self.update_time = None

    def __del__(self):
        if self.is_interactive_running:
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

        self.paths['render_output'] = user_path(rm.path_display_driver_image,
                                                scene=scene)
        debug("info",self.paths)
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
                          "Problem launching PRMan from %s." % prman_executable)
            isProblem = True

    def render(self, engine):
        DELAY = 1
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
        options = self.options + ['-Progress']
        prman_executable = os.path.join(self.paths['rmantree'], 'bin',
                                        self.paths['rman_binary'])
        if self.display_driver in ['openexr', 'tiff']:
            options = options + ['-checkpoint',
                                 "%.2fs" % self.rm.update_frequency]
        cmd = [prman_executable] + options + ["-t:%d" % self.rm.threads] + \
            [self.paths['rib_output']]
        cdir = os.path.dirname(self.paths['rib_output'])
        environ = os.environ.copy()
        environ['RMANTREE'] = self.paths['rmantree']

        # Launch the command to begin rendering.
        try:
            process = subprocess.Popen(cmd, cwd=cdir, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, env=environ)
            isProblem = False
        except:
            engine.report({"ERROR"},
                          "Problem launching PRMan from %s." % prman_executable)
            isProblem = True

        if not isProblem:
            # Wait for the file to be created.
            t1 = time.time()
            s = '.'
            while not os.path.exists(render_output) and \
                    self.display_driver != 'it':
                engine.update_stats("", ("PRMan: Starting Rendering" + s))
                if engine.test_break():
                    try:
                        process.kill()
                    except:
                        pass
                    break

                if process.poll() != None:
                    engine.report({"ERROR"}, "PRMan: Exited")
                    break

                time.sleep(DELAY)
                s = s + '.'

            if os.path.exists(render_output) or self.display_driver == 'it':

                if self.display_driver != 'it':
                    prev_mod_time = os.path.getmtime(render_output)
                engine.update_stats("", ("PRMan: Rendering."))
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
                            engine.report({"ERROR"}, "PRMan: %s " % line.decode('utf8'))
                        elif line and "WARNING" in str(line):
                            engine.report({"WARNING"}, "PRMan: %s " % line.decode('utf8'))
                        elif line and "SEVERE" in str(line):
                            engine.report({"ERROR"}, "PRMan: %s " % line.decode('utf8'))

                    if process.poll() is not None:
                        if self.display_driver != 'it':
                            update_image()
                        t2 = time.time()
                        engine.report({"INFO"}, "PRMan: Done Rendering." +
                                      " (elapsed time: " +
                                      format_seconds_to_hhmmss(t2 - t1) + ")")

                        break

                    # user exit
                    if engine.test_break():
                        try:
                            process.kill()
                            isProblem = True
                            engine.report({"INFO"},
                                          "PRMan: Rendering Cancelled.")
                        except:
                            pass
                        break

                    # check if the file updated
                    if self.display_driver != 'it':
                        new_mod_time = os.path.getmtime(render_output)

                        if new_mod_time != prev_mod_time:
                            update_image()
                            prev_mod_time = new_mod_time

            else:
                debug("error", "Export path [" + render_output +
                      "] does not exist.")
        else:
            debug("error",
                  "Problem launching PRMan from %s." % prman_executable)

        # launch the denoise process if turned on
        if self.rm.do_denoise and not isProblem:
            base, ext = render_output.rsplit('.', 1)
            # denoise data has the name .denoise.exr
            denoise_data = base + '.denoise.' + 'exr'
            filtered_name = base + '.denoise_filtered.' + 'exr'
            if os.path.exists(denoise_data):
                try:
                    # denoise to _filtered
                    cmd = [os.path.join(self.paths['rmantree'], 'bin',
                                        'denoise'), denoise_data]

                    engine.update_stats("", ("PRMan: Denoising image"))
                    t1 = time.time()
                    process = subprocess.Popen(cmd, cwd=images_dir,
                                               stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE,
                                               env=environ)
                    process.wait()
                    t2 = time.time()
                    if os.path.exists(filtered_name):
                        engine.report({"INFO"}, "PRMan: Done Denoising." +
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
                        engine.report({"ERROR"}, "PRMan: Error Denoising.")
                except:
                    engine.report({"ERROR"},
                                  "Problem launching denoise from %s." %
                                  prman_executable)
            else:
                engine.report({"ERROR"},
                              "Cannot denoise file %s. Does not exist" %
                              denoise_data)

    def set_scene(self, scene):
        self.scene = scene

    # start the interactive session.  Basically the same as ribgen, only
    # save the file
    def start_interactive(self):
        if find_it_path() == None:
            debug('error', "ERROR no 'it' installed.  \
                    Cannot start interactive rendering.")
            return

        if self.scene.camera == None:
            debug('error', "ERROR no Camera.  \
                    Cannot start interactive rendering.")
            self.end_interactive()
            return

        self.is_interactive = True
        self.is_interactive_running = True
        self.ri.Begin(self.paths['rib_output'])
        self.ri.Option("rib", {"string asciistyle": "indented,wide"})
        self.material_dict = {}
        self.lights = {}
        for obj in self.scene.objects:
            if obj.type == 'LAMP' and obj.name not in self.lights:
                self.lights[obj.name] = obj.data.name
            for mat_slot in obj.material_slots:
                if mat_slot.material not in self.material_dict:
                    self.material_dict[mat_slot.material] = []
                self.material_dict[mat_slot.material].append(obj)

        # export rib and bake
        write_rib(self, self.scene, self.ri)
        self.ri.End()
        self.convert_textures(get_texture_list(self.scene))

        if sys.platform == 'win32':
            filename = "launch:prman? -t:-1 -cwd \"%s\" -ctrl $ctrlin $ctrlout \
            -dspyserver it" % self.paths['export_dir']
        else:
            filename = "launch:prman? -t:-1 -cwd %s -ctrl $ctrlin $ctrlout \
            -dspyserver it" % self.paths['export_dir']
        self.ri.Begin(filename)
        self.ri.Option("rib", {"string asciistyle": "indented,wide"})
        interactive_initial_rib(self, self.ri, self.scene, prman)

        return


    # find the changed object and send for edits
    def issue_transform_edits(self, scene):
        active = scene.objects.active
        if active and active.is_updated:
            issue_transform_edits(self, self.ri, active, prman)
        # record the marker to rib and flush to that point
        # also do the camera in case the camera is locked to display.
        if scene.camera != active and scene.camera.is_updated:
            issue_transform_edits(self, self.ri, scene.camera, prman)
        # check for light deleted
        if not active and len(self.lights) > len([o for o in scene.objects if o.type == 'LAMP']):
            lights_deleted = []
            for light_name,data_name in self.lights.items():
                if light_name not in scene.objects:
                    delete_light(self, self.ri, data_name, prman)
                    lights_deleted.append(light_name)

            for light_name in lights_deleted:
                self.lights.pop(light_name, None)


    def issue_shader_edits(self, nt=None, node=None):
        issue_shader_edits(self, self.ri, prman, nt=nt, node=node)

    def update_light_link(self, context, ll):
        update_light_link(self, self.ri, prman, context.scene.objects.active, ll)

    # ri.end
    def end_interactive(self):
        self.is_interactive = False
        self.is_interactive_running = False
        self.ri.EditWorldEnd()
        self.ri.End()
        self.material_dict = {}
        self.lights = {}
        pass

    def gen_rib(self, engine=None):
        if self.scene.camera == None:
            debug('error', "ERROR no Camera.  \
                    Cannot generate rib.")
            return
        time_start = time.time()
        self.convert_textures(get_texture_list(self.scene))

        if engine:
            engine.report({"INFO"}, "Texture generation took %s" %
                          format_seconds_to_hhmmss(time.time() - time_start))
        else:
            self.scene.frame_set(self.scene.frame_current)
        time_start = time.time()
        self.ri.Begin(self.paths['rib_output'])
        self.ri.Option("rib", {"string asciistyle": "indented,wide"})
        write_rib(self, self.scene, self.ri)
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
        write_preview_rib(self, self.scene, self.ri)
        self.ri.End()

    def convert_textures(self, temp_texture_list):
        if not os.path.exists(self.paths['texture_output']):
            os.mkdir(self.paths['texture_output'])

        files_converted = []
        texture_list = []

        # for UDIM textures
        for in_file, out_file, options in temp_texture_list:
            if '_MAPID_' in in_file:
                in_file = get_real_path(in_file)
                for udim_file in glob.glob(in_file.replace('_MAPID_', '*')):
                    texture_list.append((udim_file, get_tex_file_name(udim_file), options))
            else:
                texture_list.append((in_file, out_file, options))

        for in_file, out_file, options in texture_list:
            in_file = get_real_path(in_file)
            out_file_path = os.path.join(
                self.paths['texture_output'], out_file)

            if os.path.isfile(out_file_path) and \
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
                if Blendcdir == '':
                    Blendcdir = None

                environ = os.environ.copy()
                environ['RMANTREE'] = self.paths['rmantree']
                process = subprocess.Popen(cmd, cwd=Blendcdir,
                                           stdout=subprocess.PIPE, env=environ)
                process.communicate()
                files_converted.append(out_file_path)

        return files_converted
