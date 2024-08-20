import sys
import os
import bpy

import re
import shutil
import mathutils
from math import radians
from ..rfb_utils import filepath_utils
from ..rfb_utils.envconfig_utils import envconfig
from ..rfb_utils import string_utils
from ..rfb_utils import shadergraph_utils
from ..rfb_utils import object_utils   
from ..rfb_utils import transform_utils
from ..rfb_utils import texture_utils
from ..rfb_utils import color_manager_blender as clr_mgr
from ..rfb_utils.prefs_utils import get_pref, get_addon_prefs
from ..rfb_utils.property_utils import __GAINS_TO_ENABLE__, __LOBES_ENABLE_PARAMS__, is_vstruct_and_linked, BlPropInfo
from ..rfb_logger import rfb_log
from ..rman_bl_nodes import __BL_NODES_MAP__, __RMAN_NODE_TYPES__
from ..rman_constants import RMAN_STYLIZED_FILTERS, RFB_FLOAT3, CYCLES_NODE_MAP, RMAN_SUPPORTED_VERSION_STRING
from ..rman_constants import RFB_ASSET_VERSION_KEY, RFB_ASSET_VERSION, BLENDER_VERSION_MAJOR, BLENDER_VERSION_MINOR
from ..rman_constants import RMAN_INTERP_MAP, BLENDER_INTERP_MAP
from ..rfb_utils.shadergraph_utils import RmanConvertNode

import rman_utils.rman_assets.lib as ral
from rman_utils.rman_assets.core import RmanAsset, FilePath
from rman_utils.rman_assets.core import TrMode, TrStorage, TrSpace, TrType
from rman_utils.rman_assets.common.external_files import ExternalFile


__BLENDER_PRESETS_HOST_PREFS__ = None

def get_host_prefs():
    global __BLENDER_PRESETS_HOST_PREFS__
    if not __BLENDER_PRESETS_HOST_PREFS__:
        __BLENDER_PRESETS_HOST_PREFS__ = BlenderHostPrefs()
        __BLENDER_PRESETS_HOST_PREFS__.initConfig()

        # restore the last library selection
        try:
            __BLENDER_PRESETS_HOST_PREFS__.cfg.setCurrentLibraryByPath(
                __BLENDER_PRESETS_HOST_PREFS__.getSelectedLibrary())
        except BaseException:
            # the last library selected by the client app can not be found.
            # we fallback to the first available library and update the
            # client's prefs.
            __BLENDER_PRESETS_HOST_PREFS__.cfg.setCurrentLibraryByName(None)
            __BLENDER_PRESETS_HOST_PREFS__.setSelectedLibrary(
                __BLENDER_PRESETS_HOST_PREFS__.cfg.getCurrentLibraryPath())       

    return __BLENDER_PRESETS_HOST_PREFS__

##
# @brief      Exception class to tell the world about our miserable failings.
#
class RmanAssetBlenderError(Exception):

    def __init__(self, value):
        self.value = "RmanAssetBlender Error: %s" % value

    def __str__(self):
        return repr(self.value)
        
        
def default_label_from_file_name(filename):
    # print filename
    lbl = os.path.splitext(os.path.basename(filename))[0]
    # print lbl
    lbl = re.sub('([A-Z]+)', r' \1', lbl)
    # print lbl
    lbl = lbl.replace('_', ' ')
    return lbl.strip().capitalize()

def asset_name_from_label(label):
    """Builds a filename from the asset label string.

    Args:
    - label (str): User-friendly label

    Returns:
    - the asset file name
    """
    assetDir = re.sub(r'[^\w]', '', re.sub(' ', '_', label)) + '.rma'
    return assetDir

class BlenderProgress:
    def __init__(self,):
        self._val = -1
        self._pbar = bpy.context.window_manager
        # print 'Progress init: using %s' % self._pbar

    def Start(self):
        self._pbar.progress_begin(0,100)

    def Update(self, val, msg=None):
        self._pbar.progress_update(val)

    def End(self):
        self._pbar.progress_end()

