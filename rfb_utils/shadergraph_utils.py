from . import color_utils
from . import filepath_utils
from . import string_utils
from . import object_utils
from .prefs_utils import get_pref
from ..rman_constants import (
    RMAN_STYLIZED_FILTERS, 
    RMAN_STYLIZED_PATTERNS, 
    RMAN_UTILITY_PATTERN_NAMES, 
    RFB_FLOAT3,
    BLENDER_41,
    RFB_LAMA_NODES
)
import math
import bpy

class BlNodeInfo:
    def __init__(self, sg_node, group_node=None, is_cycles_node=False):
        self.sg_node = sg_node
        self.group_node = group_node
        self.is_cycles_node = is_cycles_node


class RmanConvertNode:
    def __init__(self, node_type, from_node, from_socket, to_node, to_socket):
        self.node_type = node_type
        self.from_node = from_node
        self.from_socket = from_socket
        self.to_node = to_node
        self.to_socket = to_socket

    def __eq__(self, other):
        if type(other) != RmanConvertNode:
            return False
        return (self.node_type == other.node_type and self.from_node == other.from_node and self.from_socket == other.from_socket and self.to_node == other.to_node and self.to_socket == other.to_socket)
    
def find_blimage_nodes(nt):
    '''
    Find all selected Blender/Cycles image nodes in a given node tree.

    Args:
    nt (bpy.types.NodeTree) - Node tree to search

    Returns:
    (list) - a list of ShaderNodeTexImage nodes.

    '''
    nodes = []
    for n in nt.nodes:
        node_type = n.bl_idname
        if n.select and node_type == 'ShaderNodeTexImage':
            nodes.append(n)

    return nodes

def is_renderman_nodetree(material):
    return find_node(material, 'RendermanOutputNode')

def find_rman_output_node(nt):
    nodetype = 'RendermanOutputNode'
    ntree = None
            
    for mat in bpy.data.materials:
        if mat.node_tree is None:
            continue
        if mat.node_tree == nt:
            ntree = mat.node_tree
            break

        for node in mat.node_tree.nodes:
            # check if the node belongs to a group node
            node_tree = getattr(node, 'node_tree', None)
            if node_tree is None:
                continue            
            if node_tree == nt:
                ntree = mat.node_tree    

    if ntree is None:
        return None

    for node in ntree.nodes:
        if getattr(node, "bl_idname", None) == nodetype:
            if getattr(node, "is_active_output", True):
                return node
            if not active_output_node:
                active_output_node = node
    return active_output_node    


def is_mesh_light(ob):
    '''Checks to see if ob is a RenderMan mesh light

    Args:
    ob (bpy.types.Object) - Object caller wants to check.

    Returns:
    (bpy.types.Node) - the PxrMeshLight node if this is a mesh light. Else, returns None.
    '''
        
    #mat = getattr(ob, 'active_material', None)
    mat = object_utils.get_active_material(ob)
    if not mat:
        return None
    output = is_renderman_nodetree(mat)
    if not output:
        return None
    if len(output.inputs) > 1:
        socket = output.inputs[1]
        if socket.is_linked:
            node = socket.links[0].from_node
            if node.bl_label == 'PxrMeshLight':
                return node 

    return None   

def is_rman_light(ob, include_light_filters=True):
    '''Checks to see if ob is a RenderMan light

    Args:
    ob (bpy.types.Object) - Object caller wants to check.
    include_light_filters (bool) - whether or not light filters should be included

    Returns:
    (bpy.types.Node) - the shading node, else returns None.
    '''   
    return get_light_node(ob, include_light_filters=include_light_filters)

def get_rman_light_properties_group(ob):
    '''Return the RendermanLightSettings properties
    for this object. 

    Args:
    ob (bpy.types.Object) - Object caller wants to get the RendermanLightSettings for.

    Returns:
    (RendermanLightSettings) - RendermanLightSettings object
    '''

    if ob is None:
        return None
    if ob.type == 'LIGHT':
        return ob.data.renderman
    else:
        #mat = ob.active_material
        mat = object_utils.get_active_material(ob)
        if mat:
            return mat.renderman_light

    return None

def get_light_node(ob, include_light_filters=True):
    '''Return the shading node for this light object. 

    Args:
    ob (bpy.types.Object) - Object caller is interested in.
    include_light_filters (bool) - whether or not light filters should be included    

    Returns:
    (bpy.types.Node) - The associated shading node for ob
    '''

    if ob.type == 'LIGHT':
        if hasattr(ob.data, 'renderman'):
            if include_light_filters:
                return ob.data.renderman.get_light_node()
            elif ob.data.renderman.renderman_light_role == 'RMAN_LIGHT':
                return ob.data.renderman.get_light_node()
    else:
        return is_mesh_light(ob)

def socket_node_input(nt, socket):
    return next((l.from_node for l in nt.links if l.to_socket == socket), None)

