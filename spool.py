import bpy
import os
import time
from .util import user_path


def end_block(f, indent_level):
    f.write("%s}\n" % ('\t' * indent_level))


def write_parent_task_line(f, title, serial_subtasks, indent_level):
    f.write("%sTask {%s} -serialsubtasks %d -subtasks {\n" %
            ('\t' * indent_level, title, int(serial_subtasks)))


def write_cmd_task_line(f, title, cmds, indent_level):
    f.write("%sTask {%s} -cmds {\n" % ('\t' * indent_level, title))
    for key, cmd in cmds:
        f.write("%sRemoteCmd -service {%s} {%s}\n" % ('\t' * (indent_level + 1),
                                                      key, " ".join(cmd)))
    f.write("%s}\n" % ('\t' * indent_level))


def txmake_task(f, title, in_name, out_name, options, indent_level):
    cmd = ['txmake'] + options + ['-newer'] + [in_name, out_name]
    write_cmd_task_line(f, title, [('PixarRender', cmd)], indent_level)


def quote(filename):
    return '"%s"' % filename


def spool_render(rman_version_short, rib_files, denoise_files, denoise_aov_files, frame_begin, frame_end=None, denoise=None, context=None,
                 job_texture_cmds=[], frame_texture_cmds={}, rpass=None):
    prefs = bpy.context.user_preferences.addons[__package__].preferences

    out_dir = prefs.env_vars.out
    cdir = user_path(out_dir)
    scene = context.scene
    rm = scene.renderman

    alf_file = os.path.join(cdir, 'spool_%s.alf' %
                            time.strftime("%m%d%y%H%M%S"))
    per_frame_denoise = denoise == 'frame'
    crossframe_denoise = denoise == 'crossframe'

    # open file
    f = open(alf_file, 'w')
    # write header
    f.write('##AlfredToDo 3.0\n')
    # job line
    job_title = 'untitled' if not bpy.data.filepath else \
        os.path.splitext(os.path.split(bpy.data.filepath)[1])[0]
    job_title += " frames %d-%d" % (frame_begin, frame_end) if frame_end \
        else " frame %d" % frame_begin
    if per_frame_denoise:
        job_title += ' per-frame denoise'
    elif crossframe_denoise:
        job_title += ' crossframe_denoise'
    job_params = {
        'title': job_title,
        'serialsubtasks': 1,
        'envkey': 'prman-%s' % rman_version_short,
        'comment': 'Created by RenderMan for Blender'
    }
    job_str = 'Job'
    for key, val in job_params.items():
        if key == 'serialsubtasks':
            job_str += " -%s %s" % (key, str(val))
        else:
            job_str += " -%s {%s}" % (key, str(val))
    f.write(job_str + ' -subtasks {' + '\n')

    # collect textures find frame specific and job specific
    if job_texture_cmds:
        write_parent_task_line(f, 'Job Textures', False, 1)
    # do job tx makes
    for in_name, out_name, options in job_texture_cmds:
        in_name = bpy.path.abspath(in_name)
        out_name = os.path.join(rpass.paths['texture_output'], out_name)
        txmake_task(f, "TxMake %s" % os.path.split(in_name)
                    [-1], quote(in_name), quote(out_name), options, 2)
    if job_texture_cmds:
        end_block(f, 1)

    write_parent_task_line(f, 'Frame Renders', False, 1)
    # for frame
    if frame_end is None:
        frame_end = frame_begin
    for frame_num in range(frame_begin, frame_end + 1):
        if frame_num in frame_texture_cmds or denoise:
            write_parent_task_line(f, 'Frame %d' % frame_num, True, 2)

        # do frame specic txmake
        if frame_num in frame_texture_cmds:
            write_parent_task_line(f, 'Frame %d textures' %
                                   frame_num, False, 3)
            for in_name, out_name, options in frame_texture_cmds[frame_num]:
                in_name = bpy.path.abspath(in_name)
                out_name = os.path.join(
                    rpass.paths['texture_output'], out_name)
                txmake_task(f, "TxMake %s" % os.path.split(in_name)
                            [-1], quote(in_name), quote(out_name), options, 4)
            end_block(f, 3)

        # render frame
        cmd_str = ['prman', '-Progress', '-cwd', quote(cdir), '-t:%d' %
                   rm.threads, quote(rib_files[frame_num - frame_begin])]
        if rm.enable_checkpoint:
            if rm.render_limit == 0:
                cmd_str.insert(5, '-checkpoint %d%s' %
                               (rm.checkpoint_interval, rm.checkpoint_type))
            else:
                cmd_str.insert(5, '-checkpoint %d%s,%d%s' % (
                    rm.checkpoint_interval, rm.checkpoint_type, rm.render_limit, rm.checkpoint_type))
        if rm.recover:
            cmd_str.insert(5, '-recover 1')
        if rm.custom_cmd != '':
            cmd_str.insert(5, rm.custom_cmd)
        write_cmd_task_line(f, 'Render frame %d' % frame_num, [('PixarRender',
                                                                cmd_str)], 3)

        # denoise frame
        if per_frame_denoise:
            denoise_options = []
            if rm.denoise_cmd != '':
                denoise_options.append(rm.denoise_cmd)
            if rm.spool_denoise_aov and denoise_aov_files != []:
                denoise_options.insert(0, '--filtervariance 1')
                cmd_str = ['denoise'] + denoise_options + [quote(denoise_files[
                    frame_num - frame_begin][0])] + [" ".join([quote(file) for file in
                                                               denoise_aov_files[frame_num - frame_begin]])]
            else:
                if rm.denoise_gpu:
                    denoise_options.append('--override gpuIndex 0 --')
                cmd_str = ['denoise'] + denoise_options + \
                    [quote(denoise_files[
                    frame_num - frame_begin][0])]
            write_cmd_task_line(f, 'Denoise frame %d' % frame_num,
                                [('PixarRender', cmd_str)], 3)
        elif crossframe_denoise:
            denoise_options = ['--crossframe -v variance', '-F 1', '-L 1']
            if rm.spool_denoise_aov and denoise_aov_files != []:
                denoise_options.append('--filtervariance 1')
            if rm.denoise_cmd != '':
                denoise_options.append(rm.denoise_cmd)
            if rm.denoise_gpu and not rm.spool_denoise_aov:
                denoise_options.append('--override gpuIndex 0 --')
            if frame_num - frame_begin < 1:
                pass
            elif frame_num - frame_begin == 1:
                denoise_options.remove('-F 1')
                cmd_str = ['denoise'] + denoise_options + [quote(f[0])
                                                           for f in denoise_files[0:2]]
                if rm.spool_denoise_aov and denoise_aov_files != []:
                    files = [quote(item) for sublist in denoise_aov_files[0:2]
                             for item in sublist]
                    cmd_str = ['denoise'] + denoise_options + [quote(f[0])
                                                               for f in denoise_files[0:2]] + files
                write_cmd_task_line(f, 'Denoise frame %d' % (frame_num - 1),
                                    [('PixarRender', cmd_str)], 3)
            else:
                cmd_str = ['denoise'] + denoise_options + [quote(f[0])
                                                           for f in denoise_files[frame_num - frame_begin - 2: frame_num - frame_begin + 1]]
                if rm.spool_denoise_aov and denoise_aov_files != []:
                    files = [quote(item) for sublist in denoise_aov_files[
                        frame_num - frame_begin - 2: frame_num - frame_begin + 1] for item in sublist]
                    cmd_str = ['denoise'] + denoise_options + [quote(f[0])
                                                               for f in denoise_files[frame_num - frame_begin - 2: frame_num - frame_begin + 1]] + files
                write_cmd_task_line(f, 'Denoise frame %d' % (frame_num - 1),
                                    [('PixarRender', cmd_str)], 3)
            if frame_num == frame_end:
                denoise_options.remove('-L 1')
                cmd_str = ['denoise'] + denoise_options + [quote(f[0])
                                                           for f in denoise_files[frame_num - frame_begin - 1: frame_num - frame_begin + 1]]
                if rm.spool_denoise_aov and denoise_aov_files != []:
                    files = [quote(item) for sublist in denoise_aov_files[
                        frame_num - frame_begin - 1: frame_num - frame_begin + 1] for item in sublist]
                    cmd_str = ['denoise'] + denoise_options + [quote(f[0])
                                                               for f in denoise_files[frame_num - frame_begin - 1: frame_num - frame_begin + 1]] + files

                write_cmd_task_line(f, 'Denoise frame %d' % frame_num,
                                    [('PixarRender', cmd_str)], 3)

        # if len(frame_texture_cmds) or per_frame_denoise:
        if denoise or frame_num in frame_texture_cmds:
            end_block(f, 2)
    end_block(f, 1)

    # end job
    f.write("}\n")
    f.close()
    return alf_file