class BlenderHostPrefs(ral.HostPrefs):
    def __init__(self):
        super(BlenderHostPrefs, self).__init__(RMAN_SUPPORTED_VERSION_STRING)
        self.debug = False

        # === Library Prefs ===
        #
        self.rpbConfigFile = FilePath(self.getHostPref('rpbConfigFile', u''))
        # the list of user libraries from Maya prefs
        self.rpbUserLibraries = self.getHostPref('rpbUserLibraries', [])
        # We don't initialize the library configuration just yet. We want
        # to do it only once the prefs objects has been fully contructed.
        # This is currently done in rman_assets.ui.Ui.__init__()
        self.cfg = None

        # === UI Prefs ===
        #
        # our prefered swatch size in the UI.
        self.rpbSwatchSize = self.getHostPref('rpbSwatchSize', 64)
        # the last selected preview type
        self.rpbSelectedPreviewEnv = self.getHostPref(
            'rpbSelectedPreviewEnv', 0)
        # the last selected category
        self.rpbSelectedCategory = self.getHostPref('rpbSelectedCategory', u'')
        # the last selected preset
        self.rpbSelectedPreset = self.getHostPref('rpbSelectedPreset', u'')

        # the last selected library
        self.rpbSelectedLibrary = FilePath(self.getHostPref(
            'rpbSelectedLibrary', u''))
    
        storagePrefs = (
            ('rpbStorageMode', 0), 
            ('rpbStorageKey', ''), 
            ('rpbStoragePath', ''),
            ('rpbConvertToTex', 1))

        for name, default in storagePrefs:
            setattr(self, name, self.getHostPref(name, default))

        # store these to make sure we render the previews with the same version.
        self.hostTree = os.environ.get('RFMTREE', '')
        self.rmanTree = os.environ.get('RMANTREE', '')

        # === User Prefs ===
        #
        # render all HDR environments ?
        self.rpbRenderAllHDRs = self.getHostPref('rpbRenderAllHDRs', 0)
        self.rpbHideFactoryLib = self.getHostPref('rpbHideFactoryLib', 0)

        self._nodesToExport = dict()
        self.renderman_output_node = None
        self.blender_material = None
        self.bl_world = None
        self.progress = BlenderProgress()

        self.current_asset = None
        self.import_displayfilters = False

    def getHostPref(self, prefName, defaultValue): # pylint: disable=unused-argument
        if prefName == 'rpbUserLibraries':
            val = list()
            prefs = get_addon_prefs()
            for p in prefs.rpbUserLibraries:
                path = p.path
                if path.endswith('/'):
                    path = path[:-1]
                if path not in val:
                    val.append(path)
        else:
            val = get_pref(pref_name=prefName, default=defaultValue)
        return val

    def setHostPref(self, prefName, value): # pylint: disable=unused-argument
        """Save the given value in the host's preferences.
        First look at the value's type and call the matching host API.

        Args:
            prefName (str): The class attribute name for that pref.
            value (any): The value we should pass to the delegate.

        Raises:
            RmanAssetLibError: If we don't support the given data type.
        """
        isArray = isinstance(value, list)
        tvalue = value
        prefs = get_addon_prefs()
        if isArray:
            tvalue = value[0]
        if isinstance(tvalue, int):
            if isArray:
                pass
            else:
                setattr(prefs, prefName, value) 
        elif isinstance(tvalue, str):
            if isArray:
                if prefName == 'rpbUserLibraries':
                    prefs = get_addon_prefs()
                    prefs.rpbUserLibraries.clear()
                    for val in list(dict.fromkeys(value)):
                        if not os.path.exists(val):
                            continue
                        p = prefs.rpbUserLibraries.add()
                        p.path = val
            else:
                setattr(prefs, prefName, value)                
        else:
            arrayStr = ''
            if isArray:
                arrayStr = ' array'
            msg = ('HostPrefs.setHostPref: %s%s NOT supported !' %
                   (type(tvalue), arrayStr))
            pass
        bpy.ops.wm.save_userpref()        

    def saveAllPrefs(self):
        self.setHostPref('rpbUserLibraries', self.rpbUserLibraries)
        self.setHostPref('rpbSelectedLibrary', self.rpbSelectedLibrary)
        self.setHostPref('rpbSelectedCategory', self.rpbSelectedCategory)
        self.setHostPref('rpbSelectedPreset', self.rpbSelectedPreset)
        self.setHostPref('rpbStorageMode', self.rpbStorageMode)
        self.setHostPref('rpbStorageKey', self.rpbStorageKey)
        self.setHostPref('rpbStoragePath', self.rpbStoragePath)
        self.setHostPref('rpbConvertToTex', self.rpbConvertToTex) 
        self.setHostPref('rpbSwatchSize', self.rpbSwatchSize)       

    def updateLibraryConfig(self):
        self.cfg.buildLibraryList(updateFromPrefs=True)

    def getSelectedCategory(self):
        return self.rpbSelectedCategory

    def setSelectedCategory(self, val):
        self.rpbSelectedCategory = val

    def getSelectedPreset(self):
        return self.rpbSelectedPreset

    def setSelectedPreset(self, val):
        self.rpbSelectedPreset = val  

    def getSelectedLibrary(self):
        return self.rpbSelectedLibrary

    def setSelectedLibrary(self, path):
        self.rpbSelectedLibrary = path

    def getSwatchSize(self):
        return self.rpbSwatchSize

    def setSwatchSize(self, value):
        self.rpbSwatchSize = min(max(value, 64), 128)

    def doAssign(self):
        return True

    def gather_material_nodes(self, mat):
        lst = list()
        out = shadergraph_utils.is_renderman_nodetree(mat)
        self.renderman_output_node = out
        nodes = shadergraph_utils.gather_nodes(out)
        lst.extend(nodes)
        self._nodesToExport['material'] = lst

    def gather_displayfilter_nodes(self, context):
        self.bl_world = context.scene.world
        nodes = shadergraph_utils.find_displayfilter_nodes(self.bl_world)
        self._nodesToExport['displayfilter'] = nodes

    def preExportCheck(self, mode, hdr=None): # pylint: disable=unused-argument
        context = bpy.context
        if mode == 'material':
            ob = getattr(context, 'active_object', None)
            if not ob:
                if hasattr(context, 'selected_objects'):
                    ob = context.selected_objects[0]
                else:
                    scene = context.scene
                    ob = scene.view_layers[0].objects.active            
            mat = ob.active_material
            self.blender_material = mat
            self.gather_material_nodes(mat) 
            self._nodesToExport['displayfilter'] = list()
            self.gather_displayfilter_nodes(context)

            self._defaultLabel = mat.name

        elif mode == 'lightrigs':
            lst = list()
            selected_light_objects = []
            selected_objects = getattr(context, 'selected_objects', None)
            if not selected_objects:
                scene = context.scene
                selected_objects = scene.view_layers[0].objects.selected
            if selected_objects:
                for obj in selected_objects:  
                    if object_utils._detect_primitive_(obj) == 'LIGHT':
                        selected_light_objects.append(obj)
            if not selected_light_objects:
                return False
            lst.extend(selected_light_objects)
            self._nodesToExport['lightrigs'] = lst
            self._defaultLabel = lst[0].name
        elif mode == 'envmap':
            if not hdr.exists():
                rfb_log().warning('hdr file does not exist: %s', hdr)
                return False
            self._nodesToExport['envmap'] = [hdr]
            self._defaultLabel = default_label_from_file_name(hdr)
            return True
        else:
            rfb_log().error('preExportCheck: unknown mode: %s', repr(mode))
            return False
        return True

    def exportMaterial(self, categorypath, infodict, previewtype): # pylint: disable=unused-argument
        return export_asset(self._nodesToExport, 'nodeGraph', infodict, categorypath,
                            self.cfg, previewtype, isLightRig=False)

    def exportLightRig(self, categorypath, infodict): # pylint: disable=unused-argument
        return export_asset(self._nodesToExport, 'nodeGraph', infodict, categorypath,
                            self.cfg,  renderPreview='std', isLightRig=True)

    def exportEnvMap(self, categorypath, infodict): # pylint: disable=unused-argument
        return export_asset(self._nodesToExport, 'envMap', infodict, categorypath,
                            self.cfg)

    def importAsset(self, asset, assignToSelected=False): # pylint: disable=unused-argument
        import_asset(asset, assignToSelected)

    def getAllCategories(self, asDict=False):
        return sorted(ral.getAllCategories(self.cfg, asDict=asDict))

    def getAssetList(self, relpath):
        return ral.getAssetList(self.cfg, relpath)        

def fix_blender_name(name):
    return name.replace(' ', '').replace('.', '')