def socket_socket_input(nt, socket):
    return next((l.from_socket for l in nt.links if l.to_socket == socket and socket.is_linked),
                None)

def get_socket_name(node, socket):
    if type(socket) == dict:
        return socket['name'].replace(' ', '')
    # if this is a renderman node we can just use the socket name,
    else:
        if not hasattr('node', 'plugin_name'):
            from .. import rman_bl_nodes

            # cycles node?
            mapping, node_desc = rman_bl_nodes.get_cycles_node_desc(node)
            if node_desc:
                idx = -1
                is_output = socket.is_output
                node_desc_params = node_desc.outputs if is_output else node_desc.params
                sockets = node.outputs if is_output else node.inputs

                # Let's look if there's one with a similar
                # name already
                for p in node_desc_params:
                    if socket.name in p.name:
                        return p.name
                        
                # try based on index       
                for i, input in enumerate(sockets):
                    if socket.name == input.name:
                        idx = i
                        break
                    
                if idx == -1:
                    return socket.identifier.replace(' ', '')

                node_desc_param = node_desc_params[idx]

                return node_desc_param.name                        

            else:
                if socket.name in node.inputs and socket.name in node.outputs:
                    suffix = 'Out' if socket.is_output else 'In'
                    return socket.name.replace(' ', '') + suffix
        return socket.identifier.replace(' ', '')

def has_lobe_enable_props(node):
    if node.bl_idname in {"PxrSurfaceBxdfNode", "PxrLayerPatternOSLNode", "PxrLayerPatternNode"}:
        return True
    return False

def get_socket_type(node, socket):
    sock_type = socket.type.lower()
    if sock_type == 'rgba':
        return 'color'
    elif sock_type == 'value':
        return 'float'
    elif sock_type == 'vector':
        return 'point'
    else:
        return sock_type

def get_node_name(node, prefix=""):
    nm = node.name
    if node.label != "":
        nm = node.label
    if prefix != "":
        return string_utils.sanitize_node_name('%s_%s' % (prefix, nm))
    return string_utils.sanitize_node_name('%s' % nm)

def linked_sockets(sockets):
    if sockets is None:
        return []
    return [i for i in sockets if i.is_linked]

def is_socket_same_type(socket1, socket2):
    '''Compare two NodeSockets to see if they are of the same type. Types that
    are float3 like are considered the same.

    Arguments:
        socket1 (bpy.types.NodeSocket) - first socket to compare
        socket2 (bpy.types.NodeSocket) - second socket to compare

    Returns:
        (bool) - return True if both sockets are the same type
    '''

    return (type(socket1) == type(socket2)) or (is_socket_float_type(socket1) and is_socket_float_type(socket2)) or \
        (is_socket_float3_type(socket1) and is_socket_float3_type(socket2))


def is_socket_float_type(socket):
    '''Check if socket is of float type

    Arguments:
        socket (bpy.types.NodeSocket) - socket to check

    Returns:
        (bool) - return True if socket are float type
    '''    
    renderman_type = getattr(socket, 'renderman_type', None)

    if renderman_type:
        return renderman_type in ['int', 'float']

    else:
        return socket.type in ['INT', 'VALUE']

def is_socket_float3_type(socket):
    '''Check if socket is of float3 type

    Arguments:
        socket (bpy.types.NodeSocket) - socket to check

    Returns:
        (bool) - return True if socket is float3 type
    '''  

    renderman_type = getattr(socket, 'renderman_type', None)

    if renderman_type:
        return renderman_type in RFB_FLOAT3
    else:
        return socket.type in ['RGBA', 'VECTOR'] 

def set_solo_node(node, nt, solo_node_name, refresh_solo=False, solo_node_output=''):
    def hide_all(nt, node):
        if not get_pref('rman_solo_collapse_nodes'):
            return
        for n in nt.nodes:
            hide = (n != node)
            if hasattr(n, 'prev_hidden'):
                setattr(n, 'prev_hidden', n.hide)
            n.hide = hide
            for input in n.inputs:
                if not input.is_linked:
                    if hasattr(input, 'prev_hidden'):
                        setattr(input, 'prev_hidden', input.hide)
                    input.hide = hide

            for output in n.outputs:
                if not output.is_linked:
                    if hasattr(output, 'prev_hidden'):
                        setattr(output, 'prev_hidden', output.hide)
                    output.hide = hide                        

    def unhide_all(nt):
        if not get_pref('rman_solo_collapse_nodes'):
            return        
        for n in nt.nodes:
            hide = getattr(n, 'prev_hidden', False)
            n.hide = hide
            for input in n.inputs:
                if not input.is_linked:
                    hide = getattr(input, 'prev_hidden', False)
                    input.hide = hide

            for output in n.outputs:
                if not output.is_linked:
                    hide = getattr(output, 'prev_hidden', False)
                    output.hide = hide

    if refresh_solo:
        node.solo_nodetree = None
        node.solo_node_name = ''
        node.solo_node_output = ''
        unhide_all(nt)
        return

    if solo_node_name:
        node.solo_nodetree = nt
        node.solo_node_name = solo_node_name
        node.solo_node_output = solo_node_output
        solo_node = nt.nodes[solo_node_name]
        hide_all(nt, solo_node)


