from . import shadergraph_utils
from . import object_utils
from . import prefs_utils
from . import string_utils
from ..rman_constants import RMAN_GLOBAL_VOL_AGGREGATE
from ..rfb_logger import rfb_log
import bpy
import sys


# ------------- Atom's helper functions -------------
GLOBAL_ZERO_PADDING = 5
# Objects that can be exported as a polymesh via Blender to_mesh() method.
# ['MESH','CURVE','FONT']
SUPPORTED_INSTANCE_TYPES = ['MESH', 'CURVE', 'FONT', 'SURFACE']
SUPPORTED_DUPLI_TYPES = ['FACES', 'VERTS', 'GROUP']    # Supported dupli types.
# These object types can have materials.
MATERIAL_TYPES = ['MESH', 'CURVE', 'FONT']
# Objects without to_mesh() conversion capabilities.
EXCLUDED_OBJECT_TYPES = ['LIGHT', 'CAMERA', 'ARMATURE']
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

RMAN_VOL_TYPES = ['RI_VOLUME', 'OPENVDB', 'FLUID']

class BlAttribute:
    '''
    A class to represent Blender's bpy.types.Attribute
    '''

    def __init__(self):
        self.rman_type = ''
        self.rman_name = ''
        self.rman_detail = None
        self.array_len = -1
        self.values = []

    @staticmethod
    def parse_attributes(attrs_dict, ob, detail_map, detail_default='vertex'):
        '''
        Helper function to parse an array of Blender's bpy.types.Attribute

        Args:
            attrs_dict (dict): dictionary of names to BlAttribute instances
            ob (bpy.types.Object): the object that holds the bpy.types.Attribute array
            detail_map (dict): a dictionary of ints to RenderMan detail strings 
            detail_default (str): default detail if we cannot determine what the detail should
                                  be from detail_map
        '''
        import numpy as np

        for attr in ob.data.attributes:
            if attr.name.startswith('.'):
                continue
            rman_attr = None
            if attr.data_type == 'FLOAT2':
                rman_attr = BlAttribute()
                rman_attr.rman_name = attr.name
                rman_attr.rman_type = 'float2'

                npoints = len(attr.data)
                values = np.zeros(npoints*2, dtype=np.float32)
                attr.data.foreach_get('vector', values)
                values = np.reshape(values, (npoints, 2))
                rman_attr.values = values.tolist()

            elif attr.data_type == 'FLOAT_VECTOR':
                rman_attr = BlAttribute()
                rman_attr.rman_name = attr.name
                rman_attr.rman_type = 'vector'

                npoints = len(attr.data)
                values = np.zeros(npoints*3, dtype=np.float32)
                attr.data.foreach_get('vector', values)
                values = np.reshape(values, (npoints, 3))
                rman_attr.values = values.tolist()
            
            elif attr.data_type in ['BYTE_COLOR', 'FLOAT_COLOR']:
                rman_attr = BlAttribute()
                rman_attr.rman_name = attr.name
                if attr.name == 'color':
                    rman_attr.rman_name = 'Cs'
                rman_attr.rman_type = 'color'

                npoints = len(attr.data)
                values = np.zeros(npoints*4, dtype=np.float32)
                attr.data.foreach_get('color', values)
                values = np.reshape(values, (npoints, 4))
                rman_attr.values .extend(values[0:, 0:3].tolist())

            elif attr.data_type == 'FLOAT':
                rman_attr = BlAttribute()
                rman_attr.rman_name = attr.name
                rman_attr.rman_type = 'float'
                rman_attr.array_len = -1

                npoints = len(attr.data)
                values = np.zeros(npoints, dtype=np.float32)
                attr.data.foreach_get('value', values)
                rman_attr.values = values.tolist()                          
            elif attr.data_type in ['INT8', 'INT']:
                rman_attr = BlAttribute()
                rman_attr.rman_name = attr.name
                rman_attr.rman_type = 'integer'
                rman_attr.array_len = -1

                npoints = len(attr.data)
                values = np.zeros(npoints, dtype=np.int32)
                attr.data.foreach_get('value', values)
                rman_attr.values = values.tolist()                
            
            if rman_attr:
                rman_attr.rman_name = string_utils.sanitize_node_name(rman_attr.rman_name)
                attrs_dict[attr.name] = rman_attr     
                detail = detail_map.get(len(attr.data), detail_default)                
                rman_attr.rman_detail = detail

    @staticmethod
    def set_rman_primvars(primvar, bl_attributes):
        '''
        Helper function to loop over a dictionary of BlAttributes and
        set RtParamList

        Args:
            primvar (RtParamList): the RtParamList that we want to set attributes for
            bl_attributes (dict): the dictionary of BlAttributes we're reading from
        '''        
        for nm, rman_attr in bl_attributes.items():
            if rman_attr.rman_detail is None:
                continue
            if rman_attr.rman_type == "float":
                primvar.SetFloatDetail(rman_attr.rman_name, rman_attr.values, rman_attr.rman_detail)
            elif rman_attr.rman_type == "float2":
                primvar.SetFloatArrayDetail(rman_attr.rman_name, rman_attr.values, 2, rman_attr.rman_detail)
            elif rman_attr.rman_type == "vector":
                primvar.SetVectorDetail(rman_attr.rman_name, rman_attr.values, rman_attr.rman_detail)
            elif rman_attr.rman_type == 'color':
                primvar.SetColorDetail(rman_attr.rman_name, rman_attr.values, rman_attr.rman_detail)
            elif rman_attr.rman_type == 'integer':
                primvar.SetIntegerDetail(rman_attr.rman_name, rman_attr.values, rman_attr.rman_detail)

