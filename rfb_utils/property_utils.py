from . import string_utils
from . import prefs_utils
from . import osl_utils
from . import filepath_utils
from ..rman_constants import __RMAN_EMPTY_STRING__, __RESERVED_BLENDER_NAMES__, RFB_FLOAT3, BLENDER_INTERP_MAP
from ..rfb_logger import rfb_log
from bpy.props import *
import bpy
import os


__GAINS_TO_ENABLE__ = {
    'diffuseGain': 'enableDiffuse',
    'specularFaceColor': 'enablePrimarySpecular',
    'specularEdgeColor': 'enablePrimarySpecular',
    'roughSpecularFaceColor': 'enableRoughSpecular',
    'roughSpecularEdgeColor': 'enableRoughSpecular',
    'clearcoatFaceColor': 'enableClearCoat',
    'clearcoatEdgeColor': 'enableClearCoat',
    'iridescenceFaceGain': 'enableIridescence',
    'iridescenceEdgeGain': 'enableIridescence',
    'fuzzGain': 'enableFuzz',
    'subsurfaceGain': 'enableSubsurface',
    'singlescatterGain': 'enableSingleScatter',
    'singlescatterDirectGain': 'enableSingleScatter',
    'refractionGain': 'enableGlass',
    'reflectionGain': 'enableGlass',
    'glowGain': 'enableGlow',
}

# these are the names of the extra enable params
# on PxrSurface etc. to enable/disable lobes
__LOBES_ENABLE_PARAMS__ = [
    'enableDiffuse',
    'enablePrimarySpecular',
    'enableSpecular',
    'enableRoughSpecular',
    'enableClearcoat',
    'enableClearCoat',
    'enableIridescence',
    'enableFuzz',
    'enableSubsurface',
    'enableSingleScatter',
    'enableSinglescatter',
    'enableRR',
    'enableInterior',
    'enableGlass',
    'enableGlow',
]

class BlPropInfo:

    def __init__(self, node, prop_name, prop_meta):

        from . import shadergraph_utils

        self.prop_meta = prop_meta
        self.prop_name = prop_name
        self.prop = getattr(node, prop_name, None)
        self.renderman_name = prop_meta.get('renderman_name', prop_name)
        self.param_name = self.renderman_name
        self.vstructmember = prop_meta.get('vstructmember', None)
        self.vstruct = prop_meta.get('vstruct', False)
        self.label = prop_meta.get('label', prop_name)
        self.read_only = prop_meta.get('readOnly', False)
        self.not_connectable = prop_meta.get('__noconnection', True)
        self.widget = prop_meta.get('widget', 'default')
        self.prop_hidden = getattr(node, '%s_hidden' % prop_name, False)
        self.prop_disabled = getattr(node, '%s_disabled' % prop_name, False)
        self.conditionalVisOps = prop_meta.get('conditionalVisOps', dict())
        self.cond_expr = self.conditionalVisOps.get('expr', None)
        self.conditionalLockOps = prop_meta.get('conditionalLockOps', dict())
        self.lock_expr = self.conditionalLockOps.get('lock_expr', self.cond_expr)
        self.renderman_type = prop_meta.get('renderman_type', '')
        self.param_type = self.renderman_type
        self.arraySize = prop_meta.get('arraySize', None)
        self.renderman_array_type = prop_meta.get('renderman_array_type', '')
        self.type = prop_meta.get('type', '')
        self.page = prop_meta.get('page', '')
        self.hide_input = prop_meta.get('hideInput', False)
        self.options = prop_meta.get('options', list())
        self.is_ui_struct = prop_meta.get('is_ui_struct', False)
        self.ui_struct = prop_meta.get('ui_struct', None)

        inputs = getattr(node, 'inputs', dict())
        self.has_input = (prop_name in inputs)
        self.is_linked = False
        self.is_vstruct_linked = False
        self.link = None
        self.socket = None
        self.from_socket = None
        self.from_node = None
        if self.has_input:
            self.socket = inputs.get(prop_name)
            self.is_linked = self.socket.is_linked
            if self.is_linked and len(self.socket.links) > 0:
                self.link = self.socket.links[0]
                self.from_socket = self.link.from_socket
                self.from_node = self.link.from_node

        self.is_vstruct_and_linked = False
        if not self.is_linked:
            self.is_vstruct_and_linked = is_vstruct_and_linked(node, prop_name)

        self.is_texture = shadergraph_utils.is_texture_property(prop_name, prop_meta)
        self.do_export = self.is_exportable()

    def is_exportable(self):
        # check if this param needs to be exported.

        if self.widget == 'null' and not self.vstructmember:
            # if widget is marked null, don't export parameter and rely on default
            # unless it has a vstructmember
            return False
        if self.hide_input:
            return False
        if self.param_type == 'page':
            return False

        if not self.is_linked and self.param_type in ['struct', 'enum']:
            return False

        if self.prop_name == 'inputMaterial' or \
            (self.vstruct is True) or (self.type == 'vstruct'):
            return False

        return True
    
class BlPropVal:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', '')
        self.type = kwargs.get('type', '')
        self.value = None
        self.is_reference = False

    def set_value(self, value):
        self.value = value

    def set_value_reference(self, value):
        if value is None:
            return
        self.value = value
        self.is_reference = True


