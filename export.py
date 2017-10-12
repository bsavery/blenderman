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
import math
import mathutils
import os
import sys
import time
import traceback
import platform
from mathutils import Matrix, Vector, Quaternion, Euler

from . import bl_info

from .util import rib, rib_path, rib_ob_bounds
from .util import make_frame_path
from .util import init_env
from .util import get_sequence_path
from .util import user_path
from .util import path_list_convert, get_real_path
from .util import get_properties, check_if_archive_dirty
from .util import locate_openVDB_cache
from .util import debug, get_addon_prefs

from .util import find_it_path
from .nodes import export_shader_nodetree, get_textures, get_textures_for_node, get_tex_file_name
from .nodes import shader_node_rib, get_mat_name
from .nodes import replace_frame_num

addon_version = bl_info['version']

# ------------- Atom's helper functions -------------
GLOBAL_ZERO_PADDING = 5
# Objects that can be exported as a polymesh via Blender to_mesh() method.
# ['MESH','CURVE','FONT']
SUPPORTED_INSTANCE_TYPES = ['MESH', 'CURVE', 'FONT', 'SURFACE']
SUPPORTED_DUPLI_TYPES = ['FACES', 'VERTS', 'GROUP']    # Supported dupli types.
# These object types can have materials.
MATERIAL_TYPES = ['MESH', 'CURVE', 'FONT']
# Objects without to_mesh() conversion capabilities.
EXCLUDED_OBJECT_TYPES = ['LAMP', 'CAMERA', 'ARMATURE']
# Only these light types affect volumes.
VOLUMETRIC_LIGHT_TYPES = ['SPOT', 'AREA', 'POINT']
MATERIAL_PREFIX = "mat_"
TEXTURE_PREFIX = "tex_"
MESH_PREFIX = "me_"
CURVE_PREFIX = "cu_"
GROUP_PREFIX = "group_"
MESHLIGHT_PREFIX = "meshlight_"
PSYS_PREFIX = "psys_"
DUPLI_PREFIX = "dupli_"
DUPLI_SOURCE_PREFIX = "dup_src_"


def get_matrix_for_object(passedOb):
    if passedOb.parent:
        mtx = Matrix.Identity(4)
    else:
        mtx = passedOb.matrix_world
    return mtx


# check for a singular matrix
def is_singular(mtx):
    return mtx[0][0] == 0.0 and mtx[1][1] == 0.0 and mtx[2][2] == 0.0


# export the instance of an object (dupli)
def export_object_instance(ri, mtx=None, instance_handle=None, num=None):
    if mtx and not is_singular(mtx):
        ri.AttributeBegin()
        ri.Attribute("identifier", {"int id": num})
        ri.Transform(rib(mtx))
        ri.ObjectInstance(instance_handle)
        ri.AttributeEnd()


# ------------- Filtering -------------
def is_visible_layer(scene, ob):

    for i in range(len(scene.layers)):
        if scene.layers[i] and ob.layers[i]:
            return True
    return False


def is_renderable(scene, ob):
    return (is_visible_layer(scene, ob) and not ob.hide_render) or \
        (ob.type in ['ARMATURE', 'LATTICE', 'EMPTY'] and ob.dupli_type not in SUPPORTED_DUPLI_TYPES)
    # and not ob.type in ('CAMERA', 'ARMATURE', 'LATTICE'))


def is_renderable_or_parent(scene, ob):
    if ob.type == 'CAMERA':
        return True
    if is_renderable(scene, ob):
        return True
    elif hasattr(ob, 'children') and ob.children:
        for child in ob.children:
            if is_renderable_or_parent(scene, child):
                return True
    return False


def is_data_renderable(scene, ob):
    return (is_visible_layer(scene, ob) and not ob.hide_render and ob.type not in ('EMPTY', 'ARMATURE', 'LATTICE'))


def renderable_objects(scene):
    return [ob for ob in scene.objects if (is_renderable(scene, ob) or is_data_renderable(scene, ob))]


# ------------- Archive Helpers -------------
# Generate an automatic path to write an archive when
# 'Export as Archive' is enabled
def auto_archive_path(paths, objects, create_folder=False):
    filename = objects[0].name + ".rib"

    if os.getenv("ARCHIVE") is not None:
        archive_dir = os.getenv("ARCHIVE")
    else:
        archive_dir = os.path.join(paths['export_dir'], "archives")

    if create_folder and not os.path.exists(archive_dir):
        os.mkdir(archive_dir)

    return os.path.join(archive_dir, filename)


def archive_objects(scene):
    archive_obs = []

    for ob in renderable_objects(scene):
        # explicitly set
        if ob.renderman.export_archive:
            archive_obs.append(ob)

        # particle instances
        for psys in ob.particle_systems:
            rm = psys.settings.renderman
            if rm.particle_type == 'OBJECT':
                try:
                    ob = bpy.data.objects[rm.particle_instance_object]
                    archive_obs.append(ob)
                except:
                    pass

        # dupli objects (TODO)

    return archive_obs


# ------------- Data Access Helpers -------------
def get_subframes(segs, scene):
    if segs == 0:
        return []
    min = -1.0
    rm = scene.renderman
    shutter_interval = rm.shutter_angle / 360.0
    if rm.shutter_timing == 'CENTER':
        min = 0 - .5 * shutter_interval
    elif rm.shutter_timing == 'PRE':
        min = 0 - shutter_interval
    elif rm.shutter_timing == 'POST':
        min = 0

    return [min + i * shutter_interval / (segs - 1) for i in range(segs)]


def is_subd_last(ob):
    return ob.modifiers and \
        ob.modifiers[len(ob.modifiers) - 1].type == 'SUBSURF'


def is_subd_displace_last(ob):
    if len(ob.modifiers) < 2:
        return False

    return (ob.modifiers[len(ob.modifiers) - 2].type == 'SUBSURF' and
            ob.modifiers[len(ob.modifiers) - 1].type == 'DISPLACE')


def is_subdmesh(ob):
    return (is_subd_last(ob) or is_subd_displace_last(ob))


# XXX do this better, perhaps by hooking into modifier type data in RNA?
# Currently assumes too much is deforming when it isn't
def is_deforming(ob):
    deforming_modifiers = ['ARMATURE', 'MESH_SEQUENCE_CACHE', 'CAST', 'CLOTH', 'CURVE', 'DISPLACE',
                           'HOOK', 'LATTICE', 'MESH_DEFORM', 'SHRINKWRAP', 'EXPLODE',
                           'SIMPLE_DEFORM', 'SMOOTH', 'WAVE', 'SOFT_BODY',
                           'SURFACE', 'MESH_CACHE', 'FLUID_SIMULATION',
                           'DYNAMIC_PAINT']
    if ob.modifiers:
        # special cases for auto subd/displace detection
        if len(ob.modifiers) == 1 and is_subd_last(ob):
            return False
        if len(ob.modifiers) == 2 and is_subd_displace_last(ob):
            return False

        for mod in ob.modifiers:
            if mod.type in deforming_modifiers:
                return True
    if ob.data and hasattr(ob.data, 'shape_keys') and ob.data.shape_keys:
        return True

    return is_deforming_fluid(ob)


# handle special case of fluid sim a bit differently
def is_deforming_fluid(ob):
    if ob.modifiers:
        mod = ob.modifiers[len(ob.modifiers) - 1]
        return mod.type == 'SMOKE' and mod.smoke_type == 'DOMAIN'


def psys_name(ob, psys):
    return "%s.%s-%s" % (ob.name, psys.name, psys.settings.type)


# if we don't replace slashes could end up with them in file names
def fix_name(name):
    return name.replace('/', '')

# get a name for the data block.  if it's modified by the obj we need it
# specified


def data_name(ob, scene):
    if not ob:
        return ''

    if not ob.data:
        return fix_name(ob.name)

    # if this is a blob return the family name
    if ob.type == 'META':
        return fix_name(ob.name.split('.')[0])

    if is_smoke(ob) or ob.renderman.primitive == 'RI_VOLUME':
        return "%s-VOLUME" % fix_name(ob.name)

    if ob.data.users > 1 and (ob.is_modified(scene, "RENDER") or
                              ob.is_deform_modified(scene, "RENDER") or
                              ob.renderman.primitive != 'AUTO' or
                              (ob.renderman.motion_segments_override and
                               is_deforming(ob))):
        return "%s.%s-MESH" % (fix_name(ob.name), fix_name(ob.data.name))

    else:
        return "%s-MESH" % fix_name(ob.data.name)


def get_name(ob):
    return psys_name(ob) if type(ob) == bpy.types.ParticleSystem \
        else fix_name(ob.data.name)


# ------------- Geometry Access -------------
def get_strands(scene, ob, psys, objectCorrectionMatrix=False):
    # we need this to get st
    if(objectCorrectionMatrix):
        matrix = ob.matrix_world.inverted_safe()
        loc, rot, sca = matrix.decompose()
    psys_modifier = None
    for mod in ob.modifiers:
        if hasattr(mod, 'particle_system') and mod.particle_system == psys:
            psys_modifier = mod
            break

    tip_width = psys.settings.cycles.tip_width * psys.settings.cycles.radius_scale
    base_width = psys.settings.cycles.root_width * psys.settings.cycles.radius_scale
    conwidth = (tip_width == base_width)
    steps = 2 ** psys.settings.render_step
    if conwidth:
        widthString = "constantwidth"
        hair_width = base_width
        debug("info", widthString, hair_width)
    else:
        widthString = "vertex float width"
        hair_width = []

    psys.set_resolution(scene=scene, object=ob, resolution='RENDER')

    num_parents = len(psys.particles)
    num_children = len(psys.child_particles)
    total_hair_count = num_parents + num_children
    export_st = psys.settings.renderman.export_scalp_st and psys_modifier and len(
        ob.data.uv_layers) > 0

    curve_sets = []

    points = []

    vertsArray = []
    scalpS = []
    scalpT = []
    nverts = 0
    for pindex in range(total_hair_count):
        if psys.settings.child_type != 'NONE' and pindex < num_parents:
            continue

        strand_points = []
        # walk through each strand
        for step in range(0, steps + 1):
            pt = psys.co_hair(object=ob, particle_no=pindex, step=step)

            if(objectCorrectionMatrix):
                pt = pt + loc

            if not pt.length_squared == 0:
                strand_points.extend(pt)
            else:
                # this strand ends prematurely
                break

        if len(strand_points) > 1:
            # double the first and last
            strand_points = strand_points[:3] + \
                strand_points + strand_points[-3:]
            vertsInStrand = len(strand_points) // 3
            # for varying width make the width array
            if not conwidth:
                decr = (base_width - tip_width) / (vertsInStrand - 2)
                hair_width.extend([base_width] + [(base_width - decr * i)
                                                  for i in range(vertsInStrand - 2)] +
                                  [tip_width])

            # add the last point again
            points.extend(strand_points)
            vertsArray.append(vertsInStrand)
            nverts += vertsInStrand

            # get the scalp S
            if export_st:
                if pindex >= num_parents:
                    particle = psys.particles[
                        (pindex - num_parents) % num_parents]
                else:
                    particle = psys.particles[pindex]
                st = psys.uv_on_emitter(psys_modifier, particle, pindex)
                scalpS.append(st[0])
                scalpT.append(st[1])

        # if we get more than 100000 vertices, export ri.Curve and reset.  This
        # is to avoid a maxint on the array length
        if nverts > 100000:
            curve_sets.append(
                (vertsArray, points, widthString, hair_width, scalpS, scalpT))

            nverts = 0
            points = []
            vertsArray = []
            if not conwidth:
                hair_width = []
            scalpS = []
            scalpT = []

    if nverts > 0:
        curve_sets.append((vertsArray, points, widthString,
                           hair_width, scalpS, scalpT))

    psys.set_resolution(scene=scene, object=ob, resolution='PREVIEW')

    return curve_sets

# only export particles that are alive,
# or have been born since the last frame


def valid_particle(pa, valid_frames):
    return pa.die_time >= valid_frames[-1] and pa.birth_time <= valid_frames[0]


def get_particles(scene, ob, psys, valid_frames=None):
    P = []
    rot = []
    width = []

    valid_frames = (scene.frame_current,
                    scene.frame_current) if valid_frames is None else valid_frames
    psys.set_resolution(scene, ob, 'RENDER')
    for pa in [p for p in psys.particles if valid_particle(p, valid_frames)]:
        P.extend(pa.location)
        rot.extend(pa.rotation)

        if pa.alive_state != 'ALIVE':
            width.append(0.0)
        else:
            width.append(pa.size)
    psys.set_resolution(scene, ob, 'PREVIEW')
    return (P, rot, width)


def get_mesh(mesh, get_normals=False):
    nverts = []
    verts = []
    P = []
    N = []

    for v in mesh.vertices:
        P.extend(v.co)

    for p in mesh.polygons:
        nverts.append(p.loop_total)
        verts.extend(p.vertices)
        if get_normals:
            if p.use_smooth:
                for vi in p.vertices:
                    N.extend(mesh.vertices[vi].normal)
            else:
                N.extend(list(p.normal) * p.loop_total)

    if len(verts) > 0:
        P = P[:int(max(verts) + 1) * 3]
    # return the P's minus any unconnected
    return (nverts, verts, P, N)


# requires facevertex interpolation
def get_mesh_uv(mesh, name=""):
    uvs = []
    if not name:
        uv_loop_layer = mesh.uv_layers.active
    else:
        # assuming uv loop layers and uv textures share identical indices
        idx = mesh.uv_textures.keys().index(name)
        uv_loop_layer = mesh.uv_layers[idx]

    if uv_loop_layer is None:
        return None

    for uvloop in uv_loop_layer.data:
        uvs.append(uvloop.uv.x)
        uvs.append(1.0 - uvloop.uv.y)
        # renderman expects UVs flipped vertically from blender

    return uvs


# requires facevertex interpolation
def get_mesh_vcol(mesh, name=""):
    vcol_layer = mesh.vertex_colors[name] if name != "" \
        else mesh.vertex_colors.active
    cols = []

    if vcol_layer is None:
        return None

    for vcloop in vcol_layer.data:
        cols.extend(vcloop.color)

    return cols

# requires per-vertex interpolation


def get_mesh_vgroup(ob, mesh, name=""):
    vgroup = ob.vertex_groups[name] if name != "" else ob.vertex_groups.active
    weights = []

    if vgroup is None:
        return None

    for v in mesh.vertices:
        if len(v.groups) == 0:
            weights.append(0.0)
        else:
            weights.extend([g.weight for g in v.groups
                            if g.group == vgroup.index])

    return weights

# if a mesh has more than one material


def is_multi_material(mesh):
    if type(mesh) != bpy.types.Mesh or len(mesh.materials) < 2 \
            or len(mesh.polygons) == 0:
        return False
    first_mat = mesh.polygons[0].material_index
    for p in mesh.polygons:
        if p.material_index != first_mat:
            return True
    return False


def get_primvars(ob, geo, interpolation=""):
    primvars = {}
    if ob.type != 'MESH':
        return primvars

    rm = ob.data.renderman

    interpolation = 'facevarying' if not interpolation else interpolation

    # get material id if this is a multi-material mesh
    if is_multi_material(geo):
        primvars["uniform float material_id"] = rib([p.material_index
                                                     for p in geo.polygons])

    if rm.export_default_uv:
        uvs = get_mesh_uv(geo)
        if uvs and len(uvs) > 0:
            primvars["%s float[2] st" % interpolation] = uvs
    if rm.export_default_vcol:
        vcols = get_mesh_vcol(geo)
        if vcols and len(vcols) > 0:
            primvars["%s color Cs" % interpolation] = rib(vcols)

    # custom prim vars
    for p in rm.prim_vars:
        if p.data_source == 'VERTEX_COLOR':
            vcols = get_mesh_vcol(geo, p.data_name)
            if vcols and len(vcols) > 0:
                primvars["%s color %s" % (interpolation, p.name)] = rib(vcols)

        elif p.data_source == 'UV_TEXTURE':
            uvs = get_mesh_uv(geo, p.data_name)
            if uvs and len(uvs) > 0:
                primvars["%s float[2] %s" % (interpolation, p.name)] = uvs

        elif p.data_source == 'VERTEX_GROUP':
            weights = get_mesh_vgroup(ob, geo, p.data_name)
            if weights and len(weights) > 0:
                primvars["vertex float %s" % p.name] = weights

    return primvars


def get_primvars_particle(scene, psys, subframes):
    primvars = {}
    rm = psys.settings.renderman
    cfra = scene.frame_current

    for p in rm.prim_vars:
        pvars = []

        if p.data_source in ('VELOCITY', 'ANGULAR_VELOCITY'):
            if p.data_source == 'VELOCITY':
                for pa in \
                        [p for p in psys.particles if valid_particle(p, subframes)]:
                    pvars.extend(pa.velocity)
            elif p.data_source == 'ANGULAR_VELOCITY':
                for pa in \
                        [p for p in psys.particles if valid_particle(p, subframes)]:
                    pvars.extend(pa.angular_velocity)

            primvars["uniform float[3] %s" % p.name] = pvars

        elif p.data_source in \
                ('SIZE', 'AGE', 'BIRTH_TIME', 'DIE_TIME', 'LIFE_TIME', 'ID'):
            if p.data_source == 'SIZE':
                for pa in \
                        [p for p in psys.particles if valid_particle(p, subframes)]:
                    pvars.append(pa.size)
            elif p.data_source == 'AGE':
                for pa in \
                        [p for p in psys.particles if valid_particle(p, subframes)]:
                    pvars.append((cfra - pa.birth_time) / pa.lifetime)
            elif p.data_source == 'BIRTH_TIME':
                for pa in \
                        [p for p in psys.particles if valid_particle(p, subframes)]:
                    pvars.append(pa.birth_time)
            elif p.data_source == 'DIE_TIME':
                for pa in \
                        [p for p in psys.particles if valid_particle(p, subframes)]:
                    pvars.append(pa.die_time)
            elif p.data_source == 'LIFE_TIME':
                for pa in \
                        [p for p in psys.particles if valid_particle(p, subframes)]:
                    pvars.append(pa.lifetime)
            elif p.data_source == 'ID':
                pvars = [id for id, p in psys.particles.items(
                ) if valid_particle(p, subframes)]

            primvars["varying float %s" % p.name] = pvars

    return primvars