# do we need to convert this socket?
def do_convert_socket(from_socket, to_socket):
    if not to_socket:
        return False
    return (is_socket_float_type(from_socket) and is_socket_float3_type(to_socket)) or \
        (is_socket_float3_type(from_socket) and is_socket_float_type(to_socket))

def find_node_input(node, name):
    for input in node.inputs:
        if input.name == name:
            return input

    return None


def find_node(material, nodetype):
    if material and material.node_tree:
        ntree = material.node_tree

        active_output_node = None
        for node in ntree.nodes:
            if getattr(node, "bl_idname", None) == nodetype:
                if getattr(node, "is_active_output", True):
                    return node
                if not active_output_node:
                    active_output_node = node
        return active_output_node

    return None

def find_node_from_nodetree(ntree, nodetype):
    active_output_node = None
    for node in ntree.nodes:
        if getattr(node, "bl_idname", None) == nodetype:
            if getattr(node, "is_active_output", True):
                return node
            if not active_output_node:
                active_output_node = node
    return active_output_node

def find_material_from_nodetree(ntree):
    mat = None
    for m in bpy.data.materials:
        if m.node_tree == ntree.id_data:
            mat = m
            break
    return mat

def is_soloable_node(node):
    is_soloable = False
    node_type = getattr(node, 'renderman_node_type', '')
    if node_type in ('pattern', 'bxdf'):
        if node.bl_label in ['PxrLayer', 'PxrLayerMixer']:
            is_soloable = False
        else:
            is_soloable = True
    return is_soloable

def find_soloable_node(ntree):
    selected_node = None
    for n in ntree.nodes:
        node_type = getattr(n, 'renderman_node_type', '')
        if n.select and node_type in ('pattern', 'bxdf'):
            if n.bl_label in ['PxrLayer', 'PxrLayerMixer']:
                continue
            selected_node = n
            break    
    return selected_node    

def find_selected_pattern_node(ntree):
    selected_node = None
    for n in ntree.nodes:
        node_type = getattr(n, 'renderman_node_type', '')
        if n.select and node_type == 'pattern':
            if n.bl_label in ['PxrLayer', 'PxrLayerMixer']:
                continue
            selected_node = n
            break    
    return selected_node

def find_node_input(node, name):
    for input in node.inputs:
        if input.name == name:
            return input

    return None

# walk the tree for nodes to export
def gather_nodes(node, for_solo_node=False):
    '''gather all of the nodes that are connected
    to the given node

    Arguments:        
        node (byp.types.Node) - the input node we are interested in
        for_solo_node (bool) - whether we are looking for connected nodes for a solo node

    Returns:
        (list) - the list of nodes that are connected to the given node
    '''

    nodes = []
    for socket in node.inputs:
        if socket.is_linked:
            link = socket.links[0]
            from_node = link.from_node
            if for_solo_node and from_node.bl_idname == "NodeGroupInput":
                # for solo nodes, if the current node we are looking at is a NodeGroupInput
                # we know we are inside a NodeGroup.
                # we need to do some special handling here because we don't want to stop
                # collecting nodes when we hit a NodeGroupInput node, we need to look
                # for connected nodes on the "outside". So we get the NodeGroup node, where
                # these inner nodes belong to.

                # we don't need to do this for regular, non-solo node networks because
                # we already do a gather for NodeGroup nodes in RmanMaterialTranslator's
                # translate_node_group method
                from_node = get_group_node(from_node)
            for sub_node in gather_nodes(from_node, for_solo_node=for_solo_node):
                if sub_node not in nodes:
                    nodes.append(sub_node)

            
            if link.from_node.bl_idname == 'NodeReroute':
                continue

            if node.bl_idname == 'NodeReroute':
                continue
            
            # if this is a float->float3 type or float3->float connections, insert
            # either PxrToFloat3 or PxrToFloat conversion nodes         
            if is_socket_float_type(link.from_socket) and is_socket_float3_type(socket):
                convert_node = RmanConvertNode('PxrToFloat3', link.from_node, link.from_socket, link.to_node, link.to_socket)
                if convert_node not in nodes:
                    nodes.append(convert_node)
            elif is_socket_float3_type(link.from_socket) and is_socket_float_type(socket):
                convert_node = RmanConvertNode('PxrToFloat', link.from_node, link.from_socket, link.to_node, link.to_socket)
                if convert_node not in nodes:
                    nodes.append(convert_node)

    if hasattr(node, 'renderman_node_type') and node.renderman_node_type != 'output':
        nodes.append(node)
    elif not hasattr(node, 'renderman_node_type') and node.bl_idname not in ['ShaderNodeOutputMaterial', 'NodeGroupInput', 'NodeGroupOutput']:
        nodes.append(node)

    return nodes    