def get_property_default(node, prop_name):
    bl_prop_name = __RESERVED_BLENDER_NAMES__.get(prop_name, prop_name)
    prop = node.bl_rna.properties.get(bl_prop_name, None)
    dflt = None
    if prop:
        if getattr(prop, 'default_array', None):
            dflt = [p for p in prop.default_array]
        else:
            dflt = prop.default
            
    return dflt

def get_linked_val(bl_prop_info, rman_sg_node, mat_name=None, group_node=None):
    bl_prop_val = BlPropVal( 
        name=bl_prop_info.renderman_name,
        param_type=bl_prop_info.renderman_type,
    )
    param_type = bl_prop_info.renderman_type
    if group_node and bl_prop_info.from_node.bl_idname == 'NodeGroupInput':
        group_socket = group_node.inputs[bl_prop_info.from_socket.name]
        if not group_socket.is_linked:
            val = string_utils.convert_val(group_socket.default_value, type_hint=param_type)
            bl_prop_val.set_value(val)
        else:
            to_socket = group_socket
            from_socket = to_socket.links[0].from_socket
            from_node = to_socket.links[0].from_node                                

            val = get_output_param_str(rman_sg_node,
                    from_node, mat_name, from_socket, to_socket, param_type)
            bl_prop_val.set_value_reference(val)            
    else:
        val = get_output_param_str(rman_sg_node,
                bl_prop_info.from_node, mat_name, bl_prop_info.from_socket, bl_prop_info.socket, param_type)   
        bl_prop_val.set_value_reference(val)         

    return bl_prop_val 

def get_vstruct_linked_val(node, rman_sg_node, bl_prop_info, mat_name=None):
    bl_prop_val = BlPropVal( 
        name=bl_prop_info.renderman_name,
        param_type=bl_prop_info.renderman_type,
    )
    param_type = bl_prop_info.renderman_type
    vstruct_name, vstruct_member = bl_prop_info.vstructmember.split('.')
    from_socket = node.inputs[
        vstruct_name].links[0].from_socket

    if from_socket.node.bl_idname == 'ShaderNodeGroup':
        ng = from_socket.node.node_tree
        group_output = next((n for n in ng.nodes if n.bl_idname == 'NodeGroupOutput'),
                            None)
        if group_output is None:
            return False

        in_sock = group_output.inputs[from_socket.name]
        if len(in_sock.links):
            from_socket = in_sock.links[0].from_socket
            
    vstruct_from_param = "%s_%s" % (
        from_socket.identifier, vstruct_member)
    if vstruct_from_param in from_socket.node.output_meta:
        actual_socket = from_socket.node.output_meta[
            vstruct_from_param]

        node_meta = getattr(
            node, 'shader_meta') if node.bl_idname == "PxrOSLPatternNode" else node.output_meta                        
        node_meta = node_meta.get(vstruct_from_param)
        is_reference = True
        val = get_output_param_str(rman_sg_node,
                from_socket.node, mat_name, actual_socket, to_socket=None, param_type=param_type)
        if node_meta:
            expr = node_meta.get('vstructConditionalExpr')
            # check if we should connect or just set a value
            if expr:
                if expr.split(' ')[0] == 'set':
                    val = 1
                    is_reference = False      
        if is_reference:
            bl_prop_val.set_value_reference(val)
        else:
            bl_prop_val.set_value(val)
    else:
        rfb_log().warning('Warning! %s not found on %s' %
                (vstruct_from_param, from_socket.node.name))       
        
    return bl_prop_val

def get_string_val(node, ob, rman_sg_node, bl_prop_info):
    from . import texture_utils

    if rman_sg_node:
        rman_sg_node.is_frame_sensitive = rman_sg_node.is_frame_sensitive or string_utils.check_frame_sensitive(bl_prop_info.prop)

    val = string_utils.expand_string(bl_prop_info.prop)
    if bl_prop_info.is_texture:
        tx_val = texture_utils.get_txmanager().get_output_tex_from_path(node, bl_prop_info.renderman_name, val, ob=ob)
        val = tx_val if tx_val != '' else val
    elif bl_prop_info.widget == 'assetidoutput':
        display = 'openexr'
        if 'texture' in bl_prop_info.options:
            display = 'texture'
        val = string_utils.expand_string(bl_prop_info.prop, display=display, asFilePath=True)
    return val  

def get_prop_value(node, ob, rman_sg_node, bl_prop_info):
    bl_prop_val = BlPropVal( 
        name=bl_prop_info.renderman_name,
        param_type=bl_prop_info.renderman_type,
    )
    param_type = bl_prop_info.renderman_type 

    # if this is a gain on PxrSurface and the lobe isn't
    # enabled                    
    if node.bl_idname == 'PxrSurfaceBxdfNode' and \
            bl_prop_info.prop_name in __GAINS_TO_ENABLE__ and \
            not getattr(node, __GAINS_TO_ENABLE__[bl_prop_info.prop_name]):
        val = [0, 0, 0] if param_type == 'color' else 0
        bl_prop_val.set_value(val)    
    elif param_type == "string":
        val = get_string_val(node, ob, rman_sg_node, bl_prop_info)
    else:
        val = string_utils.convert_val(bl_prop_info.prop, type_hint=param_type)
    bl_prop_val.set_value(val)
    return bl_prop_val