# ------------- Filtering -------------
def is_visible_layer(scene, ob):
    #
    #FIXME for i in range(len(scene.layers)):
    #    if scene.layers[i] and ob.layers[i]:
    #        return True
    return True

def get_renderman_layer(context):
    rm_rl = None
    layer = context.view_layer  
    rm_rl = layer.renderman 

    return rm_rl    

def add_global_vol_aggregate():
    '''
    Checks to see if the global volume aggregate exists.
    If it doesn't exists, we add it.
    '''
    bl_scene = bpy.context.scene
    rm = bl_scene.renderman
    if len(rm.vol_aggregates) > 0:
        vol_agg = rm.vol_aggregates[0]
        if vol_agg.name == RMAN_GLOBAL_VOL_AGGREGATE:
            return
    vol_agg = rm.vol_aggregates.add()
    vol_agg.name = RMAN_GLOBAL_VOL_AGGREGATE
    rm.vol_aggregates.move(len(rm.vol_aggregates)-1, 0)


def should_use_bl_compositor(bl_scene):
    '''
    Check if we should use the Blender compositor

    Args:
        bl_scene (bpy.types.Scene) - the Blender scene

    Returns:
        (bool) - true if we should use the compositor; false if not
    '''
    from . import display_utils

    rm = bl_scene.renderman
    if not bpy.app.background:
        return (rm.render_into == 'blender')

    if not display_utils.using_rman_displays():
        return True

    if not rm.use_bl_compositor:
        # explicitiy turned off
        return False
    
    return bl_scene.use_nodes and bl_scene.render.use_compositing

def any_areas_shading():           
    '''
    Loop through all of the windows/areas and return True if any of
    the view_3d areas have their shading set to RENDERED. Otherwise,
    return False.
    '''    
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D' and space.shading.type == 'RENDERED':
                        return True
    return False           

def get_render_variant(bl_scene):
    #if bl_scene.renderman.is_ncr_license and bl_scene.renderman.renderVariant != 'prman':
    if not bl_scene.renderman.has_xpu_license and bl_scene.renderman.renderVariant != 'prman':
        rfb_log().warning("Your RenderMan license does not include XPU. Reverting to RIS.")
        return 'prman'

    if sys.platform == ("darwin") and bl_scene.renderman.renderVariant != 'prman':
        rfb_log().warning("XPU is not implemented on OSX: using RIS...")
        return 'prman'

    return bl_scene.renderman.renderVariant    