def gather_all_textured_nodes(ob, nodes_list):   
    nt = None
    if isinstance(ob, bpy.types.Object):
        if ob.type == 'LIGHT':
            nt = ob.data.node_tree
    elif isinstance(ob, bpy.types.Material):
        nt = ob.node_tree
    elif isinstance(ob, bpy.types.ShaderNodeGroup):
        nt = ob.node_tree
    if nt is None:
        return
        
    for node in nt.nodes:
        has_textured_params = getattr(node, 'rman_has_textured_params', False)
        if node not in nodes_list and has_textured_params:
            nodes_list.append(node)
        if node.bl_idname == 'ShaderNodeGroup':
            gather_all_textured_nodes(node, nodes_list)               

def get_nodetree_name(node):
    nt = node.id_data.original

    for nm, ng in bpy.data.node_groups.items():
        if nt == ng.original:
            return nm
            
    for mat in bpy.data.materials:
        if mat.node_tree is None:
            continue
        if mat.node_tree.original == nt:
            return mat.name

    for world in bpy.data.worlds:
        if world.node_tree.original == nt:
            return world.name         

    for ob in bpy.data.objects:
        if ob.type == 'LIGHT':
            light = ob.data
            if light.node_tree is None:
                continue
            if light.node_tree.original == nt:
                return ob.name           
        elif ob.type == 'CAMERA':
            if find_projection_node(ob) == node:
                return ob.name
    return None


def get_group_node(node):
    '''
    Find the group node that this NodeGroupOutput or
    NodeGroupInput belongs to

    Returns
        (bpy.types.NodeGroup)
    '''

    current_group_node = None
    users = bpy.context.blend_data.user_map(subset={node.id_data})
    for group_nt in users[node.id_data]:
        nodes = []
        if isinstance(group_nt, bpy.types.Material):
            nodes = group_nt.node_tree.nodes
        elif isinstance(group_nt, bpy.types.NodeGroup):
            nodes = group_nt.nodes
        elif isinstance(group_nt, bpy.types.ShaderNodeTree):
            nodes = group_nt.nodes            
        for n in nodes:
            if n.bl_idname == 'ShaderNodeGroup':
                for n2 in n.node_tree.nodes:
                    if n2 == node:
                        current_group_node = n
                        break        

    return current_group_node

def get_all_shading_nodes(scene=None):

    '''Find all shading nodes in the scene

    Arguments:
        scene (bpy.types.Scene) - (optional) the scene we want to find the shading nodes in

    Returns:
        (list) - list of all the shading nodes
    '''    

    from . import scene_utils

    nodes = list()

    if not scene:
        context = bpy.context
        scene = context.scene
        
    world = scene.world

    integrator = find_integrator_node(world)
    if integrator:
        nodes.append(integrator)

    nodes.extend(find_displayfilter_nodes(world))
    nodes.extend(find_samplefilter_nodes(world))

    for cam in bpy.data.cameras:
        n = find_projection_node(cam)
        if n:
            nodes.append(n)

    for light in scene_utils.get_all_lights(scene):
        n = get_light_node(light) 
        if n:
            nodes.append(n)

    def get_group_nodes(group_node, nodes):
        for n in group_node.node_tree.nodes:
            if n.bl_idname == 'ShaderNodeGroup':
                get_group_nodes(n, nodes)
            else:
                rman_type = getattr(n, 'renderman_node_type', None)
                if not rman_type:
                    continue
                if hasattr(n, 'prop_meta'):
                    nodes.append(n)                

    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue

        for n in mat.node_tree.nodes:
            if n.bl_idname == 'ShaderNodeGroup':
                get_group_nodes(n, nodes)
                continue
            rman_type = getattr(n, 'renderman_node_type', None)
            if not rman_type:
                continue
            if hasattr(n, 'prop_meta'):
                nodes.append(n)

    return nodes