def set_asset_params(ob, node, nodeName, Asset):
    node_type = node.bl_label

    # If node is OSL node get properties from dynamic location.
    if node.bl_idname == "PxrOSLPatternNode":
        for input_name, input in node.inputs.items():
            prop_type = input.renderman_type           
            if input.is_linked:
                to_socket = input
                from_socket = input.links[0].from_socket

                param_type = 'reference %s' % prop_type
                param_name = input_name
                val = None

            elif type(input).__name__ != 'RendermanNodeSocketStruct':

                param_type = prop_type
                param_name = input_name
                val = string_utils.convert_val(input.default_value, type_hint=prop_type)  

            pdict = {'type': param_type, 'value': val}
            Asset.addParam(nodeName, node_type, param_name, pdict)   

        return                               

    for prop_name, meta in node.prop_meta.items():
        bl_prop_info = BlPropInfo(node, prop_name, meta)

        if not bl_prop_info.do_export:
            continue

        param_widget = bl_prop_info.widget 
        prop = bl_prop_info.prop
        param_name = bl_prop_info.renderman_name 
        param_type = bl_prop_info.renderman_type 
        is_linked = bl_prop_info.is_linked

        if is_linked:
            param_type = 'reference %s' % meta['renderman_type']
            param_name = meta['renderman_name']
            
            pdict = {'type': param_type, 'value': None}
            Asset.addParam(nodeName, node_type, param_name, pdict)            

        # see if vstruct linked
        elif is_vstruct_and_linked(node, prop_name):
            val = None
            vstruct_name, vstruct_member = bl_prop_info.vstructmember.split('.')
            from_socket = node.inputs[
                vstruct_name].links[0].from_socket

            vstruct_from_param = "%s_%s" % (
                from_socket.identifier, vstruct_member)
            if vstruct_from_param in from_socket.node.output_meta:

                node_meta = getattr(
                    node, 'shader_meta') if node.bl_idname == "PxrOSLPatternNode" else node.output_meta                        
                node_meta = node_meta.get(vstruct_from_param)
                if node_meta:
                    expr = node_meta.get('vstructConditionalExpr')
                    # check if we should connect or just set a value
                    if expr:
                        if expr.split(' ')[0] == 'set':
                            val = 1
                            param_type = meta['renderman_type']      

                pdict = {'type': param_type, 'value': val}
                Asset.addParam(nodeName, node_type, param_name, pdict)                          

            else:
                rfb_log().warning('Warning! %s not found on %s' %
                        (vstruct_from_param, from_socket.node.name))

        # else output rib
        else:
            val = None

            # if this is a gain on PxrSurface and the lobe isn't
            # enabled            
            if node.bl_idname == 'PxrSurfaceBxdfNode' and \
                    prop_name in __GAINS_TO_ENABLE__ and \
                    not getattr(node, __GAINS_TO_ENABLE__[prop_name]):
                val = [0, 0, 0] if meta[
                    'renderman_type'] == 'color' else 0

            elif param_type == 'string':
                val = string_utils.expand_string(prop)
                options = meta['options']
                if bl_prop_info.is_texture:                    
                    tx_node_id = texture_utils.generate_node_id(node, param_name, ob=ob)
                    tx_val = texture_utils.get_txmanager().get_output_tex_from_id(tx_node_id)
                    val = tx_val if tx_val != '' else val
                elif param_widget == 'assetidoutput':
                    display = 'openexr'
                    if 'texture' in options:
                        display = 'texture'
                    val = string_utils.expand_string(val, display=display, asFilePath=True)

            elif param_type == 'array':
                val_array = []
                val_ref_array = []
                coll_nm = '%s_collection' % prop_name
                collection = getattr(node, coll_nm)
                array_len = len(collection)
                param_array_type = bl_prop_info.renderman_array_type
                param_type = '%s[%d]' % (param_array_type, array_len)
                
                for elem in collection:
                    nm = elem.name
                    if hasattr(node, 'inputs')  and nm in node.inputs and \
                        node.inputs[nm].is_linked:
                        val_ref_array.append('')
                    else:
                        prop = getattr(elem, 'value_%s' % param_array_type)
                        val = string_utils.convert_val(prop, type_hint=param_array_type)
                        if param_array_type in RFB_FLOAT3:
                            val_array.extend(val)
                        else:
                            val_array.append(val)
                if val_ref_array:
                    pdict = {'type': '%s [%d]' % (param_array_type, len(val_ref_array)), 'value': None}
                    Asset.addParam(nodeName, node_type, param_name, pdict)
                else:                            
                    pdict = {'type': param_array_type, 'value': val_array}
                    Asset.addParam(nodeName, node_type, param_name, pdict)
                continue
            elif param_type == 'colorramp':
                nt = bpy.data.node_groups[node.rman_fake_node_group]
                if nt:
                    ramp_name =  prop
                    color_ramp_node = nt.nodes[ramp_name]                            
                    colors = []
                    positions = []
                    for e in color_ramp_node.color_ramp.elements:
                        positions.append(float(e.position))
                        colors.append(e.color[:3])

                    array_size = len(positions)
                    pdict = {'type': 'int', 'value': array_size}
                    Asset.addParam(nodeName, node_type, prop_name, pdict)

                    pdict = {'type': 'float[%d]' % array_size, 'value': positions}
                    Asset.addParam(nodeName, node_type, "%s_Knots" % prop_name, pdict)

                    pdict = {'type': 'color[%d]' % array_size, 'value': colors}
                    Asset.addParam(nodeName, node_type, "%s_Colors" % prop_name, pdict)

                    interp = BLENDER_INTERP_MAP.get(color_ramp_node.color_ramp.interpolation,'catmull-rom')   
                    pdict = {'type': 'string', 'value': interp}
                    Asset.addParam(nodeName, node_type, "%s_Interpolation" % prop_name, pdict)                            
                continue               
            elif param_type == 'floatramp':
                nt = bpy.data.node_groups[node.rman_fake_node_group]
                if nt:
                    ramp_name =  prop
                    float_ramp_node = nt.nodes[ramp_name]                            

                    curve = float_ramp_node.mapping.curves[0]
                    knots = []
                    vals = []
                    for p in curve.points:
                        knots.append(p.location[0])
                        vals.append(p.location[1])
                        
                    array_size = len(knots)   

                    pdict = {'type': 'int', 'value': array_size}
                    Asset.addParam(nodeName, node_type, prop_name, pdict)

                    pdict = {'type': 'float[%d]' % array_size, 'value': knots}
                    Asset.addParam(nodeName, node_type, "%s_Knots" % prop_name, pdict)

                    pdict = {'type': 'float[%d]' % array_size, 'value': vals}
                    Asset.addParam(nodeName, node_type, "%s_Floats" % prop_name, pdict)                                                     

                    pdict = {'type': 'string', 'value': 'catmull-rom'}
                    Asset.addParam(nodeName, node_type, "%s_Interpolation" % prop_name, pdict)                              
        
                continue
            else:
                val = string_utils.convert_val(prop, type_hint=param_type)

            pdict = {'type': param_type, 'value': val}
            Asset.addParam(nodeName, node_type, param_name, pdict)     

def set_asset_connections(nodes_list, Asset):
    for node in nodes_list:
        if type(node) == RmanConvertNode:
            # conversion node, skip
            continue

        cnx = [l for inp in node.inputs for l in inp.links ]
        if not cnx:
            continue

        for l in cnx:
            ignoreDst = l.to_node.bl_label not in __BL_NODES_MAP__
            ignoreSrc = l.from_node.bl_label not in __BL_NODES_MAP__

            if ignoreDst or ignoreSrc:
                rfb_log().debug("Ignoring connection %s -> %s" % (l.from_node.name, l.to_node.name))
                continue       

            if shadergraph_utils.do_convert_socket(l.from_socket, l.to_socket):
                # this needs a conversion node. 
                # the connection should already have been dealt with earlier                
                continue

            from_node = l.from_node
            to_node = l.to_node
            from_socket_name = l.from_socket.name
            to_socket_name = l.to_socket.name 

            renderman_node_type = getattr(from_node, 'renderman_node_type', '')
            if renderman_node_type == 'bxdf':
                # for Bxdf nodes, use the same socket name as RfM
                from_socket_name = 'outColor'

            srcPlug = "%s.%s" % (fix_blender_name(l.from_node.name), from_socket_name)
            dstPlug = "%s.%s" % (fix_blender_name(l.to_node.name), to_socket_name)    

            Asset.addConnection(srcPlug, dstPlug)    