def set_rix_param(params, param_type, param_name, val, is_reference=False, is_array=False, array_len=-1, node=None, prop_name='', force_write=False):
    """Sets a single parameter in an RtParamList

    Arguments:
        params (RtParamList) - param list to set
        param_type (str) - rman param type
        param_name (str) - rman param name
        val (AnyType) - the value to write to the RtParamList
        is_reference (bool) - whether this is reference parameter
        is_array (bool) - whether we are writing an array param type
        array_len (int) - length of array
        node (AnyType) - the Blender object that this param originally came from. This is necessary
                        so we can grab and compare val with the default value (see get_property_default)
        prop_name (str) - name of the property that we look for the default value
        force_write (bool) - force writing of the param, regardless of what rman_emit_default_params is set to. 
    """


    if is_reference:
        if is_array:
            if param_type == 'float':
                params.SetFloatReferenceArray(param_name, val, array_len)
            elif param_type == 'int':
                params.SetIntegerReferenceArray(param_name, val, array_len)
            elif param_type == 'color':
                params.SetColorReferenceArray(param_name, val, array_len)         
        else:
            if param_type == "float":
                params.SetFloatReference(param_name, val)
            elif param_type == "int":
                params.SetIntegerReference(param_name, val)
            elif param_type == "color":
                params.SetColorReference(param_name, val)
            elif param_type == "point":
                params.SetPointReference(param_name, val)            
            elif param_type == "vector":
                params.SetVectorReference(param_name, val)
            elif param_type == "normal":
                params.SetNormalReference(param_name, val) 
            elif param_type == "struct":
                params.SetStructReference(param_name, val)        
            elif param_type == "bxdf":
                params.SetBxdfReference(param_name, val)       
    else:
        # check if we need to emit this parameter.
        if node != None and not prefs_utils.get_pref('rman_emit_default_params', False):
            pname = param_name
            if prop_name != '':
                pname = prop_name
            dflt = get_property_default(node, pname)
            

            # FIXME/TODO: currently, the python version of RtParamList
            # doesn't allow us to retrieve existing values. For now, only do the
            # default check when the param is not in there. Otherwise, we risk
            # not setting the value during IPR, if the user happens to change
            # the param val back to default. 
            if dflt != None and not params.HasParam(param_name):
                dflt = string_utils.convert_val(dflt, type_hint=param_type)

                # Check if this param is marked always_write.
                # We still have some plugins where the Args file and C++ don't agree
                # on default behavior
                always_write = False
                prop_meta = getattr(node, 'prop_meta', dict())
                if pname in node.prop_meta:
                    meta = prop_meta.get(pname)
                    always_write = meta.get('always_write', always_write)
                    # if always_write or force_write:
                    #    rfb_log().debug('Param: %s for Node: %s is marked always_write' % (pname, node.name))

                if not always_write and val == dflt:
                    return                  

        if is_array:
            if param_type == 'float':
                params.SetFloatArray(param_name, val, array_len)
            elif param_type == 'int':
                params.SetIntegerArray(param_name, val, array_len)
            elif param_type == 'color':
                params.SetColorArray(param_name, val, int(array_len/3))
            elif param_type == 'string':
                params.SetStringArray(param_name, val, array_len)
        else:
            if param_type == "float":
                params.SetFloat(param_name, float(val))
            elif param_type == "int":
                params.SetInteger(param_name, int(val))
            elif param_type == "color":
                params.SetColor(param_name, val)
            elif param_type == "string":
                if val == __RMAN_EMPTY_STRING__:
                    val = ""
                params.SetString(param_name, val.strip())
            elif param_type == "point":
                params.SetPoint(param_name, val)                            
            elif param_type == "vector":
                params.SetVector(param_name, val)
            elif param_type == "normal":
                params.SetNormal(param_name, val)    

def set_primvar_bl_props(primvars, rm, inherit_node=None):
    # set any properties marked primvar in the config file
    for prop_name, meta in rm.prop_meta.items():
        set_primvar_bl_prop(primvars, prop_name, meta, rm, inherit_node=inherit_node)

def set_primvar_bl_prop(primvars, prop_name, meta, rm, inherit_node):
    if 'primvar' not in meta:
        return
        
    conditionalVisOps = meta.get('conditionalVisOps', None)
    if conditionalVisOps:
        # check conditionalVisOps to see if this primvar applies
        # to this object
        expr = conditionalVisOps.get('expr', None)
        node = rm              
        if expr and not eval(expr):
            return

    val = getattr(rm, prop_name)
    if not val:
        return

    if 'inheritable' in meta:
        if float(val) == meta['inherit_true_value']:
            if inherit_node and hasattr(inherit_node, prop_name):
                val = getattr(inherit_node, prop_name)

    ri_name = meta['primvar']
    is_array = False
    array_len = -1
    if 'arraySize' in meta:
        is_array = True
        array_len = meta['arraySize']
    param_type = meta['renderman_type']
    set_rix_param(primvars, param_type, ri_name, val, is_reference=False, is_array=is_array, array_len=array_len, node=rm, prop_name=prop_name)                