def get_fluid_mesh(scene, ob):

    subframe = scene.frame_subframe

    fluidmod = [m for m in ob.modifiers if m.type == 'FLUID_SIMULATION'][0]
    fluidmeshverts = fluidmod.settings.fluid_mesh_vertices

    mesh = create_mesh(ob, scene)
    (nverts, verts, P, N) = get_mesh(mesh)
    removeMeshFromMemory(mesh.name)

    # use fluid vertex velocity vectors to reconstruct moving points
    P = [P[i] + fluidmeshverts[int(i / 3)].velocity[i % 3] * subframe * 0.5 for
         i in range(len(P))]

    return (nverts, verts, P, N)


def get_subd_creases(mesh):
    creases = []

    # only do creases 1 edge at a time for now,
    # detecting chains might be tricky..
    for e in mesh.edges:
        if e.crease > 0.0:
            creases.append((e.vertices[0], e.vertices[1],
                            e.crease * e.crease * 10))
            # squared, to match blender appareance better
            #: range 0 - 10 (infinitely sharp)
    return creases


def create_mesh(ob, scene):
    # 2 special cases to ignore:
    # subsurf last or subsurf 2nd last +displace last
    reset_subd_mod = False
    if is_subd_last(ob) and ob.modifiers[len(ob.modifiers) - 1].show_render:
        reset_subd_mod = True
        ob.modifiers[len(ob.modifiers) - 1].show_render = False
    # elif is_subd_displace_last(ob):
    #    ob.modifiers[len(ob.modifiers)-2].show_render = False
    #    ob.modifiers[len(ob.modifiers)-1].show_render = False
    mesh = ob.to_mesh(scene, True, 'RENDER', calc_tessface=False,
                      calc_undeformed=True)
    if reset_subd_mod:
        ob.modifiers[len(ob.modifiers) - 1].show_render = True
    return mesh


def modify_light_matrix(m, ob):
    scale = [1.0, 1.0, 1.0]
    if ob.data.type in ['AREA', 'SPOT', 'SUN']:
        data = ob.data
        m2 = Matrix.Rotation(math.radians(180), 4, 'X')
        m = m * m2
        if ob.data.type == 'AREA':
            if data.renderman.area_shape == 'rect':
                scale = [data.size, data.size_y, 1.0]
            elif data.renderman.area_shape == 'disk':
                scale = [data.size, data.size, 1.0]
            elif data.renderman.area_shape == 'sphere':
                # Force uniform scaling.  First rebuild transform w/o scale
                loc, rot, sca = m.decompose()
                med = m.median_scale
                m = (Matrix.Translation(loc) *
                     Matrix.Rotation(rot.angle, 4, rot.axis))
                # Then factor in uniform approximation of old scale
                scale = [data.size * med, data.size * med, data.size * med]
        elif ob.data.type == 'SPOT':
            scale = [0.01, 0.01, 1.0]
    elif ob.data.type == 'POINT':
        scale = [0.001, 0.001, 0.001]
    m *= Matrix.Scale(scale[0], 4, (1.0, 0.0, 0.0))
    m *= Matrix.Scale(scale[1], 4, (0.0, 1.0, 0.0))
    m *= Matrix.Scale(scale[2], 4, (0.0, 0.0, 1.0))

    if ob.data.type in ['HEMI']:
        eul = m.to_euler()
        eul = Euler([eul[0], eul[1], eul[2]], eul.order)
        m = eul.to_matrix().to_4x4()
        m = m * Matrix.Rotation(math.pi, 4, 'Z')
    elif ob.data.renderman.renderman_type not in ["FILTER"]:
        m = m * Matrix.Scale(-1.0, 4, (1, 0, 0))

    return m


def export_transform(ri, instance, concat=False, flatten=False):
    ob = instance.ob
    export_motion_begin(ri, instance.motion_data)

    if instance.transforming and len(instance.motion_data) > 0:
        samples = [sample[1] for sample in instance.motion_data]
    else:
        samples = [ob.matrix_local] if ob.parent and ob.parent_type == "object" and ob.type != 'LAMP'\
            else [ob.matrix_world]
    for m in samples:
        if instance.type == 'LAMP':
            m = modify_light_matrix(m.copy(), ob)

        if concat and ob.parent_type == "object":
            ri.ConcatTransform(rib(m))
            ri.ScopedCoordinateSystem(instance.ob.name)
        else:
            ri.Transform(rib(m))
            ri.ScopedCoordinateSystem(instance.ob.name)
    export_motion_end(ri, instance.motion_data)


def export_object_transform(ri, ob):
    m = ob.parent.matrix_world * ob.matrix_local if ob.parent \
        else ob.matrix_world
    if ob.type == 'LAMP':
        m = modify_light_matrix(m.copy(), ob)
    ri.Transform(rib(m))
    ri.ScopedCoordinateSystem(ob.name)


def export_light_source(ri, lamp):
    names = {'POINT': 'PxrSphereLight', 'SUN': 'PxrDistantLight',
             'SPOT': 'PxrDiskLight', 'HEMI': 'PxrDomeLight', 'AREA': 'PxrRectLight'}
    params = {"float exposure": [lamp.energy * 5.0],
              "__instanceid": lamp.name,
              "color lightColor": rib(lamp.color)}
    if lamp.type not in ['HEMI']:
        params['int areaNormalize'] = 1
    if lamp.type == 'SUN':
        params["float exposure"] = 0
    ri.Light(names[lamp.type], lamp.name, params)


def export_light_filters(ri, lamp, do_coordsys=False):
    rm = lamp.renderman
    for lf in rm.light_filters:
        if lf.filter_name in bpy.data.objects:
            light_filter = bpy.data.objects[lf.filter_name]
            if do_coordsys:
                ri.TransformBegin()
                export_object_transform(ri, light_filter)
                ri.TransformEnd()
            filter_plugin = light_filter.data.renderman.get_light_node()
            params = property_group_to_params(
                filter_plugin, lamp=light_filter.data)
            params['__instanceid'] = light_filter.name
            params['string coordsys'] = light_filter.name
            ri.LightFilter(light_filter.data.renderman.get_light_node_name(
            ), light_filter.data.name, params)


def export_light_shaders(ri, lamp, group_name='', portal_parent=''):
    handle = lamp.name
    rm = lamp.renderman
    # need this for rerendering
    ri.Attribute('identifier', {'string name': handle})

    # do the shader
    light_shader = rm.get_light_node()
    if light_shader:
        # make sure the shape is set on PxrStdAreaLightShape

        params = property_group_to_params(light_shader)
        params['__instanceid'] = handle
        params['string lightGroup'] = group_name
        if hasattr(light_shader, 'iesProfile'):
            params['string iesProfile'] = bpy.path.abspath(
                light_shader.iesProfile)
        if lamp.type == 'SPOT':
            params['float coneAngle'] = math.degrees(lamp.spot_size)
            params['float coneSoftness'] = lamp.spot_blend
        if lamp.type in ['SPOT', 'POINT']:
            params['int areaNormalize'] = 1
        if rm.renderman_type == 'PORTAL' and portal_parent and portal_parent.type == 'LAMP' \
                and portal_parent.data.renderman.renderman_type == 'ENV':
            parent_node = portal_parent.data.renderman.get_light_node()
            parent_params = property_group_to_params(parent_node)
            params['string domeSpace'] = portal_parent.name
            params['string portalName'] = handle
            params['string domeColorMap'] = parent_params[
                'string lightColorMap']
            if 'vector colorMapGamma' in params and params['vector colorMapGamma'] == (1.0, 1.0, 1.0):
                params['vector colorMapGamma'] = parent_params[
                    'vector colorMapGamma']
            if 'float colorMapSaturation' in params and params['float colorMapSaturation'] == 1.0:
                params['float colorMapSaturation'] = parent_params[
                    'float colorMapSaturation']
            params['float intensity'] = parent_params[
                'float intensity'] * params['float intensityMult']
            del params['float intensityMult']
            params['float exposure'] = parent_params['float exposure']
            params['color lightColor'] = [
                i * j for i, j in zip(parent_params['color lightColor'], params['color tint'])]
            del params['color tint']
            if not params['int enableTemperature']:
                params['int enableTemperature'] = parent_params[
                    'int enableTemperature']
                params['float temperature'] = parent_params[
                    'float temperature']
            params['float specular'] *= parent_params['float specular']
            params['float diffuse'] *= parent_params['float diffuse']

        primary_vis = rm.light_primary_visibility
        ri.Attribute("visibility", {'int transmission': 0, 'int indirect': 0,
                                    'int camera': int(primary_vis)})
        ri.Light(rm.get_light_node_name(), handle, params)
    else:
        export_light_source(ri, lamp)


def export_world_rib(ri, world):
    if world and world.renderman.world_rib_box != '':
        export_rib_box(ri, world.renderman.world_rib_box)


def export_world(ri, world, do_geometry=True):
    if not world:
        return

    rm = world.renderman
    # if no shader do nothing!
    if rm.use_renderman_node and rm.renderman_type == 'NONE':
        return
    params = []

    ri.AttributeBegin()

    world_type = rm.renderman_type if rm.use_renderman_node else 'ENV'
    if do_geometry:
        m = Matrix.Identity(4)
        m = m * Matrix.Rotation(math.radians(180), 4, 'Y')
        eul = m.to_euler()
        eul = Euler([-eul[0], -eul[1], eul[2]], eul.order)
        m = eul.to_matrix().to_4x4()
        m2 = Matrix.Rotation(math.radians(180), 4, 'X')
        m = m * m2
        m = m * Matrix.Scale(-1.0, 4, (1, 0, 0))
        ri.Transform(rib(m))
        # No need to name Coordinate System system for world.
        # ri.ShadingRate(rm.shadingrate)

    handle = world.name
    # need this for rerendering
    ri.Attribute('identifier', {'string name': handle})
    # do the light only if nodetree
    # make sure the shape is set on PxrStdAreaLightShape
    light_shader = rm.get_light_node()

    if rm.use_renderman_node:
        plugin_name = rm.get_light_node_name()
        params = property_group_to_params(light_shader)
    else:
        plugin_name = "PxrDomeLight"
        params = {'color lightColor': rib(world.horizon_color)}
    ri.Attribute("visibility", {'int transmission': 0, 'int indirect': 0,
                                'int camera': int(rm.light_primary_visibility)})
    ri.Light(plugin_name, handle, params)

    ri.AttributeEnd()

    ri.Illuminate(handle, rm.illuminates_by_default)


def get_light_group(light_ob):
    scene_rm = bpy.context.scene.renderman
    for lg in scene_rm.light_groups:
        if lg.name != 'All' and light_ob.name in lg.members:
            return lg.name
    return ''


def export_light(ri, instance, instances):
    ob = instance.ob
    lamp = ob.data
    rm = lamp.renderman
    params = []

    # if this is a filter just export the coord sys
    if rm.renderman_type == 'FILTER':
        ri.TransformBegin()
        export_transform(ri, instance)
        ri.TransformEnd()
    else:
        ri.AttributeBegin()
        ri.Attribute("identifier", {"string name": lamp.name})

        if rm.renderman_type == 'PORTAL' and ob.parent and ob.parent.type == 'LAMP' and \
                ob.parent.data.renderman.renderman_type == 'ENV':
            export_transform(ri, instances[ob.parent.name])

        export_transform(ri, instance)

        export_light_filters(ri, lamp)
        child_portals = []
        if rm.renderman_type == 'ENV' and ob.children:
            child_portals = [child for child in ob.children if child.type == 'LAMP' and
                             child.data.renderman.renderman_type == 'PORTAL']
        # if this is an env light and there are portals just do those instead
        # of shader
        if not child_portals:
            export_light_shaders(ri, lamp, get_light_group(ob), ob.parent)

        ri.AttributeEnd()

        if not child_portals:
            # illuminate if illumintaes and not muted
            do_light = rm.illuminates_by_default and not rm.mute
            if bpy.context.scene.renderman.solo_light:
                # check if solo
                do_light = do_light and rm.solo
            ri.Illuminate(lamp.name, do_light)
            for lf in rm.light_filters:
                if lf.filter_name in bpy.data.objects:
                    filter = bpy.data.objects[lf.filter_name].data
                    ri.EnableLightFilter(lamp.name, filter.name,
                                         filter.renderman.illuminates_by_default)


def export_material(ri, mat, handle=None, iterate_instance=False):
    if mat is None:
        return
    rm = mat.renderman

    if mat.node_tree:
        export_shader_nodetree(
            ri, mat, handle, disp_bound=rm.displacementbound,
            iterate_instance=iterate_instance)
    else:
        export_shader(ri, mat)


def export_material_archive(ri, mat):
    if mat:
        ri.ReadArchive('material.' + get_mat_name(mat.name))


def export_motion_begin(ri, motion_data):
    if len(motion_data) > 1:
        ri.MotionBegin([sample[0] for sample in motion_data])


def export_motion_end(ri, motion_data):
    if len(motion_data) > 1:
        ri.MotionEnd()


def export_hair(ri, scene, ob, psys, data, objectCorrectionMatrix=False):
    curves = data if data else get_strands(
        scene, ob, psys, objectCorrectionMatrix)

    for vertsArray, points, widthString, widths, scalpS, scalpT in curves:
        params = {"P": rib(points), widthString: widths, 'uniform integer index': range(len(vertsArray))}
        if len(scalpS):
            params['uniform float scalpS'] = scalpS
            params['uniform float scalpT'] = scalpT
        ri.Curves("cubic", vertsArray, "nonperiodic", params)


def geometry_source_rib(ri, scene, ob):
    rm = ob.renderman
    anim = rm.archive_anim_settings
    blender_frame = scene.frame_current

    if rm.geometry_source == 'ARCHIVE':
        archive_path = \
            rib_path(get_sequence_path(rm.path_archive, blender_frame, anim))
        ri.ReadArchive(archive_path)

    else:
        if rm.procedural_bounds == 'MANUAL':
            min = rm.procedural_bounds_min
            max = rm.procedural_bounds_max
            bounds = [min[0], max[0], min[1], max[1], min[2], max[2]]
        else:
            bounds = rib_ob_bounds(ob.bound_box)

        if rm.geometry_source == 'DELAYED_LOAD_ARCHIVE':
            archive_path = rib_path(get_sequence_path(rm.path_archive,
                                                      blender_frame, anim))
            ri.Procedural("DelayedReadArchive", archive_path, rib(bounds))

        elif rm.geometry_source == 'PROCEDURAL_RUN_PROGRAM':
            path_runprogram = rib_path(rm.path_runprogram)
            ri.Procedural("RunProgram", [path_runprogram,
                                         rm.path_runprogram_args],
                          rib(bounds))

        elif rm.geometry_source == 'DYNAMIC_LOAD_DSO':
            path_dso = rib_path(rm.path_dso)
            ri.Procedural("DynamicLoad", [path_dso, rm.path_dso_initial_data],
                          rib(bounds))

        elif rm.geometry_source == 'OPENVDB':
            openvdb_file = rib_path(replace_frame_num(rm.path_archive))
            params = {"constant string[2] blobbydso:stringargs": [
                openvdb_file, "density"]}
            for channel in rm.openvdb_channels:
                if channel.name != '':
                    params['varying %s %s' % (channel.type, channel.name)] = []
            ri.Volume("blobbydso:impl_openvdb", rib(bounds), [0, 0, 0],
                      params)


def export_blobby_particles(ri, scene, psys, ob, motion_data):
    rm = psys.settings.renderman
    if len(motion_data) > 1:
        export_motion_begin(ri, motion_data)

    subframes = [scene.frame_current + i for (i, data) in motion_data]

    for (i, (P, rot, widths)) in motion_data:
        op = []
        count = len(widths)
        for i in range(count):
            op.append(1001)  # only blobby ellipsoids for now...
            op.append(i * 16)
        tform = []
        for i in range(count):
            loc = Vector((P[i * 3 + 0], P[i * 3 + 1], P[i * 3 + 2]))
            rotation = Quaternion((rot[i * 4 + 0], rot[i * 4 + 1],
                                   rot[i * 4 + 2], rot[i * 4 + 3]))
            scale = rm.width if rm.constant_width else widths[i]
            mtx = Matrix.Translation(loc) * rotation.to_matrix().to_4x4() \
                * Matrix.Scale(scale, 4)
            tform.extend(rib(mtx))

        op.append(0)  # blob operation:add
        op.append(count)
        for n in range(count):
            op.append(n)

        st = ('',)
        parm = get_primvars_particle(scene, psys, subframes)
        ri.Blobby(count, op, tform, st, parm)
    if len(motion_data) > 1:
        ri.MotionEnd()