def export_material_preset(mat, nodes_to_convert, renderman_output_node, Asset):
    # first, create a Maya-like shadingEngine node for our output node
    nodeClass = 'root'
    rmanNode = 'shadingEngine'
    nodeType = 'shadingEngine'
    sg_name = Asset.label().replace('.', '_')
    nodeName = '%s_SG' % sg_name
    Asset.addNode(nodeName, nodeType,
                    nodeClass, rmanNode,
                    externalosl=False)

    if renderman_output_node.inputs['bxdf_in'].is_linked:
        infodict = {}
        infodict['name'] = 'rman__surface'
        infodict['type'] = 'reference float3'
        infodict['value'] = None
        Asset.addParam(nodeName, nodeType, 'rman__surface', infodict)   

        from_node = renderman_output_node.inputs['bxdf_in'].links[0].from_node
        srcPlug = "%s.%s" % (fix_blender_name(from_node.name), 'outColor')
        dstPlug = "%s.%s" % (nodeName, 'rman__surface')    
        Asset.addConnection(srcPlug, dstPlug)                                     

    if renderman_output_node.inputs['displace_in'].is_linked:
        infodict = {}
        infodict['name'] = 'rman__displacement'
        infodict['type'] = 'reference float3'
        infodict['value'] = None
        Asset.addParam(nodeName, nodeType, 'rman__displacement', infodict)              

        from_node = renderman_output_node.inputs['displace_in'].links[0].from_node
        srcPlug = "%s.%s" % (fix_blender_name(from_node.name), 'outColor')
        dstPlug = "%s.%s" % (nodeName, 'rman__displacement')   
        Asset.addConnection(srcPlug, dstPlug) 
   

    for node in nodes_to_convert:     
        if type(node) == RmanConvertNode:
            # insert conversion node

            node_type = node.node_type
            from_node = node.from_node
            from_socket = node.from_socket
            to_node = node.to_node
            to_socket = node.to_socket
            output_name = 'resultRGB' if node_type == 'PxrToFloat3' else 'resultF'
            node_name = 'convert_%s_%s' % (fix_blender_name(from_node.name), from_socket.name)

            Asset.addNode(
                    node_name, node_type,
                    'pattern', node_type, False)         

            # from node to convert node
            srcPlug = "%s.%s" % (fix_blender_name(from_node.name), from_socket.name)
            dstPlug = "%s.%s" % (node_name, 'input')
            Asset.addConnection(srcPlug, dstPlug)

            # from convert node to destination node
            srcPlug = "%s.%s" % (node_name, output_name)
            dstPlug = "%s.%s" % (fix_blender_name(to_node.name), to_socket.name)
            Asset.addConnection(srcPlug, dstPlug)                           

        elif type(node) != type((1,2,3)):
            externalosl = False
            renderman_node_type = getattr(node, 'renderman_node_type', '')            
            if node.bl_idname == "PxrOSLPatternNode":            
                if getattr(node, "codetypeswitch") == "EXT":
                    osl_path = string_utils.expand_string(getattr(node, 'shadercode'))
                    FileName = os.path.basename(osl_path)
                    FileNameNoEXT,ext = os.path.splitext(FileName)
                    shaders_path = os.path.join(string_utils.expand_string('<OUT>'), "shaders")
                    out_file = os.path.join(shaders_path, FileName)
                    if ext == ".oso":
                        if not os.path.exists(out_file) or not os.path.samefile(osl_path, out_file):
                            if not os.path.exists(shaders_path):
                                os.mkdir(shaders_path)
                            shutil.copy(osl_path, out_file)                
                    externalosl = True
                    Asset.processExternalFile(None, ExternalFile.k_osl, out_file)

            elif renderman_node_type == '':
                # check if a cycles node
                if node.bl_idname not in CYCLES_NODE_MAP.keys():
                    rfb_log().debug('No translation for node of type %s named %s' % (node.bl_idname, node.name))
                    continue
                mapping = CYCLES_NODE_MAP[node.bl_idname]
                cycles_shader_dir = filepath_utils.get_cycles_shader_path()
                out_file = os.path.join(cycles_shader_dir, '%s.oso' % cycles_shader_dir)
                externalosl = True
                Asset.processExternalFile(None, ExternalFile.k_osl, out_file)

            node_name = fix_blender_name(node.name)
            shader_name = node.bl_label

            Asset.addNode(
                    node_name, shader_name,
                    renderman_node_type, shader_name, externalosl)

            set_asset_params(mat, node, node_name, Asset)      

    set_asset_connections(nodes_to_convert, Asset)             

def find_portal_dome_parent(portal):  
    dome = None
    parent = portal.parent
    while parent:
        if parent.type == 'LIGHT' and hasattr(parent.data, 'renderman'): 
            rm = parent.data.renderman
            if rm.renderman_light_role == 'RMAN_LIGHT' and rm.get_light_node_name() == 'PxrDomeLight':
                dome = parent
                break
        parent = parent.parent
    return dome                     

def export_light_rig(obs, Asset):

    dome_to_portals = dict()

    for ob in obs:
        bl_node = shadergraph_utils.get_light_node(ob)

        nodeName = fix_blender_name(bl_node.name)
        nodeType = bl_node.bl_label
        nodeClass = 'light'
        rmanNodeName = bl_node.bl_label

        Asset.addNode(nodeName, nodeType,
                        nodeClass, rmanNodeName,
                        externalosl=False)

        mtx = ob.matrix_world

        # Make sure we export the light as Y-up
        if nodeType in ['PxrDomeLight', 'PxrEnvDayLight']:
            # for dome and envdaylight, flip the Z and Y rotation axes
            # and ignore scale and translations
            euler = mtx.to_euler('XYZ')
            tmp = euler.y
            euler.y = euler.z
            euler.z = tmp
            mtx = mathutils.Matrix.Identity(4) @ euler.to_matrix().to_4x4()            
        else:
            # for other lights, rotate on the X-axis
            zup_to_yup = mathutils.Matrix.Rotation(radians(-90.0), 4, 'X')
            mtx = zup_to_yup @ mtx

        floatVals = list()
        floatVals = transform_utils.convert_matrix(mtx)
        Asset.addNodeTransform(nodeName, floatVals )

        set_asset_params(ob, bl_node, nodeName, Asset)     

        if nodeType == "PxrPortaLight":
            # if a portal light, fine the associate PxrDomeLight
            dome = find_portal_dome_parent(ob)
            if not dome:
                continue
            dome_name = dome.name
            portals = dome_to_portals.get(dome_name, list())
            portals.append(nodeName)
            dome_to_portals[dome_name] = portals

    # do portal connections
    for dome,portals in dome_to_portals.items():
        for i, portal in enumerate(portals):
            dst = '%s.rman__portals[%d]' % (dome, i)
            src = '%s.message' % (portal)
            Asset.addConnection(src, dst)

    # light filters
    for ob in obs:
        light = ob.data
        rm = light.renderman            
        for i, lf in enumerate(rm.light_filters):
            light_filter = lf.linked_filter_ob
            if not light_filter:
                continue

            bl_node = shadergraph_utils.get_light_node(light_filter)

            nodeName = fix_blender_name(bl_node.name)
            nodeType = bl_node.bl_label
            nodeClass = 'lightfilter'
            rmanNodeName = bl_node.bl_label

            Asset.addNode(nodeName, nodeType,
                            nodeClass, rmanNodeName,
                            externalosl=False)

            mtx = ob.matrix_world
            floatVals = list()
            floatVals = transform_utils.convert_matrix(mtx)
            Asset.addNodeTransform(nodeName, floatVals )

            set_asset_params(ob, bl_node, nodeName, Asset)        

            srcPlug = "%s.outColor" % fix_blender_name(light_filter.name)
            dstPlug = "%s.rman__lightfilters[%d]" % (fix_blender_name(ob.name), i)    

            Asset.addConnection(srcPlug, dstPlug)    