def set_rioption_bl_prop(options, prop_name, meta, rm):     
    if 'riopt' not in meta:
        return
    
    val = getattr(rm, prop_name)
    ri_name = meta['riopt']
    is_array = False
    array_len = -1
    if 'arraySize' in meta:
        is_array = True
        array_len = meta['arraySize']
    param_type = meta['renderman_type']
    val = string_utils.convert_val(val, type_hint=param_type)
    set_rix_param(options, param_type, ri_name, val, is_reference=False, is_array=is_array, array_len=array_len, node=rm, prop_name=prop_name)

def set_riattr_bl_prop(attrs, prop_name, meta, rm, check_inherit=True, remove=True):
    if 'riattr' not in meta:
        return

    conditionalVisOps = meta.get('conditionalVisOps', None)
    if conditionalVisOps:
        # check conditionalVisOps to see if this riattr applies
        # to this object
        expr = conditionalVisOps.get('expr', None)       
        node = rm
        if expr and not eval(expr):
            return          

    val = getattr(rm, prop_name)
    ri_name = meta['riattr']
    if check_inherit and 'inheritable' in meta:
        cond = meta['inherit_true_value']
        if isinstance(cond, str):
            if exec(cond):
                if remove:
                    attrs.Remove(ri_name)
                return
        elif float(val) == cond:
            if remove:
                attrs.Remove(ri_name)
            return

    is_array = False
    array_len = -1
    if 'arraySize' in meta:
        is_array = True
        array_len = meta['arraySize']       
    param_type = meta['renderman_type'] 
    val = string_utils.convert_val(val, type_hint=param_type)                         
    set_rix_param(attrs, param_type, ri_name, val, is_reference=False, is_array=is_array, array_len=array_len, node=rm, prop_name=prop_name)


def build_output_param_str(rman_sg_node, mat_name, from_node, from_socket, convert_socket=False, param_type=''):

    from . import shadergraph_utils

    nodes_to_blnodeinfo = getattr(rman_sg_node, 'nodes_to_blnodeinfo', dict())
    if from_node in nodes_to_blnodeinfo:
        bl_node_info = nodes_to_blnodeinfo[from_node]
        sg_node = bl_node_info.sg_node
        from_node_name = str(sg_node.handle.CStr())
    else:
        from_node_name = shadergraph_utils.get_node_name(from_node, mat_name)

    from_sock_name = shadergraph_utils.get_socket_name(from_node, from_socket)
    
    # replace with the convert node's output
    if convert_socket:
        if shadergraph_utils.is_socket_float_type(from_socket):
            return "convert_%s_%s:resultRGB" % (from_node_name, from_sock_name)
        else:
            return "convert_%s_%s:resultF" % (from_node_name, from_sock_name)
    elif param_type == 'bxdf':
       return "%s" % (from_node_name) 
    else:
        return "%s:%s" % (from_node_name, from_sock_name)

def get_output_param_str(rman_sg_node, node, mat_name, socket, to_socket=None, param_type='', check_do_convert=True):

    from . import shadergraph_utils

    # if this is a node group, hook it up to the input node inside!
    if node.bl_idname == 'ShaderNodeGroup':
        ng = node.node_tree
        group_output = next((n for n in ng.nodes if n.bl_idname == 'NodeGroupOutput'),
                            None)
        if group_output is None:
            return None

        # find the index of the socket
        # we can't use the socket name as the NodeGroupOutput can have
        # sockets with the same name
        idx = -1
        for i, output in enumerate(node.outputs):
            if output == socket:
                idx = i

        in_sock = group_output.inputs[idx] 
        if len(in_sock.links):
            link = in_sock.links[0]
            rerouted_node = link.from_node
            rerouted_socket = link.from_socket
            return get_output_param_str(rman_sg_node, rerouted_node, mat_name, rerouted_socket, to_socket=to_socket, param_type=param_type)            
        else:
            return None
    if node.bl_idname == 'NodeGroupInput':
        current_group_node = shadergraph_utils.get_group_node(node)
        
        if current_group_node is None:
            return None
        
        # same as above, find the index of the socket
        # then use that index to get the incoming socket
        # on the group node
        idx = -1
        for i, output in enumerate(node.outputs):
            if output == socket:
                idx = i        

        in_sock = current_group_node.inputs[idx]
        if len(in_sock.links):
            link = in_sock.links[0]
            rerouted_node = link.from_node
            rerouted_socket = link.from_socket
            return get_output_param_str(rman_sg_node, rerouted_node, mat_name, rerouted_socket, to_socket=to_socket, param_type=param_type)
        else:
            return None

    if node.bl_idname == 'NodeReroute':
        if not node.inputs[0].is_linked:
            return None
        link = node.inputs[0].links[0]
        rerouted_node = link.from_node
        rerouted_socket = link.from_socket        
        if rerouted_node is None:
            return None
        else:
            return get_output_param_str(rman_sg_node, rerouted_node, mat_name, rerouted_socket, to_socket=to_socket, param_type=param_type)
        
    do_convert_socket = False
    if check_do_convert:
        do_convert_socket = shadergraph_utils.do_convert_socket(socket, to_socket)

    return build_output_param_str(rman_sg_node, mat_name, node, socket, do_convert_socket, param_type)    