def set_render_variant_config(bl_scene, config, render_config):
    variant = get_render_variant(bl_scene)
    if variant.startswith('xpu'):
        variant = 'xpu'
    config.SetString('rendervariant', variant)

    if variant == 'xpu':

        '''
        ## TODO: For when XPU can support multiple gpu devices...

        xpu_gpu_devices = prefs_utils.get_pref('rman_xpu_gpu_devices')
        gpus = list()
        for device in xpu_gpu_devices:
            if device.use:
                gpus.append(device.id)
        if gpus:
            render_config.SetIntegerArray('xpu:gpuconfig', gpus, len(gpus))    

        # For now, there is only one CPU
        xpu_cpu_devices = prefs_utils.get_pref('rman_xpu_cpu_devices')
        device = xpu_cpu_devices[0]

        render_config.SetInteger('xpu:cpuconfig', int(device.use))

        if not gpus and not device.use:
            # Nothing was selected, we should at least use the cpu.
            print("No devices were selected for XPU. Defaulting to CPU.")
            render_config.SetInteger('xpu:cpuconfig', 1)
        '''

        # Else, we only support selecting one GPU
        xpu_gpu_device = int(prefs_utils.get_pref('rman_xpu_gpu_selection'))
        if xpu_gpu_device > -1:
            render_config.SetIntegerArray('xpu:gpuconfig', [xpu_gpu_device], 1)

        # For now, there is only one CPU
        xpu_cpu_devices = prefs_utils.get_pref('rman_xpu_cpu_devices')
        if len(xpu_cpu_devices) > 0:
            device = xpu_cpu_devices[0]
            render_config.SetInteger('xpu:cpuconfig', int(device.use))    

            if xpu_gpu_device == -1 and not device.use:
                # Nothing was selected, we should at least use the cpu.
                print("No devices were selected for XPU. Defaulting to CPU.")
                render_config.SetInteger('xpu:cpuconfig', 1)                         
        else:
            render_config.SetInteger('xpu:cpuconfig', 1)         

def set_render_variant_spool(bl_scene, args, is_tractor=False):
    variant = get_render_variant(bl_scene)
    if variant.startswith('xpu'):
        variant = 'xpu'
    args.append('-variant')
    args.append(variant)

    if variant == 'xpu':
        device_list = list()
        if not is_tractor:
            '''
            ## TODO: For when XPU can support multiple gpu devices...
            xpu_gpu_devices = prefs_utils.get_pref('rman_xpu_gpu_devices')
            for device in xpu_gpu_devices:
                if device.use:
                    device_list.append('gpu%d' % device.id)

            xpu_cpu_devices = prefs_utils.get_pref('rman_xpu_cpu_devices')
            device = xpu_cpu_devices[0]

            if device.use or not device_list:
                device_list.append('cpu')
            '''
            xpu_gpu_device = int(prefs_utils.get_pref('rman_xpu_gpu_selection'))
            if xpu_gpu_device > -1:
                device_list.append('gpu%d' % xpu_gpu_device)

            xpu_cpu_devices = prefs_utils.get_pref('rman_xpu_cpu_devices')
            if len(xpu_cpu_devices) > 0:
                device = xpu_cpu_devices[0]

                if device.use or xpu_gpu_device < 0:
                    device_list.append('cpu')            
            else:
                device_list.append('cpu')      

        else:
            # Don't add the gpu list if we are spooling to Tractor
            # There is no way for us to know what is available on the blade,
            # so just ask for CPU for now.
            device_list.append('cpu')

        if device_list:
            device_list = ','.join(device_list)
            args.append('-xpudevices:%s' % device_list)  

def get_all_portals(light_ob):
    """Return a list of portals

    Args:
    light_ob (bpy.types.Object) - light object

    Returns:
    (list) - list of portals attached to this light
    """    

    portals = list()
    if light_ob.type != 'LIGHT':
        return portals

    light = light_ob.data
    rm = light.renderman  
    light_shader = rm.get_light_node()

    if light_shader:
        light_shader_name = rm.get_light_node_name()

        if light_shader_name == 'PxrDomeLight':
            for portal_pointer in rm.portal_lights:
                if portal_pointer.linked_portal_ob:
                    portals.append(portal_pointer.linked_portal_ob)
                 
    return portals