def export_displayfilter_nodes(world, nodes, Asset):
    any_stylized = False
    for node in nodes:
        nodeName = fix_blender_name(node.name)
        shaderName = node.bl_label
        externalosl = False

        Asset.addNode(
                nodeName, shaderName,
                'displayfilter', shaderName, externalosl) 
        set_asset_params(world, node, nodeName, Asset) 

        if not any_stylized and shaderName in RMAN_STYLIZED_FILTERS:
            any_stylized = True

    if any_stylized:
        # add stylized channels to Asset
        from .. import rman_config
        stylized_tmplt = rman_config.__RMAN_DISPLAY_TEMPLATES__.get('Stylized', None)
        rman_dspy_channels = rman_config.__RMAN_DISPLAY_CHANNELS__

        for chan in stylized_tmplt['channels']:
            settings = rman_dspy_channels[chan]
            chan_src = settings['channelSource']
            chan_type = settings['channelType']

            Asset.addNode(chan, chan,
                        'displaychannel', 'DisplayChannel',
                        datatype=chan_type)
            
            pdict = dict()
            pdict['value'] = chan_src
            pdict['name'] = 'source'
            pdict['type'] = 'string'
            if pdict['value'].startswith('lpe:'):
                pdict['value'] = 'color ' + pdict['value']
            Asset.addParam(chan, 'rmanDisplayChannel', 'source', pdict)        
                                            
def parse_texture(imagePath, Asset):
    """Gathers infos from the image header

    Args:
        imagePath {list} -- A list of texture paths.
        Asset {RmanAsset} -- the asset in which the infos will be stored.
    """
    img = FilePath(imagePath)
    # gather info on the envMap
    #
    Asset.addTextureInfos(img)

def setParams(Asset, node, paramsList):
    '''Set param values.
       Note: we are only handling a subset of maya attribute types.'''
    float3 = ['color', 'point', 'vector', 'normal']
    ramp_names = []
    rman_ramp_size = dict()    
    rman_ramps = dict()
    rman_color_ramps = dict()

    # Look for ramps
    for param in paramsList:
        pname = param.name()
        if pname in node.outputs:
            continue

        if pname not in node.prop_meta:
            continue

        prop_meta = node.prop_meta[pname]        
        param_widget = prop_meta.get('widget', 'default')        

        if prop_meta['renderman_type'] == 'colorramp':
            prop = getattr(node, pname)            
            nt = node.rman_fake_node_group_ptr
            if nt:
                ramp_name = prop
                color_ramp_node = nt.nodes[ramp_name]                    
                rman_color_ramps[pname] = color_ramp_node  
                rman_ramp_size[pname] = param.value()           
            ramp_names.append(pname)       
            continue
        elif prop_meta['renderman_type'] == 'floatramp':
            prop = getattr(node, pname)
            nt = node.rman_fake_node_group_ptr
            if nt:
                ramp_name =  prop
                float_ramp_node = nt.nodes[ramp_name]  
                rman_ramps[pname] = float_ramp_node
                rman_ramp_size[pname] = param.value()                  
            ramp_names.append(pname)
            continue

    # set ramp params
    for nm in ramp_names:
        knots_param = None
        colors_param = None
        floats_param = None
        interpolation_param = None

        if (nm not in rman_ramps) and (nm not in rman_color_ramps):
            continue

        for param in paramsList:
            pname = param.name()
            if pname in node.outputs:
                continue            
            if pname.startswith(nm):
                if '_Knots' in pname:
                    knots_param = param
                elif '_Colors' in pname: 
                    colors_param = param
                elif '_Floats' in pname:
                    floats_param = param
                elif '_Interpolation' in pname:
                    interpolation_param = param
            
        if colors_param:
            n = rman_color_ramps[nm]
            elements = n.color_ramp.elements
            size = rman_ramp_size[nm]
            knots_vals = knots_param.value()
            colors_vals = colors_param.value() 
            rman_interp = interpolation_param.value()

            interp = RMAN_INTERP_MAP.get(rman_interp, 'LINEAR')    
            n.color_ramp.interpolation = interp     

            # remove all of the points except for the first two
            for i in range(len(elements)-1, 1, -1):
                elements.remove(elements[-1])                  

            if len(colors_vals) == size:
                for i in range(0, size):
                    if i == 0:
                        elem = elements[0]
                        elem.position = knots_vals[i]
                    elif i == 1:
                        elem = elements[1]
                        elem.position = knots_vals[i]
                    else:
                        elem = elements.new(knots_vals[i])
                    elem.color = (colors_vals[i][0], colors_vals[i][1], colors_vals[i][2], 1.0)
            else:
                j = 0
                for i in range(0, size):
                    if i == 0:
                        elem = elements[0]
                        elem.position = knots_vals[i]
                    elif i == 1:
                        elem = elements[1]
                        elem.position = knots_vals[i]                       
                    else:
                        elem = elements.new(knots_vals[i])
                    elem.color = (colors_vals[j], colors_vals[j+1], colors_vals[j+2], 1.0)
                    j += 3

        elif floats_param:
            n = rman_ramps[nm]
            curve = n.mapping.curves[0]
            points = curve.points
            size = rman_ramp_size[nm]
            knots_vals = knots_param.value()
            floats_vals = floats_param.value()

            # remove all of the points except for the first two
            for i in range(len(points)-1, 1, -1):
                points.remove(points[-1])

            for i in range(0, size):  
                if i == 0:
                    point = points[0]
                    point.location[0] = knots_vals[i]
                    point.location[1] = floats_vals[i]    
                elif i == 1:
                    point = points[1]
                    point.location[0] = knots_vals[i]
                    point.location[1] = floats_vals[i]                        
                else:                
                    points.new(knots_vals[i], floats_vals[i])            

    for param in paramsList:
        pname = param.name()
        if pname in node.outputs:
            continue        
        ptype = param.type()

        prop_meta = node.prop_meta.get(pname, dict())
        param_widget = prop_meta.get('widget', 'default')        

        if pname in ramp_names:
            continue

        is_ramp_param = False
        for nm in ramp_names:
            if pname.startswith(nm):
                is_ramp_param = True
                break

        if is_ramp_param:
            continue

        # arrays
        elif '[' in ptype:
            # always set the array length

            # try to get array length
            rman_type = ptype.split('[')[0].strip()
            array_len = ptype.split('[')[1].split(']')[0]
            if array_len == '':
                continue
            array_len = int(array_len)
            coll_nm = '%s_collection' % pname  
            coll_idx_nm = '%s_collection_index' % pname
            collection = getattr(node, coll_nm, None)
            if collection is None:
                continue
            elem_type = rman_type
            if 'reference' in elem_type:
                elem_type = elem_type.replace('reference ', '')
            if elem_type == 'integer':
                elem_type = 'int'

            for i in range(array_len):
                if BLENDER_VERSION_MAJOR <=3 and BLENDER_VERSION_MINOR < 2:
                    override = {'node': node}           
                    bpy.ops.renderman.add_remove_array_elem(override,
                                                        'EXEC_DEFAULT', 
                                                        action='ADD',
                                                        param_name=pname,
                                                        collection=coll_nm,
                                                        collection_index=coll_idx_nm,
                                                        elem_type=elem_type)            

                else:
                    context_override = bpy.context.copy()
                    context_override["node"] = node
                    with bpy.context.temp_override(**context_override):
                        bpy.ops.renderman.add_remove_array_elem(
                                                                'EXEC_DEFAULT', 
                                                                action='ADD',
                                                                param_name=pname,
                                                                collection=coll_nm,
                                                                collection_index=coll_idx_nm,
                                                                elem_type=elem_type)            

            pval = param.value()
            if pval is None or pval == []:
                # connected param
                continue    

            plen = len(pval)
            if rman_type in ['integer', 'float', 'string']:
                for i in range(0, plen):
                    val = pval[i]
                    elem = collection[i]
                    elem.type = elem_type
                    setattr(node, 'value_%s' % elem.type, val)

            # float3 types
            elif rman_type in float3:
                j = 1
                if isinstance(pval[0], list):
                    for i in range(0, plen):
                        elem = collection[j]
                        val = (pval[i][0], pval[i][0], pval[i][0])
                        elem.type = elem_type
                        setattr(node, 'value_%s' % elem.type, val)                        
                        j +=1
                else:        
                    for i in range(0, plen, 3):
                        elem = collection[j]                        
                        val = (pval[i], pval[i+1], pval[i+2])
                        elem.type = elem_type
                        setattr(node, 'value_%s' % elem.type, val)
                        j = j+1            

        elif pname in node.bl_rna.properties.keys():
            if ptype is None or ptype in ['vstruct', 'struct']:
                # skip vstruct and struct params : they are only useful when connected.
                continue

            pval = param.value()

            if pval is None or pval == []:
                # connected param
                continue

            if pname == "placementMatrix":
                # this param is always connected.
                continue
            if 'string' in ptype:
                if pval != '':
                    depfile = Asset.getDependencyPath(pname, pval)
                    if depfile:
                        pval = depfile
                try:
                    setattr(node, pname, pval)
                except:
                    rfb_log().error('setParams FAILED: %s  ptype: %s  pval: %s' %
                                (pname, ptype, repr(pval)))

            elif ptype in float3:
                try:
                   setattr(node, pname, pval)
                except:
                    rfb_log().error('setParams float3 FAILED: %s  ptype: %s  pval: %s' %
                          (pname, ptype, repr(pval)))
            else:
                try:
                    if type(getattr(node,pname)) == type(""):
                        setattr(node, pname, str(pval))
                    else:
                        setattr(node, pname, pval)
                except:
                    if type(getattr(node, pname)) == bpy.types.EnumProperty:
                        try:
                            setattr(node, pname, str(pval))
                        except:
                            rfb_log().error('setParams FAILED: %s  ptype: %s  pval: %s' %
                                (pname, ptype, repr(pval)))


    # if this is a PxrSurface, turn on all of the enable gains.
    if hasattr(node, 'plugin_name') and node.plugin_name in ['PxrLayer', 'PxrSurface']:
        for enable in __LOBES_ENABLE_PARAMS__:
            setattr(node, enable, True)