def save_bl_ramps(bl_scene):
    '''
    Save all ramps to our custom collection properties
    '''

    for node in get_all_shading_nodes():
        if not hasattr(node, 'rman_fake_node_group'):
            continue        
        for prop_name, meta in node.prop_meta.items():
            param_widget = meta.get('widget', 'default')
            param_type = meta['renderman_type']           
            if param_type == 'colorramp':
                nt = bpy.data.node_groups.get(node.rman_fake_node_group, None)
                if nt:
                    prop = getattr(node, prop_name) 
                    ramp_name =  prop
                    color_ramp_node = nt.nodes[ramp_name]                            
                    colors = []
                    positions = []
                    bl_ramp = '%s_bl_ramp' % prop_name
                    bl_ramp_prop = getattr(node, bl_ramp)
                    bl_ramp_prop.clear()
                    for e in color_ramp_node.color_ramp.elements:
                        r = bl_ramp_prop.add()
                        r.position = e.position
                        r.rman_value = e.color
       
            elif param_type == 'floatramp':
                nt = bpy.data.node_groups.get(node.rman_fake_node_group, None)
                if nt:
                    prop = getattr(node, prop_name) 
                    ramp_name =  prop
                    float_ramp_node = nt.nodes[ramp_name]                            

                    curve = float_ramp_node.mapping.curves[0]
                    knots = []
                    vals = []
                    bl_ramp = '%s_bl_ramp' % prop_name
                    bl_ramp_prop = getattr(node, bl_ramp)
                    bl_ramp_prop.clear()
                    for p in curve.points:
                        r = bl_ramp_prop.add()
                        r.position = p.location[0]
                        r.rman_value = p.location[1]

def reload_bl_ramps(bl_scene, check_library=True):
    '''
    Reload all ramps from our custom collection properties. We only
    do this if the NodeTree is from a library.
    '''

    for node in get_all_shading_nodes():
        nt = node.id_data
        if check_library and not nt.library:
            continue

        if not hasattr(node, 'rman_fake_node_group'):
            continue

        color_rman_ramps = node.__annotations__.get('__COLOR_RAMPS__', [])
        float_rman_ramps = node.__annotations__.get('__FLOAT_RAMPS__', [])
        node_group = bpy.data.node_groups.get(node.rman_fake_node_group, None)
        if not node_group:       
            node_group = bpy.data.node_groups.new(
                node.rman_fake_node_group, 'ShaderNodeTree') 
            node_group.use_fake_user = True

        node.rman_fake_node_group_ptr = node_group
        for prop_name in color_rman_ramps:  
            prop = getattr(node, prop_name)       
            ramp_name =  prop               
            n = node_group.nodes.get(ramp_name, None)
            if not n:
                n = node_group.nodes.new('ShaderNodeValToRGB')
                n.name = ramp_name                
            bl_ramp_prop = getattr(node, '%s_bl_ramp' % prop_name)
            if len(bl_ramp_prop) < 1:
                continue                 

            elements = n.color_ramp.elements
            for i in range(0, len(bl_ramp_prop)):
                r = bl_ramp_prop[i]
                if i < len(elements):
                    elem = elements[i]
                    elem.position = r.position
                else:                    
                    elem = elements.new(r.position)
                elem.color = r.rman_value                   

            if len(bl_ramp_prop) < len(elements):
                for elem in [elements[i] for i in range(len(bl_ramp_prop), len(elements)-1)]:
                    elements.remove(elem) 

                # we cannot remove the last element, so 
                # just copy the values and remove the second to last
                # element
                last_elem = elements[-1]
                prev_elem = elements[-2]
                last_elem.color = prev_elem.color
                last_elem.position = prev_elem.position   
                elements.remove(prev_elem)             

        for prop_name in float_rman_ramps:
            prop = getattr(node, prop_name)       
            ramp_name =  prop               
            n = node_group.nodes.get(ramp_name, None)
            if not n:
                n = node_group.nodes.new('ShaderNodeVectorCurve') 
                n.name = ramp_name
            bl_ramp_prop = getattr(node, '%s_bl_ramp' % prop_name)    
            if len(bl_ramp_prop) < 1:
                continue              

            curve = n.mapping.curves[0]
            points = curve.points
            for i in range(0, len(bl_ramp_prop)):
                r = bl_ramp_prop[i]
                if i < len(points):
                    point = points[i]
                    point.location[0] = r.position
                    point.location[1] = r.rman_value
                else:
                    points.new(r.position, r.rman_value)                               

            if len(bl_ramp_prop) < len(points):
                for elem in [points[i] for i in range(len(bl_ramp_prop), len(points)-1)]:
                    points.remove(elem) 

                last_elem = points[-1]
                prev_elem = points[-2]
                last_elem.location[0] = prev_elem.location[0]
                last_elem.location[1] = prev_elem.location[1]   
                points.remove(prev_elem)                                 

def is_texture_property(prop_name, meta):
    param_type = meta['renderman_type']
    if param_type != 'string':
        return False
    options = meta['options']
    param_widget = meta.get('widget', 'default')
    if param_widget in ['fileinput', 'assetidinput']:
        if 'ies' in options:
            return False
        elif ('texture' in options) or ('env' in options) or ('imageplane' in options):    
            return True
    return False

