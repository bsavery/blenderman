from .rman_translator import RmanTranslator
from ..rman_sg_nodes.rman_sg_material import RmanSgMaterial
from ..rfb_utils import string_utils
from ..rfb_utils import property_utils
from ..rfb_utils import shadergraph_utils
from ..rfb_utils import color_utils
from ..rfb_utils import gpmaterial_utils
from ..rfb_utils import filepath_utils
from ..rfb_utils.shadergraph_utils import RmanConvertNode
from ..rman_constants import __RESERVED_BLENDER_NAMES__

from ..rfb_logger import rfb_log
import math
import re
import bpy

__MAP_CYCLES_PARAMS__ = {
    "ShaderNodeTexNoise": {
        "dimensions": "noise_dimensions"
    },
    "ShaderNodeAttribute": {
        "name": "attribute_name"
    }
}

def get_root_node(node, type='bxdf'):
    rman_type = getattr(node, 'renderman_node_type', node.bl_idname)
    if rman_type == type:
        return node
    elif rman_type =='ShaderNodeGroup':
        ng = node.node_tree
        out = next((n for n in ng.nodes if n.bl_idname == 'NodeGroupOutput'),
                None)
        if out is None:
            return None
        return out        
    return None

def get_cycles_value(node, param_name):
    val = getattr(node, param_name, None)
    if node.bl_idname in __MAP_CYCLES_PARAMS__:
        params_map = __MAP_CYCLES_PARAMS__[node.bl_idname]
        val = getattr(node, params_map.get(param_name, param_name), None)
    return val