def createNodes(Asset):

    nodeDict = {}
    nt = None

    mat = bpy.data.materials.new(Asset.label())
    mat.use_nodes = True
    nt = mat.node_tree       
    shadergraph_utils.hide_cycles_nodes(mat)

    # create output node
    output_node = nt.nodes.new('RendermanOutputNode')

    curr_x = 250
    for node in Asset.nodeList():
        nodeId = node.name()
        nodeType = node.type()
        nodeClass = node.nodeClass()
        # print('%s %s: %s' % (nodeId, nodeType, nodeClass))
        fmt, vals, ttype = node.transforms()
        # print('+ %s %s: %s' % (fmt, vals, ttype))

        if nodeClass == 'bxdf':
            bl_node_name = __BL_NODES_MAP__.get(nodeType, None)
            if not bl_node_name:
                continue
            created_node = nt.nodes.new(bl_node_name)
            created_node.location[0] = -curr_x
            curr_x = curr_x + 250
            created_node.name = nodeId
            created_node.label = nodeId
        
        elif nodeClass == 'displace':
            bl_node_name = __BL_NODES_MAP__.get(nodeType, None)
            if not bl_node_name:
                continue
            created_node = nt.nodes.new(bl_node_name)            
            created_node.location[0] = -curr_x
            curr_x = curr_x + 250
            created_node.name = nodeId
            created_node.label = nodeId
           
        elif nodeClass == 'pattern':
            if nodeType == 'PxrDisplace':
                # Temporary. RfM presets seem to be setting PxrDisplace as a pattern node
                bl_node_name = __BL_NODES_MAP__.get(nodeType, None)
                if not bl_node_name:
                    continue
                created_node = nt.nodes.new(bl_node_name)            
                created_node.location[0] = -curr_x
                curr_x = curr_x + 250
                created_node.name = nodeId
                created_node.label = nodeId
              
            elif node.externalOSL():
                # if externalOSL() is True, it is a dynamic OSL node i.e. one
                # loaded through a PxrOSL node.
                # if PxrOSL is used, we need to find the oso in the asset to
                # use it in a PxrOSL node.
                oso = Asset.getDependencyPath(ExternalFile.k_osl, nodeType + '.oso')
                if oso is None:
                    err = ('createNodes: OSL file is missing "%s"'
                           % nodeType)
                    raise RmanAssetBlenderError(err)
                created_node = nt.nodes.new('PxrOSLPatternNode')
                created_node.location[0] = -curr_x
                curr_x = curr_x + 250
                created_node.codetypeswitch = 'EXT'
                created_node.shadercode = oso
                created_node.RefreshNodes({}, nodeOR=created_node)
            else:
                bl_node_name = __BL_NODES_MAP__.get(nodeType, None)
                if not bl_node_name:
                    continue
                created_node = nt.nodes.new(bl_node_name)   
                created_node.location[0] = -curr_x
                curr_x = curr_x + 250
                created_node.name = nodeId
                created_node.label = nodeId                             

        elif nodeClass == 'root':
            output_node.name = nodeId
            nodeDict[nodeId] = output_node.name
            
            continue

        if created_node:
            nodeDict[nodeId] = created_node.name
            setParams(Asset, created_node, node.paramsDict())

        if nodeClass == 'bxdf':
            created_node.update_mat(mat)

    return mat,nt,nodeDict

