from . import string_utils
from . import filepath_utils
from . import scene_utils
from . import shadergraph_utils
from .property_utils import BlPropInfo
#from . import object_utils
from .prefs_utils import get_pref
from ..rfb_logger import rfb_log
from rman_utils import txmanager
from rman_utils.txmanager import core as txcore
from rman_utils.txmanager import txparams as txparams
from rman_utils.txmanager.txfile import TxFile
from .color_manager_blender import color_manager

from bpy.app.handlers import persistent
from copy import deepcopy

import os
import bpy
import uuid
import re

__RFB_TXMANAGER__ = None

def get_nodeid(node):
    """Return the contents of the 'txm_id' attribute of a node.
    Returns None if the attribute doesn't exist."""
    try:
        tokens = node.split('|')
        if len(tokens) < 3:
            return ""
        node_tree = tokens[0]
        node_name = tokens[1]
        prop_name = tokens[2]
        library = tokens[3]
        node, ob = scene_utils.find_node_by_name(node_name, node_tree, library=library)
        if node is None:
            return None
        txm_id = getattr(node, 'txm_id')
        return txm_id
    except ValueError:
        return None


def set_nodeid(node, node_id):
    """Set a node's 'txm_id' attribute with node_id. If the attribute doesn't
    exist yet, it will be created."""
    tokens = node.split('|')
    if len(tokens) < 3:
        return ""
    node_tree = tokens[0]
    node_name = tokens[1]
    prop_name = tokens[2]
    library = tokens[3]
    node, ob = scene_utils.find_node_by_name(node_name, node_tree, library=library) 
    if node:
        try:
            setattr(node, 'txm_id', node_id)
        except AttributeError:
            return ""