def export_particle_instances(ri, scene, rpass, psys, ob, motion_data, type='OBJECT'):
    rm = psys.settings.renderman

    params = get_primvars_particle(
        scene, psys, [scene.frame_current + i for (i, data) in motion_data])

    if type == 'OBJECT':
        master_ob = bpy.data.objects[rm.particle_instance_object]
        # first call object Begin and read in archive of the master
        deforming = is_deforming(master_ob)
        master_archive = get_archive_filename(data_name(master_ob, scene), rpass, deforming,
                                              relative=True)

    instance_handle = ri.ObjectBegin()
    if type == 'OBJECT':
        ri.ReadArchive(master_archive)
    elif type == 'sphere':
        ri.Sphere(1.0, -1.0, 1.0, 360.0)
    else:
        ri.Disk(0, 1.0, 360.0)
    ri.ObjectEnd()

    if type == 'OBJECT' and rm.use_object_material and len(master_ob.data.materials) > 0:
        export_material_archive(ri, master_ob.data.materials[0])

    width = rm.width

    num_points = len(motion_data[0][1][2])
    for i in range(num_points):
        ri.AttributeBegin()

        if len(motion_data) > 1:
            export_motion_begin(ri, motion_data)

        for (seg, (P, rot, point_width)) in motion_data:
            loc = Vector((P[i * 3 + 0], P[i * 3 + 1], P[i * 3 + 2]))
            rotation = Quaternion((rot[i * 4 + 0], rot[i * 4 + 1],
                                   rot[i * 4 + 2], rot[i * 4 + 3]))
            scale = width if rm.constant_width else point_width[i]
            mtx = Matrix.Translation(loc) * rotation.to_matrix().to_4x4() \
                * Matrix.Scale(scale, 4)

            ri.Transform(rib(mtx))
            ri.CoordinateSystem(ob.name)
        if len(motion_data) > 1:
            ri.MotionEnd()

        instance_params = {}
        for param in params:
            instance_params[param] = params[param][i]

        ri.Attribute("user", instance_params)

        ri.ObjectInstance(instance_handle)
        ri.AttributeEnd()


def export_particle_points(ri, scene, psys, ob, motion_data, objectCorrectionMatrix=False):
    rm = psys.settings.renderman
    if(objectCorrectionMatrix):
        matrix = ob.matrix_world.inverted_safe()
        loc, rot, sca = matrix.decompose()
    if len(motion_data) > 1:
        export_motion_begin(ri, motion_data)

    for (i, (P, rot, width)) in motion_data:
        params = get_primvars_particle(
            scene, psys, [scene.frame_current + i for (i, data) in motion_data])
        params[ri.P] = rib(P)
        params["uniform string type"] = rm.particle_type
        if rm.constant_width:
            params["constantwidth"] = rm.width
        elif rm.export_default_size:
            params["varying float width"] = width
        ri.Points(params)

    if len(motion_data) > 1:
        ri.MotionEnd()

# only for emitter types for now


def export_particles(ri, scene, rpass, ob, psys, data=None, objectCorrectionMatrix=False):

    rm = psys.settings.renderman

    if not data:
        data = [(0, get_particles(scene, ob, psys))]
    # Write object instances or points
    if rm.particle_type == 'particle':
        export_particle_points(ri, scene, psys, ob, data,
                               objectCorrectionMatrix)
    elif rm.particle_type == 'blobby':
        export_blobby_particles(ri, scene, psys, ob, data)
    else:
        export_particle_instances(
            ri, scene, rpass, psys, ob, data, type=rm.particle_type)


def export_comment(ri, comment):
    ri.ArchiveRecord('comment', comment)


def recursive_texture_set(ob):
    mat_set = []
    SUPPORTED_MATERIAL_TYPES = ['MESH', 'CURVE', 'FONT', 'SURFACE']
    if ob.type in SUPPORTED_MATERIAL_TYPES:
        for mat in ob.data.materials:
            if mat:
                mat_set.append(mat)

    for child in ob.children:
        mat_set += recursive_texture_set(child)

    if ob.dupli_group:
        for child in ob.dupli_group.objects:
            mat_set += recursive_texture_set(child)

    return mat_set


def get_texture_list(scene):
    # if not rpass.light_shaders: return

    textures = []
    mats_to_scan = []
    for o in renderable_objects(scene):
        if o.type == 'CAMERA' or o.type == 'EMPTY':
            continue
        elif o.type == 'LAMP':
            if o.data.renderman.get_light_node():
                textures = textures + \
                    get_textures_for_node(o.data.renderman.get_light_node())
        else:
            mats_to_scan += recursive_texture_set(o)
    if scene.world and scene.world.renderman.renderman_type != 'NONE':
        textures = textures + \
            get_textures_for_node(scene.world.renderman.get_light_node())

    # cull duplicates by only doing mats once
    for mat in set(mats_to_scan):
        new_textures = get_textures(mat)
        if new_textures:
            textures.extend(new_textures)
    return textures


def get_select_texture_list(object):
    textures = []
    for mat in set(recursive_texture_set(object)):
        new_textures = get_textures(mat)
        if(new_textures):
            textures.extend(new_textures)
    return textures


def get_texture_list_preview(scene):
    # if not rpass.light_shaders: return
    textures = []
    return get_textures(find_preview_material(scene))


def export_scene_lights(ri, instances):
    # if not rpass.light_shaders: return
    export_comment(ri, '##Light Filters')
    for instance in [inst for name, inst in instances.items() if inst.type == 'LAMP']:
        if instance.ob.data.renderman.renderman_type == 'FILTER':
            export_light(ri, instance, instances)

    export_comment(ri, '##Lights')
    for instance in [inst for name, inst in instances.items() if inst.type == 'LAMP']:
        if instance.ob.data.renderman.renderman_type not in ['FILTER']:
            export_light(ri, instance, instances)


def export_default_bxdf(ri, name):
    # default bxdf a nice grey plastic
    ri.Bxdf("PxrDisney", "default", {
            'color baseColor': [0.18, 0.18, 0.18], 'string __instanceid': name})


def export_shader(ri, mat):
    rm = mat.renderman
    # if rm.surface_shaders.active == '' or not rpass.surface_shaders: return
    name = get_mat_name(mat.name)
    params = {"color baseColor": rib(mat.diffuse_color),
              "float specular": mat.specular_intensity,
              'string __instanceid': get_mat_name(mat.name)}

    if mat.emit:
        params["color emitColor"] = rib(mat.diffuse_color)
    if mat.subsurface_scattering.use:
        params["float subsurface"] = mat.subsurface_scattering.scale
        params["color subsurfaceColor"] = \
            rib(mat.subsurface_scattering.color)
    if mat.raytrace_mirror.use:
        params["float metallic"] = mat.raytrace_mirror.reflect_factor
    ri.Bxdf("PxrDisney", get_mat_name(mat.name), params)


def is_smoke(ob):
    for mod in ob.modifiers:
        if mod.type == "SMOKE" and mod.domain_settings:
            return True
    return False


def detect_primitive(ob):
    if type(ob) == bpy.types.ParticleSystem:
        return ob.settings.type

    rm = ob.renderman

    if rm.primitive == 'AUTO':
        if ob.type == 'MESH':
            if is_subdmesh(ob):
                return 'SUBDIVISION_MESH'
            elif is_smoke(ob):
                return 'SMOKE'
            else:
                return 'POLYGON_MESH'
        elif ob.type == 'CURVE':
            return 'CURVE'
        elif ob.type in ('SURFACE', 'FONT'):
            return 'POLYGON_MESH'
        elif ob.type == "META":
            return "META"
        else:
            return 'NONE'
    else:
        return rm.primitive


def get_curve(curve):
    splines = []

    for spline in curve.splines:
        P = []
        width = []
        npt = len(spline.bezier_points) * 3

        for bp in spline.bezier_points:
            P.extend(bp.handle_left)
            P.extend(bp.co)
            P.extend(bp.handle_right)
            width.append(bp.radius * 0.01)

        # basis = ["bezier", 3, "bezier", 3]
        basis = ["BezierBasis", 3, "BezierBasis", 3]
        if spline.use_cyclic_u:
            period = 'periodic'
            # wrap the initial handle around to the end, to begin on the CV
            P = P[3:] + P[:3]
        else:
            period = 'nonperiodic'
            # remove the two unused handles
            npt -= 2
            P = P[3:-3]

        splines.append((P, width, npt, basis, period))

    return splines


def export_curve(ri, scene, ob, data):
    if ob.type == 'CURVE':
        curves = data if data is not None else get_curve(ob.data)

        for P, width, npt, basis, period in curves:
            ri.Basis(basis[0], basis[1], basis[2], basis[3])
            ri.Curves("cubic", [npt], period, {"P": rib(P), "width": width})

    else:
        debug("error",
              "export_curve: recieved a non-supported object type of [%s]." %
              ob.type)


def export_subdivision_mesh(ri, scene, ob, data=None):
    mesh = data if data is not None else create_mesh(ob, scene)

    # if is_multi_material(mesh):
    #    export_multi_material(ri, mesh)

    creases = get_subd_creases(mesh)
    (nverts, verts, P, N) = get_mesh(mesh)
    # if this is empty continue:
    if nverts == []:
        debug("error empty subdiv mesh %s" % ob.name)
        removeMeshFromMemory(mesh.name)
        return
    tags = ['interpolateboundary', 'facevaryinginterpolateboundary']
    nargs = [1, 0, 1, 0]
    intargs = [ob.data.renderman.interp_boundary,
               ob.data.renderman.face_boundary]
    floatargs = []

    primvars = get_primvars(ob, mesh, "facevarying")
    primvars['P'] = P

    if not is_multi_material(mesh):
        if len(creases) > 0:
            for c in creases:
                tags.append('crease')
                nargs.extend([2, 1])
                intargs.extend([c[0], c[1]])
                floatargs.append(c[2])

        ri.SubdivisionMesh("catmull-clark", nverts, verts, tags, nargs,
                           intargs, floatargs, primvars)
    else:
        nargs = [1, 0, 0, 1, 0, 0]
        if len(creases) > 0:
            for c in creases:
                tags.append('crease')
                nargs.extend([2, 1, 0])
                intargs.extend([c[0], c[1]])
                floatargs.append(c[2])

        string_args = []
        for mat_id, faces in \
                get_mats_faces(nverts, primvars).items():
            tags.append("faceedit")
            nargs.extend([2 * len(faces), 0, 3])
            for face in faces:
                intargs.extend([1, face])
            export_material_archive(ri, mesh.materials[mat_id])
            ri.Resource(mesh.materials[mat_id].name, "attributes",
                        {'string operation': 'save',
                         'string subset': 'shading'})
            string_args.extend(['attributes', mesh.materials[mat_id].name,
                                'shading'])
        ri.HierarchicalSubdivisionMesh("catmull-clark", nverts, verts, tags, nargs,
                                       intargs, floatargs, string_args, primvars)

    removeMeshFromMemory(mesh.name)


def get_mats_faces(nverts, primvars):
    if "uniform float material_id" not in primvars:
        return {}

    else:
        mats = {}

        for face_id, num_verts in enumerate(nverts):
            mat_id = primvars["uniform float material_id"][face_id]
            if mat_id not in mats:
                mats[mat_id] = []
            mats[mat_id].append(face_id)
        return mats


def split_multi_mesh(nverts, verts, primvars):
    if "uniform float material_id" not in primvars:
        return {0: (nverts, verts, primvars)}
    else:
        meshes = {}
        vert_index = 0
        for face_id, num_verts in enumerate(nverts):
            mat_id = primvars["uniform float material_id"][face_id]
            if mat_id not in meshes:
                meshes[mat_id] = ([], [], {'P': []})
                for key, val in primvars.items():
                    if "facevarying" not in key:
                        continue
                    meshes[mat_id][2][key] = []

            meshes[mat_id][0].append(num_verts)
            meshes[mat_id][1].extend(verts[vert_index:vert_index + num_verts])
            for key, val in primvars.items():
                if "facevarying" not in key:
                    continue
                item_len = 3
                item_type = key.split()[1]
                if "int" in item_type or "float" in item_type:
                    item_len = 1
                    if "[" in item_type:
                        item_len = int(item_type.split('[')[1].split(']')[0])
                meshes[mat_id][2][key].extend(
                    primvars[key][vert_index * item_len:
                                  vert_index * item_len + num_verts * item_len])
            vert_index += num_verts

        # now sort the verts and replace
        for mat_id, mat_mesh in meshes.items():
            unique_verts = sorted(set(mat_mesh[1]))
            vert_mapping = [0] * len(verts)
            for i, v_index in enumerate(unique_verts):
                vert_mapping[v_index] = i
                mat_mesh[2]['P'].extend(
                    primvars['P'][int(v_index * 3):int(v_index * 3) + 3])

            for i, vert_old in enumerate(mat_mesh[1]):
                mat_mesh[1][i] = vert_mapping[vert_old]
        return meshes


def export_polygon_mesh(ri, scene, ob, data=None):
    debug("info", "export_polygon_mesh [%s]" % ob.name)

    mesh = data if data is not None else create_mesh(ob, scene)

    # for multi-material output all those
    (nverts, verts, P, N) = get_mesh(mesh, get_normals=True)
    # if this is empty continue:
    if nverts == []:
        debug("error empty poly mesh %s" % ob.name)
        removeMeshFromMemory(mesh.name)
        return
    primvars = get_primvars(ob, mesh, "facevarying")
    primvars['P'] = P
    primvars['facevarying normal N'] = N
    if not is_multi_material(mesh):
        ri.PointsPolygons(nverts, verts, primvars)
    else:
        for mat_id, (nverts, verts, primvars) in \
                split_multi_mesh(nverts, verts, primvars).items():
            # if this is a multi_material mesh output materials
            export_material_archive(ri, mesh.materials[mat_id])
            ri.PointsPolygons(nverts, verts, primvars)
    removeMeshFromMemory(mesh.name)


def removeMeshFromMemory(passedName):
    # Extra test because this can crash Blender if not done correctly.
    result = False
    mesh = bpy.data.meshes.get(passedName)
    if mesh is not None:
        if mesh.users == 0:
            try:
                mesh.user_clear()
                can_continue = True
            except:
                can_continue = False

            if can_continue:
                try:
                    bpy.data.meshes.remove(mesh)
                    result = True
                except:
                    result = False
            else:
                # Unable to clear users, something is holding a reference to it.
                # Can't risk removing. Favor leaving it in memory instead of
                # risking a crash.
                result = False
    else:
        # We could not fetch it, it does not exist in memory, essentially
        # removed.
        result = True
    return result


def export_points(ri, scene, ob, motion):
    rm = ob.renderman

    mesh = create_mesh(ob, scene)

    motion_blur = ob.name in motion['deformation']

    if motion_blur:
        export_motion_begin(ri, scene, ob)
        samples = motion['deformation'][ob.name]
    else:
        samples = [get_mesh(mesh)]

    for nverts, verts, P, N in samples:
        params = {
            ri.P: rib(P),
            "uniform string type": rm.primitive_point_type,
            "constantwidth": rm.primitive_point_width
        }
        ri.Points(params)

    if motion_blur:
        ri.MotionEnd()

    removeMeshFromMemory(mesh.name)


def export_openVDB(ri, ob):
    cacheFile = locate_openVDB_cache(bpy.context.scene.frame_current)
    if not cacheFile:
        debug('error', "Please save and export OpenVDB files before rendering.")
        return
    params = {"constant string[2] blobbydso:stringargs": [cacheFile, "density:fogvolume"], "varying float density": [],
              "varying float flame": [], "varying float heat": []}
    ri.Volume("blobbydso:impl_openvdb", rib_ob_bounds(ob.bound_box), [0, 0, 0],
              params)


# make an ri Volume from the smoke modifier
def export_smoke(ri, ob):
    smoke_modifier = None
    for mod in ob.modifiers:
        if mod.type == "SMOKE":
            smoke_modifier = mod
            break
    smoke_data = smoke_modifier.domain_settings
    # the original object has the modifier too.
    if not smoke_data:
        return

    if smoke_data.cache_file_format == 'OPENVDB':
        export_openVDB(ri, ob)
        return

    params = {
        "varying float density": smoke_data.density_grid,
        "varying float flame": smoke_data.flame_grid,
        "varying color color": [item for index, item in enumerate(smoke_data.color_grid) if index % 4 != 0]
    }

    smoke_res = rib(smoke_data.domain_resolution)
    if smoke_data.use_high_resolution:
        smoke_res = [(smoke_data.amplify + 1) * i for i in smoke_res]

    ri.Volume("box", rib_ob_bounds(ob.bound_box),
              smoke_res, params)


def export_volume(ri, ob):
    rm = ob.renderman
    ri.Volume("box", rib_ob_bounds(ob.bound_box), [0, 0, 0])


def export_sphere(ri, ob):
    rm = ob.renderman
    ri.Sphere(rm.primitive_radius, rm.primitive_zmin, rm.primitive_zmax,
              rm.primitive_sweepangle)


def export_cylinder(ri, ob):
    rm = ob.renderman
    ri.Cylinder(rm.primitive_radius, rm.primitive_zmin, rm.primitive_zmax,
                rm.primitive_sweepangle)


def export_cone(ri, ob):
    rm = ob.renderman
    ri.Cone(rm.primitive_height, rm.primitive_radius, rm.primitive_sweepangle)


def export_disk(ri, ob):
    rm = ob.renderman
    ri.Disk(rm.primitive_height, rm.primitive_radius, rm.primitive_sweepangle)


def export_torus(ri, ob):
    rm = ob.renderman
    ri.Torus(rm.primitive_majorradius, rm.primitive_minorradius,
             rm.primitive_phimin, rm.primitive_phimax, rm.primitive_sweepangle)


def export_particle_system(ri, scene, rpass, ob, psys, objectCorrectionMatrix=False, data=None):
    if psys.settings.type == 'EMITTER':
        # particles are always deformation
        export_particles(ri, scene, rpass, ob, psys,
                         data, objectCorrectionMatrix)
    else:
        ri.Basis("CatmullRomBasis", 1, "CatmullRomBasis", 1)
        ri.Attribute("dice", {"int roundcurve": int(
            psys.settings.renderman.round_hair), "int hair": 1})
        if data is not None and len(data) > 0:
            export_motion_begin(ri, data)
            for subframe, sample in data:
                export_hair(ri, scene, ob, psys, sample,
                            objectCorrectionMatrix)
            ri.MotionEnd()
        else:
            export_hair(ri, scene, ob, psys, None, objectCorrectionMatrix)