def get_all_volume_objects(scene):
    """Return a list of volume objects in the scene

    Args:
    scene (byp.types.Scene) - scene file to look for lights

    Returns:
    (list) - volume objects
    """    
    global RMAN_VOL_TYPES
    volumes = list()
    for ob in scene.objects:
        if object_utils._detect_primitive_(ob) in RMAN_VOL_TYPES:
            volumes.append(ob)
    return volumes

def get_light_group(light_ob, scene):
    """Return the name of the lightGroup for this
    light, if any

    Args:
    light_ob (bpy.types.Object) - object we are interested in
    scene (byp.types.Scene) - scene file to look for lights

    Returns:
    (str) - light group name
    """

    scene_rm = scene.renderman
    for lg in scene_rm.light_groups:
        for member in lg.members:
            if light_ob == member.light_ob:
                return lg.name
    return ''         

def get_all_lights(scene, include_light_filters=True):
    """Return a list of all lights in the scene, including
    mesh lights

    Args:
    scene (byp.types.Scene) - scene file to look for lights
    include_light_filters (bool) - whether or not light filters should be included in the list

    Returns:
    (list) - list of all lights
    """

    lights = list()
    for ob in scene.objects:
        if ob.type == 'LIGHT':
            if hasattr(ob.data, 'renderman'):
                if include_light_filters:
                    lights.append(ob)
                elif ob.data.renderman.renderman_light_role == 'RMAN_LIGHT':            
                    lights.append(ob)
        else:
            mat = getattr(ob, 'active_material', None)
            if not mat:
                continue
            output = shadergraph_utils.is_renderman_nodetree(mat)
            if not output:
                continue
            if len(output.inputs) > 1:
                socket = output.inputs[1]
                if socket.is_linked:
                    node = socket.links[0].from_node
                    if node.bl_label == 'PxrMeshLight':
                        lights.append(ob)       
    return lights

def get_all_lightfilters(scene):
    """Return a list of all lightfilters in the scene

    Args:
    scene (byp.types.Scene) - scene file to look for lights
    
    Returns:
    (list) - list of all lightfilters
    """

    lightfilters = list()
    for ob in scene.objects:
        if ob.type == 'LIGHT':
            if hasattr(ob.data, 'renderman'):
                if ob.data.renderman.renderman_light_role == 'RMAN_LIGHTFILTER':            
                    lightfilters.append(ob)

    return lightfilters    

def get_light_groups_in_scene(scene):
    """ Return a dictionary of light groups in the scene

    Args:
    scene (byp.types.Scene) - scene file to look for lights

    Returns:
    (dict) - dictionary of light gropus to lights
    """

    lgt_grps = dict()
    for light in get_all_lights(scene, include_light_filters=False):
        light_shader = shadergraph_utils.get_light_node(light, include_light_filters=False)
        lgt_grp_nm = getattr(light_shader, 'lightGroup', '')
        if lgt_grp_nm:
            lights_list = lgt_grps.get(lgt_grp_nm, list())
            lights_list.append(light)
            lgt_grps[lgt_grp_nm] = lights_list

    return lgt_grps

def find_node_owner(node, context=None):
    """ Return the owner of this node

    Args:
    node (bpy.types.ShaderNode) - the node that the caller is trying to find its owner
    context (bpy.types.Context) - Blender context

    Returns:
    (id_data) - The owner of this node
    """    
    nt = node.id_data

    def check_group(group_node, nt):
        node_tree = getattr(group_node, 'node_tree', None)
        if node_tree is None:
            return False          
        if node_tree == nt:
            return node_tree

        for n in group_node.node_tree.nodes:
            if n.bl_idname == 'ShaderNodeGroup':
                if check_group(n, nt):
                    return True
        return False
            
    for mat in bpy.data.materials:
        if mat.node_tree is None:
            continue
        if mat.node_tree == nt:
            return mat
        for n in mat.node_tree.nodes:
            # check if the node belongs to a group node
            node_tree = getattr(n, 'node_tree', None)
            if node_tree is None:
                continue            
            if check_group(n, nt):
                return mat

    for world in bpy.data.worlds:
        if world.node_tree == nt:
            return world

    for ob in bpy.data.objects:
        if ob.type == 'LIGHT':
            light = ob.data
            if light.node_tree == nt:
                return ob
        elif ob.type == 'CAMERA':
            if shadergraph_utils.find_projection_node(ob) == node:
                return ob
    return None