class RfBTxManager(object):

    def __init__(self):        
        self.txmanager = txcore.TxManager(host_token_resolver_func=self.host_token_resolver_func, 
                                        host_prefs_func=self.get_prefs,
                                        host_tex_done_func=self.done_callback,
                                        host_load_func=load_scene_state,
                                        host_save_func=save_scene_state,
                                        texture_extensions=self.get_ext_list(),
                                        color_manager=color_manager(),
                                        set_nodeid_func=set_nodeid,
                                        get_nodeid_func=get_nodeid
                                        )
        self.rman_scene = None

    @property
    def rman_scene(self):
        return self.__rman_scene

    @rman_scene.setter
    def rman_scene(self, rman_scene):
        self.__rman_scene = rman_scene      

    def get_prefs(self):
        prefs = dict()
        prefs['num_workers'] = get_pref('rman_txmanager_workers')
        prefs['fallback_path'] = string_utils.expand_string(get_pref('path_fallback_textures_path'), 
                                                  asFilePath=True)
        prefs['fallback_always'] = get_pref('path_fallback_textures_path_always')
        prefs['keep_extension'] = get_pref('rman_txmanager_keep_extension')

        return prefs

    def get_ext_list(self):
        ext_prefs = get_pref('rman_txmanager_tex_extensions')
        ext_list = ['.%s' % ext for ext in ext_prefs.split()]
        return ext_list

    def host_token_resolver_func(self, outpath):
        outpath = string_utils.expand_string(outpath, asFilePath=True)
        return outpath

    def done_callback(self, nodeID, txfile):
        def tex_done():
            try:
                # try and refresh the texture manager UI
                bpy.ops.rman_txmgr_list.refresh('EXEC_DEFAULT')
            except:
                pass
            from .. import rman_render
            output_texture = self.get_output_tex(txfile)
            rr = rman_render.RmanRender.get_rman_render()
            rr.rman_scene_sync.flush_texture_cache([output_texture])
            rr.rman_scene_sync.texture_updated(nodeID)
            
        return tex_done    

    def get_output_tex(self, txfile):
        '''
        Get the real output texture path given a TxFile 
        '''
        if txfile.state in (txmanager.STATE_EXISTS, txmanager.STATE_IS_TEX):
            output_tex = txfile.get_output_texture()
            output_tex = string_utils.expand_string(output_tex, asFilePath=True)    
        elif txfile.state == txmanager.STATE_INPUT_MISSING:       
            output_tex = txfile.input_image
            output_tex = string_utils.expand_string(output_tex, asFilePath=True)                
        else:
            output_tex = self.txmanager.get_placeholder_tex()

        return output_tex        

    def get_output_tex_from_path(self, node, param_name, file_path, ob=None):
        node_name = generate_node_name(node, param_name, ob=ob)
        plug_uuid = self.txmanager.get_plug_id(node_name, param_name)

        # lookup the txmanager for an already converted texture
        txfile = self.txmanager.get_txfile_from_id(plug_uuid)   
        if txfile is None:
            if file_path == '':
                return file_path
            category = getattr(node, 'renderman_node_type', 'pattern') 
            node_type = ''
            node_type = node.bl_label            
            self.txmanager.add_texture(plug_uuid, file_path, nodetype=node_type, category=category)    
            txfile = self.txmanager.get_txfile_from_id(plug_uuid)            
            bpy.ops.rman_txmgr_list.add_texture('EXEC_DEFAULT', filepath=file_path, nodeID=plug_uuid)
            txmake_all(blocking=False)
            if txfile:
                self.done_callback(plug_uuid, txfile)                     
        if txfile:
            return self.get_output_tex(txfile)

        return file_path
        
    def get_output_tex_from_id(self, nodeID):
        '''
        Get the real output texture path given a nodeID
        '''
        txfile = self.txmanager.get_txfile_from_id(nodeID)
        if not txfile:
            return ''

        return self.get_output_tex(txfile)

    def get_txfile_from_id(self, nodeID):
        '''
        Get the txfile from given a nodeID
        '''
        txfile = self.txmanager.get_txfile_from_id(nodeID)
        return txfile       
                
    def get_txfile(self, node, param_name, ob=None):
        nodeID = generate_node_id(node, param_name, ob=ob)
        return self.get_txfile_from_id(nodeID)

    def txmake_all(self, blocking=True):
        self.txmanager.txmake_all(start_queue=True, blocking=blocking)   

    def add_texture(self, node, ob, param_name, file_path, node_type='PxrTexture', category='pattern'):
        node_name = generate_node_name(node, param_name, ob=ob)
        plug_uuid = self.txmanager.get_plug_id(node_name, param_name)  

        if file_path == "":
            txfile = self.txmanager.get_txfile_from_id(plug_uuid)
            if txfile:
                self.txmanager.remove_texture(plug_uuid)
                bpy.ops.rman_txmgr_list.remove_texture('EXEC_DEFAULT', nodeID=plug_uuid)
        else:
            # lookup the txmanager for an already converted texture
            txfile = self.txmanager.get_txfile_from_id(plug_uuid)         
            if txfile is None or txfile.input_image != file_path:
                self.txmanager.add_texture(plug_uuid, file_path, nodetype=node_type, category=category)    
                bpy.ops.rman_txmgr_list.add_texture('EXEC_DEFAULT', filepath=file_path, nodeID=plug_uuid)
                txfile = self.txmanager.get_txfile_from_id(plug_uuid)
                txmake_all(blocking=False)
                if txfile:
                    self.done_callback(plug_uuid, txfile)    
                    if not txfile.source_is_tex():    
                        param_colorspace = '%s_colorspace'  % param_name
                        ociconvert = getattr(node, param_colorspace, None)
                        if ociconvert:
                            update_txfile_colorspace(txfile, ociconvert)

    def is_file_src_tex(self, node, prop_name):
        id = scene_utils.find_node_owner(node)
        nodeID = generate_node_id(node, prop_name, ob=id)
        txfile = self.get_txfile_from_id(nodeID)
        if txfile is None:
            category = getattr(node, 'renderman_node_type', 'pattern') 
            node_type = ''
            node_type = node.bl_label    
            file_path = getattr(node, prop_name)        
            self.txmanager.add_texture(nodeID, file_path, nodetype=node_type, category=category)    
            txfile = self.txmanager.get_txfile_from_id(nodeID)
            try:            
                bpy.ops.rman_txmgr_list.add_texture('EXEC_DEFAULT', filepath=file_path, nodeID=nodeID)
            except RuntimeError:
                pass
            txmake_all(blocking=False)
            if txfile:
                self.done_callback(nodeID, txfile)                     
        
        if txfile:
            return (txfile.state == txmanager.STATE_IS_TEX)  
        return False

    def does_file_exist(self, file_path):
        outpath = string_utils.expand_string(file_path, asFilePath=True)
        if os.path.exists(outpath):
            return True

        if re.search(TxFile.tokenExpr, outpath):
            return True
        return False

    def does_nodeid_exists(self, nodeID):
        txfile = self.txmanager.get_txfile_from_id(nodeID)
        if txfile:
            return True
        return False

def get_txmanager():
    global __RFB_TXMANAGER__
    if __RFB_TXMANAGER__ is None:
        __RFB_TXMANAGER__ = RfBTxManager()
    return __RFB_TXMANAGER__    