# many thanks to @rendermouse for this code


def export_blobby_family(ri, scene, ob):

    # we are searching the global metaball collection for all mballs
    # linked to the current object context, so we can export them
    # all as one family in RiBlobby

    family = data_name(ob, scene)
    master = bpy.data.objects[family]

    fam_blobs = []

    for mball in bpy.data.metaballs:
        fam_blobs.extend([el for el in mball.elements if get_mball_parent(
            el.id_data).name.split('.')[0] == family])

    # transform
    tform = []

    # opcodes
    op = []
    count = len(fam_blobs)
    for i in range(count):
        op.append(1001)  # only blobby ellipsoids for now...
        op.append(i * 16)

    for meta_el in fam_blobs:

        # Because all meta elements are stored in a single collection,
        # these elements have a link to their parent MetaBall, but NOT the actual tree parent object.
        # So I have to go find the parent that owns it.  We need the tree parent in order
        # to get any world transforms that alter position of the metaball.
        parent = get_mball_parent(meta_el.id_data)

        m = {}
        loc = meta_el.co

        # mballs that are only linked to the master by name have their own position,
        # and have to be transformed relative to the master
        ploc, prot, psc = parent.matrix_world.decompose()

        m = Matrix.Translation(loc)

        sc = Matrix(((meta_el.radius, 0, 0, 0),
                     (0, meta_el.radius, 0, 0),
                     (0, 0, meta_el.radius, 0),
                     (0, 0, 0, 1)))

        ro = prot.to_matrix().to_4x4()

        m2 = m * sc * ro
        tform = tform + rib(parent.matrix_world * m2)

    op.append(0)  # blob operation:add
    op.append(count)
    for n in range(count):
        op.append(n)

    st = ('',)
    parm = {}

    ri.Blobby(count, op, tform, st, parm)


def get_mball_parent(mball):
    for ob in bpy.data.objects:
        if ob.data == mball:
            return ob


def export_geometry_data(ri, scene, ob, data=None):
    prim = ob.renderman.primitive if ob.renderman.primitive != 'AUTO' \
        else detect_primitive(ob)

    # unsupported type
    if prim == 'NONE':
        debug("WARNING", "Unsupported prim type on %s" % (ob.name))

    if prim == 'SPHERE':
        export_sphere(ri, ob)
    elif prim == 'CYLINDER':
        export_cylinder(ri, ob)
    elif prim == 'CONE':
        export_cone(ri, ob)
    elif prim == 'DISK':
        export_disk(ri, ob)
    elif prim == 'TORUS':
        export_torus(ri, ob)
    elif prim == 'RI_VOLUME':
        export_volume(ri, ob)

    elif prim == 'META':
        export_blobby_family(ri, scene, ob)

    elif prim == 'SMOKE':
        export_smoke(ri, ob)

    # curve only
    elif prim == 'CURVE' or prim == 'FONT':
        # If this curve is extruded or beveled it can produce faces from a
        # to_mesh call.
        l = ob.data.extrude + ob.data.bevel_depth
        if l > 0:
            export_polygon_mesh(ri, scene, ob, data)
        else:
            export_curve(ri, scene, ob, data)

    # mesh only
    elif prim == 'POLYGON_MESH':
        export_polygon_mesh(ri, scene, ob, data)
    elif prim == 'SUBDIVISION_MESH':
        export_subdivision_mesh(ri, scene, ob, data)
    elif prim == 'POINTS':
        export_points(ri, ob, data)


def is_transforming(ob, do_mb, recurse=False):
    transforming = (do_mb and ob.animation_data is not None)
    if not transforming and ob.parent:
        transforming = is_transforming(ob.parent, do_mb, recurse=True)
        if not transforming and ob.parent.type == 'CURVE' and ob.parent.data:
            transforming = ob.parent.data.use_path
    return transforming


# Instance holds all the data needed for making an instance of data_block
class Instance:
    name = ''
    type = ''
    transforming = False
    motion_data = []
    archive_filename = ''
    ob = None
    material = None

    def __init__(self, name, type, ob=None,
                 transforming=False):
        self.name = name
        self.type = type
        self.transforming = transforming
        self.ob = ob
        self.motion_data = []
        self.children = []
        self.data_block_names = []
        self.parent = None
        if hasattr(ob, 'parent') and ob.parent:
            self.parent = ob.parent.name
        if hasattr(ob, 'children') and ob.children:
            for child in ob.children:
                self.children.append(child.name)


# Data block holds the info for exporting the archive of a data_block
class DataBlock:
    motion_data = []
    archive_filename = ''
    deforming = False
    type = ''
    data = None
    name = ''
    material = []
    do_export = False
    dupli_data = False

    def __init__(self, name, type, archive_filename, data, deforming=False, material=[], do_export=True, dupli_data=False):
        self.name = name
        self.type = type
        self.archive_filename = archive_filename
        self.deforming = deforming
        self.data = data
        self.motion_data = []
        self.material = material
        self.do_export = do_export
        self.dupli_data = dupli_data


def has_emissive_material(db):
    for mat in db.material:
        if mat and mat.node_tree:
            nt = mat.node_tree

            out = next((n for n in nt.nodes if hasattr(n, 'renderman_node_type') and n.renderman_node_type == 'output'),
                       None)
            if out and out.inputs['Light'].is_linked:
                return True
    return False


def export_for_bake(db):
    for mat in db.material:
        if mat and mat.node_tree:
            for n in mat.node_tree.nodes:
                if n.bl_idname in ("PxrBakeTexturePatternNode", "PxrBakePointCloudPatternNode"):
                    return True
        return False

# return if a psys should be animated
# NB:  we ALWAYS need the animating psys if the emitter is transforming,
# not just if MB is on


def is_psys_animating(ob, psys, do_mb):
    return (psys.settings.frame_start != psys.settings.frame_end) or is_transforming(ob, True, recurse=True)

# constructs a list of instances and data blocks based on objects in a scene
# only the needed for rendering data blocks and instances are cached
# also save a data structure of the set of motion segments with
# instances/datablocks that have the number of motion segments


def get_instances_and_blocks(obs, rpass):
    bake = rpass.bake
    instances = {}
    data_blocks = {}
    motion_segs = {}
    scene = rpass.scene
    mb_on = scene.renderman.motion_blur if not bake else False
    mb_segs = scene.renderman.motion_segments

    for ob in obs:
        inst = get_instance(ob, rpass.scene, mb_on)
        if inst:
            ob_mb_segs = ob.renderman.motion_segments if ob.renderman.motion_segments_override else mb_segs

            # add the instance to the motion segs list if transforming
            if inst.transforming:
                if ob_mb_segs not in motion_segs:
                    motion_segs[ob_mb_segs] = ([], [])
                motion_segs[ob_mb_segs][0].append(inst.name)

            # now get the data_blocks for the instance
            inst_data_blocks = get_data_blocks_needed(ob, rpass, mb_on)
            for db in inst_data_blocks:
                do_db = False if (bake and not export_for_bake(db)) else True

                if do_db and not db.dupli_data:
                    inst.data_block_names.append(db.name)

                # if this data_block is already in the list to export...
                if db.name in data_blocks:
                    continue

                # add data_block to mb list
                if do_db and db.deforming and mb_on:
                    if ob_mb_segs not in motion_segs:
                        motion_segs[ob_mb_segs] = ([], [])
                    motion_segs[ob_mb_segs][1].append(db.name)

                if do_db:
                    data_blocks[db.name] = db

            instances[inst.name] = inst

    return instances, data_blocks, motion_segs

# get the used materials for an object


def get_used_materials(ob):
    if ob.type == 'MESH' and len(ob.data.materials) > 0:
        if len(ob.data.materials) == 1:
            return [ob.data.materials[0]]
        mat_ids = []
        mesh = ob.data
        num_materials = len(ob.data.materials)
        for p in mesh.polygons:
            if p.material_index not in mat_ids:
                mat_ids.append(p.material_index)
            if num_materials == len(mat_ids):
                break
        return [mesh.materials[i] for i in mat_ids]
    else:
        return [ob.active_material]

# get the instance type for this object.
# If no instance needs exporting, return None


def get_instance(ob, scene, do_mb):
    if is_renderable_or_parent(scene, ob):
        return Instance(ob.name, ob.type, ob, is_transforming(ob, do_mb))
    else:
        return None


# get the data_block needed for a dupli
def get_dupli_block(ob, rpass, do_mb):
    if not ob:
        return []

    if hasattr(ob, 'dupli_type') and ob.dupli_type in SUPPORTED_DUPLI_TYPES:
        name = ob.name + '-DUPLI'
        # duplis aren't animated
        dbs = []
        deforming = False
        if ob.dupli_type == 'GROUP' and ob.dupli_group:
            for dupli_ob in ob.dupli_group.objects:
                sub_dbs = get_dupli_block(dupli_ob, rpass, do_mb)
                if not deforming:
                    for db in sub_dbs:
                        if db.deforming:
                            deforming = True
                            break
                dbs.extend(sub_dbs)
        archive_filename = get_archive_filename(name, rpass, deforming)
        dbs.append(DataBlock(name, "DUPLI", archive_filename, ob, deforming=deforming,
                             dupli_data=True,
                             do_export=file_is_dirty(rpass.scene, ob, archive_filename)))
        return dbs

    else:
        name = data_name(ob, rpass.scene)
        deforming = is_deforming(ob)
        archive_filename = get_archive_filename(data_name(ob, rpass.scene),
                                                rpass, deforming)

        return [DataBlock(name, "MESH", archive_filename, ob,
                          deforming, material=get_used_materials(ob),
                          do_export=file_is_dirty(
                              rpass.scene, ob, archive_filename),
                          dupli_data=True)]


# get the data blocks needed for an object
def get_data_blocks_needed(ob, rpass, do_mb):
    if not is_renderable(rpass.scene, ob):
        return []
    data_blocks = []
    emit_ob = True
    dupli_emitted = False
    # get any particle systems, or if a particle sys is duplis
    if len(ob.particle_systems):
        emit_ob = False
        for psys in ob.particle_systems:
            # if this is an objct emitter use dupli
            if psys.settings.use_render_emitter:
                emit_ob = True
            if psys.settings.render_type not in ['OBJECT', 'GROUP']:
                name = psys_name(ob, psys)
                type = 'PSYS'
                data = (ob, psys)
                archive_filename = get_archive_filename(name, rpass,
                                                        is_psys_animating(ob, psys, do_mb))
            else:
                name = ob.name + '-DUPLI'
                type = 'DUPLI'
                archive_filename = get_archive_filename(name, rpass,
                                                        is_psys_animating(ob, psys, do_mb))
                dupli_emitted = True
                data = ob
                if psys.settings.render_type == 'OBJECT':
                    data_blocks.extend(get_dupli_block(
                        psys.settings.dupli_object, rpass, do_mb))
                elif psys.settings.dupli_group:
                    for dupli_ob in psys.settings.dupli_group.objects:
                        data_blocks.extend(
                            get_dupli_block(dupli_ob, rpass, do_mb))

            mat = [ob.material_slots[psys.settings.material -
                                     1].material] if psys.settings.material and psys.settings.material <= len(ob.material_slots) else []
            data_blocks.append(DataBlock(name, type, archive_filename, data,
                                         is_psys_animating(ob, psys, do_mb), material=mat,
                                         do_export=file_is_dirty(rpass.scene, ob, archive_filename)))

    if hasattr(ob, 'dupli_type') and ob.dupli_type in SUPPORTED_DUPLI_TYPES and not dupli_emitted:
        name = ob.name + '-DUPLI'
        # duplis aren't animated
        dupli_deforming = False
        if ob.dupli_type == 'GROUP' and ob.dupli_group:
            for dupli_ob in ob.dupli_group.objects:
                sub_dbs = get_dupli_block(dupli_ob, rpass, do_mb)
                if not dupli_deforming:
                    dupli_deforming = any(db.deforming for db in sub_dbs)
                data_blocks.extend(sub_dbs)
        archive_filename = get_archive_filename(name, rpass, dupli_deforming)
        data_blocks.append(DataBlock(name, "DUPLI", archive_filename, ob, dupli_deforming,
                                     do_export=file_is_dirty(rpass.scene, ob, archive_filename)))

    # now the objects data
    if is_data_renderable(rpass.scene, ob) and emit_ob:
        # Check if the object is referring to an archive to use rather then its
        # geometry.
        if ob.renderman.geometry_source != 'BLENDER_SCENE_DATA':
            name = data_name(ob, rpass.scene)
            deforming = is_deforming(ob)
            archive_filename = bpy.path.abspath(ob.renderman.path_archive)
            data_blocks.append(DataBlock(name, "MESH", archive_filename, ob,
                                         deforming, material=get_used_materials(
                                             ob),
                                         do_export=False))
        else:
            name = data_name(ob, rpass.scene)
            deforming = is_deforming(ob)
            archive_filename = get_archive_filename(data_name(ob, rpass.scene),
                                                    rpass, deforming)
            data_blocks.append(DataBlock(name, "MESH", archive_filename, ob,
                                         deforming, material=get_used_materials(
                                             ob),
                                         do_export=file_is_dirty(rpass.scene, ob, archive_filename)))

    return data_blocks


def relpath_archive(archive_filename, rpass):
    if not archive_filename:
        return ''
    else:
        return os.path.relpath(archive_filename, rpass.paths['archive'])


def file_is_dirty(scene, ob, archive_filename):
    if scene.renderman.lazy_rib_gen:
        return check_if_archive_dirty(ob.renderman.update_timestamp,
                                      archive_filename)
    else:
        return True


def get_transform(instance, subframe):
    if not instance.transforming:
        return
    else:
        ob = instance.ob
        if ob.parent and ob.parent_type == "object":
            mat = ob.matrix_local
        else:
            mat = ob.matrix_world
        instance.motion_data.append((subframe, mat.copy()))


def get_deformation(data_block, subframe, scene, subframes):
    if not data_block.deforming or not data_block.do_export:
        return
    else:
        if data_block.type == "MESH":
            mesh = create_mesh(data_block.data, scene)
            data_block.motion_data.append((subframe, mesh))
        elif data_block.type == "PSYS":
            ob, psys = data_block.data
            if psys.settings.type == "EMITTER":
                begin_frame = scene.frame_current - 1 if subframe == 1 else scene.frame_current
                end_frame = scene.frame_current + 1 if subframe != 1 else scene.frame_current
                points = get_particles(
                    scene, ob, psys, subframes)
                data_block.motion_data.append((subframe, points))
            else:
                # this is hair
                hairs = get_strands(scene, ob, psys)
                data_block.motion_data.append((subframe, hairs))

# Create two lists, one of data blocks to export and one of instances to export
# Collect and store motion blur transformation data in a pre-process.
# More efficient, and avoids too many frame updates in blender.


def cache_motion(scene, rpass, objects=None):
    if objects is None:
        objects = scene.objects
    origframe = scene.frame_current
    instances, data_blocks, motion_segs = \
        get_instances_and_blocks(objects, rpass)

    # the aim here is to do only a minimal number of scene updates,
    # so we process objects in batches of equal numbers of segments
    # and update the scene only once for each of those unique fractional
    # frames per segment set
    for num_segs, (instance_names, data_names) in motion_segs.items():
        # prepare list of frames/sub-frames in advance,
        # ordered from future to present,
        # to prevent too many scene updates
        # (since loop ends on current frame/subframe)
        subframes = get_subframes(num_segs, scene)
        actual_subframes = [origframe + subframe for subframe in subframes]
        for seg in subframes:
            if seg < 0.0:
                scene.frame_set(origframe - 1, 1.0 + seg)
            else:
                scene.frame_set(origframe, seg)

            for name in instance_names:
                get_transform(instances[name], seg)

            for name in data_names:
                get_deformation(data_blocks[name],
                                seg, scene, actual_subframes)

    scene.frame_set(origframe, 0)

    return data_blocks, instances


def get_valid_empties(scene, rpass):
    empties = []
    for object in scene.objects:
        if(object.type == 'EMPTY'):
            if(object.renderman.geometry_source == 'ARCHIVE'):
                empties.append(object)
    return empties


# export data_blocks
def export_data_archives(ri, scene, rpass, data_blocks, engine):
    for name, db in data_blocks.items():
        if not db.do_export:
            continue
        try:
            ri.Begin(db.archive_filename)
            debug('info', db.archive_filename)
            if db.type == "MESH":
                export_mesh_archive(ri, scene, db)
            elif db.type == "PSYS":
                export_particle_archive(ri, scene, rpass, db)
            elif db.type == "DUPLI":
                export_dupli_archive(ri, scene, rpass, db, data_blocks)
            ri.End()
        except Exception as err:
            ri.End()
            if engine:
                engine.report({'ERROR'}, 'Rib gen error exporting %s: ' %
                              db.archive_filename + traceback.format_exc())
            else:
                print('ERROR: Rib gen error exporting %s:' %
                      db.archive_filename, traceback.format_exc())

# Deal with the special needs of a RIB archive but after that pass on to
# the same functions that export_data_archives does.


def export_RIBArchive_data_archive(ri, scene, rpass, data_blocks, exportMaterials, objectMatrix=False, correctionMatrix=False):
    for name, db in data_blocks.items():
        if not db.do_export:
            continue
        if(db.material and exportMaterials):
            # Tell the object to use the baked in material.
            for mat in db.material:
                export_material_archive(ri, mat)
        if db.type == "MESH":
            # Gets the world location and uses the ri transform to set it in
            # the archive.
            if objectMatrix:
                ri.Transform(rib(db.data.matrix_world))
                ri.CoordinateSystem(db.name)
            export_mesh_archive(ri, scene, db)
        elif db.type == "PSYS":
            # ri.Transform(rib(Matrix.Identity(4)))
            export_particle_archive(ri, scene, rpass, db, correctionMatrix)
        elif db.type == "DUPLI":
            export_dupli_archive(ri, scene, rpass, db, data_blocks)