def is_vstruct_or_linked(node, param):
    if param not in node.prop_meta:
        return True
    meta = node.prop_meta[param]
    if 'vstructmember' not in meta.keys():
        if param in node.inputs:
            return node.inputs[param].is_linked
        return False
    elif param in node.inputs and node.inputs[param].is_linked:
        return True
    else:
        vstruct_name, vstruct_member = meta['vstructmember'].split('.')
        if node.inputs[vstruct_name].is_linked:
            from_socket = node.inputs[vstruct_name].links[0].from_socket
            vstruct_from_param = "%s_%s" % (
                from_socket.identifier, vstruct_member)
            return vstruct_conditional(from_socket.node, vstruct_from_param)
        else:
            return False

# tells if this param has a vstuct connection that is linked and
# conditional met
def is_vstruct_and_linked(node, param):
    if param not in node.prop_meta:
        return True    
    meta = node.prop_meta[param]

    if 'vstructmember' not in meta.keys():
        return False

    vstruct_name, vstruct_member = meta['vstructmember'].split('.')
    if node.inputs[vstruct_name].is_linked:
        from_socket = node.inputs[vstruct_name].links[0].from_socket
        # if coming from a shader group hookup across that
        if from_socket.node.bl_idname == 'ShaderNodeGroup':
            ng = from_socket.node.node_tree
            group_output = next((n for n in ng.nodes if n.bl_idname == 'NodeGroupOutput'),
                                None)
            if group_output is None:
                return False

            in_sock = group_output.inputs[from_socket.name]
            if len(in_sock.links):
                from_socket = in_sock.links[0].from_socket
        vstruct_from_param = "%s_%s" % (
            from_socket.identifier, vstruct_member)          
        return vstruct_conditional(from_socket.node, vstruct_from_param)

    return False

# gets the value for a node walking up the vstruct chain
def get_val_vstruct(node, param):
    if param in node.inputs and node.inputs[param].is_linked:
        from_socket = node.inputs[param].links[0].from_socket
        return get_val_vstruct(from_socket.node, from_socket.identifier)
    elif is_vstruct_and_linked(node, param):
        return True
    else:
        return getattr(node, param)

# parse a vstruct conditional string and return true or false if should link
def vstruct_conditional(node, param):
    if not hasattr(node, 'shader_meta') and not hasattr(node, 'output_meta'):
        return False
    meta = getattr(
        node, 'shader_meta') if node.bl_idname == "PxrOSLPatternNode" else node.output_meta
    if param not in meta:
        return False
    meta = meta[param]
    if 'vstructConditionalExpr' not in meta.keys():
        return True

    expr = meta['vstructConditionalExpr']
    expr = expr.replace('connect if ', '')
    set_zero = False
    if ' else set 0' in expr:
        expr = expr.replace(' else set 0', '')
        set_zero = True

    tokens = expr.split()
    new_tokens = []
    i = 0
    num_tokens = len(tokens)
    while i < num_tokens:
        token = tokens[i]
        prepend, append = '', ''
        while token[0] == '(':
            token = token[1:]
            prepend += '('
        while token[-1] == ')':
            token = token[:-1]
            append += ')'

        if token == 'set':
            i += 1
            continue

        # is connected change this to node.inputs.is_linked
        if i < num_tokens - 2 and tokens[i + 1] == 'is'\
                and 'connected' in tokens[i + 2]:
            token = "is_vstruct_or_linked(node, '%s')" % token
            last_token = tokens[i + 2]
            while last_token[-1] == ')':
                last_token = last_token[:-1]
                append += ')'
            i += 3
        else:
            i += 1
        if hasattr(node, token):
            token = "get_val_vstruct(node, '%s')" % token

        new_tokens.append(prepend + token + append)

    if 'if' in new_tokens and 'else' not in new_tokens:
        new_tokens.extend(['else', 'False'])
    return eval(" ".join(new_tokens))

def set_dspymeta_params(node, prop_name, params):
    if node.plugin_name not in ['openexr', 'deepexr']:
        # for now, we only accept openexr an deepexr
        return

    prefix = 'exrheader_'
    prop = getattr(node, prop_name)
    for meta in prop:
        nm = '%s%s' % (prefix, meta.name)
        meta_type = meta.type
        val = getattr(meta, 'value_%s' % meta_type)
        if meta_type == 'float':
            params.SetFloat(nm, val)
        elif meta_type == 'int':
            params.SetInteger(nm, val)
        elif meta_type == 'string':
            params.SetString(nm, val)
        elif meta_type == 'v2f':
            params.SetFloatArray(nm, val, 2)
        elif meta_type == 'v3f':
            params.SetFloatArray(nm, val, 3)
        elif meta_type == 'v2i':
            params.SetIntegerArray(nm, val, 2)            
        elif meta_type == 'v3i':
            params.SetIntegerArray(nm, val, 3)
        elif meta_type == 'box2f':
            params.SetFloatArray(nm, val, 4)
        elif meta_type == 'box2i':
            params.SetIntegerArray(nm, val, 4)
        elif meta_type == 'm33f':
            params.SetFloatArray(nm, val, 9)
        elif meta_type == 'm44f':
            params.SetFloatArray(nm, val, 16)