def import_light_rig(Asset):
    nodeDict = {}

    filter_nodes = dict()
    light_nodes = dict()
    domelight_nodes = dict()
    portallight_nodes = dict()

    curr_x = 250
    try:
        cdata = Asset._assetData['compatibility']
        asset_version = Asset.getMetadata(RFB_ASSET_VERSION_KEY)
        do_rotate = True
        if asset_version is None and cdata['host']['name'] == 'Blender':
            # version 1.0 of light rigs from Blender doesn't need the Y-up to Z-up rotation
            do_rotate = False
    except Exception as e:
        rfb_log().error("Error determining compatibility: %s" % e)


    for node in Asset.nodeList():
        nodeId = node.name()
        nodeType = node.type()
        nodeClass = node.nodeClass()

        if nodeClass not in ['light', 'lightfilter']:
            continue

        # print('%s %s: %s' % (nodeId, nodeType, nodeClass))
        fmt, vals, ttype = node.transforms()
        # print('+ %s %s: %s' % (fmt, vals, ttype))      

        created_node = None
        light = None
                      
        if nodeClass == 'light':
            # we don't deal with mesh lights
            if nodeType == 'PxrMeshLight':
                continue

            bpy.ops.object.rman_add_light(rman_light_name=nodeType)

        elif nodeClass == 'lightfilter':
            bpy.ops.object.rman_add_light_filter(rman_lightfilter_name=nodeType, add_to_selected=False)

        try:
            light = bpy.context.active_object
        except:
            light = bpy.context.view_layer.objects.active
        nt = light.data.node_tree

        light.name = nodeId
        light.data.name = nodeId      

        created_node = light.data.renderman.get_light_node()          

        if created_node:
            nodeDict[nodeId] = created_node.name
            setParams(Asset, created_node, node.paramsDict())

        if nodeClass == 'light':
            light_nodes[nodeId] = light
        elif nodeClass == 'lightfilter':
            filter_nodes[nodeId] = light

        if nodeType == "PxrDomeLight":
            domelight_nodes[nodeId] = light
        elif nodeType == "PxrPortalLight":
            portallight_nodes[nodeId] = light          

        if fmt[2] == TrMode.k_flat:
            if fmt[0] == TrStorage.k_matrix:                   
                light.matrix_world[0] = vals[0:4]
                light.matrix_world[1] = vals[4:8]
                light.matrix_world[2] = vals[8:12]
                light.matrix_world[3] = vals[12:]
                light.matrix_world.transpose()
            elif fmt[0] == TrStorage.k_TRS:  
                light.location = vals[0:3]                    
                light.scale = vals[6:9]

                # rotation
                light.rotation_euler = (radians(vals[3]), radians(vals[4]), radians(vals[5]))
                
        if do_rotate:     
            # we need to rotate the lights to Z-up
            if nodeType in ['PxrDomeLight', 'PxrEnvDayLight']:
                # for dome and envdaylight, flip the Y and Z rotation axes
                # and ignore scale and translations
                euler = light.matrix_world.to_euler('XYZ')
                tmp = euler.y
                euler.y = euler.z
                euler.z = tmp
                light.matrix_world = mathutils.Matrix.Identity(4) @ euler.to_matrix().to_4x4()
            else:                    
                # for other lights, rotate on the X-axis
                yup_to_zup = mathutils.Matrix.Rotation(radians(90.0), 4, 'X')
                light.matrix_world = yup_to_zup @ light.matrix_world

        if bpy.context.view_layer.objects.active:
            bpy.context.view_layer.objects.active.select_set(False)                 

    lights_to_filters = dict()            

    # loop over connections, and map each light to filters
    for con in Asset.connectionList():

        srcNode = con.srcNode()
        dstNode = con.dstNode()

        # check if this is portal light/dome light connection
        # if so, let's do it, here
        if (srcNode in portallight_nodes) and (dstNode in domelight_nodes):
            portal = portallight_nodes[srcNode]
            dome = domelight_nodes[dstNode]
            portal.parent = dome
            continue        

        if dstNode not in lights_to_filters:
            lights_to_filters[dstNode] = [srcNode]
        else:
            lights_to_filters[dstNode].append(srcNode)


    for light,filters in lights_to_filters.items():
        if light not in light_nodes:
            continue
        light_node = light_nodes[light]
        for i,f in enumerate(filters):
            filter_node = filter_nodes[f]

            light_filter_item = light_node.data.renderman.light_filters.add()
            light_filter_item.linked_filter_ob = filter_node            

    return nodeDict    

def connectNodes(Asset, nt, nodeDict):
    output = shadergraph_utils.find_node_from_nodetree(nt, 'RendermanOutputNode')
    bxdf_socket = output.inputs['bxdf_in']
    displace_socket = output.inputs['displace_in']

    for con in Asset.connectionList():
        #print('+ %s.%s -> %s.%s' % (nodeDict[con.srcNode()](), con.srcParam(),
        #                             nodeDict[con.dstNode()](), con.dstParam()))

        srcName = nodeDict.get(con.srcNode(), '')
        dstName = nodeDict.get(con.dstNode(), '')
        if srcName == '' or dstName == '':
            continue

        srcNode = nt.nodes.get(srcName, None)
        dstNode = nt.nodes.get(dstName, None)

        if srcNode == None or dstNode == None:
            continue

        srcSocket = con.srcParam()
        dstSocket = con.dstParam()
        renderman_node_type = getattr(srcNode, 'renderman_node_type', '')
        if srcSocket in srcNode.outputs and dstSocket in dstNode.inputs:
            nt.links.new(srcNode.outputs[srcSocket], dstNode.inputs[dstSocket])
        elif output == dstNode:        
            # check if this is a root node connection
            if dstSocket == 'surfaceShader' or dstSocket == 'rman__surface':
                nt.links.new(srcNode.outputs['bxdf_out'], output.inputs['bxdf_in'])
            elif dstSocket == 'displacementShader' or dstSocket == 'rman__displacement':           
                nt.links.new(srcNode.outputs['displace_out'], output.inputs['displace_in'])
        elif renderman_node_type == 'bxdf':         
            # this is a regular upstream bxdf connection
            nt.links.new(srcNode.outputs['bxdf_out'], dstNode.inputs[dstSocket])  
        else:            
            rfb_log().debug('error connecting %s.%s to %s.%s' % (srcNode.name,srcSocket, dstNode.name, dstSocket))

    if not bxdf_socket.is_linked:
        # Our RenderManOutputNode still does not have a bxdf connected
        # look for all bxdf nodes and find one that does not have a connected output
        bxdf_candidate = None
        displace_candidate = None
        for node in nt.nodes:
            renderman_node_type = getattr(node, 'renderman_node_type', '')             
            if renderman_node_type == 'bxdf':                
                if not node.outputs['bxdf_out'].is_linked:
                    bxdf_candidate = node
            elif renderman_node_type == 'displace':
                displace_candidate = node

        if bxdf_candidate:
            nt.links.new(bxdf_candidate.outputs['bxdf_out'], output.inputs['bxdf_in'])

        if not displace_socket.is_linked and displace_candidate:
            nt.links.new(displace_candidate.outputs['displace_out'], output.inputs['displace_in'])