# export each data read archive
def export_instance_read_archive(ri, instance, instances, data_blocks, rpass, is_child=False, visible_objects=None):
    ri.AttributeBegin()
    ri.Attribute("identifier", {"string name": instance.name})
    if instance.ob:
        export_object_attributes(ri, rpass.scene, instance.ob, visible_objects)
    # now the matrix, if we're transforming do the motion here
    if instance.type != 'META':
        export_transform(ri, instance, concat=is_child)

    object_material = False
    if instance.ob and instance.type == 'MESH':
        ob = instance.ob
        object_material = ob.active_material and ob.material_slots[ob.active_material_index].link == 'OBJECT'
        if object_material:
            export_material_archive(ri, ob.active_material)

    for db_name in instance.data_block_names:
        if db_name in data_blocks:
            if(hasattr(data_blocks[db_name].data, 'renderman')):
                if(data_blocks[db_name].data.renderman.geometry_source != 'BLENDER_SCENE_DATA'):
                    export_data_rib_archive(
                        ri, data_blocks[db_name], instance, rpass)
                else:
                    export_data_read_archive(ri, data_blocks[db_name], rpass, skip_material=object_material)
            else:
                export_data_read_archive(ri, data_blocks[db_name], rpass, skip_material=object_material)

        # now the children
    for child_name in instance.children:
        if child_name in instances:
            export_instance_read_archive(
                ri, instances[child_name], instances, data_blocks, rpass, is_child=True, visible_objects=visible_objects)

    if instance.ob and instance.ob.renderman.post_object_rib_box != '':
        export_rib_box(ri, instance.ob.renderman.post_object_rib_box)

    ri.AttributeEnd()


def export_data_read_archive(ri, data_block, rpass, skip_material=False):
    ri.AttributeBegin()

    if not skip_material:
        for mat in data_block.material:
            export_material_archive(ri, mat)

    archive_filename = relpath_archive(data_block.archive_filename, rpass)

    # we want these relative paths of the archive
    if data_block.type == 'MESH' and not rpass.bake:
        # PxrMeshLight can't be in DRA
        if has_emissive_material(data_block):
            ri.ReadArchive(archive_filename)
        else:
            bounds = get_bounding_box(data_block.data)
            params = {"string filename": archive_filename,
                      "float[6] bound": bounds}
            ri.Procedural2(ri.Proc2DelayedReadArchive, ri.SimpleBound, params)
    else:
        if data_block.type != 'DUPLI':
            ri.Transform([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])
            ri.CoordinateSystem(data_block.name)
        ri.ReadArchive(archive_filename)

    ri.AttributeEnd()


def export_data_rib_archive(ri, data_block, instance, rpass):

    ri.AttributeBegin()
    ob = instance.ob
    rm = ob.renderman

    for mat in data_block.material:
        export_material_archive(ri, mat)

    if rm.geometry_source == "ARCHIVE" and ".zip" in instance.ob.renderman.path_archive:
        arvhiveInfo = instance.ob.renderman
        relPath = os.path.splitext(get_real_path(arvhiveInfo.path_archive))[0]
        archiveFileExtention = ".zip"
        objectName = os.path.split(os.path.splitext(relPath)[0])[1]
        archiveAnimated = arvhiveInfo.archive_anim_settings.animated_sequence
        if(archiveAnimated is True):
            current_frame = bpy.context.scene.frame_current
            zero_fill = str(current_frame).zfill(4)
            archive_filename = relPath + archiveFileExtention + \
                "!" + os.path.join(zero_fill, objectName + ".rib")
            ri.ReadArchive(archive_filename)

        else:
            archive_filename = relPath + archiveFileExtention + "!" + objectName + ".rib"
            ri.ReadArchive(archive_filename)
    else:
        geometry_source_rib(ri, rpass.scene, ob)
    ri.AttributeEnd()


def export_empties_archives(ri, ob):
    ri.AttributeBegin()
    ri.Attribute("identifier", {"string name": ob.name})
    # Perform custom transform export since this is the only time empties are
    # exprted.
    matrix = ob.matrix_local
    ri.Transform(rib(matrix))
    ri.CoordinateSystem(ob.name)

    # visible_objects=visible_objects

    arvhiveInfo = ob.renderman
    relPath = os.path.splitext(get_real_path(arvhiveInfo.path_archive))[0]

    archiveFileExtention = ".zip"

    objectName = os.path.split(os.path.splitext(relPath)[0])[1]
    archiveAnimated = arvhiveInfo.archive_anim_settings.animated_sequence

    ri.AttributeBegin()
    if(archiveAnimated is True):
        current_frame = bpy.context.scene.frame_current
        zero_fill = str(current_frame).zfill(4)
        archive_filename = relPath + archiveFileExtention + \
            "!" + os.path.join(zero_fill, objectName + ".rib")
        ri.ReadArchive(archive_filename)

    else:
        archive_filename = relPath + archiveFileExtention + "!" + objectName + ".rib"
        ri.ReadArchive(archive_filename)
    ri.AttributeEnd()


def export_archive(*args):
    pass

# return the filename for a readarchive that this object will be written into
# objects with attached psys's, probably always need to be animated


def get_archive_filename(name, rpass, animated, relative=False):
    path = rpass.paths['frame_archives'] if animated \
        else rpass.paths['static_archives']
    path = os.path.join(path, name + ".rib")
    if relative:
        path = os.path.relpath(path, rpass.paths['archive'])
    return path


def export_rib_box(ri, text_name):
    if text_name not in bpy.data.texts:
        return
    text_block = bpy.data.texts.get(text_name)
    for line in text_block.lines:
        ri.ArchiveRecord(ri.VERBATIM, line.body + "\n")


# here we would export object attributes like holdout, sr, etc
def export_object_attributes(ri, scene, ob, visible_objects):
    # save space! don't export default attribute settings to the RIB
    # shading attributes

    # if ob.renderman.do_holdout:
    #    ri.Attribute("identifier", {"string lpegroup": ob.renderman.lpe_group})
    # gather object groups this object belongs to

    # Adds external RIB to object_attributes
    rm = ob.renderman
    if rm.pre_object_rib_box != '':
        export_rib_box(ri, rm.pre_object_rib_box)

    obj_groups_str = "*"
    for obj_group in scene.renderman.object_groups:
        if ob.name in obj_group.members.keys():
            obj_groups_str += ',' + obj_group.name
    # add to trace sets
    if obj_groups_str != '*':
        ri.Attribute("grouping", {"string membership": obj_groups_str})
        ri.Attribute("identifier", {
                     "string lpegroup": obj_groups_str})

    if ob.renderman.shading_override:
        approx_params = {}
        dice_params = {}
        # output motionfactor always, could not find documented default value?
        if ob.renderman.geometric_approx_focus != -1.0:
            approx_params[
                "float focusfactor"] = ob.renderman.geometric_approx_focus
        if ob.renderman.geometric_approx_motion != 1.0:
            approx_params[
                "float motionfactor"] = ob.renderman.geometric_approx_motion
        if ob.renderman.shadingrate != 1:
            dice_params["float micropolygonlength"] = ob.renderman.shadingrate
        if ob.renderman.watertight:
            dice_params["int watertight"] = 1
        ri.Attribute("dice", dice_params)
        ri.Attribute("Ri", approx_params)

    # visibility attributes
    vis_params = {'int camera': int(ob.renderman.visibility_camera),
                  'int indirect': int(ob.renderman.visibility_trace_indirect),
                  'int transmission': int(ob.renderman.visibility_trace_transmission)}

    if visible_objects and ob.name not in visible_objects:
        vis_params["int camera"] = 0
    ri.Attribute("visibility", vis_params)
    if ob.renderman.matte:
        ri.Matte(ob.renderman.matte)

    # ray tracing attributes
    trace_params = {}
    shade_params = {}
    if ob.renderman.raytrace_intersectpriority != 0:
        trace_params[
            "int intersectpriority"] = ob.renderman.raytrace_intersectpriority
        shade_params["float indexofrefraction"] = ob.renderman.raytrace_ior

    if ob.renderman.holdout:
        trace_params["int holdout"] = 1

    if ob.renderman.raytrace_override:
        if ob.renderman.raytrace_maxdiffusedepth != 1:
            trace_params[
                "int maxdiffusedepth"] = ob.renderman.raytrace_maxdiffusedepth
        if ob.renderman.raytrace_maxspeculardepth != 2:
            trace_params[
                "int maxspeculardepth"] = ob.renderman.raytrace_maxspeculardepth
        if not ob.renderman.raytrace_tracedisplacements:
            trace_params["int displacements"] = 0
        if not ob.renderman.raytrace_autobias:
            trace_params["int autobias"] = 0
            if ob.renderman.raytrace_bias != 0.01:
                trace_params["float bias"] = ob.renderman.raytrace_bias
        if ob.renderman.raytrace_samplemotion:
            trace_params["int samplemotion"] = 1
        if ob.renderman.raytrace_decimationrate != 1:
            trace_params[
                "int decimationrate"] = ob.renderman.raytrace_decimationrate
        if ob.renderman.raytrace_intersectpriority != 0:
            trace_params[
                "int intersectpriority"] = ob.renderman.raytrace_intersectpriority
        if ob.renderman.raytrace_pixel_variance != 1.0:
            shade_params[
                "relativepixelvariance"] = ob.renderman.raytrace_pixel_variance

    if shade_params:
        ri.Attribute("shade", shade_params)
    if trace_params:
        ri.Attribute("trace", trace_params)

    # light linking
    # get links this is a part of
    ll_str = "obj_object>%s" % ob.name
    lls = [ll for ll in scene.renderman.ll if ll_str in ll.name]
    # get links this is a group that is a part of
    for group in scene.renderman.object_groups:
        if ob.name in group.members.keys():
            ll_str = "obj_group>%s" % group.name
            lls += [ll for ll in scene.renderman.ll if ll_str in ll.name]

    # for each light link do illuminates
    for link in lls:
        strs = link.name.split('>')

        scene_lights = [l.name for l in scene.objects if l.type == 'LAMP']
        light_names = [strs[1]] if strs[0] == "lg_light" else \
            scene.renderman.light_groups[strs[1]].members.keys()
        if strs[0] == 'lg_group' and strs[1] == 'All':
            light_names = scene_lights
        for light_name in light_names:
            if link.illuminate != "DEFAULT" and light_name in scene.objects:
                light_ob = scene.objects[light_name]
                lamp = light_ob.data
                if lamp.renderman.renderman_type == 'FILTER':
                    # for each lamp this is a part of do enable light filter
                    filter_name = light_name
                    for light_nm in scene_lights:
                        if filter_name in scene.objects[light_nm].data.renderman.light_filters.keys():
                            ri.EnableLightFilter(
                                light_nm, filter_name, link.illuminate == 'ON')
                else:
                    ri.Illuminate(light_name, link.illuminate == 'ON')

    user_attr = {}
    for i in range(8):
        name = 'MatteID%d' % i
        if getattr(rm, name) != [0.0, 0.0, 0.0]:
            user_attr["color %s" % name] = rib(getattr(rm, name))

    if hasattr(ob, 'color'):
        user_attr["color Cs"] = rib(ob.color[:3])

    if len(user_attr):
        ri.Attribute('user', user_attr)


def get_bounding_box(ob):
    bounds = rib_ob_bounds(ob.bound_box)
    return bounds

# export the archives for an mesh. If this is a
# deforming mesh we'll need to do more than one


def export_mesh_archive(ri, scene, data_block):
    # if we cached a deforming mesh get it.
    motion_data = data_block.motion_data if data_block.deforming else None
    ob = data_block.data

    if motion_data is not None and len(motion_data):
        export_motion_begin(ri, motion_data)
        for (subframes, sample) in motion_data:
            export_geometry_data(ri, scene, ob, data=sample)
        ri.MotionEnd()
    else:
        export_geometry_data(ri, scene, ob)

    data_block.motion_data = None


# export the archives for an mesh. If this is a
# deforming mesh the particle export will handle it
def export_particle_archive(ri, scene, rpass, data_block, objectCorrectionMatrix=False):
    ob, psys = data_block.data
    data = data_block.motion_data if data_block.deforming else None
    export_particle_system(ri, scene, rpass, ob, psys,
                           objectCorrectionMatrix, data=data)
    data_block.motion_data = None

# export the archives for an mesh. If this is a
# deforming mesh the particle export will handle it


def export_dupli_archive(ri, scene, rpass, data_block, data_blocks):
    ob = data_block.data

    ob.dupli_list_create(scene, "RENDER")
    if ob.dupli_type == 'GROUP' and ob.dupli_group:
        for dupob in ob.dupli_list:
            ri.AttributeBegin()
            dupli_name = "%s.DUPLI.%s.%d" % (ob.name, dupob.object.name,
                                             dupob.index)
            ri.Attribute('identifier', {'string name': dupli_name})
            ri.ConcatTransform(
                rib(ob.matrix_world.inverted_safe() * dupob.matrix))
            mat = dupob.object.active_material
            if mat:
                export_material_archive(ri, mat)
            source_data_name = data_name(dupob.object, scene)
            if hasattr(dupob.object, 'dupli_type') and dupob.object.dupli_type in SUPPORTED_DUPLI_TYPES:
                source_data_name = dupob.object.name + '-DUPLI'
            deforming = is_deforming(dupob.object)
            ri.ReadArchive(get_archive_filename(source_data_name, rpass,
                                                deforming, True))
            ri.AttributeEnd()
        ob.dupli_list_clear()
        return

    # gather list of object masters
    object_masters = {}
    for num, dupob in enumerate(ob.dupli_list):
        if dupob.object.name not in object_masters:
            instance_handle = ri.ObjectBegin()
            mat = dupob.object.active_material
            if mat:
                export_material_archive(ri, mat)
            ri.Transform(rib(Matrix.Identity(4)))
            ri.CoordinateSystem(dupob.object.name)

            if dupob.object.renderman.geometry_source == 'ARCHIVE':
                dupob_rm = dupob.object.renderman
                relPath = os.path.splitext(
                    get_real_path(dupob_rm.path_archive))[0]
                archiveFileExtention = ".zip"
                objectName = os.path.split(os.path.splitext(relPath)[0])[1]
                if dupob_rm.archive_anim_settings.animated_sequence:
                    current_frame = bpy.context.scene.frame_current
                    zero_fill = str(current_frame).zfill(4)
                    archive_filename = relPath + archiveFileExtention + \
                        "!" + os.path.join(zero_fill, objectName + ".rib")
                    ri.ReadArchive(archive_filename)
                else:
                    archive_filename = relPath + archiveFileExtention + "!" + objectName + ".rib"
                    ri.ReadArchive(archive_filename)
            else:
                source_data_name = data_name(dupob.object, scene)
                deforming = is_deforming(dupob.object)
                ri.ReadArchive(get_archive_filename(source_data_name, rpass,
                                                    deforming, True))
            ri.ObjectEnd()
            object_masters[dupob.object.name] = instance_handle
            # export "null" bxdf to clear material for object master
            ri.Bxdf("null", "null")

        # dupli_name = "%s.DUPLI.%s.%d" % (ob.name, dupob.object.name,
        #                                 dupob.index)
        instance_handle = object_masters[dupob.object.name]
        export_object_instance(ri, dupob.matrix, instance_handle, num)

    ob.dupli_list_clear()


# export an archive with all the materials and read it back in
def export_materials_archive(ri, rpass, scene):
    archive_filename = user_path(scene.renderman.path_object_archive_static,
                                 scene).replace('{object}', 'materials')
    ri.Begin(archive_filename)
    for mat_name, mat in bpy.data.materials.items():
        ri.ArchiveBegin('material.' + get_mat_name(mat_name))
        # ri.Attribute("identifier", {"name": mat_name})
        export_material(ri, mat)
        ri.ArchiveEnd()
    ri.End()

    ri.ReadArchive(os.path.relpath(archive_filename, rpass.paths['archive']))


def update_timestamp(rpass, obj):
    if obj and rpass.update_time:
        obj.renderman.update_timestamp = rpass.update_time

# takes a list of bpy.types.properties and converts to params for rib