def get_rerouted_node(node):
    '''Find and return the rerouted node and socket, given
    a NodeReroute node

    Arguments:
        node (bpy.types.Node) - A shader node of type NodeReroute

    Returns:
        (bpy.types.Node) - the rerouted node
        (bpy.types.NodeSocket) - the socket that should be connected from the rerouted node
    '''

    if not node.inputs[0].is_linked:
        return (None, None)

    from_node = node.inputs[0].links[0].from_node
    if from_node.bl_idname == 'NodeReroute':
        return get_rerouted_node(from_node)

    socket = node.inputs[0].links[0].from_socket
    return (from_node, socket)

def find_integrator_node(world):
    '''Find and return the integrator node from the world nodetree

    Arguments:
        world (bpy.types.World) - Blender world object

    Returns:
        (RendermanIntegratorNode) - the integrator ShadingNode
    '''
    rm = world.renderman
    if not world.use_nodes:
        return None
    
    output = find_node(world, 'RendermanIntegratorsOutputNode')
    if output:
        socket = output.inputs[0]
        if socket.is_linked:
            return socket.links[0].from_node

    return None

def find_displayfilter_nodes(world):
    '''Find and return all display filter nodes from the world nodetree

    Arguments:
        world (bpy.types.World) - Blender world object

    Returns:
        (list) - list of display filter nodes
    '''  
    df_nodes = []      
    if not world.use_nodes:
        return df_nodes 

    output = find_node(world, 'RendermanDisplayfiltersOutputNode')
    if output:
        for i, socket in enumerate(output.inputs):
            if socket.is_linked:
                bl_df_node = socket.links[0].from_node
                df_nodes.append(bl_df_node)   

    return df_nodes      

def find_samplefilter_nodes(world):
    '''Find and return all sample filter nodes from the world nodetree

    Arguments:
        world (bpy.types.World) - Blender world object

    Returns:
        (list) - list of sample filter nodes
    '''    
    sf_nodes = []
    if not world.use_nodes:
        return sf_nodes 

    output = find_node(world, 'RendermanSamplefiltersOutputNode')
    if output:
        for i, socket in enumerate(output.inputs):
            if socket.is_linked:
                bl_sf_node = socket.links[0].from_node
                sf_nodes.append(bl_sf_node)   

    return sf_nodes

def find_projection_node(camera):
    '''Find the projection node, if any

    Arguments:
        camera (bpy.types.Camera) - Camera object

    Returns:
        (bpy.types.ShaderNode) - projection node
    '''    
    projection_node = None
    if isinstance(camera, bpy.types.Camera):
        nt = camera.renderman.rman_nodetree
    else:
        nt = camera.data.renderman.rman_nodetree
    if nt:
        output = find_node_from_nodetree(nt, 'RendermanProjectionsOutputNode')
        socket = output.inputs[0]
    
        if socket.is_linked:
            projection_node = socket.links[0].from_node  

    return projection_node       

def find_all_stylized_filters(world):
    nodes = list()
    output = find_node(world, 'RendermanDisplayfiltersOutputNode')
    if not output:
        return nodes   

    for i, socket in enumerate(output.inputs):
        if socket.is_linked:
            link = socket.links[0]
            node = link.from_node    
            if node.bl_label in RMAN_STYLIZED_FILTERS:
                nodes.append(node)

    return nodes
                          
def has_stylized_pattern_node(ob, node=None):
    prop_name = ''
    if not node:
        mat = object_utils.get_active_material(ob)
        if not mat:
            return False
        nt = mat.node_tree
        output = is_renderman_nodetree(mat)
        if not output:
            return False
        socket = output.inputs[0]
        if not socket.is_linked:
            return False

        link = socket.links[0]
        node = link.from_node 

    for nm in RMAN_UTILITY_PATTERN_NAMES:
        if hasattr(node, nm):
            prop_name = nm

            prop_meta = node.prop_meta[prop_name]
            if prop_meta['renderman_type'] == 'array':
                coll_nm = '%s_collection' % prop_name   
                collection = getattr(node, coll_nm)

                for i in range(len(collection)):
                    nm = '%s[%d]' % (prop_name, i)  
                    if hasattr(node, 'inputs')  and nm in node.inputs and \
                        node.inputs[nm].is_linked:      
                        to_socket = node.inputs[nm]                    
                        from_node = to_socket.links[0].from_node
                        if from_node.bl_label in RMAN_STYLIZED_PATTERNS:
                            return from_node                                                     

            elif node.inputs[prop_name].is_linked: 
                to_socket = node.inputs[prop_name]                    
                from_node = to_socket.links[0].from_node
                if from_node.bl_label in RMAN_STYLIZED_PATTERNS:
                    return from_node        

    return False

def check_if_connected(srcNode, dstNode):
    found = False
    for socket in srcNode.outputs:
        if socket.is_linked:
            for link in socket.links:
                if link.to_node == dstNode:
                    found = True
                else:
                    found = found or check_if_connected(link.to_node, dstNode)
    return found

