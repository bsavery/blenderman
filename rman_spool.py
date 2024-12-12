import subprocess
import os
import getpass
import socket
import platform
import datetime
import bpy
from .rfb_utils import filepath_utils
from .rfb_utils import string_utils
from .rfb_utils.envconfig_utils import envconfig
from .rfb_utils import display_utils
from .rfb_utils import scene_utils
from .rfb_utils.prefs_utils import get_pref
from .rman_config import __RFB_CONFIG_DICT__ as rfb_config
from .rfb_logger import rfb_log

import tractor.api.author as author

class RmanSpool(object):

    def __init__(self, rman_render, rman_scene, depsgraph):
        self.rman_render = rman_render
        self.rman_scene = rman_scene
        self.is_localqueue = True
        self.is_tractor = False
        self.any_denoise = False
        self.tractor_cfg = rfb_config['tractor_cfg']
        if depsgraph:
            self.bl_scene = depsgraph.scene_eval
            self.depsgraph = depsgraph
            self.is_localqueue = (self.bl_scene.renderman.queuing_system == 'lq')
            self.is_tractor = (self.bl_scene.renderman.queuing_system == 'tractor')

    def add_job_level_attrs(self, job):
        dirmaps = get_pref('rman_tractor_dirmaps', [])
        for dirmap in dirmaps:
            job.newDirMap(src=dirmap.from_path,
                        dst=dirmap.to_path,
                        zone=dirmap.zone)

        for k in rfb_config['dirmaps']:
            dirmap = rfb_config['dirmaps'][k]
            job.newDirMap(src=str(dirmap['from']),
                        dst=str(dirmap['to']),
                        zone=str(dirmap['zone']))

        rman_vers = envconfig().build_info.version()
        envkeys = []
        if self.is_localqueue:
            envkeys.append('rmantree=%s' % envconfig().rmantree)
        else:
            envkeys.append('prman-%s' % rman_vers)
        
        user_envkeys = self.tractor_cfg.get('envkeys', get_pref('rman_tractor_envkeys'))
        job.envkey = envkeys + user_envkeys.split()

        service = self.tractor_cfg.get('service', get_pref('rman_tractor_service'))
        job.service = service
        job.priority = float(self.tractor_cfg.get('priority', get_pref('rman_tractor_priority')))
        job.metadata = self.tractor_cfg.get('metadata', get_pref('rman_tractor_metadata'))
        job.comment = self.tractor_cfg.get('comment', get_pref('rman_tractor_comment'))

        crews = self.tractor_cfg.get('crews', get_pref('rman_tractor_crews'))
        if crews != '':
            job.crews = crews.split()
        projects = self.tractor_cfg.get('projects', get_pref('rman_tractor_projects'))
        if projects != '':
            job.projects = projects.split()

        whendone = self.tractor_cfg.get('whendone', get_pref('rman_tractor_whendone'))
        whenerror = self.tractor_cfg.get('whenerror', get_pref('rman_tractor_whenerror'))
        whenalways = self.tractor_cfg.get('whenalways', get_pref('rman_tractor_whenalways'))
        if whendone != '':
            job.newPostscript(argv=whendone, when="done", service=service)
        if whenerror != '':
            job.newPostscript(argv=whenerror, when="error", service=service)            
        if whenalways != '':
            job.newPostscript(argv=whenalways, when="always", service=service)  

        after = self.tractor_cfg.get('after', get_pref('rman_tractor_after'))
        if after != '':
            try:
                aftersplit = after.split(' ')
                if len(aftersplit) == 2:
                    t_date = aftersplit[0].split('/')
                    t_time = aftersplit[1].split(':')
                    if len(t_date) == 2 and len(t_time) == 2:
                        today = datetime.datetime.today()
                        job.after = datetime.datetime(today.year, int(t_date[0]),
                                                        int(t_date[1]),
                                                        int(t_time[0]),
                                                        int(t_time[1]), 0)
                    else:
                        print('Could not parse after date: %s. Ignoring.' % after)
                else:
                    print('Could not parse after date: %s. Ignoring.' % after)
            except:
                print('Could not parse after date: %s. Ignoring.' % after)        

    def _add_additional_prman_args(self, args):
        rm = self.bl_scene.renderman
        if rm.custom_cmd != '':
            tokens = rm.custom_cmd.split(' ')
            for tok in tokens:
                args.append(tok)

        if rm.recover:
            args.append('-recover')
            args.append('1')
        else:
            args.append('-recover')
            args.append('%r')

        scene_utils.set_render_variant_spool(self.bl_scene, args, self.is_tractor)

    def add_preview_task(self, task, imgs):
        if imgs is None:
            return
        it_path = envconfig().rman_it_path
        if platform.system() == 'Windows':        
            it_path = '"%s"' % it_path
        img = imgs
        if isinstance(imgs, list):
            img = " ".join(imgs)
        task.preview = "%s %s" % (it_path, img)
            
    def add_prman_render_task(self, parentTask, title, threads, rib, img):
        rm = self.bl_scene.renderman
        out_dir = '<OUT>'

        task = author.Task()
        task.title = title
        self.add_preview_task(task, img)

        command = author.Command(local=False, service="PixarRender")
        command.argv = ["prman"]
        self._add_additional_prman_args(command.argv)

        proj = string_utils.expand_string(out_dir, asFilePath=True) 
        
        command.argv.append('-Progress')
        command.argv.append('-t:%d' % threads)
        command.argv.append('-cwd')
        command.argv.append("%%D(%s)" % proj)

        # rib file
        command.argv.append("%%D(%s)" % rib)

        task.addCommand(command)
        parentTask.addChild(task)            

    def add_blender_render_task(self, frame, parentTask, title, bl_filename, chunk=None):
        rm = self.bl_scene.renderman

        task = author.Task()
        task.title = title

        command = author.Command(local=False, service="PixarRender")
        bl_blender_path = 'blender'
        if self.is_localqueue:
            bl_blender_path = bpy.app.binary_path
        command.argv = [bl_blender_path]

        command.argv.append('-b')
        command.argv.append('%%D(%s)' % bl_filename)
        begin = frame
        end = frame
        if chunk:
            command.argv.append('-f')
            command.argv.append('%s..%s' % (str(frame), str(frame+(chunk))))
            end = frame+chunk
        else:
            command.argv.append('-f')
            command.argv.append(str(frame))            

        task.addCommand(command)

        imgs = list()
        dspys_dict = display_utils.get_dspy_dict(self.rman_scene, expandTokens=False)  
        for i in range(begin, end+1):
            img = string_utils.expand_string(dspys_dict['displays']['beauty']['filePath'], 
                                                frame=i,
                                                asFilePath=True)         
            imgs.append(img)     


        self.add_preview_task(task, imgs)
        parentTask.addChild(task)

    def generate_blender_batch_tasks(self, anim, parent_task, tasktitle,
                                start, last, by, chunk, bl_filename): 
       
        if anim is False:
     
            frametasktitle = ("%s Frame: %d " %
                            (tasktitle, int(start)))
            frametask = author.Task()
            frametask.title = frametasktitle
            frametask.serialsubtasks = True

            prmantasktitle = "%s (render)" % frametasktitle

            self.add_blender_render_task(start, frametask, prmantasktitle,
                                bl_filename)

            parent_task.addChild(frametask)

        else:
            parent_task.serialsubtasks = True

            renderframestask = author.Task()
            renderframestask.serialsubtasks = False
            renderframestasktitle = ("Render Layer: %s "%
                                    (str(self.depsgraph.view_layer.name)))
            renderframestask.title = renderframestasktitle

            if (chunk+1) > 1 and by < 2 and (start+chunk < last+1):               
                iframe = start
                while (iframe < last+1):
                    diff = chunk
                    if ((iframe + chunk) > last+1):
                        diff = (last) - iframe
                    prmantasktitle = ("%s Frames: (%d-%d) (blender)" %
                                    (tasktitle, iframe, iframe+diff))

                    self.add_blender_render_task(iframe, renderframestask, prmantasktitle,
                                        bl_filename, chunk=diff) 
                    iframe += diff+1
            else:
                for iframe in range(start, last + 1, by):
                    prmantasktitle = ("%s Frame: %d (blender)" %
                                    (tasktitle, int(iframe)))

                    self.add_blender_render_task(iframe, renderframestask, prmantasktitle,
                                        bl_filename)

            parent_task.addChild(renderframestask)                                 

    def generate_rib_render_tasks(self, anim, parent_task, tasktitle,
                                start, last, by, threads):

        rm = self.bl_scene.renderman

        if anim is False:

            rib_expanded = string_utils.expand_string(rm.path_rib_output, 
                                                    frame=start, 
                                                    asFilePath=True)

            dspys_dict = display_utils.get_dspy_dict(self.rman_scene, expandTokens=False)    
            img_expanded = ''
            if not self.rman_scene.rman_bake:        
                img_expanded = string_utils.expand_string(dspys_dict['displays']['beauty']['filePath'], 
                                                    frame=start,
                                                    asFilePath=True)                                                          
                                                    
            frametasktitle = ("%s Frame: %d " %
                            (tasktitle, int(start)))
            frametask = author.Task()
            frametask.title = frametasktitle
            frametask.serialsubtasks = True

            prmantasktitle = "%s (render)" % frametasktitle

            self.add_prman_render_task(frametask, prmantasktitle, threads,
                                rib_expanded, img_expanded)
            
            parent_task.addChild(frametask)

        else:
            parent_task.serialsubtasks = True

            renderframestask = author.Task()
            renderframestask.serialsubtasks = False
            renderframestasktitle = ("Render Layer: %s "%
                                    (str(self.depsgraph.view_layer.name)))
            renderframestask.title = renderframestasktitle

            dspys_dict = display_utils.get_dspy_dict(self.rman_scene, expandTokens=False)                  

            for iframe in range(int(start), int(last + 1), int(by)):
                rib_expanded = string_utils.expand_string(rm.path_rib_output, 
                                                        frame=iframe, 
                                                        asFilePath=True)
                img_expanded = string_utils.expand_string(dspys_dict['displays']['beauty']['filePath'], 
                                                        frame=iframe,
                                                        asFilePath=True)         

                prmantasktitle = ("%s Frame: %d (prman)" %
                                (tasktitle, int(iframe)))

                self.add_prman_render_task(renderframestask, prmantasktitle, threads,
                                      rib_expanded, img_expanded)

            parent_task.addChild(renderframestask)

    def generate_aidenoise_tasks(self, start, last, by):
        tasktitle = "Denoiser Renders"
        parent_task = author.Task()
        parent_task.title = tasktitle          
        rm = self.bl_scene.renderman   
        dspys_dict = display_utils.get_dspy_dict(self.rman_scene, expandTokens=False)  
        
        img_files = list()
        preview_img_files = list()
        have_variance = False
        beauty_path = dspys_dict['displays']['beauty']['filePath']
        variance_file = string_utils.expand_string(beauty_path, 
                                            frame=1,
                                            asFilePath=True)            
        path = filepath_utils.get_real_path(rm.ai_denoiser_output_dir)
        if not os.path.exists(path):
            path = os.path.join(os.path.dirname(variance_file), 'denoised')
        do_cross_frame = (rm.ai_denoiser_mode == 'crossframe')            
        if by > 1:        
            do_cross_frame = False # can't do crossframe if by > 1
            for frame_num in range(start, last + 1, by):
                self.rman_render.bl_frame_current = frame_num
            
                variance_file = string_utils.expand_string(beauty_path, 
                                                    frame=frame_num,
                                                    asFilePath=True)  

                for dspy,params in dspys_dict['displays'].items():
                    if not params['denoise']:
                        continue
                    if dspy == 'beauty':
                        if not have_variance:
                            have_variance = True
                        img_files.append(variance_file)
                        preview_img_files.append(os.path.join(path, os.path.basename(variance_file)))
                    else:
                        token_dict = {'aov': dspy}
                        aov_file = string_utils.expand_string(params['filePath'], 
                                                frame=frame_num,
                                                token_dict=token_dict,
                                                asFilePath=True)    
                        img_files.append(aov_file)   
        else:   
            # use frame range format
            # ex: foo.####.exr start-last
            for frame_num in range(start, last + 1):           
                variance_file = string_utils.expand_string(beauty_path, 
                                                    frame=frame_num,
                                                    asFilePath=True)   
                preview_img_files.append(os.path.join(path, os.path.basename(variance_file)))
                               
            for dspy,params in dspys_dict['displays'].items():
                if not params['denoise']:
                    continue
                if dspy == 'beauty':
                    if not have_variance:
                        have_variance = True
                    variance_file = string_utils.expand_string(beauty_path, 
                                                        frame='#',
                                                        asFilePath=True)                        
                    img_files.append(variance_file)
                else:
                    token_dict = {'aov': dspy}
                    aov_file = string_utils.expand_string(params['filePath'], 
                                            token_dict=token_dict,
                                            frame="#",
                                            asFilePath=True)    
                    img_files.append(aov_file)       

            img_files.append('%d-%d' % (start, last))        

        if not have_variance or len(img_files) < 1:
            return None
       
        if start == last:
            do_cross_frame = False

        cur_frame = self.rman_scene.bl_frame_current
        task = author.Task()
        if do_cross_frame:
            task.title = 'Denoise Frames %d - %d (Cross Frame)' % (start, last)
        else:
            task.title = 'Denoise Frames (%d - %d)' % (start, last)
        
        command = author.Command(local=False, service="PixarRender")                

        command.argv = ["denoise_batch"]        

        if do_cross_frame:
            command.argv.append('--crossframe')  
        
        if rm.ai_denoiser_verbose:
            command.argv.append('-v')
        command.argv.append('-a')
        command.argv.append('%.3f' % rm.ai_denoiser_asymmetry)
        command.argv.append('-o')
        command.argv.append(path)
        if rm.ai_denoiser_flow:
            command.argv.append('-f')
        if rm.ai_denoiser_remap_diffuse:
            command.argv.append('--diffuse')
            command.argv.append(rm.ai_denoiser_remap_diffuse)
        if rm.ai_denoiser_remap_specular:
            command.argv.append('--specular')
            command.argv.append(rm.ai_denoiser_remap_specular)
        if rm.ai_denoiser_remap_albedo:
            command.argv.append('--albedo')
            command.argv.append(rm.ai_denoiser_remap_albedo)
        if rm.ai_denoiser_remap_irradiance:
            command.argv.append('--irradiance')
            command.argv.append(rm.ai_denoiser_remap_irradiance)
        if rm.ai_denoiser_remap_alpha:
            command.argv.append('--alpha')
            command.argv.append(rm.ai_denoiser_remap_alpha) 
        command.argv.append('--progress')
        if envconfig().build_info.version() > "26.2":
            command.argv.append('--tiles')
            tilesX, tilesY = string_utils.convert_val(rm.ai_denoiser_tiles, type_hint="int2")
            command.argv.append(tilesX)
            command.argv.append(tilesY)                       

        command.argv.extend(img_files)
                                                         
        task.addCommand(command)
        self.add_preview_task(task, preview_img_files)
        parent_task.addChild(task) 

        self.rman_render.bl_frame_current = cur_frame
        return parent_task
                        
    def blender_batch_render(self, bl_filename, bl_stash_blend_cache=""):

        scene = self.bl_scene 
        rm = scene.renderman
        frame_begin = self.bl_scene.frame_start
        frame_end = self.bl_scene.frame_end
        frame_current = self.bl_scene.frame_current
        by = self.bl_scene.frame_step     
        chunk = min(rm.bl_batch_frame_chunk, frame_end)-1

        # update variables
        string_utils.set_var('scene', self.bl_scene.name.replace(' ', '_'))
        string_utils.set_var('layer', self.rman_scene.bl_view_layer.name.replace(' ', '_'))      

        if not rm.external_animation:
            frame_begin = self.bl_scene.frame_current
            frame_end = frame_begin

        job = author.Job()
        
        scene_name = self.bl_scene.name
        bl_view_layer = self.depsgraph.view_layer.name
        job_title = 'untitled' if not bpy.data.filepath else \
            os.path.splitext(os.path.split(bpy.data.filepath)[1])[0]
        job_title += ' %s ' % bl_view_layer
        job_title += " frames %d-%d" % (frame_begin, frame_end) if frame_end \
            else " frame %d" % frame_begin


        job.title = str(job_title)
        job.serialsubtasks = True
        job.service = 'PixarRender'
        self.add_job_level_attrs(job)

        frame_begin = self.bl_scene.frame_start
        frame_end = self.bl_scene.frame_end
        if not rm.external_animation:
            frame_begin = self.bl_scene.frame_current
            frame_end = frame_begin        

        tasktitle = "Render %s" % (str(scene_name))
        parent_task = author.Task()
        parent_task.title = tasktitle
        anim = (frame_begin != frame_end)

        self.generate_blender_batch_tasks(anim, parent_task, tasktitle,
                                frame_begin, frame_end, by, chunk, bl_filename)

        job.addChild(parent_task)                                

        # Don't generate denoise tasks if we're baking
        # or using the Blender compositor
        if rm.ai_denoiser_launch and rm.hider_type == 'RAYTRACE' and (not rm.use_bl_compositor and not scene.use_nodes):
            parent_task = self.generate_aidenoise_tasks(frame_begin, frame_end, by)                               
                
            if parent_task:
                job.addChild(parent_task)
        
        scene_filename = bpy.data.filepath
        if scene_filename == '':
            jobfile = string_utils.expand_string('<OUT>/<scene>.<layer>.alf', 
                                                asFilePath=True)            
        else:
            jobfile = os.path.splitext(scene_filename)[0] + '.%s.alf' % bl_view_layer.replace(' ', '_')

        stashFileCleanup = author.Command(local=False)
        stashFileCleanup.argv = ["TractorBuiltIn", "File", "delete",
                                 "%%D(%s)" % bl_filename]
        job.addCleanup(stashFileCleanup)

        jobFileCleanup = author.Command(local=False)
        jobFileCleanup.argv = ["TractorBuiltIn", "File", "delete",
                                 "%%D(%s)" % jobfile]
        job.addCleanup(jobFileCleanup)

        if bl_stash_blend_cache != "":
            blend_cache_clean = author.Command(local=False)
            blend_cache_clean.argv = ["TractorBuiltIn", "File", "delete",
                                     "%%D(%s)" % bl_stash_blend_cache]
            job.addCleanup(blend_cache_clean)


        try:
            f = open(jobfile, 'w')
            as_tcl = job.asTcl()
            f.write(as_tcl)
            f.close()
        except IOError as ioe:
            rfb_log().error('IO Exception when writing job file %s: %s' % (jobfile, str(ioe)))
            return
        except Exception as e:
            rfb_log().error('Could not write job file %s: %s' % (jobfile, str(e)))
            return

        self.spool(job, jobfile)
        string_utils.update_frame_token(frame_current)

    
    def batch_render(self):

        scene = self.bl_scene 
        rm = scene.renderman
        frame_begin = self.bl_scene.frame_start
        frame_end = self.bl_scene.frame_end
        frame_current = self.bl_scene.frame_current        
        by = self.bl_scene.frame_step        

        if not rm.external_animation:
            frame_begin = self.bl_scene.frame_current
            frame_end = frame_begin

        job = author.Job()
        
        scene_name = self.bl_scene.name
        bl_view_layer = self.depsgraph.view_layer.name
        job_title = 'untitled' if not bpy.data.filepath else \
            os.path.splitext(os.path.split(bpy.data.filepath)[1])[0]
        job_title += ' %s ' % bl_view_layer
        job_title += " frames %d-%d" % (frame_begin, frame_end) if frame_end \
            else " frame %d" % frame_begin


        job.title = str(job_title)
        
        job.serialsubtasks = True
        job.service = 'PixarRender'
        self.add_job_level_attrs(job)

        threads = self.bl_scene.renderman.batch_threads
        anim = (frame_begin != frame_end)

        tasktitle = "Render %s" % (str(scene_name))
        parent_task = author.Task()
        parent_task.title = tasktitle

        self.generate_rib_render_tasks(anim, parent_task, tasktitle,
                                frame_begin, frame_end, by, threads)
        job.addChild(parent_task)

        # Don't denoise if we're baking
        if rm.ai_denoiser_launch and rm.hider_type == 'RAYTRACE':
            parent_task = self.generate_aidenoise_tasks(frame_begin, frame_end, by)
                
            if parent_task:
                job.addChild(parent_task)

        bl_filename = bpy.data.filepath
        if bl_filename == '':
            jobfile = string_utils.expand_string('<OUT>/<scene>.<layer>.alf', 
                                                asFilePath=True)            
        else:
            jobfile = os.path.splitext(bl_filename)[0] + '.%s.alf' % bl_view_layer.replace(' ', '_')        

        jobFileCleanup = author.Command(local=False)
        jobFileCleanup.argv = ["TractorBuiltIn", "File", "delete",
                                 "%%D(%s)" % jobfile]
        job.addCleanup(jobFileCleanup)

        try:
            f = open(jobfile, 'w')
            as_tcl = job.asTcl()
            f.write(as_tcl)
            f.close()
        except IOError as ioe:
            rfb_log().error('IO Exception when writing job file %s: %s' % (jobfile, str(ioe)))
            return
        except Exception as e:
            rfb_log().error('Could not write job file %s: %s' % (jobfile, str(e)))
            return

        self.spool(job, jobfile)
        string_utils.update_frame_token(frame_current)

    def spool(self, job, jobfile):

        env = dict(os.environ)
        # if $OCIO is undefined, use filmic blender config
        if not env.get('OCIO', None):
            env['OCIO'] = os.path.join(os.environ['RMANTREE'], 'lib', 'ocio', 'filmic-blender', 'config.ocio')

        for i in env:
            if not isinstance(env[i], str):
                env[i] = str(env[i])        

        args = list()

        if self.is_localqueue:
            lq = envconfig().rman_lq_path
            args.append(lq)
            args.append(jobfile)
            rfb_log().info('Spooling job to LocalQueue: %s.', jobfile)
            subprocess.Popen(args, env=env)
        else:
            # spool to tractor
            tractor_engine = get_pref("rman_tractor_hostname")
            tractor_port = str(get_pref("rman_tractor_port"))
            owner = getpass.getuser()
            if not get_pref("rman_tractor_local_user"):
                owner = get_pref("rman_tractor_user")

            tractor_engine = self.tractor_cfg.get('engine', tractor_engine)
            tractor_port = str(self.tractor_cfg.get('port', tractor_port))
            owner = self.tractor_cfg.get('user', owner)            

            # env var trumps rfb.json
            tractor_env = envconfig().getenv('TRACTOR_ENGINE')
            if tractor_env:
                tractor_env = tractor_env.split(':')
                tractor_engine = tractor_env[0]
                if len(tractor_env) > 1:
                    tractor_port = tractor_env[1]

            owner = envconfig().getenv('TRACTOR_USER', owner)            

            try:
                spoolhost = socket.gethostname()
                job.spool(block=True, spoolfile=jobfile, spoolhost=spoolhost,
                        owner=owner, hostname=tractor_engine,
                        port=int(tractor_port))
                rfb_log().info('Spooling to Tractor Engine: %s:%s, Job File: %s', tractor_engine,
                            tractor_port, jobfile)
            except author.SpoolError as spoolError:
                rfb_log().error("Cannot spool to Tractor: %s" % str(spoolError))

            except Exception as e:
                rfb_log().error("Cannot spool to Tractor: %s" % str(e))
                