def property_group_to_params(node, lamp=None):
    params = {}
    for prop_name, meta in node.prop_meta.items():
        prop = getattr(node, prop_name)
        # if property group recurse
        if meta['renderman_type'] == 'page' or prop_name == 'notes' or meta['renderman_type'] == 'enum':
            continue
        # if input socket is linked reference that
        else:
            # if struct is not linked continue
            if 'arraySize' in meta:
                params['%s[%d] %s' % (meta['renderman_type'], len(prop),
                                      meta['renderman_name'])] = rib(prop)
            elif ('widget' in meta and meta['widget'] == 'assetIdInput' and prop_name != 'iesProfile'):
                params['%s %s' % (meta['renderman_type'],
                                  meta['renderman_name'])] = \
                    rib(get_tex_file_name(prop),
                        type_hint=meta['renderman_type'])

            else:
                params['%s %s' % (meta['renderman_type'],
                                  meta['renderman_name'])] = \
                    rib(prop, type_hint=meta['renderman_type'])

    if lamp and node.plugin_name in ['PxrBlockerLightFilter', 'PxrRampLightFilter',
                                     'PxrRodLightFilter']:
        rm = lamp.renderman
        nt = lamp.node_tree
        if nt and rm.float_ramp_node in nt.nodes.keys():
            knot_param = 'ramp_Knots' if node.plugin_name == 'PxrRampLightFilter' else 'falloff_Knots'
            float_param = 'ramp_Floats' if node.plugin_name == 'PxrRampLightFilter' else 'falloff_Floats'
            del params['float[16] %s' % knot_param]
            del params['float[16] %s' % float_param]
            float_node = nt.nodes[rm.float_ramp_node]
            curve = float_node.mapping.curves[0]
            knots = []
            vals = []
            # double the start and end points
            knots.append(curve.points[0].location[0])
            vals.append(curve.points[0].location[1])
            for p in curve.points:
                knots.append(p.location[0])
                vals.append(p.location[1])
            knots.append(curve.points[-1].location[0])
            vals.append(curve.points[-1].location[1])
            params['float[%d] %s' % (len(knots), knot_param)] = knots
            params['float[%d] %s' % (len(vals), float_param)] = vals

        if nt and rm.color_ramp_node in nt.nodes.keys():
            del params['float[16] colorRamp_Knots']
            color_node = nt.nodes[rm.color_ramp_node]
            color_ramp = color_node.color_ramp
            colors = []
            positions = []
            # double the start and end points
            positions.append(float(color_ramp.elements[0].position))
            colors.extend(color_ramp.elements[0].color[:3])
            for e in color_ramp.elements:
                positions.append(float(e.position))
                colors.extend(e.color[:3])
            positions.append(
                float(color_ramp.elements[-1].position))
            colors.extend(color_ramp.elements[-1].color[:3])
            params['float[%d] colorRamp_Knots' % len(positions)] = positions
            params['color[%d] colorRamp_Colors' % len(positions)] = colors

    return params


def export_integrator(ri, rpass, scene, preview=False):
    rm = scene.renderman
    integrator = rm.integrator
    if preview or rpass.is_interactive:
        integrator = "PxrPathTracer"

    integrator_settings = getattr(rm, "%s_settings" % integrator)
    params = property_group_to_params(integrator_settings)

    ri.Integrator(integrator, "integrator", params)


def render_get_resolution(r):
    xres = int(r.resolution_x * r.resolution_percentage * 0.01)
    yres = int(r.resolution_y * r.resolution_percentage * 0.01)
    return xres, yres


def render_get_aspect(r, camera=None):
    xres, yres = render_get_resolution(r)

    xratio = xres * r.pixel_aspect_x / 200.0
    yratio = yres * r.pixel_aspect_y / 200.0

    if camera is None or camera.type != 'PERSP':
        fit = 'AUTO'
    else:
        fit = camera.sensor_fit

    if fit == 'HORIZONTAL' or fit == 'AUTO' and xratio > yratio:
        aspectratio = xratio / yratio
        xaspect = aspectratio
        yaspect = 1.0
    elif fit == 'VERTICAL' or fit == 'AUTO' and yratio > xratio:
        aspectratio = yratio / xratio
        xaspect = 1.0
        yaspect = aspectratio
    else:
        aspectratio = xaspect = yaspect = 1.0

    return xaspect, yaspect, aspectratio


def export_render_settings(ri, rpass, scene, preview=False):
    rm = scene.renderman
    r = scene.render

    depths = {'int maxdiffusedepth': rm.max_diffuse_depth,
              'int maxspeculardepth': rm.max_specular_depth,
              'int displacements': 1}
    if preview or rpass.is_interactive:
        depths = {'int maxdiffusedepth': rm.preview_max_diffuse_depth,
                  'int maxspeculardepth': rm.preview_max_specular_depth,
                  'int displacements': 1}

    dicing_params = {"float micropolygonlength": rm.shadingrate,
                     "string strategy": rm.dicing_strategy,
                     "string instancestrategy": "worlddistance",
                     "float instanceworlddistancelength": rm.instanceworlddistancelength}

    if rm.dicing_strategy is "worlddistance":
        dicing_params["float worlddistancelength"] = rm.worlddistancelength

    # ri.PixelSamples(rm.pixelsamples_x, rm.pixelsamples_y)
    ri.PixelFilter(rm.pixelfilter, rm.pixelfilter_x, rm.pixelfilter_y)
    ri.Attribute("dice", dicing_params)
    ri.Attribute("trace", depths)
    if rm.use_statistics:
        ri.Option("statistics", {'int endofframe': 1,
                                 'string xmlfilename': 'stats.%04d.xml' % scene.frame_current})


def export_camera_matrix(ri, scene, ob, motion_data=[]):

    if motion_data:
        export_motion_begin(ri, motion_data)
        samples = [sample[1] for sample in motion_data]
    else:
        samples = [ob.matrix_world]

    for sample in samples:
        mat = sample
        loc = sample.translation
        rot = sample.to_euler()

        s = Matrix(([1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]))
        r = Matrix.Rotation(-rot[0], 4, 'X')
        r *= Matrix.Rotation(-rot[1], 4, 'Y')
        r *= Matrix.Rotation(-rot[2], 4, 'Z')
        l = Matrix.Translation(-loc)
        m = s * r * l

        ri.Transform(rib(m))
        ri.CoordinateSystem(ob.name)

    export_motion_end(ri, motion_data)


def export_camera(ri, scene, instances, camera_to_use=None):
    r = scene.render
    if camera_to_use:
        ob = camera_to_use
        motion = []
    else:
        if not scene.camera or scene.camera.type != 'CAMERA':
            return
        i = instances[scene.camera.name]
        ob = i.ob
        motion = i.motion_data
    cam = ob.data
    rm = scene.renderman

    xaspect, yaspect, aspectratio = render_get_aspect(r, cam)

    if rm.depth_of_field:
        if cam.dof_object:
            dof_distance = (ob.location - cam.dof_object.location).length
        else:
            dof_distance = cam.dof_distance
        ri.DepthOfField(cam.renderman.fstop, (cam.lens * 0.001), dof_distance)

    if scene.renderman.motion_blur:
        shutter_interval = rm.shutter_angle / 360.0
        shutter_open, shutter_close = 0, 1
        if rm.shutter_timing == 'CENTER':
            shutter_open, shutter_close = 0 - .5 * \
                shutter_interval, 0 + .5 * shutter_interval
        elif rm.shutter_timing == 'PRE':
            shutter_open, shutter_close = 0 - shutter_interval, 0
        elif rm.shutter_timing == 'POST':
            shutter_open, shutter_close = 0, shutter_interval
        ri.Shutter(shutter_open, shutter_close)
        # ri.Option "shutter" "efficiency" [ %f %f ] \n' %
        # (rm.shutter_efficiency_open, rm.shutter_efficiency_close))

    ri.Clipping(cam.clip_start, cam.clip_end)

    if scene.render.use_border and not scene.render.use_crop_to_border:
        ri.CropWindow(scene.render.border_min_x, scene.render.border_max_x,
                      1.0 - scene.render.border_min_y, 1.0 - scene.render.border_max_y)

    if cam.renderman.projection_type != 'none':
        # use pxr Camera
        params = property_group_to_params(cam.renderman.get_projection_node())
        if cam.renderman.get_projection_name() == 'PxrCamera':
            lens = cam.lens
            sensor = cam.sensor_height \
                if cam.sensor_fit == 'VERTICAL' else cam.sensor_width
            params['float fov'] = 360.0 * \
                math.atan((sensor * 0.5) / lens / aspectratio) / math.pi
        ri.Projection(cam.renderman.get_projection_name(), params)
    elif cam.type == 'PERSP':
        lens = cam.lens

        sensor = cam.sensor_height \
            if cam.sensor_fit == 'VERTICAL' else cam.sensor_width

        fov = 360.0 * math.atan((sensor * 0.5) / lens / aspectratio) / math.pi
        ri.Projection("perspective", {"fov": fov})
    elif cam.type == 'PANO':
        ri.Projection("sphere", {"float hsweep": 360, "float vsweep": 180})
    else:
        lens = cam.ortho_scale
        xaspect = xaspect * lens / (aspectratio * 2.0)
        yaspect = yaspect * lens / (aspectratio * 2.0)
        ri.Projection("orthographic")

    # convert the crop border to screen window, flip y
    resolution = render_get_resolution(scene.render)
    if scene.render.use_border and scene.render.use_crop_to_border:
        screen_min_x = -xaspect + 2.0 * scene.render.border_min_x * xaspect
        screen_max_x = -xaspect + 2.0 * scene.render.border_max_x * xaspect
        screen_min_y = -yaspect + 2.0 * (scene.render.border_min_y) * yaspect
        screen_max_y = -yaspect + 2.0 * (scene.render.border_max_y) * yaspect
        ri.ScreenWindow(screen_min_x, screen_max_x, screen_min_y, screen_max_y)
        res_x = resolution[0] * (scene.render.border_max_x -
                                 scene.render.border_min_x)
        res_y = resolution[1] * (scene.render.border_max_y -
                                 scene.render.border_min_y)
        ri.Format(int(res_x), int(res_y), 1.0)
    else:
        if cam.type == 'PANO':
            ri.ScreenWindow(-1, 1, -1, 1)
        else:
            ri.ScreenWindow(-xaspect, xaspect, -yaspect, yaspect)
        ri.Format(resolution[0], resolution[1], 1.0)

    export_camera_matrix(ri, scene, ob, motion)

    ri.Camera("world", {'float[2] shutteropening': [rm.shutter_efficiency_open,
                                                    rm.shutter_efficiency_open]})


def export_camera_render_preview(ri, scene):
    r = scene.render

    xaspect, yaspect, aspectratio = render_get_aspect(r)

    ri.Clipping(0.100000, 100.000000)
    ri.Projection("perspective", {"fov": 37.8493})
    ri.ScreenWindow(-xaspect, xaspect, -yaspect, yaspect)
    resolution = render_get_resolution(scene.render)
    ri.Format(resolution[0], resolution[1], 1.0)
    ri.Transform([0, -0.25, -1, 0, 1, 0, 0, 0, 0,
                  1, -0.25, 0, 0, -.75, 3.25, 1])


def export_options(ri, scene):
    rm = scene.renderman
    params = {'int geocachememory': rm.geo_cache_size * 100,
              'int opacitycachememory': rm.opacity_cache_size * 100,
              'int texturememory': rm.texture_cache_size * 100,
              }
    ri.Option("limits", params)
    if rm.asfinal:
        ri.Option("checkpoint", {"int asfinal": 1})
    ri.Option("searchpath", {"string procedural": [
              ".:${RMANTREE}/lib/plugins:@"]})
    ri.Option("user", {"int osl:lazy_builtins": 1, "int osl:lazy_inputs": 1})

    lpe_options = {
        "string diffuse2": "Diffuse",
        "string diffuse3": "Subsurface",
        "string specular2": "Specular",
        "string specular3": "RoughSpecular",
        "string specular4": "Clearcoat",
        "string specular5": "Iridescence",
        "string specular6": "Fuzz",
        "string specular7": "SingleScatter",
        "string specular8": "Glass",
    }

    ri.Option('lpe', lpe_options)


def export_searchpaths(ri, paths):
    ri.Option("ribparse", {"string varsubst": ["$"]})
    ri.Option("searchpath", {"string shader": ["%s" %
                                               ':'.join(path_list_convert(paths['shader'], to_unix=True))]})
    rel_tex_paths = [os.path.relpath(path, paths['export_dir'])
                     for path in paths['texture']]
    ri.Option("searchpath", {"string texture": ["%s" %
                                                ':'.join(path_list_convert(rel_tex_paths + ["@"], to_unix=True))]})
    # ri.Option("searchpath", {"string procedural": ["%s" % \
    #    ':'.join(path_list_convert(paths['procedural'], to_unix=True))]})
    ri.Option("searchpath", {"string archive": os.path.relpath(
        paths['archive'], paths['export_dir'])})


def export_header(ri):
    render_name = os.path.basename(bpy.data.filepath)
    export_comment(ri, 'Generated by RenderMan for Blender, v%s.%s.%s \n' % (
        addon_version[0], addon_version[1], addon_version[2]))
    export_comment(ri, 'From File: %s on %s\n' %
                   (render_name, time.strftime("%A %c")))


def export_header_rib(ri, scene):
    rm = scene.renderman
    if rm.frame_rib_box != '':
        export_rib_box(ri, rm.frame_rib_box)

# --------------- Hopefully temporary --------------- #


def get_instance_materials(ob):
    obmats = []
    # Grab materials attached to object instances ...
    if hasattr(ob, 'material_slots'):
        for ms in ob.material_slots:
            obmats.append(ms.material)
    # ... and to the object's mesh data
    if hasattr(ob.data, 'materials'):
        for m in ob.data.materials:
            obmats.append(m)
    return obmats


def find_preview_material(scene):
    # taken from mitsuba exporter
    objects_materials = {}

    for object in renderable_objects(scene):
        for mat in get_instance_materials(object):
            if mat is not None:
                if object.name not in objects_materials.keys():
                    objects_materials[object] = []
                objects_materials[object].append(mat)

    # find objects that are likely to be the preview objects
    preview_objects = [o for o in objects_materials.keys()
                       if o.name.startswith('preview')]
    if len(preview_objects) < 1:
        return

    # find the materials attached to the likely preview object
    likely_materials = objects_materials[preview_objects[0]]
    if len(likely_materials) < 1:
        return

    return likely_materials[0]

# --------------- End Hopefully temporary --------------- #


def preview_model(ri, scene, mat):
    if mat.preview_render_type == 'SPHERE':
        ri.Sphere(1, -1, 1, 360)
    elif mat.preview_render_type == 'FLAT':  # FLAT PLANE
        # ri.Scale(0.75, 0.75, 0.75)
        # ri.Translate(0.0, 0.0, 0.01)
        ri.PointsPolygons([4, ],
                          [0, 1, 2, 3],
                          {ri.P: [0, -1, -1, 0, 1, -1, 0, 1, 1, 0, -1, 1]})
    elif mat.preview_render_type == 'CUBE':
        ri.Scale(.75, .75, .75)
        export_geometry_data(ri, scene, scene.objects[
                             'preview_cube'], data=None)
    elif mat.preview_render_type == 'HAIR':
        ri.Scale(.75, .75, .75)
        export_geometry_data(ri, scene, scene.objects[
                             'preview_hair'], data=None)
    elif mat.preview_render_type == 'MONKEY':
        ri.Scale(.75, .75, .75)
        ri.Rotate(90, 1, 0, 0)
        ri.Rotate(90, 0, 1, 0)
        export_geometry_data(ri, scene, scene.objects[
                             'preview_monkey'], data=None)
    else:
        ri.Scale(2, 2, 2)
        ri.Rotate(90, 0, 0, 1)
        ri.Rotate(45, 1, 0, 0)
        export_geometry_data(ri, scene, scene.objects[
                             'preview.002'], data=None)


def export_displayfilters(ri, scene):
    rm = scene.renderman
    display_filter_names = []
    for df in rm.display_filters:
        params = property_group_to_params(df.get_filter_node())
        params['__instanceid'] = df.name
        ri.DisplayFilter(df.get_filter_name(), df.name, params)
        display_filter_names.append(df.name)

    if len(display_filter_names) > 1:
        params = {'reference displayfilter[%d] filter' % len(
            display_filter_names): display_filter_names}
        ri.DisplayFilter('PxrDisplayFilterCombiner', 'combiner', params)


def export_samplefilters(ri, rpass, scene):
    rm = scene.renderman
    filter_names = []
    display_driver = rpass.display_driver
    addon_prefs = get_addon_prefs()
    for sf in rm.sample_filters:
        params = property_group_to_params(sf.get_filter_node())
        ri.SampleFilter(sf.get_filter_name(), sf.name, params)
        filter_names.append(sf.name)

        # pxrshadowfilter aov generation
        if sf.filter_type == 'PxrShadowFilter':
            ri.DisplayChannel("color %s" % sf.PxrShadowFilter_settings.occludedAov, {
                              "string source": "color lpe:holdouts;C[DS]+[LO]"})
            dspy_name = user_path(
                addon_prefs.path_aov_image, scene=scene, display_driver=rpass.display_driver,
                layer_name='Shadow', pass_name='Occluded')
            ri.Display('+' + dspy_name, display_driver,
                       sf.PxrShadowFilter_settings.occludedAov, {"int asrgba": 1})

            ri.DisplayChannel("color %s" % sf.PxrShadowFilter_settings.unoccludedAov, {
                              "string source": "color lpe:holdouts;unoccluded;C[DS]+[LO]"})
            dspy_name = user_path(
                addon_prefs.path_aov_image, scene=scene, display_driver=rpass.display_driver,
                layer_name='Shadow', pass_name='Unoccluded')
            ri.Display('+' + dspy_name, display_driver,
                       sf.PxrShadowFilter_settings.unoccludedAov, {"int asrgba": 1})

            if sf.PxrShadowFilter_settings.shadowAov != 'a':
                ri.DisplayChannel("color %s" %
                                  sf.PxrShadowFilter_settings.shadowAov)
                dspy_name = user_path(
                    addon_prefs.path_aov_image, scene=scene, display_driver=rpass.display_driver,
                    layer_name='Shadow', pass_name='ShadowOutput')
                ri.Display('+' + dspy_name, display_driver,
                           sf.PxrShadowFilter_settings.shadowAov, {"int asrgba": 1})

    if len(filter_names) > 1:
        params = {'reference samplefilter[%d] filter' % len(
            filter_names): filter_names}
        ri.SampleFilter('PxrSampleFilterCombiner', 'combiner', params)