def hide_cycles_nodes(id):
    cycles_output_node = None
    if isinstance(id, bpy.types.Material):
        cycles_output_node = find_node(id, 'ShaderNodeOutputMaterial')
    elif isinstance(id, bpy.types.Light):
        cycles_output_node = find_node(id, 'ShaderNodeOutputLight')
    elif isinstance(id, bpy.types.World):
        cycles_output_node = find_node(id, 'ShaderNodeOutputWorld')
    if not cycles_output_node:
        return
    cycles_output_node.hide = True
    for i in cycles_output_node.inputs:
        if i.is_linked:
            i.links[0].from_node.hide = True    


def create_bxdf(bxdf):
    mat = bpy.data.materials.new(bxdf)
    mat.use_nodes = True
    nt = mat.node_tree
    hide_cycles_nodes(mat)    

    output = nt.nodes.new('RendermanOutputNode')

    if bxdf in RFB_LAMA_NODES:
        # This is a LaMa node. Automatically create
        # a LamaSurface node.
        srf = nt.nodes.new('LamaSurfaceBxdfNode')
        srf.location = srf.location
        srf.location[0] -= 300
        nt.links.new(srf.outputs[0], output.inputs[0])
        output.inputs[1].hide = True
        output.inputs[3].hide = True

        lama_node = nt.nodes.new('%sBxdfNode' % bxdf)
        lama_node.location = srf.location
        lama_node.location[0] -= 300

        nt.links.new(lama_node.outputs[0], srf.inputs['materialFront'])
        lama_node.update_mat(mat)
    else:
        default = nt.nodes.new('%sBxdfNode' % bxdf)
        default.location = output.location
        default.location[0] -= 300
        nt.links.new(default.outputs[0], output.inputs[0])
        output.inputs[1].hide = True
        output.inputs[3].hide = True  
        default.update_mat(mat)    

        if bxdf == 'PxrLayerSurface':
            create_pxrlayer_nodes(nt, default)   

    return mat 

def create_pxrlayer_nodes(nt, bxdf):
    from .. import rman_bl_nodes

    mixer = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__["PxrLayerMixer"])
    layer1 = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__["PxrLayer"])
    layer2 = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__["PxrLayer"])

    mixer.location = bxdf.location
    mixer.location[0] -= 300

    layer1.location = mixer.location
    layer1.location[0] -= 300
    layer1.location[1] += 300

    layer2.location = mixer.location
    layer2.location[0] -= 300
    layer2.location[1] -= 300

    nt.links.new(mixer.outputs[0], bxdf.inputs[0])
    nt.links.new(layer1.outputs[0], mixer.inputs['baselayer'])
    nt.links.new(layer2.outputs[0], mixer.inputs['layer1'])         

def _convert_grease_pencil_stroke_texture(mat, nt, output):
    from .. import rman_bl_nodes

    gp_mat = mat.grease_pencil
    col =  gp_mat.color[:3]
    # col = color_utils.linearizeSRGB(col)
    alpha = gp_mat.color[3]

    bl_image = gp_mat.stroke_image
    bxdf = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__['PxrConstant'])
    bxdf.location = output.location
    bxdf.location[0] -= 300
    bxdf.emitColor = col
    bxdf.presence = alpha
    nt.links.new(bxdf.outputs[0], output.inputs[0])

    if not bl_image:
        bxdf.emitColor = [0.0, 0.0, 0.0, 1.0]
    else:
        real_file = filepath_utils.get_real_path(bl_image.filepath)
        manifold = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__['PxrManifold2D'])
        manifold.angle = -math.degrees(gp_mat.pattern_angle)
        manifold.scaleS = gp_mat.pattern_scale[0]
        manifold.scaleT = gp_mat.pattern_scale[1]
        manifold.offsetS = gp_mat.texture_offset[0]
        manifold.offsetT = gp_mat.texture_offset[1]
        manifold.invertT = 1

        texture = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__['PxrTexture'])
        texture.filename = real_file
        texture.linearize = 1
        nt.links.new(manifold.outputs[0], texture.inputs[3])  

        mix = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__['PxrMix'])
        mix.color2 = col
        mix.mix = gp_mat.mix_stroke_factor
        nt.links.new(texture.outputs[0], mix.inputs[0])
        nt.links.new(mix.outputs[0], bxdf.inputs[0])

        nt.links.new(texture.outputs[4], bxdf.inputs[1])              