def find_node_by_name(node_name, ob_name, library=''):
    """ Finder shader node and object by name(s)

    Args:
    node_name (str) - name of the node we are trying to find
    ob_name (str) - object name we are trying to look for that has node_name
    library (str) - the name of the library the object is coming from.

    Returns:
    (list) - node and object
    """    

    if library != '':
        for group_node in bpy.data.node_groups:
            if group_node.library and group_node.library.name == library and  group_node.name == ob_name:
                node = group_node.nodes.get(node_name, None) 
                if node:
                    return (node, group_node)

        for mat in bpy.data.materials:
            if mat.library and mat.library.name == library and mat.name == ob_name:
                node = mat.node_tree.nodes.get(node_name, None)
                if node:
                    return (node, mat)

        for world in bpy.data.worlds:
            if world.library and world.library.name == library and world.name == ob_name:
                node = world.node_tree.nodes.get(node_name, None)
                if node:
                    return (node, world)

        for obj in bpy.data.objects:
            if obj.library and obj.library.name == library and obj.name == ob_name:
                rman_type = object_utils._detect_primitive_(obj)
                if rman_type in ['LIGHT', 'LIGHTFILTER']:
                    light_node = shadergraph_utils.get_light_node(obj, include_light_filters=True)
                    return (light_node, obj)
                elif rman_type == 'CAMERA':
                    node = shadergraph_utils.find_projection_node(obj)
                    if node:
                        return (node, obj)        

    else:
        group_node = bpy.data.node_groups.get(ob_name)
        if group_node:
            node = group_node.nodes.get(node_name, None) 
            if node:
                return (node, group_node)

        mat = bpy.data.materials.get(ob_name, None)
        if mat:
            node = mat.node_tree.nodes.get(node_name, None)
            if node:
                return (node, mat)

        world = bpy.data.worlds.get(ob_name, None)
        if world:
            node = world.node_tree.nodes.get(node_name, None)
            if node:
                return (node, world)

        obj = bpy.data.objects.get(ob_name, None)
        if obj:
            rman_type = object_utils._detect_primitive_(obj)
            if rman_type in ['LIGHT', 'LIGHTFILTER']:
                light_node = shadergraph_utils.get_light_node(obj, include_light_filters=True)
                return (light_node, obj)
            elif rman_type == 'CAMERA':
                node = shadergraph_utils.find_projection_node(obj)
                if node:
                    return (node, obj)

    return (None, None)