channel_name_map = {
    "directDiffuseLobe": "diffuse",
    "subsurfaceLobe": "diffuse",
    "Subsurface": "diffuse",
    "transmissiveSingleScatterLobe": "diffuse",
    "Caustics": "diffuse",
    "Albedo": "diffuse",
    "Diffuse": "diffuse",
    "IndirectDiffuse": "indirectdiffuse",
    "indirectDiffuseLobe": "indirectdiffuse",
    "directSpecularPrimaryLobe": "specular",
    "directSpecularRoughLobe": "specular",
    "directSpecularClearcoatLobe": "specular",
    "directSpecularIridescenceLobe": "specular",
    "directSpecularFuzzLobe": "specular",
    "directSpecularGlassLobe": "specular",
    "transmissiveGlassLobe": "specular",
    "Reflection": "specular",
    "Refraction": "specular",
    "Specular": "specular",
    "indirectSpecularPrimaryLobe": "indirectspecular",
    "indirectSpecularRoughLobe": "indirectspecular",
    "IndirectSpecular": "indirectspecular",
    "indirectSpecularClearcoatLobe": "indirectspecular",
    "indirectSpecularIridescenceLobe": "indirectspecular",
    "indirectSpecularFuzzLobe": "indirectspecular",
    "indirectSpecularGlassLobe": "indirectspecular",
    "Shadows": "emission",
    "All Lighting": "emission",
    "Emission": "emission"
}


def get_channel_name(aov, layer_name):
    aov_name = aov.name.replace(' ', '')
    aov_channel_name = aov.channel_name
    if not aov.aov_name or not aov.channel_name:
        return ''
    elif aov.aov_name == "color rgba":
        aov_channel_name = "Ci,a"
    # Remaps any color lpe channel names to a denoise friendly one
    elif aov_name in channel_name_map.keys():
        aov_channel_name = '%s_%s_%s' % (
            channel_name_map[aov_name], aov_name, layer_name)

    elif aov.aov_name == "color custom_lpe":
        aov_channel_name = aov.name

    else:
        aov_channel_name = '%s_%s' % (
            aov_name, layer_name)

    return aov_channel_name


def export_display(ri, rpass, scene):
    rm = scene.renderman

    # Set bucket shape
    if rm.enable_checkpoint and not rpass.is_interactive:
        ri.Option("bucket", {"string order": ['horizontal']})

    elif rm.bucket_shape == 'SPIRAL':
        settings = scene.render

        if rm.bucket_sprial_x <= settings.resolution_x and rm.bucket_sprial_y <= settings.resolution_y:
            if rm.bucket_sprial_x == -1 and rm.bucket_sprial_y == -1:
                ri.Option(
                    "bucket", {"string order": [rm.bucket_shape.lower()]})
            elif rm.bucket_sprial_x == -1:
                halfX = settings.resolution_x / 2
                debug("info", halfX)
                ri.Option("bucket", {"string order": [rm.bucket_shape.lower()],
                                     "orderorigin": [int(halfX),
                                                     rm.bucket_sprial_y]})
            elif rm.bucket_sprial_y == -1:
                halfY = settings.resolution_y / 2
                ri.Option("bucket", {"string order": [rm.bucket_shape.lower()],
                                     "orderorigin": [rm.bucket_sprial_y,
                                                     int(halfY)]})
            else:
                ri.Option("bucket", {"string order": [rm.bucket_shape.lower()],
                                     "orderorigin": [rm.bucket_sprial_x,
                                                     rm.bucket_sprial_y]})
        else:
            debug("info", "OUTSLIDE LOOP")
            ri.Option("bucket", {"string order": [rm.bucket_shape.lower()]})
    else:
        ri.Option("bucket", {"string order": [rm.bucket_shape.lower()]})

    display_driver = rpass.display_driver
    rpass.output_files = []
    addon_prefs = get_addon_prefs()
    main_display = user_path(
        addon_prefs.path_display_driver_image, scene=scene, display_driver=rpass.display_driver)
    debug("info", "Main_display: " + main_display)

    # just going to always output rgba
    dspy_info = {}

    # if it inject some image info
    if display_driver == 'it':
        dspy_info = make_dspy_info(scene)

    ri.Display(main_display, display_driver, "rgba", dspy_info)
    rpass.output_files.append(main_display)

    display_params = {'int asrgba': 1}

    for layer in scene.render.layers:
        # custom aovs
        rm_rl = None
        for render_layer_settings in rm.render_layers:
            if layer.name == render_layer_settings.render_layer:
                rm_rl = render_layer_settings
                break

        layer_name = layer.name.replace(' ', '')

        # there's no render layer settins
        if not rm_rl:
            # so use built in aovs
            aovs = [
                # (name, do?, declare type/name, source)
                ("z", layer.use_pass_z, "float", None),
                ("Nn", layer.use_pass_normal, "normal", None),
                ("dPdtime", layer.use_pass_vector, "vector", None),
                ("u", layer.use_pass_uv, "float", None),
                ("v", layer.use_pass_uv, "float", None),
                ("id", layer.use_pass_object_index, "float", None),
                ("shadows", layer.use_pass_shadow, "color",
                 "color lpe:shadowcollector"),
                ("reflection", layer.use_pass_reflection, "color",
                 "color lpe:reflectioncollector"),
                ("diffuse", layer.use_pass_diffuse_direct, "color",
                 "color lpe:diffuse"),
                ("indirectdiffuse", layer.use_pass_diffuse_indirect,
                 "color", "color lpe:indirectdiffuse"),
                ("albedo", layer.use_pass_diffuse_color, "color",
                 "color lpe:nothruput;noinfinitecheck;noclamp;unoccluded;overwrite;C(U2L)|O"),
                ("specular", layer.use_pass_glossy_direct, "color",
                 "color lpe:specular"),
                ("indirectspecular", layer.use_pass_glossy_indirect,
                 "color", "color lpe:indirectspecular"),
                ("subsurface", layer.use_pass_subsurface_indirect,
                 "color", "color lpe:subsurface"),
                ("refraction", layer.use_pass_refraction, "color",
                 "color lpe:refraction"),
                ("emission", layer.use_pass_emit, "color",
                 "color lpe:emission"),
            ]

            # declare display channels
            for aov, doit, declare_type, source in aovs:
                if doit and declare_type:
                    params = {"int[4] quantize": [0, 0, 0, 0]}
                    if source:
                        params['string source'] = source
                    ri.DisplayChannel('%s %s' % (declare_type, aov), params)

            # if layer.use_pass_combined:
            #     main_params = {}

            #     #if display_driver == 'openexr':
            #     #    if rm.exr_format_options != 'default':
            #     #        main_params["string type"] = rm.exr_format_options
            #     #    if rm.exr_compression != 'default':
            #     #        main_params["string compression"] = rm.exr_compression

            # exports all AOV's
            for aov, doit, declare, source in aovs:
                if doit:
                    dspy_name = user_path(
                        addon_prefs.path_aov_image, scene=scene, display_driver=rpass.display_driver,
                        layer_name=layer_name, pass_name=aov)
                    ri.Display('+' + dspy_name, display_driver,
                               aov, display_params)
                    rpass.output_files.append(dspy_name)

        # else we have custom rman render layer settings
        else:
            for aov in rm_rl.custom_aovs:
                aov_name = aov.name.replace(' ', '')
                # if theres a blank name we can't make a channel
                if not aov_name:
                    continue
                source_type, source = aov.aov_name.split()
                exposure_gain = aov.exposure_gain
                exposure_gamma = aov.exposure_gamma
                remap_a = aov.remap_a
                remap_b = aov.remap_b
                remap_c = aov.remap_c
                quantize_zero = aov.quantize_zero
                quantize_one = aov.quantize_one
                quantize_min = aov.quantize_min
                quantize_max = aov.quantize_max
                pixel_filter = aov.aov_pixelfilter
                stats = aov.stats_type
                pixelfilter_x = aov.aov_pixelfilter_x
                pixelfilter_y = aov.aov_pixelfilter_y
                channel_name = get_channel_name(aov, layer_name)

                if channel_name == '':
                    continue
                if aov.aov_name == "color custom_lpe":
                    source = aov.custom_lpe_string

                # light groups need to be surrounded with '' in lpes
                G_string = "'%s'" % rm_rl.object_group if rm_rl.object_group != '' else ""
                LG_string = "'%s'" % rm_rl.light_group if rm_rl.light_group != '' else ""
                try:
                    source = source.replace("%G", G_string)
                    source = source.replace("%LG", LG_string)
                except:
                    pass

                params = {"string source": source_type + " " + source,
                          "float[2] exposure": [exposure_gain, exposure_gamma],
                          "float[3] remap": [remap_a, remap_b, remap_c],
                          "int[4] quantize": [quantize_zero, quantize_one, quantize_min, quantize_max]}
                if pixel_filter != 'default':
                    params["filter"] = pixel_filter
                    params["filterwidth"] = [pixelfilter_x, pixelfilter_y]
                if stats != 'none':
                    params["string statistics"] = stats

                if source == 'rgba':
                    del params['string source']
                    ri.DisplayChannel("color Ci", params)
                    ri.DisplayChannel("float a", params)
                else:
                    ri.DisplayChannel(source_type + ' %s' %
                                      channel_name, params)

            # if this is a multilayer combine em!
            if rm_rl.export_multilayer and rpass.external_render:
                channels = []
                for aov in rm_rl.custom_aovs:
                    channel_name = get_channel_name(aov, layer_name)
                    channels.append(channel_name)
                out_type, ext = ('openexr', 'exr')
                if rm_rl.use_deep:
                    channels = [x for x in channels if not (
                        "z_back" in x or 'z_depth' in x)]
                    out_type, ext = ('deepexr', 'exr')
                params = {"string storage": rm_rl.exr_storage}
                if rm_rl.exr_format_options != 'default':
                    params["string type"] = rm_rl.exr_format_options
                if rm_rl.exr_compression != 'default':
                    params["string compression"] = rm_rl.exr_compression
                if channels[0] == "Ci,a" and not rm.spool_denoise_aov and not rm.enable_checkpoint:
                    params["int asrgba"] = 1
                dspy_name = user_path(
                    addon_prefs.path_aov_image, scene=scene, display_driver=rpass.display_driver,
                    layer_name=layer_name, pass_name='multilayer')
                ri.Display('+' + dspy_name, out_type,
                           ','.join(channels), params)

            else:
                for aov in rm_rl.custom_aovs:
                    aov_name = aov.name.replace(' ', '')
                    aov_channel_name = get_channel_name(aov, layer_name)
                    if aov_channel_name == '':
                        continue

                    if layer == scene.render.layers[0] and aov == 'rgba':
                        # we already output this skip
                        continue

                    params = {
                        "int asrgba": 1} if not rm.spool_denoise_aov and not rm.enable_checkpoint else {}
                    dspy_name = user_path(
                        addon_prefs.path_aov_image, scene=scene, display_driver=rpass.display_driver,
                        layer_name=layer_name, pass_name=aov_name)
                    rpass.output_files.append(dspy_name)
                    ri.Display('+' + dspy_name, display_driver,
                               aov_channel_name, params)

    if (rm.do_denoise and not rpass.external_render or rm.external_denoise and rpass.external_render) and not rpass.is_interactive:
        # add display channels for denoising
        denoise_aovs = [
            # (name, declare type/name, source, statistics, filter)
            ("Ci", 'color', None, None, None),
            ("a", 'float', None, None, None),
            ("mse", 'color', 'color Ci', 'mse', None),
            ("albedo", 'color',
             'color lpe:nothruput;noinfinitecheck;noclamp;unoccluded;overwrite;C(U2L)|O',
             None, None),
            ("albedo_var", 'color', 'color lpe:nothruput;noinfinitecheck;noclamp;unoccluded;overwrite;C(U2L)|O',
             "variance", None),
            ("diffuse", 'color', 'color lpe:C(D[DS]*[LO])|O', None, None),
            ("diffuse_mse", 'color', 'color lpe:C(D[DS]*[LO])|O', 'mse', None),
            ("specular", 'color', 'color lpe:CS[DS]*[LO]', None, None),
            ("specular_mse", 'color', 'color lpe:CS[DS]*[LO]', 'mse', None),
            ("z", 'float', 'float z', None, True),
            ("z_var", 'float', 'float z', "variance", True),
            ("normal", 'normal', 'normal Nn', None, None),
            ("normal_var", 'normal', 'normal Nn', "variance", None),
            ("forward", 'vector', 'vector motionFore', None, None),
            ("backward", 'vector', 'vector motionBack', None, None)
        ]

        for aov, declare_type, source, statistics, do_filter in denoise_aovs:
            params = {}
            if source:
                params['string source'] = source
            if statistics:
                params['string statistics'] = statistics
            if do_filter:
                params['string filter'] = rm.pixelfilter
            ri.DisplayChannel('%s %s' % (declare_type, aov), params)

        # output denoise_data.exr
        image_base, ext = main_display.rsplit('.', 1)
        ri.Display('+' + image_base + '.variance.exr', 'openexr',
                   "Ci,a,mse,albedo,albedo_var,diffuse,diffuse_mse,specular,specular_mse,z,z_var,normal,normal_var,forward,backward",
                   {"string storage": "tiled"})


def export_hider(ri, rpass, scene, preview=False):
    if rpass.bake:
        ri.Hider("bake")

    else:
        rm = scene.renderman

        pv = rm.pixel_variance
        hider_params = {'int maxsamples': rm.max_samples,
                        'int minsamples': rm.min_samples,
                        'int incremental': int(rm.incremental)}

        if preview or rpass.is_interactive:
            hider_params['int maxsamples'] = rm.preview_max_samples
            hider_params['int minsamples'] = rm.preview_min_samples
            hider_params['int incremental'] = 1
            pv = rm.preview_pixel_variance

        if (not rpass.external_render and rm.render_into == 'blender') or (rm.integrator in ['PxrVCM', 'PxrUPBP']) or rm.enable_checkpoint:
            hider_params['int incremental'] = 1

        if not preview:
            cam = scene.camera.data.renderman
            hider_params["float[4] aperture"] = [cam.aperture_sides,
                                                 cam.aperture_angle, cam.aperture_roundness, cam.aperture_density]
            hider_params["float dofaspect"] = [cam.dof_aspect]
            hider_params["float darkfalloff"] = [rm.dark_falloff]

        if not rm.sample_motion_blur:
            hider_params["samplemotion"] = 0

        ri.PixelVariance(pv)

        if rm.do_denoise and not rpass.external_render or rm.external_denoise and rpass.external_render:
            hider_params['string pixelfiltermode'] = 'importance'

        ri.Hider("raytrace", hider_params)


# I hate to make rpass global but it makes things so much easier
def write_rib(rpass, scene, ri, visible_objects=None, engine=None, do_objects=True):

    # precalculate motion blur data
    data_blocks, instances = cache_motion(scene, rpass)

    # get a list of empties to check if they contain a RIB archive.
    # this should be the only time empties are evaluated.
    emptiesToExport = get_valid_empties(scene, rpass)

    if do_objects:
        # export rib archives of objects
        export_data_archives(ri, scene, rpass, data_blocks, engine)

    export_header(ri)
    export_header_rib(ri, scene)
    export_searchpaths(ri, rpass.paths)
    export_options(ri, scene)

    if not rpass.bake:
        export_display(ri, rpass, scene)
        export_displayfilters(ri, scene)
        export_samplefilters(ri, rpass, scene)
    else:
        ri.Display("null", "null", "rgba")

    export_hider(ri, rpass, scene)

    if not rpass.bake:
        export_integrator(ri, rpass, scene)

    # export_inline_rib(ri, rpass, scene)

    scene.frame_set(scene.frame_current)
    ri.FrameBegin(scene.frame_current)

    if not rpass.bake:
        export_camera(ri, scene, instances)
        export_render_settings(ri, rpass, scene)

    # export_global_illumination_settings(ri, rpass, scene)

    ri.WorldBegin()

    # export_global_illumination_lights(ri, rpass, scene)
    # export_world_coshaders(ri, rpass, scene) # BBM addition
    if not rpass.bake:
        export_world_rib(ri, scene.world)
        export_world(ri, scene.world)
        export_scene_lights(ri, instances)
        export_default_bxdf(ri, "default")
    export_materials_archive(ri, rpass, scene)
    # now output the object archives
    for name, instance in instances.items():
        if not instance.parent:
            export_instance_read_archive(
                ri, instance, instances, data_blocks, rpass, visible_objects=visible_objects)

    for object in emptiesToExport:
        export_empties_archives(ri, object)

    instances = None
    ri.WorldEnd()

    ri.FrameEnd()


def write_preview_rib(rpass, scene, ri):
    preview_rib_data_path = \
        rib_path(os.path.join(os.path.dirname(os.path.realpath(__file__)),
                              'preview', "preview_scene.rib"))

    export_header(ri)
    export_searchpaths(ri, rpass.paths)

    # temporary tiff display to be read back into blender render result
    ri.FrameBegin(1)
    ri.Display(os.path.basename(rpass.paths['render_output']), "tiff", "rgb",
               {ri.DISPLAYQUANTIZE: [0, 0, 0, 0]})

    temp_scene = bpy.data.scenes[0]
    export_hider(ri, rpass, temp_scene, preview=True)
    export_integrator(ri, rpass, temp_scene, preview=True)

    export_camera_render_preview(ri, scene)
    export_render_settings(ri, rpass, scene, preview=True)

    ri.WorldBegin()

    # preview scene: walls, lights
    ri.ReadArchive(preview_rib_data_path)

    # preview model and material
    ri.AttributeBegin()
    ri.Attribute("identifier", {"string name": ["Preview"]})
    ri.Translate(0, 0, 0.75)

    mat = find_preview_material(scene)
    if mat:
        export_material(ri, mat, 'preview')
        preview_model(ri, scene, mat)
    ri.AttributeEnd()

    ri.WorldEnd()
    ri.FrameEnd()

    # if mat is none this will tell the render pass not to render
    return mat != None