class RmanMaterialTranslator(RmanTranslator):

    def __init__(self, rman_scene):
        super().__init__(rman_scene)
        self.bl_type = 'MATERIAL'

    def export(self, mat, db_name):

        sg_material = self.rman_scene.sg_scene.CreateMaterial(db_name)
        rman_sg_material = RmanSgMaterial(self.rman_scene, sg_material, db_name)
        self.update(mat, rman_sg_material)
        return rman_sg_material

    def update(self, mat, rman_sg_material, time_sample=0):

        rm = mat.renderman
        succeed = False

        rman_sg_material.has_meshlight = False
        rman_sg_material.sg_node.SetBxdf(None)        
        rman_sg_material.sg_node.SetLight(None)
        rman_sg_material.sg_node.SetDisplace(None)        

        handle = string_utils.sanitize_node_name(rman_sg_material.db_name)
        if mat.grease_pencil:
            if not mat.node_tree or not shadergraph_utils.is_renderman_nodetree(mat):
                self.export_shader_grease_pencil(mat, rman_sg_material, handle=handle)
                return

        if mat.node_tree:
            succeed = self.export_shader_nodetree(mat, rman_sg_material, handle=handle)

        if not succeed:
            succeed = self.export_simple_shader(mat, rman_sg_material, mat_handle=handle)     

    def export_shader_grease_pencil(self, mat, rman_sg_material, handle):
        gp_mat = mat.grease_pencil
        rman_sg_material.is_gp_material = True

        if gp_mat.show_stroke:
            stroke_style = gp_mat.stroke_style
            if not rman_sg_material.sg_stroke_mat:
                rman_sg_material.sg_stroke_mat = self.rman_scene.sg_scene.CreateMaterial('%s-STROKE_MAT' % rman_sg_material.db_name)

            if stroke_style == 'SOLID':
                gpmaterial_utils.gp_material_stroke_solid(mat, self.rman_scene.rman, rman_sg_material, '%s-STROKE' % handle)
            elif stroke_style == 'TEXTURE':
                gpmaterial_utils.gp_material_stroke_texture(mat, self.rman_scene.rman, rman_sg_material, '%s-STROKE' % handle)
            
        if gp_mat.show_fill:
            fill_style = gp_mat.fill_style
            if not rman_sg_material.sg_fill_mat:
                rman_sg_material.sg_fill_mat = self.rman_scene.sg_scene.CreateMaterial('%s-FILL_MAT' % rman_sg_material.db_name)

            if fill_style == 'TEXTURE':                                 
                gpmaterial_utils.gp_material_fill_texture(mat, self.rman_scene.rman, rman_sg_material, '%s-FILL' % handle)
            elif fill_style == 'CHECKER':
                gpmaterial_utils.gp_material_fill_checker(mat, self.rman_scene.rman, rman_sg_material, '%s-FILL' % handle)

            elif fill_style == 'GRADIENT':
                gpmaterial_utils.gp_material_fill_gradient(mat, self.rman_scene.rman, rman_sg_material, '%s-FILL' % handle)
            else:
                gpmaterial_utils.gp_material_fill_solid(mat, self.rman_scene.rman, rman_sg_material, '%s-FILL' % handle)

    def create_pxrdiffuse_node(self, rman_sg_material, handle):     
        instance = string_utils.sanitize_node_name(handle + '_PXRDIFFUSE')
        sg_node = self.rman_scene.rman.SGManager.RixSGShader("Bxdf", 'PxrDiffuse', instance) 
        rman_sg_material.sg_node.SetBxdf([sg_node])                   
             
    def export_shader_nodetree(self, material, rman_sg_material, handle):

        if material and material.node_tree:

            out = shadergraph_utils.is_renderman_nodetree(material)
            has_solo_node = False

            if out:
                nt = material.node_tree

                # check if there's a solo node
                if out.solo_node_name:
                    if out.solo_nodetree:
                        solo_nodetree = out.solo_nodetree
                        solo_node = solo_nodetree.nodes.get(out.solo_node_name, None)
                    else:
                        # try the material node tree
                        solo_node = material.node_tree.nodes.get(out.solo_node_name, None)
                        solo_nodetree = material.node_tree
                        
                    if solo_node:
                        has_solo_node = self.export_solo_shader(material, solo_nodetree, out, solo_node, rman_sg_material, handle)                        
                    else:
                        rfb_log().error("Solo node requested, but could not find nodetree.")

                # bxdf
                if not has_solo_node:
                    socket = out.inputs.get('bxdf_in', None)
                    if socket is None:
                        # try old name
                        socket = out.inputs.get('Bxdf', None)
                    if socket and socket.is_linked and len(socket.links) > 0:
                        from_node = socket.links[0].from_node
                        linked_node = get_root_node(from_node, type='bxdf')
                        if linked_node:
                            bxdfList = []
                            sub_nodes = []
                            rman_sg_material.nodes_to_blnodeinfo.clear()                       
                            sub_nodes.extend(shadergraph_utils.gather_nodes(from_node))
                            for sub_node in sub_nodes:
                                shader_sg_nodes = self.shader_node_sg(material, sub_node, rman_sg_material, mat_name=handle)
                                for s in shader_sg_nodes:
                                    bxdfList.append(s) 

                            for node, bl_node_info in rman_sg_material.nodes_to_blnodeinfo.items():
                                if bl_node_info.is_cycles_node:
                                    continue
                                property_utils.property_group_to_rixparams(node, rman_sg_material, bl_node_info.sg_node, ob=material, group_node=bl_node_info.group_node)
                            
                            if bxdfList:
                                rman_sg_material.sg_node.SetBxdf(bxdfList)   
                        else:
                            self.create_pxrdiffuse_node(rman_sg_material, handle)         
                    else:
                        self.create_pxrdiffuse_node(rman_sg_material, handle)

                # light
                if not has_solo_node:
                    socket = out.inputs.get('light_in', None)
                    if socket is None:
                        # try old name
                        socket = out.inputs.get('Light', None)
                    if socket and socket.is_linked and len(socket.links) > 0:
                        from_node = socket.links[0].from_node
                        linked_node = get_root_node(socket.links[0].from_node, type='light')
                        if linked_node:
                            lightNodesList = []
                            sub_nodes = []
                            rman_sg_material.nodes_to_blnodeinfo.clear()                
                            sub_nodes.extend(shadergraph_utils.gather_nodes(from_node))                        
                            for sub_node in sub_nodes:
                                shader_sg_nodes = self.shader_node_sg(material, sub_node, rman_sg_material, mat_name=handle)
                                for s in shader_sg_nodes:
                                    lightNodesList.append(s) 
                            for node, bl_node_info in rman_sg_material.nodes_to_blnodeinfo.items():
                                if bl_node_info.is_cycles_node:
                                    continue                            
                                property_utils.property_group_to_rixparams(node, rman_sg_material, bl_node_info.sg_node, ob=material, group_node=bl_node_info.group_node)
                                                        
                            if lightNodesList:
                                rman_sg_material.sg_node.SetLight(lightNodesList)                                   

                # displacement
                socket = out.inputs.get('displace_in', None)
                if socket is None:
                    # use old name
                    socket = out.inputs.get('Displacement', None)                
                if socket and socket.is_linked and len(socket.links) > 0:
                    from_node = socket.links[0].from_node
                    linked_node = get_root_node(from_node, type='displace')
                    if linked_node:                    
                        dispList = []
                        sub_nodes = []
                        rman_sg_material.nodes_to_blnodeinfo.clear()                  
                        sub_nodes.extend(shadergraph_utils.gather_nodes(from_node))                             
                        for sub_node in sub_nodes:
                            shader_sg_nodes = self.shader_node_sg(material, sub_node, rman_sg_material, mat_name=handle)
                            for s in shader_sg_nodes:
                                dispList.append(s) 
                        for node, bl_node_info in rman_sg_material.nodes_to_blnodeinfo.items():
                            if bl_node_info.is_cycles_node:
                                continue
                            property_utils.property_group_to_rixparams(node, rman_sg_material, bl_node_info.sg_node, ob=material, group_node=bl_node_info.group_node)
                                                                              
                        if dispList:
                            rman_sg_material.sg_node.SetDisplace(dispList)  

                return True                        
                    
            elif shadergraph_utils.find_node(material, 'ShaderNodeOutputMaterial'):
                rfb_log().debug("Error Material %s needs a RenderMan BXDF" % material.name)
                return False

        return False

    def export_solo_shader(self, mat, nt, out, solo_node, rman_sg_material, mat_handle=''):
        bxdfList = []
        rman_sg_material.nodes_to_blnodeinfo.clear()         

        nodes_list = shadergraph_utils.gather_nodes(solo_node, for_solo_node=True)
        rman_sg_material.nodes_to_blnodeinfo.clear()

        rman_solo_sg_node = None        
        for sub_node in nodes_list:
            shader_sg_nodes = self.shader_node_sg(mat, sub_node, rman_sg_material, mat_name=mat_handle)
            for s in shader_sg_nodes:                
                if sub_node == solo_node:
                    rman_solo_sg_node = s
                else:
                    bxdfList.append(s)                     

            for node, bl_node_info in rman_sg_material.nodes_to_blnodeinfo.items():
                property_utils.property_group_to_rixparams(node, rman_sg_material, bl_node_info.sg_node, ob=mat, group_node=bl_node_info.group_node)

        bxdfList.append(rman_solo_sg_node)

        node_type = getattr(solo_node, 'renderman_node_type', '')
        if bxdfList:
            if node_type == 'pattern':
                sg_node = self.rman_scene.rman.SGManager.RixSGShader("Bxdf", 'PxrConstant', '__RMAN_SOLO_SHADER__')
                params = sg_node.params
                from_socket = solo_node.outputs[0]
                if out.solo_node_output:
                    from_socket = solo_node.outputs.get(out.solo_node_output)       
                val = property_utils.get_output_param_str(rman_sg_material, solo_node, mat_handle, from_socket, check_do_convert=False)

                # check the output type
                if from_socket.renderman_type in ['color', 'normal', 'vector', 'point']:               
                    property_utils.set_rix_param(params, 'color', 'emitColor', val, is_reference=True)
                    bxdfList.append(sg_node)
                elif from_socket.renderman_type in ['float']:
                    to_float3 = self.rman_scene.rman.SGManager.RixSGShader("Pattern", 'PxrToFloat3', '__RMAN_SOLO_SHADER_PXRTOFLOAT3__')
                    property_utils.set_rix_param(to_float3.params, from_socket.renderman_type, 'input', val, is_reference=True)
                    val = '__RMAN_SOLO_SHADER_PXRTOFLOAT3__:resultRGB'
                    property_utils.set_rix_param(params, 'color', 'emitColor', val, is_reference=True)
                    bxdfList.append(to_float3)
                    bxdfList.append(sg_node)
                
            rman_sg_material.sg_node.SetBxdf(bxdfList)   
            return True             

        return False       


    def export_simple_shader(self, mat, rman_sg_material, mat_handle=''):
        rm = mat.renderman
        name = mat_handle
        if name == '':
            name = 'material_%s' % mat.name_full

        bxdf_name = '%s_PxrDisneyBsdf' % name
        sg_node = self.rman_scene.rman.SGManager.RixSGShader("Bxdf", "PxrDisneyBsdf", bxdf_name)
        rix_params = sg_node.params
        # use the material's Viewport Display properties
        diffuse_color = string_utils.convert_val(mat.diffuse_color, type_hint='color')
        rix_params.SetColor('baseColor', diffuse_color)
        if len(mat.diffuse_color) == 4:
            # use the alpha from diffuse_color as presence
            rix_params.SetFloat('presence', mat.diffuse_color[3])
        rix_params.SetFloat('metallic', mat.metallic )
        rix_params.SetFloat('roughness', mat.roughness)
        rix_params.SetFloat('specReflectScale', mat.metallic )
       
        rman_sg_material.sg_node.SetBxdf([sg_node])        

        return True

    def translate_node_group(self, mat, rman_sg_material, group_node, mat_name):
        ng = group_node.node_tree
        out = next((n for n in ng.nodes if n.bl_idname == 'NodeGroupOutput'),
                None)
        if out is None:
            return

        nodes_to_export = shadergraph_utils.gather_nodes(out)
        sg_nodes = []
        for node in nodes_to_export:
            sg_nodes += self.shader_node_sg(mat, node, rman_sg_material, mat_name=mat_name, group_node=group_node)
        return sg_nodes       

    def translate_cycles_math_node(self, mat, rman_sg_material, node, mat_name, group_node=None):
        instance_name = shadergraph_utils.get_node_name(node, mat_name)
        sg_node = self.rman_scene.rman.SGManager.RixSGShader("Pattern", 'node_math', instance_name)
        params = sg_node.params   
        params.SetString('type', node.operation)
        
        for i, in_name in enumerate(node.inputs.keys()):            
            input = node.inputs[in_name]
            param_name = "Value%d" % (i+1)
            param_type = 'float'
            if input.is_linked:
                link = input.links[0]
                val = property_utils.get_output_param_str(rman_sg_material,
                    link.from_node, mat_name, link.from_socket, input)

                property_utils.set_rix_param(params, param_type, param_name, val, is_reference=True)                

            else:
                val = input.default_value
                property_utils.set_rix_param(params, param_type, param_name, val, is_reference=False)

        rman_sg_material.nodes_to_blnodeinfo[node] = shadergraph_utils.BlNodeInfo(sg_node, group_node=group_node, is_cycles_node=True)
        return [sg_node]

    def translate_cycles_node(self, mat, rman_sg_material, node, mat_name, group_node=None):
        from .. import rman_bl_nodes        

        if node.bl_idname == 'ShaderNodeGroup':
            return self.translate_node_group(mat, rman_sg_material, node, mat_name)
        elif node.bl_idname == 'ShaderNodeMath':
            return self.translate_cycles_math_node(mat, rman_sg_material, node, mat_name, group_node=group_node)            

        mapping, node_desc = rman_bl_nodes.get_cycles_node_desc(node)

        if not mapping:
            rfb_log().error('No translation for node of type %s named %s' %
                (node.bl_idname, node.name))
            return []

        instance_name = shadergraph_utils.get_node_name(node, mat_name)
        sg_node = self.rman_scene.rman.SGManager.RixSGShader("Pattern", mapping, instance_name)
        params = sg_node.params      
        rman_sg_material.nodes_to_blnodeinfo[node] = shadergraph_utils.BlNodeInfo(sg_node, group_node=group_node, is_cycles_node=True)
        
        for in_name, input in node.inputs.items():
            param_name = "%s" % shadergraph_utils.get_socket_name(node, input)
            param_type = "%s" % shadergraph_utils.get_socket_type(node, input)
            if input.is_linked:
                link = input.links[0]
                val = property_utils.get_output_param_str(rman_sg_material,
                    link.from_node, mat_name, link.from_socket, input)

                property_utils.set_rix_param(params, param_type, param_name, val, is_reference=True)                

            else:
                val = string_utils.convert_val(input.default_value,
                                type_hint=shadergraph_utils.get_socket_type(node, input))
                # skip if this is a vector set to 0 0 0
                if input.type == 'VECTOR' and val == [0.0, 0.0, 0.0]:
                    continue

                property_utils.set_rix_param(params, param_type, param_name, val, is_reference=False)

        for node_desc_param in node_desc.params:
            param_name = node_desc_param._name
            if param_name in node.inputs:
                continue
            param_type = node_desc_param.type
            if param_name in __RESERVED_BLENDER_NAMES__:
                val = node_desc_param.default
            else:
                val = get_cycles_value(node, param_name)
                if val is None:
                    continue
                val = string_utils.convert_val(val,
                                type_hint=param_type)

                if param_type == 'string':
                    val = str(val)

            property_utils.set_rix_param(params, param_type, param_name, val, is_reference=False)            

        ramp_size = 256
        if node.bl_idname == 'ShaderNodeValToRGB':
            colors = []
            alphas = []

            for i in range(ramp_size):
                c = node.color_ramp.evaluate(float(i) / (ramp_size - 1.0))
                colors.extend(c[:3])
                alphas.append(c[3])

            params.SetColorArray('ramp_color', colors, ramp_size)
            params.SetFloatArray('ramp_alpha', alphas, ramp_size)

        elif node.bl_idname == 'ShaderNodeVectorCurve':
            colors = []
            node.mapping.initialize()
            r = node.mapping.curves[0]
            g = node.mapping.curves[1]
            b = node.mapping.curves[2]

            for i in range(ramp_size):
                v = float(i) / (ramp_size - 1.0)
                r_val = node.mapping.evaluate(r, v) 
                g_val = node.mapping.evaluate(r, v)
                b_val = node.mapping.evaluate(r, v)
                colors.extend([r_val, g_val, b_val])

            params.SetColorArray('ramp', colors, ramp_size)

        elif node.bl_idname == 'ShaderNodeRGBCurve':
            colors = []
            node.mapping.initialize()
            c = node.mapping.curves[0]
            r = node.mapping.curves[1]
            g = node.mapping.curves[2]
            b = node.mapping.curves[3]

            for i in range(ramp_size):
                v = float(i) / (ramp_size - 1.0)
                c_val = node.mapping.evaluate(c, v)
                r_val = node.mapping.evaluate(r, v) * c_val
                g_val = node.mapping.evaluate(r, v) * c_val
                b_val = node.mapping.evaluate(r, v) * c_val
                colors.extend([r_val, g_val, b_val])


            params.SetColorArray('ramp', colors, ramp_size)
    
        return [sg_node]        

    def shader_node_sg(self, mat, node, rman_sg_material, mat_name, group_node=None):
 
        sg_node = None

        if type(node) == RmanConvertNode:
            node_type = node.node_type
            from_node = node.from_node
            from_socket = node.from_socket
            input_type = 'float' if node_type == 'PxrToFloat3' else 'color'
            node_name = 'convert_%s_%s' % (shadergraph_utils.get_node_name(
                from_node, mat_name), shadergraph_utils.get_socket_name(from_node, from_socket))
            if from_node.bl_idname == 'ShaderNodeGroup':
                node_name = 'convert_' + property_utils.get_output_param_str(rman_sg_material,
                    from_node, mat_name, from_socket).replace(':', '_')
                    
            val = property_utils.get_output_param_str(rman_sg_material, from_node, mat_name, from_socket)
            if val is not None and val != '':
                sg_node = self.rman_scene.rman.SGManager.RixSGShader("Pattern", node_type, node_name)
                rix_params = sg_node.params       
                if input_type == 'color':
                    rix_params.SetColorReference('input', val)
                else:
                    rix_params.SetFloatReference('input', val)            
                    
            return [sg_node]
        elif node.bl_idname == 'NodeReroute':
            # This is a reroute node. Ignore. We will deal with these when we build
            # the connection string
            return list()
        elif not hasattr(node, 'renderman_node_type'):
            return self.translate_cycles_node(mat, rman_sg_material, node, mat_name, group_node=group_node)

        instance = shadergraph_utils.get_node_name(node, mat_name)
        if group_node:
            group_node_name = string_utils.get_unique_group_name(group_node)
            instance = shadergraph_utils.get_node_name(node, mat_name + '_' + group_node_name)

        if not hasattr(node, 'renderman_node_type'):
            return list()

        if node.renderman_node_type == "pattern":
            if node.bl_label == 'PxrOSL':
                shader = node.shadercode 
                if shader:
                    osl_path = string_utils.expand_string(shader)
                    osl_path = filepath_utils.get_real_path(osl_path)
                    sg_node = self.rman_scene.rman.SGManager.RixSGShader("Pattern", osl_path, instance)
                    
            else:
                shader = node.bl_label
                sg_node = self.rman_scene.rman.SGManager.RixSGShader("Pattern", shader, instance)
        elif node.renderman_node_type == "light":
            light_group_name = ''            
            for lg in self.rman_scene.bl_scene.renderman.light_groups:
                if mat_name in lg.members.keys():
                    light_group_name = lg.name
                    break

            sg_node = self.rman_scene.rman.SGManager.RixSGShader("Light", node.bl_label, mat_name)

            if node.bl_label == 'PxrMeshLight':
                # flag this material as having a mesh light
                rman_sg_material.has_meshlight = True

            # export any light filters
            self.update_light_filters(mat, rman_sg_material)       

        elif node.renderman_node_type == "displace":
            sg_node = self.rman_scene.rman.SGManager.RixSGShader("Displacement", node.bl_label, instance)
        else:
            sg_node = self.rman_scene.rman.SGManager.RixSGShader("Bxdf", node.bl_label, instance)        

        rman_sg_material.nodes_to_blnodeinfo[node] = shadergraph_utils.BlNodeInfo(sg_node, group_node=group_node)
        return [sg_node]       

    def update_light_filters(self, mat, rman_sg_material):
        rm = mat.renderman_light 
        lightfilter_translator = self.rman_scene.rman_translators['LIGHTFILTER']
        lightfilter_translator.export_light_filters(mat, rman_sg_material, rm)             