def _convert_grease_pencil_fill_texture(mat, nt, output):
    from .. import rman_bl_nodes    

    gp_mat = mat.grease_pencil
    col = gp_mat.fill_color[:3]
    # col = color_utils.linearizeSRGB(col)
    alpha = gp_mat.fill_color[3]
    mix_color = gp_mat.mix_color[:3]
    mix_alpha = gp_mat.mix_color[3]

    bxdf = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__['PxrConstant'])
    bxdf.location = output.location
    bxdf.location[0] -= 300
    bxdf.emitColor = col
    bxdf.presence = alpha
    nt.links.new(bxdf.outputs[0], output.inputs[0])

    bl_image = gp_mat.fill_image

    if not bl_image:
        bxdf.emitColor = [0.0, 0.0, 0.0, 1.0]
    else:
        real_file = filepath_utils.get_real_path(bl_image.filepath)
        manifold = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__['PxrManifold2D'])
        manifold.angle = -math.degrees(gp_mat.texture_angle)
        manifold.scaleS = gp_mat.texture_scale[0]
        manifold.scaleT = gp_mat.texture_scale[1]
        manifold.offsetS = gp_mat.texture_offset[0]
        manifold.offsetT = gp_mat.texture_offset[1]
        manifold.invertT = 1

        texture = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__['PxrTexture'])
        texture.filename = real_file
        texture.linearize = 1
        nt.links.new(manifold.outputs[0], texture.inputs[3])

        mix = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__['PxrMix'])
        mix.color2 = col
        mix.mix = gp_mat.mix_factor
        nt.links.new(texture.outputs[0], mix.inputs[0])
        nt.links.new(mix.outputs[0], bxdf.inputs[0])            

        nt.links.new(texture.outputs[4], bxdf.inputs[1])
        
def _convert_grease_pencil_fill_checker(mat, nt, output):
    from .. import rman_bl_nodes    

    gp_mat = mat.grease_pencil
    col = gp_mat.fill_color[:3]
    # col = color_utils.linearizeSRGB(col)
    alpha = gp_mat.fill_color[3]
    mix_color = gp_mat.mix_color[:3]
    mix_alpha = gp_mat.mix_color[3]

    bxdf = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__['PxrConstant'])
    bxdf.location = output.location
    bxdf.location[0] -= 300
    bxdf.emitColor = col
    bxdf.presence = alpha
    nt.links.new(bxdf.outputs[0], output.inputs[0])   

    manifold = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__['PxrManifold2D'])
    manifold.angle = -math.degrees(gp_mat.pattern_angle)
    manifold.scaleS = (1/gp_mat.pattern_gridsize) * gp_mat.pattern_scale[0]
    manifold.scaleT = (1/gp_mat.pattern_gridsize) * gp_mat.pattern_scale[1]

    checker = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__['PxrChecker'])
    checker.colorA = col
    checker.colorB = mix_color

    nt.links.new(manifold.outputs[0], checker.inputs[2])

    checker2 = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__['PxrChecker'])
    checker2.colorA = col
    checker2.colorB = mix_color 

    nt.links.new(manifold.outputs[0], checker2.inputs[2])

    float3_1 = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__['PxrToFloat3'])
    float3_1.input = alpha

    float3_2 = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__['PxrToFloat3'])
    float3_2.input = mix_alpha

    mix = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__['PxrMix'])
    nt.links.new(float3_1.outputs[0], mix.inputs[0])
    nt.links.new(float3_2.outputs[0], mix.inputs[1])
    nt.links.new(checker2.outputs[1], mix.inputs[2])

    nt.links.new(checker.outputs[0], bxdf.inputs[0])
    nt.links.new(mix.outputs[0], bxdf.inputs[1])

def convert_grease_pencil_mat(mat, nt, output):
    from .. import rman_bl_nodes

    gp_mat = mat.grease_pencil
    if gp_mat.show_stroke:
        stroke_style = gp_mat.stroke_style
        if stroke_style == 'TEXTURE':
            _convert_grease_pencil_stroke_texture(mat, nt, output)
        else:
            col =  gp_mat.color[:3]
            # col = color_utils.linearizeSRGB(col)
            alpha = gp_mat.color[3]

            bxdf = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__['PxrConstant'])
            bxdf.location = output.location
            bxdf.location[0] -= 300
            bxdf.emitColor = col
            bxdf.presence = alpha
            nt.links.new(bxdf.outputs[0], output.inputs[0])    
    elif gp_mat.show_fill:
        fill_style = gp_mat.fill_style
        if fill_style == 'CHECKER':
            _convert_grease_pencil_fill_checker(mat, nt, output)
        elif fill_style == 'TEXTURE':
            _convert_grease_pencil_fill_texture(mat, nt, output)
        else:    
            col = gp_mat.fill_color[:3]
            # col = color_utils.linearizeSRGB(col)
            alpha = gp_mat.fill_color[3]
            mix_color = gp_mat.mix_color[:3]
            mix_alpha = gp_mat.mix_color[3]    
    
            bxdf = nt.nodes.new(rman_bl_nodes.__BL_NODES_MAP__['PxrConstant'])
            bxdf.location = output.location
            bxdf.location[0] -= 300
            bxdf.emitColor = col
            bxdf.presence = alpha
            nt.links.new(bxdf.outputs[0], output.inputs[0])    