def set_pxrosl_params(node, rman_sg_node, params, ob=None, mat_name=None):

    prop_meta = getattr(node, 'prop_meta', dict())
    shader_path = filepath_utils.get_real_path(node.shadercode)
    already_read = False
    for input_name, input in node.inputs.items():
        if input_name not in prop_meta and already_read == False: 
            # re-read the OSL shader to get the meta data
            if os.path.exists(shader_path):
                rfb_log().debug("Re-read OSL shader: %s" % shader_path)
                prop_names, prop_meta = osl_utils.readOSO(shader_path)
            already_read = True
        meta = prop_meta.get(input_name, dict())
        prop_type = input.renderman_type
        shader_default_value = meta.get('default', None)
        connectable = meta.get('connectable', True)
        if input.is_linked and connectable:
            to_socket = input
            from_socket = input.links[0].from_socket

            param_type = prop_type
            param_name = input_name

            val = get_output_param_str(rman_sg_node, from_socket.node, mat_name, from_socket, to_socket, param_type)
            if val:
                set_rix_param(params, param_type, param_name, val, is_reference=True)    
        elif type(input).__name__ != 'RendermanNodeSocketStruct':
            if shader_default_value is None:
                # if there is no shader default, skip
                # this might be a point parameter that's set to something like "P" as a default
                continue
            param_type = prop_type
            param_name = input_name
            val = string_utils.convert_val(input.default_value, type_hint=prop_type)
            set_rix_param(params, param_type, param_name, val, is_reference=False)    

def set_ramp_rixparams(node, prop_name, prop, param_type, params):
    nt = node.rman_fake_node_group_ptr
    ramp_name =  prop
    if nt and ramp_name not in nt.nodes:
        # this shouldn't happen, but sometimes can
        # try to look at the bpy.data.node_groups version
        nt = bpy.data.node_groups[node.rman_fake_node_group]    
        if nt and ramp_name not in nt.nodes:
            nt = None
    if param_type == 'colorramp':
        if nt:
            color_ramp_node = nt.nodes[ramp_name]                            
            colors = []
            positions = []
            # double the start and end points
            positions.append(float(color_ramp_node.color_ramp.elements[0].position))
            colors.append(color_ramp_node.color_ramp.elements[0].color[:3])
            for e in color_ramp_node.color_ramp.elements:
                positions.append(float(e.position))
                colors.append(e.color[:3])
            positions.append(
                float(color_ramp_node.color_ramp.elements[-1].position))
            colors.append(color_ramp_node.color_ramp.elements[-1].color[:3])

            params.SetInteger('%s' % prop_name, len(positions))
            params.SetFloatArray("%s_Knots" % prop_name, positions, len(positions))
            params.SetColorArray("%s_Colors" % prop_name, colors, len(positions))

            interp = BLENDER_INTERP_MAP.get(color_ramp_node.color_ramp.interpolation,'catmull-rom')
            params.SetString("%s_Interpolation" % prop_name, interp )  
        else:         
            # this might be from a linked file
            bl_ramp_prop = getattr(node, '%s_bl_ramp' % prop_name)
            if len(bl_ramp_prop) < 1:
                return          

            colors = []
            positions = []    
            r = bl_ramp_prop[0]         
            colors.append(r.rman_value[:3])
            positions.append(r.position)

            for i in range(0, len(bl_ramp_prop)):
                r = bl_ramp_prop[i]
                colors.append(r.rman_value[:3])
                positions.append(r.position)
            colors.append(bl_ramp_prop[-1].rman_value[:3])
            positions.append(bl_ramp_prop[-1].position)

            params.SetInteger('%s' % prop_name, len(positions))
            params.SetFloatArray("%s_Knots" % prop_name, positions, len(positions))
            params.SetColorArray("%s_Colors" % prop_name, colors, len(positions))

            interp = 'catmull-rom'
            params.SetString("%s_Interpolation" % prop_name, interp )                                 

    elif param_type == 'floatramp':  
        if nt:
            float_ramp_node = nt.nodes[ramp_name]                            

            curve = float_ramp_node.mapping.curves[0]
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

            params.SetInteger('%s' % prop_name, len(knots))
            params.SetFloatArray('%s_Knots' % prop_name, knots, len(knots))
            params.SetFloatArray('%s_Floats' % prop_name, vals, len(vals))    
            
            interp_name = '%s_Interpolation' % prop_name
            interp = getattr(node, interp_name, 'linear')
            params.SetString("%s_Interpolation" % prop_name, interp )         
        else:
            # this might be from a linked file
            bl_ramp_prop = getattr(node, '%s_bl_ramp' % prop_name)
            if len(bl_ramp_prop) < 1:
                return          

            vals = []
            knots = []    
            r = bl_ramp_prop[0]         
            vals.append(r.rman_value[:3])
            knots.append(r.position)

            for i in range(0, len(bl_ramp_prop)):
                r = bl_ramp_prop[i]
                vals.append(r.rman_value[:3])
                knots.append(r.position)
            vals.append(bl_ramp_prop[-1].rman_value)
            knots.append(bl_ramp_prop[-1].position)

            params.SetInteger('%s' % prop_name, len(knots))
            params.SetFloatArray('%s_Knots' % prop_name, knots, len(knots))
            params.SetFloatArray('%s_Floats' % prop_name, vals, len(vals))   

            interp_name = '%s_Interpolation' % prop_name
            interp = getattr(node, interp_name, 'linear')
            params.SetString("%s_Interpolation" % prop_name, interp )          