def update_texture(node, ob=None, check_exists=False, is_library=False):
    bl_idname = getattr(node, 'bl_idname', '')
    if bl_idname == "PxrOSLPatternNode":
        for input_name, input in node.inputs.items():
            if hasattr(input, 'is_texture') and input.is_texture:
                prop = input.default_value
                nodeID = generate_node_id(node, input_name)
                real_file = filepath_utils.get_real_path(prop)
                get_txmanager().txmanager.add_texture(nodeID, real_file)    
                bpy.ops.rman_txmgr_list.add_texture('EXEC_DEFAULT', filepath=real_file, nodeID=nodeID)                                                      
        return
    elif node.bl_idname == 'ShaderNodeGroup':
        nt = node.node_tree
        for node in nt.nodes:
            update_texture(node, ob=ob)
        return

    prop_meta = getattr(node, 'prop_meta', dict())
    textured_params = getattr(node, 'rman_textured_params', list())
    for prop_name in textured_params:
        meta = prop_meta.get(prop_name, dict())
        bl_prop_info = BlPropInfo(node, prop_name, meta)
        node_type = ''
        if isinstance(ob, bpy.types.Object):
            if ob.type == 'LIGHT':
                node_type = ob.data.renderman.get_light_node_name()
            else:
                node_type = node.bl_label                            
        else:
            node_type = node.bl_label

        if ob and check_exists:
            nodeID = generate_node_id(node, prop_name, ob=ob)
            if get_txmanager().does_nodeid_exists(nodeID):
                continue

        fpath = bl_prop_info.prop
        if is_library:
            # if this is coming from a library, replace <blend_dir> with the full path
            blend_file = filepath_utils.get_real_path(ob.library.filepath)
            fpath = fpath.replace('<blend_dir>', os.path.dirname(blend_file))

        category = getattr(node, 'renderman_node_type', 'pattern') 
        get_txmanager().add_texture(node, ob, prop_name, fpath, node_type=node_type, category=category)        

def update_txfile_colorspace(txfile, ociconvert, blocking=False):
    if ociconvert == '0':
        return
    params = txfile.params.as_dict()     
    if params['ocioconvert'] != ociconvert:
        params['ocioconvert'] = ociconvert
        txfile.params.from_dict(params)
        txfile.set_params(txfile.params)
        txfile.build_texture_dict()
        if txfile.check_dirty(force_check=True):
            txfile.delete_texture_files()            
            get_txmanager().txmake_all(blocking=blocking)                 

def generate_node_name(node, prop_name, ob=None, nm=None):
    node_name = ''
    if not nm:
        nm = shadergraph_utils.get_nodetree_name(node)
    if nm:        
        node_name = '%s|%s|%s|' %  (nm, node.name, prop_name)
    elif ob:
        node_name = '%s|%s|%s|' % (ob.name, node.name, prop_name)

    if node_name != '':
        if ob and ob.library:
            node_name = '%s%s|' % (node_name, ob.library.name)
        else:
            node_name = '%s|' % node_name
    
    if node_name == '':
        prop = ''
        real_file = ''
        if hasattr(node, prop_name):
            prop = getattr(node, prop_name)
            real_file = filepath_utils.get_real_path(prop)
        node_name = '%s|%s|' % (node.name, real_file)
    return node_name       

def generate_node_id(node, prop_name, ob=None):
    node_name = generate_node_name(node, prop_name, ob=ob)
    plug_uuid = get_txmanager().txmanager.get_plug_id(node_name, prop_name)
    return plug_uuid

def get_textures(id, check_exists=False, mat=None):
    if id is None or not id.node_tree:
        return

    ob = id
    if mat:
        ob = mat
    nodes_list = list()
    shadergraph_utils.gather_all_textured_nodes(ob, nodes_list)
    is_library = False
    if hasattr(id, 'library') and id.library:
        is_library = True
    for node in nodes_list:
        update_texture(node, ob=ob, check_exists=check_exists, is_library=is_library)

def get_blender_image_path(bl_image):
    if bl_image.packed_file:
        bl_image.unpack()
    real_file = bpy.path.abspath(bl_image.filepath, library=bl_image.library)          
    return real_file 

def add_images_from_image_editor():
    
    # convert images in the image editor
    for img in bpy.data.images:
        if img.type != 'IMAGE':
            continue
        img_path = get_blender_image_path(img)
        if img_path != '' and os.path.exists(img_path): 
            nodeID = str(uuid.uuid1())
            txfile = get_txmanager().txmanager.add_texture(nodeID, img_path)        
            bpy.ops.rman_txmgr_list.add_texture('EXEC_DEFAULT', filepath=img_path, nodeID=nodeID)       
            if txfile:
                get_txmanager().done_callback(nodeID, txfile)  
         