def set_lightlinking_properties(ob, light_ob, illuminate, update_light=True):
    light_props = shadergraph_utils.get_rman_light_properties_group(light_ob)
    if light_props.renderman_light_role not in {'RMAN_LIGHTFILTER', 'RMAN_LIGHT'}:
        return

    if update_light:
        light_ob.update_tag(refresh={'DATA'})
    changed = False
    if light_props.renderman_light_role == 'RMAN_LIGHT':
        exclude_subset = []
        if illuminate == 'OFF':
            do_add = True
            for j, subset in enumerate(ob.renderman.rman_lighting_excludesubset):
                if subset.light_ob == light_ob:            
                    do_add = False
                exclude_subset.append('%s' % string_utils.sanitize_node_name(subset.light_ob.name_full))
            if do_add:
                subset = ob.renderman.rman_lighting_excludesubset.add()
                subset.name = light_ob.name
                subset.light_ob = light_ob
                changed = True
                exclude_subset.append('%s' % string_utils.sanitize_node_name(light_ob.name_full))
        else:
            idx = -1
            for j, subset in enumerate(ob.renderman.rman_lighting_excludesubset):
                if subset.light_ob == light_ob:                    
                    changed = True
                    idx = j
                else:
                    exclude_subset.append('%s' % string_utils.sanitize_node_name(subset.light_ob.name_full))
            if changed:
                ob.renderman.rman_lighting_excludesubset.remove(j)
        ob.renderman.rman_lighting_excludesubset_string = ','.join(exclude_subset)                
    else:
        lightfilter_subset = []
        if illuminate == 'OFF':
            do_add = True
            for j, subset in enumerate(ob.renderman.rman_lightfilter_subset):
                if subset.light_ob == light_ob:
                    do_add = False
                lightfilter_subset.append('-%s' % string_utils.sanitize_node_name(subset.light_ob.name_full))    
                         
            if do_add:
                subset = ob.renderman.rman_lightfilter_subset.add()
                subset.name = light_ob.name
                subset.light_ob = light_ob
                changed = True                      
                lightfilter_subset.append('-%s' % string_utils.sanitize_node_name(light_ob.name_full))
        else:  
            idx = -1
            for j, subset in enumerate(ob.renderman.rman_lightfilter_subset):
                if subset.light_ob == light_ob:
                    changed = True 
                    idx = j                   
                else:  
                    lightfilter_subset.append('-%s' % string_utils.sanitize_node_name(subset.light_ob.name_full))
            if changed:
                ob.renderman.rman_lightfilter_subset.remove(idx)
        ob.renderman.rman_lightfilter_subset_string = ','.join(lightfilter_subset)

    return changed

def reset_workspace(scene):
    from .. import rman_config    
    
    # Set all output paths to default.
    # There doesn't seem to be a way to set properties back to default, so do it manually
    rmcfg = rman_config.__RMAN_CONFIG__.get('rman_properties_scene', None)
    for param_name, ndp in rmcfg.params.items():
        if ndp.panel != 'RENDER_PT_renderman_workspace':
            continue
        setattr(scene.renderman, param_name, ndp.default)    

def use_renderman_textures(context, force_colorspace=True, blocking=True):
    '''
    Change all textures on texture nodes to use the RenderMan .tex file

    Arguments:
        context (bpy.context) - the current Blender context
        force_colorspace (bool) - if on, force the use of the node's selection
        of colorspace, if the node and the texture manager disagree on what colorpsace
        the texture should be using
        blocking (bool) - updating the colorspace will trigger a txmake event. Set this to False
        if you don't want to block while txmake is running
    '''
    from . import texture_utils

    for node in shadergraph_utils.get_all_shading_nodes():       
        for prop_name, meta in node.prop_meta.items():
            param_type = meta['renderman_type']
            if param_type != 'string':
                continue
            if shadergraph_utils.is_texture_property(prop_name, meta):
                prop = getattr(node, prop_name)
                if prop != '':
                    ob = find_node_owner(node, context)
                    txfile = texture_utils.get_txmanager().get_txfile(node, prop_name, ob=ob)  
                    if txfile and not txfile.source_is_tex():
                        colorspace_nm = '%s_colorspace' % prop_name
                        colorspace = getattr(node, colorspace_nm, None)
                        if colorspace:
                            # check the colorspace
                            params = txfile.params.as_dict()   
                            if params['ocioconvert'] != colorspace and force_colorspace:
                                texture_utils.update_txfile_colorspace(txfile, colorspace, blocking=blocking)
                        setattr(node, prop_name, txfile.get_output_texture())
                        continue                  

def is_renderable(scene, ob):
    return (is_visible_layer(scene, ob) and not ob.hide_render) or \
        (ob.type in ['ARMATURE', 'LATTICE', 'EMPTY'] and ob.instance_type not in SUPPORTED_DUPLI_TYPES)
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

def _get_subframes_(segs, scene):
    if segs == 0:
        return []
    min = -1.0
    rm = scene.renderman
    shutter_interval = rm.shutter_angle / 360.0
    if rm.shutter_timing == 'FRAME_CENTER':
        min = 0 - .5 * shutter_interval
    elif rm.shutter_timing == 'FRAME_CLOSE':
        min = 0 - shutter_interval
    elif rm.shutter_timing == 'FRAME_OPEN':
        min = 0

    return [min + i * shutter_interval / (segs - 1) for i in range(segs)]
    