def set_array_rixparams(node, rman_sg_node, mat_name, bl_prop_info, prop_name, prop, params):   
    coll_nm = '%s_collection' % prop_name
    val_array = []
    val_ref_array = []
    param_type = bl_prop_info.renderman_array_type
    param_name = bl_prop_info.renderman_name     
    collection = getattr(node, coll_nm)
    any_connections = False
    inputs = getattr(node, 'inputs', dict())
    input_array_size = len(collection)    
    for i in range(input_array_size):
        elem = collection[i]
        nm = '%s[%d]' % (prop_name, i)
        if nm in node.inputs and inputs[nm].is_linked:
            any_connections = True
            to_socket = node.inputs[nm]
            from_socket = to_socket.links[0].from_socket
            from_node = to_socket.links[0].from_node

            val = get_output_param_str(rman_sg_node,
                from_node, mat_name, from_socket, to_socket, param_type)
            if val:
                if getattr(from_socket, 'is_array', False):      
                    # the socket from the incoming connection is an array
                    # clear val_ref_array so far and resize it to this
                    # socket's array size                    
                    array_size = from_socket.array_size
                    val_ref_array.clear()
                    for i in range(array_size):        
                        cnx_val = '%s[%d]' % (val, i)
                        val_ref_array.append(cnx_val)
                    break
                val_ref_array.append(val)            
            else:
                val_ref_array.append("")            
        else:
            prop = getattr(elem, 'value_%s' % param_type)
            val = string_utils.convert_val(prop, type_hint=param_type)
            if param_type in RFB_FLOAT3:
                val_array.extend(val)
            else:
                val_array.append(val)
            val_ref_array.append("")

    if any_connections:
        set_rix_param(params, param_type, param_name, val_ref_array, is_reference=True, is_array=True, array_len=len(val_ref_array))
    else:
        set_rix_param(params, param_type, param_name, val_array, is_reference=False, is_array=True, array_len=len(val_array))                               

def set_ui_struct_rixparams(node, rman_sg_node, ui_struct_name, params, ob=None, mat_name=None, group_node=None):        
    ui_structs = getattr(node, 'ui_structs', dict())
    ui_struct_members = ui_structs[ui_struct_name]
    array_len = getattr(node, '%s_arraylen' % ui_struct_name)
    for member in ui_struct_members:
        sub_prop_names = getattr(node, member)   
        vals = list()   
        val_ref_array = list() 
        param_type = ""   
        any_connections = False      
        for prop_name in sub_prop_names[:array_len]:
            meta = node.prop_meta[prop_name]
            bl_prop_info = BlPropInfo(node, prop_name, meta)
            param_type = bl_prop_info.renderman_type      
            is_linked = bl_prop_info.is_linked    
            val = None      
            is_reference = False

            if is_linked:
                bl_prop_val = get_linked_val(bl_prop_info, rman_sg_node, mat_name=mat_name, group_node=group_node)
                if bl_prop_val.value:
                    val = bl_prop_val.value
                    any_connections = any_connections or bl_prop_val.is_reference
                    is_reference =  bl_prop_val.is_reference

            # see if vstruct linked
            elif bl_prop_info.is_vstruct_and_linked:
                bl_prop_val = get_vstruct_linked_val(node, rman_sg_node, bl_prop_info, mat_name=mat_name)
                if bl_prop_val.value:
                    val = bl_prop_val.value
                    any_connections = any_connections or bl_prop_val.is_reference
                    is_reference =  bl_prop_val.is_reference                                       
            else:
                bl_prop_val = get_prop_value(node, ob, rman_sg_node, bl_prop_info)
                val = bl_prop_val.value

            if val is not None:
                if is_reference:
                    val_ref_array.append(val)
                else:
                    if param_type in RFB_FLOAT3:
                        vals.extend(val)
                    else:
                        vals.append(val)
                    val_ref_array.append("")
            
        if any_connections:
            set_rix_param(params, param_type, member, val_ref_array, is_reference=True, is_array=True, array_len=len(val_ref_array), node=node, force_write=True)
        else:
            set_rix_param(params, param_type, member, vals, is_reference=False, is_array=True, array_len=len(vals), node=node, force_write=True)