def parse_scene_for_textures(bl_scene=None):

    #add_images_from_image_editor()

    if bl_scene:
        for o in scene_utils.renderable_objects(bl_scene):
            if o.type == 'EMPTY':
                continue
            elif o.type == 'CAMERA':
                node = shadergraph_utils.find_projection_node(o) 
                if node:
                    update_texture(node, ob=o)
            elif o.type == 'LIGHT':
                node = o.data.renderman.get_light_node()
                if node:
                    update_texture(node, ob=o)
   
    for world in bpy.data.worlds:
        if not world.use_nodes:
            continue
        node = shadergraph_utils.find_integrator_node(world)
        if node:
            update_texture(node, ob=world)
        for node in shadergraph_utils.find_displayfilter_nodes(world):
            update_texture(node, ob=world)
        for node in shadergraph_utils.find_samplefilter_nodes(world):
            update_texture(node, ob=world)            
 
    for mat in bpy.data.materials:
        get_textures(mat)
            
def parse_for_textures(bl_scene):    
    rfb_log().debug("Parsing scene for textures.")                                   
    parse_scene_for_textures(bl_scene)

def save_scene_state(state):
    """Save the serialized TxManager object in scene.renderman.txmanagerData.
    """
    if bpy.context.engine != 'PRMAN_RENDER':
        return
    scene = bpy.context.scene
    rm = getattr(scene, 'renderman', None)
    if rm:
        try:
            setattr(rm, 'txmanagerData', state)
        except AttributeError:
            pass

def load_scene_state():
    """Load the JSON serialization from scene.renderman.txmanagerData and use it
    to update the texture manager.
    """
    if bpy.context.engine != 'PRMAN_RENDER':
        return
    scene = bpy.context.scene
    rm = getattr(scene, 'renderman', None)
    state = '{}'
    if rm:
        state = getattr(rm, 'txmanagerData', state)
    return state

@persistent
def txmanager_load_cb(bl_scene):
    if bpy.context.engine != 'PRMAN_RENDER':
        return    
    get_txmanager().txmanager.reset()
    get_txmanager().txmanager.load_state()
    scene = bpy.context.scene
    rm = getattr(scene, 'renderman', None)
    state = None
    if rm:
        state = getattr(rm, 'txmanagerData', state)
    if state is None:
        bpy.ops.rman_txmgr_list.parse_scene('EXEC_DEFAULT')
        bpy.ops.rman_txmgr_list.clear_unused('EXEC_DEFAULT')

@persistent
def txmanager_pre_save_cb(bl_scene):
    if bpy.context.engine != 'PRMAN_RENDER':
        return    
    get_txmanager().txmanager.save_state()  

def depsgraph_handler(depsgraph_update, depsgraph):
    id = depsgraph_update.id
    # check new linked in materials
    if id.library:
        link_file_handler(id)
        return
    # check if nodes were renamed
    elif isinstance(id, bpy.types.Object):
        check_node_rename(id)
    elif isinstance(id, bpy.types.Material):
        check_node_rename(id)

def check_node_rename(id):    
    nodes_list = list()
    ob = None
    if isinstance(id, bpy.types.Material):
        ob = id.original
        shadergraph_utils.gather_all_textured_nodes(ob, nodes_list)
    elif isinstance(id, bpy.types.Object):
        ob = id.original
        if id.type == 'CAMERA':
            node = shadergraph_utils.find_projection_node(ob) 
            if node:
                nodes_list.append(node)

        elif id.type == 'LIGHT':
            shadergraph_utils.gather_all_textured_nodes(ob, nodes_list)

    for node in nodes_list:
        txm_id = getattr(node, 'txm_id', None)
        node_name = generate_node_name(node, '', nm=ob.name)
        # check if the txm_id property matches what we think the node name
        # should be
        if txm_id != node_name:
            # txm_id differs, update the texture manager
            update_texture(node, ob=ob, check_exists=False)
        
def link_file_handler(id):
    if isinstance(id, bpy.types.Material):
        get_textures(id, check_exists=True)

    elif isinstance(id, bpy.types.Object):
        if id.type == 'CAMERA':
            node = shadergraph_utils.find_projection_node(id) 
            if node:
                update_texture(node, ob=id, check_exists=True)

        elif id.type == 'LIGHT':
            nodes_list = list()
            ob = id.original
            shadergraph_utils.gather_all_textured_nodes(ob, nodes_list)
            for node in nodes_list:
                update_texture(node, ob=ob, check_exists=True)

def txmake_all(blocking=True):
    get_txmanager().txmake_all(blocking=blocking)        