def create_displayfilter_nodes(Asset):
    has_stylized = False
    df_list = Asset.displayFilterList()
    world = bpy.context.scene.world

    if not world.renderman.use_renderman_node:
        bpy.ops.material.rman_add_rman_nodetree('EXEC_DEFAULT', idtype='world')

    output = shadergraph_utils.find_node(world, 'RendermanDisplayfiltersOutputNode')
    nt = world.node_tree 
    nodeDict = {}      
    
    for df_node in df_list:
        node_id = df_node.name()
        node_type = df_node.rmanNode()

        bl_node_name = __BL_NODES_MAP__.get(node_type, None)
        if not bl_node_name:
            continue
        created_node = nt.nodes.new(bl_node_name)    
        created_node.name = node_id
        created_node.label = node_id        
        output.add_input()    
        nt.links.new(created_node.outputs['displayfilter_out'], output.inputs[-1])
        nodeDict[node_id] = created_node.name
        setParams(Asset, created_node, df_node.paramsDict())

        if not has_stylized and node_type in RMAN_STYLIZED_FILTERS:
            bpy.ops.scene.rman_enable_stylized_looks('EXEC_DEFAULT')
            has_stylized = True

def import_asset(Asset, assignToSelected):
    hostPrefs = get_host_prefs()
    hostPrefs.current_asset = Asset

    assetType = Asset.type()

    if assetType == "nodeGraph":
        mat = None
        if Asset.displayFilterList():
            bpy.ops.renderman.rman_import_displayfilters_dlg('EXEC_DEFAULT')
            if hostPrefs.import_displayfilters:
                create_displayfilter_nodes(Asset)
        if Asset.nodeList():
            path = os.path.dirname(Asset.path())
            paths = path.split('/')
            if 'Materials' in paths:
                mat,nt,newNodes = createNodes(Asset)
                connectNodes(Asset, nt, newNodes)
            elif 'LightRigs' in paths:
                newNodes = import_light_rig(Asset)

        if mat and assignToSelected:     
            scene = bpy.context.scene            
            for ob in scene.view_layers[0].objects.selected:
                if ob.type == 'EMPTY':
                    ob.renderman.rman_material_override = mat
                    ob.update_tag(refresh={'OBJECT'})
                elif hasattr(ob, 'active_material'):
                    ob.active_material = mat

    elif assetType == "envMap":
        scene = bpy.context.scene
        dome_lights = [ob for ob in scene.objects if ob.type == 'LIGHT' \
            and ob.data.renderman.get_light_node_name() == 'PxrDomeLight']

        selected_dome_lights = [ob for ob in dome_lights if ob.select_get()]
        env_map_path = Asset.envMapPath()

        if not selected_dome_lights:
            if not dome_lights:
                # create a new dome light              
                bpy.ops.object.rman_add_light(rman_light_name='PxrDomeLight')
                ob = bpy.context.view_layer.objects.active
                plugin_node = ob.data.renderman.get_light_node()
                plugin_node.lightColorMap = env_map_path                    

            elif len(dome_lights) == 1:
                light = dome_lights[0].data
                plugin_node = light.renderman.get_light_node()
                plugin_node.lightColorMap = env_map_path
            else:
                rfb_log().error('More than one dome in scene.  Not sure which to use')
        else:
            for light in selected_dome_lights:
                light = dome_lights[0].data
                plugin_node = light.renderman.get_light_node()
                plugin_node.lightColorMap = env_map_path

    else:
        raise RmanAssetBlenderError("Unknown asset type : %s" % assetType)            

def export_asset(nodes, atype, infodict, category, cfg, renderPreview='std',
                 alwaysOverwrite=False, isLightRig=False):
    """Exports a nodeGraph or envMap as a RenderManAsset.

    Args:
        nodes (dict) -- dictionary containing the nodes to export
        atype (str) -- Asset type : 'nodeGraph' or 'envMap'
        infodict (dict) -- dict with 'label', 'author' & 'version'
        category (str) -- Category as a path, i.e.: "/Lights/LookDev"

    Kwargs:
        renderPreview (str) -- Render an asset preview ('std', 'fur', None).\
                        Render the standard preview swatch by default.\
                        (default: {'std'})
        alwaysOverwrite {bool) -- Will ask the user if the asset already \
                        exists when not in batch mode. (default: {False})
    """
    label = infodict['label']
    Asset = RmanAsset(assetType=atype, label=label, previewType=renderPreview,
                              storage=infodict.get('storage', None),
                              convert_to_tex=infodict.get('convert_to_tex', True)
    )

    # On save, we can get the current color manager to store the config.
    color_mgr = clr_mgr.color_manager()
    ocio_config = {
        'config': color_mgr.cfg_name,
        'path': color_mgr.config_file_path(),
        'rules': color_mgr.conversion_rules,
        'aliases': color_mgr.aliases
    }
    rfb_log().debug('ocio_config %s', '=' * 80)
    rfb_log().debug('     config = %s', ocio_config['config'])
    rfb_log().debug('       path = %s', ocio_config['path'])
    rfb_log().debug('      rules = %s', ocio_config['rules'])
    Asset.ocio = ocio_config    

    # Add user metadata
    #
    metadata = infodict.get('metadata', dict())
    for k, v in metadata.items():
        if k == 'label':
            continue
        Asset.addMetadata(k, v)

    # add version
    Asset.addMetadata(RFB_ASSET_VERSION_KEY, RFB_ASSET_VERSION)

    # Compatibility data
    # This will help other application decide if they can use this asset.
    #
    prmanversion = envconfig().build_info.version()
    Asset.setCompatibility(hostName='Blender',
                           hostVersion=bpy.app.version_string,
                           rendererVersion=prmanversion)                           

    # parse scene
    hostPrefs = get_host_prefs()
    if atype == "nodeGraph":
        if not isLightRig:
            export_material_preset(hostPrefs.blender_material, nodes['material'], hostPrefs.renderman_output_node, Asset)
            Asset.registerUsedNodeTypes()
            is_stylized = 'PxrStylized' in Asset.getUsedNodeTypes(asString=True)
            if is_stylized and nodes['displayfilter']:
                export_displayfilter_nodes(hostPrefs.bl_world, nodes['displayfilter'], Asset)
        else:
            export_light_rig(nodes['lightrigs'], Asset)
    elif atype == "envMap":
        parse_texture(nodes['envmap'][0], Asset)
    else:
        raise RmanAssetBlenderError("%s is not a known asset type !" % atype)

   #  Get path to our library
    #
    assetPath = ral.getAbsCategoryPath(cfg, category)

    #  Create our directory
    #
    assetDir = asset_name_from_label(str(label))
    dirPath = assetPath.join(assetDir)
    if not dirPath.exists():
        os.mkdir(dirPath)

    #   Check if we are overwriting an existing asset
    #
    jsonfile = dirPath.join("asset.json")
    if jsonfile.exists():
        if alwaysOverwrite:
            print('Replacing existing file : %s' % jsonfile)
        else:
            return False

    #  Save our json file
    #
    # print("exportAsset: %s..." %   dirPath)
    Asset.save(jsonfile, compact=False)
    return True