def set_node_rixparams(node, rman_sg_node, params, ob=None, mat_name=None, group_node=None):
    # If node is OSL node get properties from dynamic location.
    if node.bl_label == "PxrOSL":
        set_pxrosl_params(node, rman_sg_node, params, ob=ob, mat_name=mat_name)
        return params

    for prop_name, meta in node.prop_meta.items():
        bl_prop_info = BlPropInfo(node, prop_name, meta)
        param_widget = bl_prop_info.widget 
        param_type = bl_prop_info.renderman_type 
        param_name = bl_prop_info.renderman_name      
        is_linked = bl_prop_info.is_linked
        prop = bl_prop_info.prop

        if not bl_prop_info.do_export:
            continue

        if bl_prop_info.is_ui_struct:
            array_len = getattr(node, '%s_arraylen' % prop_name)
            if array_len > 0:
                set_ui_struct_rixparams(node, rman_sg_node, prop_name, params, ob=ob, mat_name=mat_name, group_node=group_node)
            continue
        elif bl_prop_info.ui_struct:
            # Skip if this is a ui_struct member. This should be taken care of above
            # in set_ui_struct_rix_params
            continue      
        elif param_widget == 'displaymetadata':
            set_dspymeta_params(node, prop_name, params)
            continue
        # array
        elif param_type == 'array':
            # this is a regular array
            set_array_rixparams(node, rman_sg_node, mat_name, bl_prop_info, prop_name, prop, params)
            continue
        # ramps
        elif param_type in ['colorramp', 'floatramp']:
            set_ramp_rixparams(node, prop_name, prop, param_type, params)        
            continue
       
        if is_linked:
            bl_prop_val = get_linked_val(bl_prop_info, rman_sg_node, mat_name=mat_name, group_node=group_node)
            if bl_prop_val.value: 
                set_rix_param(params, param_type, param_name, bl_prop_val.value, is_reference=bl_prop_val.is_reference)
            else:
                rfb_log().debug("Could not find connection for: %s.%s" % (node.name, param_name))                                 

        # see if vstruct linked
        elif bl_prop_info.is_vstruct_and_linked:
            bl_prop_val = get_vstruct_linked_val(node, rman_sg_node, bl_prop_info, mat_name=mat_name)
            set_rix_param(params, param_type, param_name, bl_prop_val.value, is_reference=bl_prop_val.is_reference)

        # else export just the property's value
        else:
            bl_prop_val = get_prop_value(node, ob, rman_sg_node, bl_prop_info)
            is_array = False 
            array_len = -1
            if bl_prop_info.arraySize:
                is_array = True
                array_len = int(bl_prop_info.arraySize)

            set_rix_param(params, param_type, param_name, bl_prop_val.value, is_reference=False, is_array=is_array, array_len=array_len, node=node)
            
    return params      

def property_group_to_rixparams(node, rman_sg_node, sg_node, ob=None, mat_name=None, group_node=None):

    params = sg_node.params
    set_node_rixparams(node, rman_sg_node, params, ob=ob, mat_name=mat_name, group_node=group_node)

def portal_inherit_dome_params(portal_node, dome, dome_node, rixparams):
    '''
    Portal lights need to inherit some parameter values from the dome light
    it is parented to.
    '''   

    from . import texture_utils

    inheritAttrs = {
        "float specular": 1.0,
        "float diffuse": 1.0,
        "int visibleInRefractionPath": True,
        "float shadowDistance": -1.0,
        "float shadowFalloff": -1.0,
        "float shadowFalloffGamma": 1.0,
        "color shadowColor": (0.0,0.0,0.0),
        "int enableShadows": True,
        "string shadowSubset": "",
        "string shadowExcludeSubset": "",
        "vector colorMapGamma": (1.0,1.0,1.0),
        "float colorMapSaturation": 1.0,
    }
    
    for param, dflt in inheritAttrs.items():
        param_type, param_name = param.split(' ')
        dome_val = getattr(dome_node, param_name)
        portal_val = getattr(portal_node, param_name)
        if portal_val != dflt:
            set_rix_param(rixparams, param_type, param_name, portal_val, is_reference=False)
        else:
            set_rix_param(rixparams, param_type, param_name, dome_val, is_reference=False)

    # for color temperature, only inherit if enableTemperature is not True
    # on the portal light
    prop = getattr(portal_node, 'enableTemperature')
    if string_utils.convert_val(prop):
        rixparams.SetInteger('enableTemperature', string_utils.convert_val(prop, type_hint='int'))        
        prop = getattr(portal_node, 'temperature')
        rixparams.SetFloat('temperature', string_utils.convert_val(prop, type_hint='float'))   
    else:
        prop = getattr(dome_node, 'enableTemperature')
        rixparams.SetInteger('enableTemperature', string_utils.convert_val(prop, type_hint='int'))        
        prop = getattr(dome_node, 'temperature')
        rixparams.SetFloat('temperature', string_utils.convert_val(prop, type_hint='float'))         

    # inherit lightColorMap directly from the dome
    tx_node_id = texture_utils.generate_node_id(dome_node, 'lightColorMap', ob=dome)
    tx_val = texture_utils.get_txmanager().get_output_tex_from_id(tx_node_id)
    rixparams.SetString('domeColorMap', tx_val) 

    # inherit exposure directly from dome 
    prop = getattr(dome_node, 'exposure')
    rixparams.SetFloat('exposure', string_utils.convert_val(prop, type_hint='float')) 

    # for intensity, inherit from the dome
    # and scale it by intensityMult
    prop = getattr(dome_node, 'intensity')
    intensityMult = getattr(portal_node, 'intensityMult')
    intensity = intensityMult * prop
    rixparams.SetFloat('intensity', float(intensity))

    # lightColor = lightColor * tint
    lightColor = getattr(dome_node, 'lightColor')
    tint = getattr(portal_node, 'tint')
    portal_color = [lightColor[0] * tint[0], lightColor[1] * tint[1], lightColor[2] * tint[2]]
    rixparams.SetColor('lightColor', portal_color ) 