def write_archive_RIB(rpass, scene, ri, object, overridePath, exportMats, exportRange):
    success = True  # Store if the export is a success or not default to true

    fileExt = ".zip"

    # precalculate data
    data_blocks, instances = cache_motion(scene, rpass, objects=[object])

    # Override precalculated data (simpler then creating new methods)
    for name, db in data_blocks.items():
        fileName = db.archive_filename
        if(overridePath != "" and os.path.exists(os.path.split(overridePath)[0])):
            # Assume that the user always wants an export when this method is
            # called.
            db.do_export = True
            db.archive_filename = os.path.split(fileName)[1]
        else:
            success = False

    # Open zip file for writing
    if(overridePath != ""):
        archivePath = os.path.join(os.path.split(overridePath)[
                                   0], object.name + fileExt)
        ri.Begin(archivePath)
    else:
        success = False

    if success:
        # export rib archives of objects
        if(exportRange):
            # Get range numbers from the timeline and use that as our range.
            # This is how baking works so we should remain in line with how
            #   blender wants to do things.
            rangeStart = scene.frame_start
            rangeEnd = scene.frame_end
            rangeLength = rangeEnd - rangeStart
            # Assume user is smart and wont pass us a negative range.
            for i in range(rangeStart, rangeEnd + 1):
                scene.frame_current = i
                zeroFill = str(i).zfill(4)
                data_blocks, instances = cache_motion(
                    scene, rpass, objects=[object])
                archivePathRIB = os.path.join(zeroFill, object.name + ".rib")
                ri.Begin(archivePathRIB)
                if(exportMats):  # Bake in materials if asked.
                    materialsList = object.material_slots
                    # Convert any textures just in case.
                    rpass.convert_textures(get_select_texture_list(object))
                    for materialSlot in materialsList:
                        ri.ArchiveBegin(os.path.join(
                            zeroFill, 'material.' + materialSlot.name))
                        export_material(ri, materialSlot.material)
                        ri.ArchiveEnd()
                for name, db in data_blocks.items():
                    db.do_export = True
                export_RIBArchive_data_archive(
                    ri, scene, rpass, data_blocks, exportMats, True, True)
                ri.End()
            # Reset back to start frame for niceties.
            scene.frame_current = rangeStart
        else:
            archivePathRIB = object.name + ".rib"
            ri.Begin(archivePathRIB)
            # If we need to export material bake it in
            if(exportMats):
                materialsList = object.material_slots
                # Convert any textures so they will be available on archive
                # load.
                rpass.convert_textures(get_select_texture_list(object))
                for materialSlot in materialsList:
                    ri.ArchiveBegin('material.' + materialSlot.name)
                    export_material(ri, materialSlot.material)
                    ri.ArchiveEnd()
            export_RIBArchive_data_archive(
                ri, scene, rpass, data_blocks, exportMats, False, True)
            ri.End()
        ri.End()

    # Check if the file was created. I don't really think we need to check in
    # the .zip
    if(not os.path.exists(archivePath)):
        success = False

    returnList = [success, archivePath]
    return returnList


def anim_archive_path(filepath, frame):
    if filepath.find("#") != -1:
        ribpath = make_frame_path(filepath, fr)
    else:
        ribpath = os.path.splitext(filepath)[0] + "." + str(frame).zfill(4) + \
            os.path.splitext(filepath)[1]
    return ribpath


def write_auto_archives(paths, scene, info_callback):
    for ob in archive_objects(scene):
        export_archive(scene, [ob], archive_motion=True,
                       frame_start=scene.frame_current,
                       frame_end=scene.frame_current)


def interactive_initial_rib(rpass, ri, scene, prman):

    dspy_info = make_dspy_info(scene)

    ri.Display('rerender', 'it', 'rgba', dspy_info)
    export_hider(ri, rpass, scene, True)

    ri.EditWorldBegin(
        rpass.paths['rib_output'], {"string rerenderer": "raytrace"})
    ri.Option('rerender', {'int[2] lodrange': [0, 3]})
    cw = rpass.crop_window
    ri.CropWindow(cw[0], cw[1], cw[2], cw[3])

    ri.ArchiveRecord("structure", ri.STREAMMARKER + "_initial")
    prman.RicFlush("_initial", 0, ri.FINISHRENDERING)


def make_dspy_info(scene):
    """
    Create some render parameter from scene and pass it to image tool.

    If current scene renders to "it", collect some useful infos from scene
    and send them alongside the render job to RenderMan's image tool. Applies to
    renderpass result only, does not affect postprocessing like denoise.
    """
    params = {}
    rm = scene.renderman
    from time import localtime, strftime
    ts = strftime("%a %x, %X", localtime())
    ts = bytes(ts, 'ascii', 'ignore').decode('utf-8', 'ignore')

    dspy_notes = "Render start:\t%s\r\r" % ts
    dspy_notes += "Integrator:\t%s\r\r" % rm.integrator
    dspy_notes += "Samples:\t%d - %d\r" % (rm.min_samples, rm.max_samples)
    dspy_notes += "Pixel Variance:\t%f\r\r" % rm.pixel_variance

    # moved this in front of integrator check. Was called redundant in
    # both cases
    integrator = getattr(rm, "%s_settings" % rm.integrator)

    if rm.integrator == 'PxrPathTracer':
        dspy_notes += "Mode:\t%s\r" % integrator.sampleMode
        dspy_notes += "Light:\t%d\r" % integrator.numLightSamples
        dspy_notes += "Bxdf:\t%d\r" % integrator.numBxdfSamples

        if integrator.sampleMode == 'bxdf':
            dspy_notes += "Indirect:\t%d\r\r" % integrator.numIndirectSamples
        else:
            dspy_notes += "Diffuse:\t%d\r" % integrator.numDiffuseSamples
            dspy_notes += "Specular:\t%d\r" % integrator.numSpecularSamples
            dspy_notes += "Subsurface:\t%d\r" % integrator.numSubsurfaceSamples
            dspy_notes += "Refraction:\t%d\r" % integrator.numRefractionSamples

    elif rm.integrator == "PxrVCM":
        dspy_notes += "Light:\t%d\r" % integrator.numLightSamples
        dspy_notes += "Bxdf:\t%d\r\r" % integrator.numBxdfSamples

    # escaping line break is requiered
    params["string dspyParams"] = """ itOpenHandler {::ice::startTimer;};;;                     \
                                      itCloseHandler {::ice::endTimer %%arglist; };;;           \
                                      dspyRender -renderer preview -time %d -crop %f %f %f %f   \
                                      -notes %s""" % (scene.frame_current,
                                                      scene.render.border_min_x,
                                                      scene.render.border_max_x,
                                                      1.0 - scene.render.border_min_y,
                                                      1.0 - scene.render.border_max_y,
                                                      dspy_notes)
    return params

# flush the current edit


def edit_flush(ri, edit_num, prman):
    ri.ArchiveRecord("structure", ri.STREAMMARKER + "%d" % edit_num)
    prman.RicFlush("%d" % edit_num, 0, ri.SUSPENDRENDERING)


def issue_light_vis(rpass, ri, lamp, prman):
    rpass.edit_num += 1
    edit_flush(ri, rpass.edit_num, prman)

    ri.EditBegin('attribute', {'string scopename': lamp.name})
    ri.Attribute('visibility', {'int camera': int(
        lamp.renderman.light_primary_visibility), })
    ri.EditEnd()


def issue_light_transform_edit(ri, obj):
    lamp = obj.data
    ri.EditBegin('attribute', {'string scopename': obj.data.name})
    export_object_transform(ri, obj)
    ri.EditEnd()


def issue_light_filter_transform_edit(ri, rpass, obj):
    lights_attached_to = rpass.light_filter_map[obj.name]
    for light_data_name, light_name in lights_attached_to:
        ri.EditBegin('instance')
        light_obj = bpy.data.objects[light_name]
        lamp = light_obj.data

        export_light_filters(ri, lamp, do_coordsys=True)

        # reset the transform for light
        export_object_transform(ri, light_obj)

        export_light_shaders(ri, lamp, get_light_group(light_obj), obj.parent)
        ri.EditEnd()


def issue_camera_edit(ri, rpass, camera):
    ri.EditBegin('option')
    export_camera(ri, rpass.scene, [], camera_to_use=camera)
    ri.EditEnd()


def update_crop_window(ri, rpass, prman, cw):
    rpass.edit_num += 1
    edit_flush(ri, rpass.edit_num, prman)
    ri.EditBegin('option')
    ri.CropWindow(cw[0], cw[1], cw[2], cw[3])
    ri.EditEnd()

# search this material/lamp for textures to re txmake and do them


def reissue_textures(ri, rpass, mat):
    made_tex = False
    if mat is not None:
        textures = get_textures(mat) if type(mat) == bpy.types.Material else \
            get_textures_for_node(mat.renderman.get_light_node())

        files = rpass.convert_textures(textures)
        if files and len(files) > 0:
            return True
    return False

# return true if an object has an emissive connection


def is_emissive(object):
    if hasattr(object.data, 'materials'):
        # update the light position and shaders if updated
        for mat in object.data.materials:
            if mat is not None and mat.node_tree:
                nt = mat.node_tree
                if 'Output' in nt.nodes and \
                        nt.nodes['Output'].inputs['Light'].is_linked:
                    return True
    return False


def add_light(rpass, ri, active, prman):
    ri.EditBegin('attribute')
    ob = active
    lamp = ob.data
    rm = lamp.renderman
    ri.AttributeBegin()
    export_object_transform(ri, ob)
    ri.ShadingRate(rm.shadingrate)

    export_light_shaders(ri, lamp)

    ri.AttributeEnd()
    ri.Illuminate(lamp.name, rm.illuminates_by_default)
    ri.EditEnd()


def delete_light(rpass, ri, name, prman):
    rpass.edit_num += 1
    edit_flush(ri, rpass.edit_num, prman)
    ri.EditBegin('attribute', {'string scopename': name})
    ri.Attribute('visibility', {'int camera': 0, })
    ri.Bxdf('null', 'null', {})
    ri.EditEnd()
    rpass.edit_num += 1
    edit_flush(ri, rpass.edit_num, prman)
    ri.EditBegin('overrideilluminate')
    ri.Illuminate(name, False)
    ri.EditEnd()


def reset_light_illum(rpass, ri, prman, lights, do_solo=True):
    rpass.edit_num += 1
    edit_flush(ri, rpass.edit_num, prman)
    ri.EditBegin('overrideilluminate')

    for light in lights:
        rm = light.data.renderman
        do_light = rm.illuminates_by_default and not rm.mute
        if do_solo and rpass.scene.renderman.solo_light:
            # check if solo
            do_light = do_light and rm.solo
        ri.Illuminate(light.data.name, do_light)
    ri.EditEnd()


def mute_lights(rpass, ri, prman, lights):
    rpass.edit_num += 1
    edit_flush(ri, rpass.edit_num, prman)
    ri.EditBegin('overrideilluminate')

    for light in lights:
        ri.Illuminate(light.data.name, 0)
    ri.EditEnd()


def solo_light(rpass, ri, prman):
    rpass.edit_num += 1
    edit_flush(ri, rpass.edit_num, prman)
    ri.EditBegin('overrideilluminate')
    ri.Illuminate("*", 0)
    for light in rpass.scene.objects:
        if light.type == "LAMP":
            rm = light.data.renderman
            if rm.solo:
                do_light = rm.illuminates_by_default and not rm.mute
                ri.Illuminate(light.data.name, do_light)
                break
    ri.EditEnd()
    if rm.solo:
        return light
# test the active object type for edits to do then do them


def issue_transform_edits(rpass, ri, active, prman):
    if active.type == 'LAMP' and active.name not in rpass.lights:
        add_light(rpass, ri, active, prman)
        rpass.lights[active.name] = active.data.name
        return

    if active.type not in ['LAMP', 'CAMERA'] and not is_emissive(active):
        return

    rpass.edit_num += 1

    edit_flush(ri, rpass.edit_num, prman)
    # only update lamp if shader is update or pos, seperately
    if active.type == 'LAMP':
        lamp = active.data
        if lamp.renderman.renderman_type == 'FILTER':
            issue_light_filter_transform_edit(ri, rpass, active)
        else:
            issue_light_transform_edit(ri, active)

    elif active.type == 'CAMERA' and active.is_updated:
        issue_camera_edit(ri, rpass, active)
    else:
        if is_emissive(active):
            issue_light_transform_edit(ri, active)


def update_light_link(rpass, ri, prman, link, remove=False):
    rpass.edit_num += 1
    scene = rpass.scene
    edit_flush(ri, rpass.edit_num, prman)
    strs = link.name.split('>')
    ob_names = [strs[3]] if strs[2] == "obj_object" else \
        scene.renderman.object_groups[strs[3]].members.keys()

    for ob_name in ob_names:
        ri.EditBegin('attribute', {'string scopename': ob_name})
        scene_lights = [l.name for l in scene.objects if l.type == 'LAMP']
        light_names = [strs[1]] if strs[0] == "lg_light" else \
            scene.renderman.light_groups[strs[1]].members.keys()
        if strs[0] == 'lg_group' and strs[1] == 'All':
            light_names = [l.name for l in scene.objects if l.type == 'LAMP']
        for light_name in light_names:
            lamp = scene.objects[light_name].data
            rm = lamp.renderman
            if rm.renderman_type == 'FILTER':
                filter_name = light_name
                for light_nm in light_names:
                    if filter_name in scene.objects[light_nm].data.renderman.light_filters.keys():
                        lamp_nm = scene.objects[light_nm].data.name
                        if remove or link.illuminate == "DEFAULT":
                            ri.EnableLightFilter(lamp_nm, filter_name, 1)
                        else:
                            ri.EnableLightFilter(
                                lamp_nm, filter_name, link.illuminate == 'ON')
            else:
                if remove or link.illuminate == "DEFAULT":
                    ri.Illuminate(
                        lamp.name, lamp.renderman.illuminates_by_default)
                else:
                    ri.Illuminate(lamp.name, link.illuminate == 'ON')
        ri.EditEnd()

# test the active object type for edits to do then do them


def issue_shader_edits(rpass, ri, prman, nt=None, node=None, ob=None):
    if node is None:
        mat = None
        if bpy.context.object:
            mat = bpy.context.object.active_material
            if mat not in rpass.material_dict:
                rpass.material_dict[mat] = [bpy.context.object]
            # if the last edit was a material edit skip the attribute edit
            # we get two edits when should get one.
            if rpass.last_edit_mat == mat:
                rpass.last_edit_mat = None
                return
        lamp = None
        world = bpy.context.scene.world
        if mat is None and hasattr(bpy.context, 'lamp') and bpy.context.lamp:
            lamp = bpy.context.object
            mat = bpy.context.lamp
        elif mat is None and nt and nt.name == 'World':
            mat = world
        if mat is None:
            return
        # do an attribute full rebind
        tex_made = False
        if reissue_textures(ri, rpass, mat):
            tex_made = True

        # if texture made flush it
        if tex_made:
            rpass.edit_num += 1
            edit_flush(ri, rpass.edit_num, prman)
        rpass.edit_num += 1
        edit_flush(ri, rpass.edit_num, prman)
        # for obj in objs:
        if mat in rpass.material_dict:
            if ob:
                ri.EditBegin(
                    'attribute', {'string scopename': "^" + ob.name + "$"})
                export_material(ri, mat, iterate_instance=True)
                ri.EditEnd()
            else:
                for obj in rpass.material_dict[mat]:
                    ri.EditBegin(
                        'attribute', {'string scopename': "^" + obj.name + "$"})
                    export_material(ri, mat, iterate_instance=True)
                    ri.EditEnd()
        elif lamp:
            lamp_ob = lamp
            lamp = mat
            ri.EditBegin('attribute', {'string scopename': lamp.name})
            export_light_filters(ri, lamp, do_coordsys=True)

            export_object_transform(ri, lamp_ob)
            export_light_shaders(ri, lamp, get_light_group(ob))
            ri.EditEnd()

        elif world:
            ri.EditBegin('attribute', {'string scopename': world.name})
            export_world(ri, mat.data, do_geometry=True)
            ri.EditEnd()

    else:
        world = bpy.context.scene.world
        mat = None
        instance_num = 0
        mat_name = None

        if bpy.context.object:
            mat = bpy.context.object.active_material
            if mat:
                instance_num = mat.renderman.instance_num
                if rpass.last_edit_mat == mat:
                    rpass.last_edit_mat = None
                    return
                rpass.last_edit_mat = mat
                mat_name = get_mat_name(mat.name)
        # if this is a lamp use that for the mat/name
        if mat is None and node and issubclass(type(node.id_data), bpy.types.Lamp):
            mat = node.id_data
        elif mat is None and nt and nt.name == 'World':
            mat = bpy.context.scene.world
        elif mat is None and bpy.context.object and bpy.context.object.type == 'CAMERA':
            rpass.edit_num += 1
            edit_flush(ri, rpass.edit_num, prman)

            ri.EditBegin('option')
            export_camera(ri, rpass.scene, [],
                          camera_to_use=rpass.scene.camera)
            ri.EditEnd()
            return
        elif mat is None \
                and hasattr(node, "renderman_node_type") \
                and node.renderman_node_type \
                in {'displayfilter', 'displaysamplefilter'}:
            edit_flush(ri, rpass.edit_num, prman)

            ri.EditBegin('instance')
            export_displayfilters(ri, bpy.context.scene)
            ri.EditEnd()
            return
        elif mat is None:
            return

        if not mat_name:
            mat_name = mat.name  # for world/light

        tex_made = False
        if reissue_textures(ri, rpass, mat):
            tex_made = True

        # if texture made flush it
        if tex_made:
            rpass.edit_num += 1
            edit_flush(ri, rpass.edit_num, prman)
        rpass.edit_num += 1
        edit_flush(ri, rpass.edit_num, prman)

        ri.EditBegin('instance')
        handle = mat_name
        if instance_num > 0:
            handle += "_%d" % instance_num
        shader_node_rib(ri, node, handle)
        ri.EditEnd()
