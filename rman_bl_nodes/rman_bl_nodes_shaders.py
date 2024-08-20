from ..rfb_logger import rfb_log
from ..rfb_utils.osl_utils import readOSO
from ..rfb_utils import rman_socket_utils
from ..rfb_utils import string_utils
from ..rfb_utils import shadergraph_utils
from ..rfb_utils import draw_utils
from ..rfb_utils.property_utils import BlPropInfo, __LOBES_ENABLE_PARAMS__
from ..rfb_utils import filepath_utils
from ..rman_config import __RFB_CONFIG_DICT__
from ..rman_constants import RFB_FLOAT3, RFB_SHADER_ALLOWED_CONNECTIONS, __RMAN_SOCKET_MAP__
from .. import rman_bl_nodes
from .. import rfb_icons
from .. import rman_render
from copy import deepcopy
from bpy.types import Menu
from bpy.props import EnumProperty, StringProperty, CollectionProperty, BoolProperty, PointerProperty
import _cycles
import bpy
import os
import shutil
import tempfile

NODE_LAYOUT_SPLIT = 0.5

# Base class for all custom nodes in this tree type.
# Defines a poll function to enable instantiation.
class RendermanShadingNode(bpy.types.ShaderNode):
    bl_label = 'Output'
    prev_hidden: BoolProperty(default=False, description="Whether or not this node was previously hidden.")
    new_links = []
    num_links = -1

    def update_mat(self, mat):
        if self.renderman_node_type == 'bxdf' and self.outputs['bxdf_out'].is_linked:
            mat.specular_color = [1, 1, 1]
            mat.diffuse_color = [1, 1, 1, 1]
            mat.specular_intensity = 0

            bxdf_name = self.bl_label
            bxdf_props = __RFB_CONFIG_DICT__['bxdf_viewport_color_mapping'].get(bxdf_name, None)
            if bxdf_props:
                diffuse_color = bxdf_props.get('diffuse_color', None)
                if diffuse_color:
                    if isinstance(diffuse_color[0], str):
                        diffuse_color = getattr(self, diffuse_color[0])
                    mat.diffuse_color[:3] = [i for i in diffuse_color]

                specular_color = bxdf_props.get('specular_color', None)
                if specular_color:
                    if isinstance(specular_color[0], str):
                        specular_color = getattr(self, specular_color[0])
                    mat.specular_color[:3] = [i for i in specular_color]   

                specular_intensity = bxdf_props.get('specular_intensity', None)
                if specular_intensity:
                    if isinstance(specular_intensity, str):
                        specular_intensity = getattr(self, specular_intensity)
                    mat.specular_intensity = specular_intensity

                metallic = bxdf_props.get('metallic', None)
                if metallic:
                    if isinstance(metallic, str):
                        metallic = getattr(self, metallic)
                    mat.metallic = metallic                    

                roughness = bxdf_props.get('roughness', None)
                if roughness:
                    if isinstance(roughness, str):
                        roughness = getattr(self, roughness)
                    mat.roughness = roughness   
        elif isinstance(mat, bpy.types.Material):
            mat.node_tree.update_tag()

    def draw_label(self):
        nm = self.name
        if self.label:
            nm = self.label
        if bpy.context.material:
            mat = bpy.context.material
            if shadergraph_utils.is_soloable_node(self):
                out_node = shadergraph_utils.find_node(mat, 'RendermanOutputNode')
                if out_node.solo_nodetree == self.id_data and self.name == out_node.solo_node_name:
                    nm = "%s (SOLO)" % nm
        return nm

    # all the properties of a shader will go here, also inputs/outputs
    # on connectable props will have the same name
    # node_props = None
    def draw_buttons(self, context, layout):
        nt = self.id_data
        mat = context.material
        out_node = shadergraph_utils.find_node(mat, 'RendermanOutputNode')
        self.draw_nonconnectable_props(context, layout, self.prop_names, output_node=out_node)
        if self.bl_idname == "PxrOSLPatternNode":
            layout.operator("node.rman_refresh_osl_shader")

    def draw_buttons_ext(self, context, layout):
        nt = self.id_data
        mat = bpy.context.material
        out_node = shadergraph_utils.find_node(mat, 'RendermanOutputNode')   
        rman_icon = rfb_icons.get_node_icon(self.bl_label)
        split = layout.split(factor=0.75)
        col = split.column(align=True)
        col.label(text=self.bl_label, icon_value=rman_icon.icon_id)  
        if shadergraph_utils.is_soloable_node(self):
            self.draw_solo_button(nt, out_node, split)
            # draw solo output select menu
            if self.name == out_node.solo_node_name:            
                solo_node = nt.nodes.get(out_node.solo_node_name, None)
                if solo_node:
                    col = layout.column(align=True)
                    col.context_pointer_set("nodetree", nt)  
                    col.context_pointer_set("node", out_node) 
                    col.menu('NODE_MT_renderman_node_solo_output_menu', text='Select Output')

        layout.separator()
        self.draw_nonconnectable_props(context, layout, self.prop_names, output_node=out_node)

    def draw_solo_button(self, nt, rman_output_node, layout):
        layout.context_pointer_set("nodetree", nt)  
        layout.context_pointer_set("node", rman_output_node)                  

        if rman_output_node.solo_node_name == '':
            col = layout.column(align=True)
            rman_icon = rfb_icons.get_icon('rman_solo_off')
            op = col.operator('node.rman_set_node_solo', text='', icon_value=rman_icon.icon_id, emboss=False)
            op.refresh_solo = False
            op.solo_node_name = self.name           
        else:
            rman_icon = rfb_icons.get_icon('rman_solo_on')
            if rman_output_node.solo_nodetree == self.id_data and  self.name == rman_output_node.solo_node_name:
                col = layout.column(align=True)
                op = col.operator('node.rman_set_node_solo', text='', icon_value=rman_icon.icon_id, emboss=False)
                op.refresh_solo = True
                op.solo_node_name = self.name                             
            else:
                rman_icon = rfb_icons.get_icon('rman_solo_off')
                col = layout.column(align=True)
                op = col.operator('node.rman_set_node_solo', text='', icon_value=rman_icon.icon_id, emboss=False)
                op.refresh_solo = False
                op.solo_node_name = self.name 
                col = layout.column(align=True)
                op = col.operator('node.rman_set_node_solo', text='', icon='FILE_REFRESH', emboss=False)
                op.refresh_solo = True                          

    def draw_nonconnectable_prop(self, context, layout, prop_name, output_node=None, level=0):
        node = self
        prop_meta = node.prop_meta[prop_name]
        bl_prop_info = BlPropInfo(node, prop_name, prop_meta)
        ui_structs = getattr(node, 'ui_structs', dict())
        if not bl_prop_info.is_ui_struct and bl_prop_info.prop is None:
            return
        if bl_prop_info.widget == 'null':
            return

        # evaluate the conditionalVisOps
        if bl_prop_info.conditionalVisOps and bl_prop_info.cond_expr:
            try:
                hidden = not eval(bl_prop_info.cond_expr)
                if bl_prop_info.conditionalLockOps:
                    bl_prop_info.prop_disabled = hidden                     
                else:
                    if hidden:
                        return
            except Exception as err:                        
                rfb_log().error("Error handling conditionalVisOp: %s" % str(err))
                pass

        if bl_prop_info.prop_hidden:
            return

        if bl_prop_info.is_ui_struct:                      
            ui_prop = prop_name + "_uio"
            ui_open = getattr(node, ui_prop)
            icon = draw_utils.get_open_close_icon(ui_open)

            split = layout.split(factor=NODE_LAYOUT_SPLIT)
            row = split.row()
            row.enabled = not bl_prop_info.prop_disabled
            row.context_pointer_set("node", node)
            op = row.operator('node.rman_open_close_page', text='', icon=icon, emboss=False)            
            op.prop_name = ui_prop
            prop_label = bl_prop_info.label
            arraylen_nm = '%s_arraylen' % prop_name
            arraylen = getattr(node, arraylen_nm)
            array_label = prop_label + ' [%d]:' % arraylen
            row.label(text=array_label) 
            if ui_open:         
                row = layout.row(align=True)
                draw_utils.draw_indented_label(row, None, level+1)                
                row.prop(node, arraylen_nm, text=bl_prop_info.label) 
                draw_utils.draw_sticky_toggle(row, node, prop_name, output_node) 
                ui_struct_members = ui_structs.get(prop_name)
                for i in range(arraylen):
                    draw_utils.draw_indented_label(layout, prop_label + ' [%d]:' % i, level)
                    for nm in ui_struct_members:
                        sub_prop_name = '%s[%d]' % (nm, i)
                        meta = node.prop_meta[sub_prop_name]
                        if meta.get('__noconnection', False):
                             self.draw_nonconnectable_prop(context, layout, sub_prop_name, output_node=output_node, level=level+1)

            return                
        elif bl_prop_info.widget == 'colorramp':
            node_group = self.rman_fake_node_group_ptr
            if not node_group:
                row = layout.row(align=True)
                row.context_pointer_set("node", node)
                row.operator('node.rman_fix_ramp')
                row.operator('node.rman_fix_all_ramps')
                return                
                            
            ramp_name =  getattr(node, prop_name)
            ramp_node = node_group.nodes[ramp_name]
            nt = node.id_data
            layout.enabled = (nt.library is None)
            layout.template_color_ramp(
                    ramp_node, 'color_ramp')                  
            return                            
        elif bl_prop_info.widget == 'floatramp':
            node_group = self.rman_fake_node_group_ptr 
            if not node_group:
                node_group = bpy.data.node_groups.get(node.rman_fake_node_group, None)            
            if not node_group:
                row = layout.row(align=True)
                row.context_pointer_set("node", node)
                row.operator('node.rman_fix_ramp')
                row.operator('node.rman_fix_all_ramps')
                return                       

            ramp_name =  getattr(node, prop_name)
            ramp_node = node_group.nodes[ramp_name]
            nt = node.id_data
            layout.enabled = (nt.library is None)
            layout.template_curve_mapping(
                    ramp_node, 'mapping')         
            interp_name = '%s_Interpolation' % prop_name
            if hasattr(node, interp_name):
                layout.prop(node, interp_name, text='Ramp Interpolation')                              
            return
                    
        if prop_name not in node.inputs:
            if bl_prop_info.renderman_type == 'page':
                sub_prop_names = list(bl_prop_info.prop)
                if shadergraph_utils.has_lobe_enable_props(node):
                    # check if a lobe is enabled
                    # if not, we don't draw the page
                    lobe_enabled = True
                    for pn in sub_prop_names:
                        if pn in __LOBES_ENABLE_PARAMS__:
                            sub_prop_names.remove(pn)
                            if not getattr(node, pn):
                                lobe_enabled = False
                            break                   
                    if not lobe_enabled:
                        return     
                has_any = False
                for nm in sub_prop_names:
                    if nm not in node.inputs:
                        has_any = True

                if not has_any:
                    # don't draw the page if all subprops are inputs/outputs
                    return

                prop_disabled = getattr(node, '%s_disabled' % prop_name, False)
                
                ui_prop = prop_name + "_uio"
                ui_open = getattr(node, ui_prop)
                icon = draw_utils.get_open_close_icon(ui_open)

                split = layout.split(factor=NODE_LAYOUT_SPLIT)
                row = split.row()
                row.enabled = not prop_disabled
                draw_utils.draw_indented_label(row, None, level)

                row.context_pointer_set("node", node)               
                op = row.operator('node.rman_open_close_page', text='', icon=icon, emboss=False)            
                op.prop_name = ui_prop
                page_label = bl_prop_info.label
                row.label(text=page_label)                
                if ui_open:                  
                    self.draw_nonconnectable_props(
                        context, layout, sub_prop_names, output_node, level=level+1)          
                return

            elif bl_prop_info.renderman_type == 'array':
                row = layout.row(align=True)
                col = row.column()
                row = col.row()                
                row.enabled = not bl_prop_info.prop_disabled
                prop_label = bl_prop_info.label
                coll_nm = '%s_collection' % prop_name
                collection = getattr(node, coll_nm)
                array_len = len(collection)
                array_label = prop_label + ' [%d]:' % array_len
                row.label(text=array_label)         
                coll_idx_nm = '%s_collection_index' % prop_name
                row.template_list("RENDERMAN_UL_Array_List", "", node, coll_nm, node, coll_idx_nm, rows=5)
                col = row.column(align=True)
                row = col.row()
                row.context_pointer_set("node", node)
                op = row.operator('renderman.add_remove_array_elem', icon="ADD", text="")
                op.collection = coll_nm
                op.collection_index = coll_idx_nm
                op.param_name = prop_name
                op.action = 'ADD'
                op.elem_type = bl_prop_info.renderman_array_type
                row = col.row()
                row.context_pointer_set("node", node)
                op = row.operator('renderman.add_remove_array_elem', icon="REMOVE", text="")
                op.collection = coll_nm
                op.collection_index = coll_idx_nm
                op.param_name = prop_name
                op.action = 'REMOVE'
                op.elem_type = bl_prop_info.renderman_array_type

                coll_index = getattr(node, coll_idx_nm, None)
                if coll_idx_nm is None:
                    return

                if coll_index > -1 and coll_index < len(collection):
                    item = collection[coll_index]
                    row = layout.row(align=True)
                    socket_name = '%s[%d]' % (prop_name, coll_index)
                    socket = node.inputs.get(socket_name, None)
                    if not socket:
                        row.prop(item, 'value_%s' % item.type, slider=True)                

                return

            split = layout.split(factor=0.95)
            row = split.row(align=True)
            row.enabled = not bl_prop_info.prop_disabled
            draw_utils.draw_indented_label(row, None, level)

            if bl_prop_info.widget == 'propsearch':                 
                # use a prop_search layout
                options = prop_meta['options']
                prop_search_parent = options.get('prop_parent')
                prop_search_name = options.get('prop_name')
                eval(f'row.prop_search(node, prop_name, {prop_search_parent}, "{prop_search_name}")') 
                if prop_search_parent == 'context.scene.renderman':
                    rman_icon = rfb_icons.get_icon('rman_blender')
                    if prop_search_name == 'object_groups':                
                        row.operator('scene.rman_open_groups_editor', text='', icon_value=rman_icon.icon_id )
                    elif prop_search_name == 'vol_aggregates':
                        row.operator('scene.rman_open_vol_aggregates_editor', text='', icon_value=rman_icon.icon_id )                
                draw_utils.draw_sticky_toggle(row, node, prop_name, output_node)   

            elif bl_prop_info.read_only:
                if bl_prop_info.not_connectable:
                    row2 = row.row()
                    row2.prop(node, prop_name)
                    row2.enabled=False
                else:
                    row.label(text=bl_prop_info.label)
                    row2 = row.row()
                    row2.prop(node, prop_name, text="", slider=True)
                    row2.enabled=False    
                draw_utils.draw_sticky_toggle(row2, node, prop_name, output_node)
            else:
                row.prop(node, prop_name, slider=True)           
                draw_utils.draw_sticky_toggle(row, node, prop_name, output_node)                       
            
            if bl_prop_info.is_texture:
                prop_val = getattr(node, prop_name)
                if prop_val != '':
                    from ..rfb_utils import texture_utils
                    from ..rfb_utils import scene_utils
                    if texture_utils.get_txmanager().is_file_src_tex(node, prop_name):
                        return
                    colorspace_prop_name = '%s_colorspace' % prop_name
                    if not hasattr(node, colorspace_prop_name):
                        return
                    row = layout.row(align=True)
                    if texture_utils.get_txmanager().does_file_exist(prop_val):
                        row.prop(node, colorspace_prop_name, text='Color Space')
                        rman_icon = rfb_icons.get_icon('rman_txmanager')  
                        id = scene_utils.find_node_owner(node)
                        nodeID = texture_utils.generate_node_id(node, prop_name, ob=id)                                      
                        op = row.operator('rman_txmgr_list.open_txmanager', text='', icon_value=rman_icon.icon_id)   
                        op.nodeID = nodeID     
                    else:
                        row.label(text="Input mage does not exists.", icon='ERROR')       

    def draw_nonconnectable_props(self, context, layout, prop_names, output_node=None, level=0):        
        if level == 0 and shadergraph_utils.has_lobe_enable_props(self):
            # We want to draw the enable lobe params at the top of the node
            col = layout.column(align=True)
            for prop_name in __LOBES_ENABLE_PARAMS__:
                if hasattr(self, prop_name):
                    prop_meta = self.prop_meta[prop_name]
                    if self.bl_label == 'PxrLayer':
                        page_label = '%s' % prop_meta['page']
                        col.prop(self, prop_name, text=page_label)
                    else:
                        page_label = '%s' % prop_meta['label']
                        col.prop(self, prop_name, text=page_label )                      

        if self.bl_idname == "PxrOSLPatternNode":
            prop = getattr(self, "codetypeswitch")
            layout.prop(self, "codetypeswitch")
            if getattr(self, "codetypeswitch") == 'INT':
                prop = getattr(self, "internalSearch")
                layout.prop_search(
                    self, "internalSearch", bpy.data, "texts", text="")
            elif getattr(self, "codetypeswitch") == 'EXT':
                prop = getattr(self, "shadercode")
                layout.prop(self, "shadercode")
            elif getattr(self, "codetypeswitch") == 'NODE':
                layout.prop(self, "expression")
        else:            
            for prop_name in prop_names:
                self.draw_nonconnectable_prop(context, layout, prop_name, output_node=output_node, level=level)


    def copy(self, node):
        # Look for textures
        from ..rfb_utils import texture_utils
        prop_meta = getattr(self, 'prop_meta', dict())
        for prop_name, meta in prop_meta.items():
            if shadergraph_utils.is_texture_property(prop_name, meta):
                # This is a bit weird. Unfortunately, we can't seem to find the owner
                # of this node from here (ex: which material owns this node).
                # For now, we just parse the whole scene for textures.
                texture_utils.parse_for_textures(bpy.context.scene)
                break

        # Copy ramps
        color_rman_ramps = node.__annotations__.get('__COLOR_RAMPS__', [])
        float_rman_ramps = node.__annotations__.get('__FLOAT_RAMPS__', [])

        if color_rman_ramps or float_rman_ramps:
            self_color_rman_ramps = self.__annotations__.get('__COLOR_RAMPS__', [])
            self_float_rman_ramps = self.__annotations__.get('__FLOAT_RAMPS__', [])   

            node_group = bpy.data.node_groups.new(
                '.__RMAN_FAKE_NODEGROUP__', 'ShaderNodeTree') 
            node_group.use_fake_user = True  
            self.rman_fake_node_group_ptr = node_group
            self.rman_fake_node_group = node_group.name  

            nt = node.rman_fake_node_group_ptr
            if not nt:
                nt = bpy.data.node_groups[node.rman_fake_node_group]
                node.rman_fake_ndoe_group_ptr = nt

            for i, prop_name in enumerate(color_rman_ramps):
                ramp_name = getattr(node, prop_name)
                node_color_ramp_node = nt.nodes[ramp_name]
                n = node_group.nodes.new('ShaderNodeValToRGB')

                for j,e in enumerate(node_color_ramp_node.color_ramp.elements):
                    if j == 0 or (j==len(node_color_ramp_node.color_ramp.elements)-1):
                        new_elem = n.color_ramp.elements[j]
                        new_elem.position = e.position
                    else:
                        new_elem = n.color_ramp.elements.new(e.position)
                    new_elem.color = (e.color[0],e.color[1],e.color[2],e.color[3])

                self_ramp_name = self_color_rman_ramps[i]
                setattr(self, self_ramp_name, n.name)


            for i, prop_name in enumerate(float_rman_ramps):
                ramp_name = getattr(node, prop_name)
                node_float_ramp_node = nt.nodes[ramp_name]                
                n = node_group.nodes.new('ShaderNodeVectorCurve') 

                curve = node_float_ramp_node.mapping.curves[0]
                points = curve.points
                new_points = n.mapping.curves[0].points
                for j,point in enumerate(points):
                    if j == 0 or (j==len(points)-1):
                        new_points[j].location[0] = point.location[0]
                        new_points[j].location[1]= point.location[1]
                    else:
                        new_points.new(point.location[0], point.location[1])

                self_ramp_name = self_float_rman_ramps[i]
                setattr(self, self_ramp_name, n.name)

    def RefreshNodes(self, context, nodeOR=None, materialOverride=None):

        # Compile shader.        If the call was from socket draw get the node
        # information anther way.
        if hasattr(context, "node"):
            node = context.node
        else:
            node = nodeOR

        out_path = string_utils.expand_string('<OUT>', asFilePath=True)
        compile_path = os.path.join(out_path, "shaders")

        if os.path.exists(compile_path):
            pass
        else:
            os.mkdir(compile_path)

        if getattr(node, "codetypeswitch") == "EXT":
            osl_path = string_utils.expand_string(getattr(node, 'shadercode'))
            osl_path = filepath_utils.get_real_path(osl_path)
            FileName = os.path.basename(osl_path)
            FileNameNoEXT = os.path.splitext(FileName)[0]
            FileNameOSO = FileNameNoEXT
            FileNameOSO += ".oso"
            export_path = os.path.join(compile_path, FileNameOSO)
            if os.path.splitext(FileName)[1] == ".oso":
                if not os.path.exists(osl_path):
                    return "OSL: %s not found" % osl_path
                else:
                    out_file = os.path.join(compile_path, FileNameOSO)
                    if not os.path.exists(out_file) or not os.path.samefile(osl_path, out_file):
                        shutil.copy(osl_path, out_file)
                    # Assume that the user knows what they were doing when they
                    # compiled the osl file.
                    ok = True
            else:
                ok = node.compile_osl(osl_path, compile_path)
        elif getattr(node, "codetypeswitch") == "INT" and node.internalSearch:
            script = bpy.data.texts[node.internalSearch]
            osl_path = bpy.path.abspath(
                script.filepath, library=script.library)
            if script.is_in_memory or script.is_dirty or \
                    script.is_modified or not os.path.exists(osl_path):
                osl_file = tempfile.NamedTemporaryFile(
                    mode='w', suffix=".osl", delete=False)
                osl_file.write(script.as_string())
                osl_file.close()
                FileNameNoEXT = os.path.splitext(script.name)[0]
                FileNameOSO = FileNameNoEXT
                FileNameOSO += ".oso"
                node.plugin_name = FileNameNoEXT
                ok = node.compile_osl(osl_file.name, compile_path, script.name)
                export_path = os.path.join(compile_path, FileNameOSO)
                os.remove(osl_file.name)
                setattr(node, 'shadercode', export_path)
            else:
                ok = node.compile_osl(osl_path, compile_path)
                FileName = os.path.basename(osl_path)
                FileNameNoEXT = os.path.splitext(FileName)[0]
                node.plugin_name = FileNameNoEXT
                FileNameOSO = FileNameNoEXT
                FileNameOSO += ".oso"
                export_path = os.path.join(compile_path, FileNameOSO)
                setattr(node, 'shadercode', export_path)
        else:
            ok = False
            rfb_log().error("OSL: Shader cannot be compiled. Shader name not specified")
            return "OSL: Shader cannot be compiled. Shader name not specified"
        # If Shader compiled successfully then update node.
        if ok:
            rfb_log().info("OSL: Shader Compiled Successfully!")
            # Read in new properties
            prop_names, shader_meta = readOSO(export_path)
            rfb_log().debug('OSL: %s MetaInfo: %s' % (str(prop_names), str(shader_meta)))
            # Set node name to shader name
            node.label = shader_meta["shader"]
            node.name = shader_meta["shader"]
            node.plugin_name = shader_meta["shader"]
            # Generate new inputs and outputs
            setattr(node, 'shader_meta', shader_meta)
            node.setOslProps(prop_names, shader_meta)
        else:
            rfb_log().error("OSL: NODE COMPILATION FAILED")
            return "OSL: NODE COMPILATION FAILED"
        
        return None

    def compile_osl(self, inFile, outPath, nameOverride=""):
        if not nameOverride:
            FileName = os.path.basename(inFile)
            FileNameNoEXT = os.path.splitext(FileName)[0]
            out_file = os.path.join(outPath, FileNameNoEXT)
            out_file += ".oso"
        else:
            FileNameNoEXT = os.path.splitext(nameOverride)[0]
            out_file = os.path.join(outPath, FileNameNoEXT)
            out_file += ".oso"
        ok = _cycles.osl_compile(inFile, out_file)

        return ok
    
    def insert_link(self, link):
        if link in RendermanShadingNode.new_links:
            pass
        else:
            RendermanShadingNode.new_links.append(link)    
    
    def accept_link(self, node_tree, link):
        from_node = link.from_node
        to_node = link.to_node
        from_socket = link.from_socket
        to_socket = link.to_socket
        from_node_type = getattr(from_node, 'renderman_node_type', None)
        to_node_type = getattr(to_node, 'renderman_node_type', None)
        if from_node_type:  
            if not shadergraph_utils.is_socket_same_type(from_socket, to_socket):
                
                if shadergraph_utils.is_socket_float_type(from_socket) and shadergraph_utils.is_socket_float3_type(to_socket):
                    # allow for float -> float3 like connections
                    return True
                elif shadergraph_utils.is_socket_float3_type(from_socket) and shadergraph_utils.is_socket_float_type(to_socket):
                    # allow for float3 -> float/int connections
                    return True
                
                return False

            # if this is a struct, check that the struct name matches
            elif from_node_type == 'struct':
                if to_node_type != 'struct':
                    return False
                if link.from_socket.struct_name != link.to_socket.struct_name:
                    return False
            return True                       

        return True
    
    def check_allowed_connections(self, node_tree, link):
        to_node = link.to_node
        from_node = link.from_node

        if to_node.bl_label not in RFB_SHADER_ALLOWED_CONNECTIONS and from_node.bl_label not in RFB_SHADER_ALLOWED_CONNECTIONS:
            return True
        
        if to_node.bl_label in RFB_SHADER_ALLOWED_CONNECTIONS:
            ac_dict = RFB_SHADER_ALLOWED_CONNECTIONS[to_node.bl_label]
            to_socket = link.to_socket
            allowed = ac_dict['inputs'].get(to_socket.name, list())
            if from_node.bl_label in allowed:
                return True
            # check if a regular parameter connection is allowed
            return to_node.accept_link(node_tree, link)

        if from_node.bl_label in RFB_SHADER_ALLOWED_CONNECTIONS:
            ac_dict = RFB_SHADER_ALLOWED_CONNECTIONS[from_node.bl_label]
            from_socket = link.from_socket
            allowed = ac_dict['outputs'].get(from_socket.name, list())
            if to_node.bl_label in allowed:
                return True
            # check if a regular parameter connection is allowed
            return from_node.accept_link(node_tree, link)
        return True

    def update(self):
        node_tree = self.id_data
        for link in RendermanShadingNode.new_links:
            if link is None:
                continue
            to_node = link.to_node
            from_node = link.from_node
            if not to_node:
                continue
            if not from_node:
                continue
            accept_link = True
            if hasattr(to_node, 'accept_link'):
                accept_link = to_node.accept_link(node_tree, link)
            accept_link = accept_link and self.check_allowed_connections(node_tree, link)
            if not accept_link:
                node_tree = self.id_data
                try:
                    node_tree.links.remove(link) 
                    bpy.ops.renderman.printer('INVOKE_DEFAULT', level="ERROR", message="Link is not valid")
                except Exception as e:
                    rfb_log().debug("Cannot remove link: %s" % str(e))
                    pass       

        do_update = False
        if RendermanShadingNode.new_links:
            do_update = True
            RendermanShadingNode.new_links.clear()

        if RendermanShadingNode.num_links != len(node_tree.links):
            do_update = True
            RendermanShadingNode.num_links = len(node_tree.links)
        
        if do_update:
            self.id_data.update_tag()

    @classmethod
    def poll(cls, ntree):
        rd = bpy.context.scene.render
        if rd.engine != 'PRMAN_RENDER':
            return False

        if hasattr(ntree, 'bl_idname'):
            return ntree.bl_idname == 'ShaderNodeTree'
        else:
            return True

    def poll_instance(cls, ntree):
        rd = bpy.context.scene.render
        if rd.engine != 'PRMAN_RENDER':
            return False

        if hasattr(ntree, 'bl_idname'):
            return ntree.bl_idname == 'ShaderNodeTree'
        else:
            return True            

    def setOslProps(self, prop_names, shader_meta):
        # save links
        links = dict()
        values = dict()
        for input_name, socket in self.inputs.items():
            if socket.is_linked:
                links[input_name] = {"from_node": socket.links[0].from_node, "from_socket": socket.links[0].from_socket}
            else:
                if isinstance(socket.default_value, bpy.types.bpy_prop_array):
                    # deecopy seems to fail on bpy_prop_array types, so manually copy
                    val = list()
                    for v in socket.default_value:
                        val.append(v)
                    values[input_name] = val
                else:
                    values[input_name] = deepcopy(socket.default_value)
        for input_name, socket in self.outputs.items():
            if socket.is_linked:
                links[input_name] = {"from_node": socket.links[0].to_node, "from_socket": socket.links[0].to_socket}

        # Reset the inputs and outputs
        self.outputs.clear()
        self.inputs.clear()

        prop_meta = getattr(self, 'prop_meta', dict())
        for prop_name in prop_names:
            prop_meta[prop_name] = shader_meta[prop_name]
            prop_type = shader_meta[prop_name]["type"]
            if shader_meta[prop_name]["IO"] == "out":
                socket = self.outputs.new(
                    __RMAN_SOCKET_MAP__[prop_type], prop_name)
                if prop_name in links and socket.hide is False:
                    link = links[prop_name]
                    self.id_data.links.new(socket, link['from_socket'])

            else:
                prop_default = shader_meta[prop_name]["default"]
                if prop_default:
                    if prop_type == "float":
                        prop_default = float(prop_default)
                    elif prop_type == "int":
                        prop_default = int(float(prop_default))
                    elif prop_type == "color":
                        # error checking on len(prop_default)
                        # we want len(prop_default) = 4
                        if len(prop_default) < 4:
                            prop_default += (4-len(prop_default)) * (1.0,)
                        elif len(prop_default) > 4:
                            prop_default = prop_default[:4]

                if prop_type == "matrix":
                    self.inputs.new(__RMAN_SOCKET_MAP__["struct"], prop_name, prop_name)
                elif prop_type == "void":
                    pass
                elif 'lockgeom' in shader_meta[prop_name] and shader_meta[prop_name]['lockgeom'] == 0:
                    pass
                else:
                    input = self.inputs.new(__RMAN_SOCKET_MAP__[shader_meta[prop_name]["type"]],
                                            prop_name, identifier=prop_name)
                    if prop_default:
                        input.default_value = prop_default
                    if prop_type == 'struct' or prop_type == 'point':
                        input.hide_value = True
                    input.renderman_type = prop_type
                    if prop_name in links and input.hide is False:
                        link = links[prop_name]
                        self.id_data.links.new(link['from_socket'], input)
                    elif prop_name in values:
                        input.default_value = values.get(prop_name, input.default_value)

        rfb_log().debug("Shader: %s", shader_meta["shader"])
        rfb_log().debug("Properties: %s" % str(prop_names))
        rfb_log().debug("Shader meta data: %s" % str(shader_meta))
        self.prop_meta = prop_meta

class RendermanOutputNode(RendermanShadingNode):
    bl_label = 'RenderMan Material'
    renderman_node_type = 'output'
    bl_icon = 'MATERIAL'
    node_tree = None

    def update_solo_node_name(self, context):
        rr = rman_render.RmanRender.get_rman_render()        
        mat = getattr(bpy.context, 'material', None)
        if mat:
            rr.rman_scene_sync.update_material(mat)       

    def filter_method_items(self, context):
        items=[
            ('STICKY', 'Sticky', 'Show only parameters that are marked as sticky.'),
            ("MATCH", 'Match', "Show only parameters that match a search string.")
        ]
        return items

    def mactch_on_items(self, context):
        items=[
            ('PARAM_NAME', 'Param Name', "Match on the parameter name"),
            ("PARAM_LABEL", 'Param Label', "Match on the parameter label"),
            ("NODE_NAME", "Node Name", "Match the node name"),
            ("NODE_TYPE", "Node Type", "Match the node type (ex: PxrDirt)"),
            ("NODE_LABEL", "Node Label", "Match the node label")
        ]       
        return items 


    solo_node_name: StringProperty(name='Solo Node', update=update_solo_node_name)
    solo_node_output: StringProperty(name='Solo Node Output')
    solo_nodetree: PointerProperty(type=bpy.types.NodeTree)


    bxdf_filter_method: EnumProperty(name="Filter Method",
                                items=filter_method_items
                                )
    bxdf_filter_parameters: BoolProperty(name="Filter Parameters", default=False)
    bxdf_match_expression: StringProperty(name="Search", default="")
    bxdf_match_on: EnumProperty(name="Match On",
                                items=mactch_on_items
                                )    

    disp_filter_method: EnumProperty(name="Filter Method",
                                items=filter_method_items
                                )
    disp_filter_parameters: BoolProperty(name="Filter Parameters", default=False)
    disp_match_expression: StringProperty(name="Search", default="")
    disp_match_on: EnumProperty(name="Match On",
                                items=mactch_on_items
                                )        

    light_filter_method: EnumProperty(name="Filter Method",
                                items=filter_method_items
                                )
    light_filter_parameters: BoolProperty(name="Filter Parameters", default=False)
    light_match_expression: StringProperty(name="Search", default="")    
    light_match_on: EnumProperty(name="Match On",
                                items=mactch_on_items
                                )            

    def is_sticky_selected(self):
        if (self.bxdf_filter_parameters == False and 
            self.disp_filter_parameters  == False and 
            self.light_filter_parameters == False):
            return False
        return (self.bxdf_filter_method == 'STICKY' or 
                self.disp_filter_method == 'STICKY' or
                self.light_filter_method == 'STICKY'
        ) 

    def init(self, context):
        self._init_inputs()   

    def _init_inputs(self):
        input = self.inputs.new('RendermanNodeSocketBxdf', 'bxdf_in', identifier='Bxdf')
        input.hide_value = True
        input = self.inputs.new('RendermanNodeSocketLight', 'light_in', identifier='Light')
        input.hide_value = True
        input = self.inputs.new('RendermanNodeSocketDisplacement', 'displace_in', identifier='Displacement')
        input.hide_value = True
        input = self.inputs.new('RendermanNodeSocketLightFilter', 'lightfilter_in', identifier='LightFilter')
        input.hide_value = True    

    def draw_buttons(self, context, layout):
        return

    def draw_buttons_ext(self, context, layout):
        return
    
    def accept_link(self, node_tree, link):
        if not hasattr(link.from_socket, 'renderman_type'):
            return False
        if not hasattr(link.to_socket, 'renderman_type'):
            return False
        if link.from_socket.renderman_type == link.to_socket.renderman_type:
            return True
        
        # FIXME: this should removed eventually
        if link.to_socket.bl_idname == 'RendermanShaderSocket':
            return True

        return False
    
    def update(self):
        super().update()

        # check if the solo node still exists
        if self.solo_node_name:
            if self.solo_nodetree:
                solo_nodetree = self.solo_nodetree
                solo_node = solo_nodetree.nodes.get(self.solo_node_name, None)
                if solo_node is None:
                    shadergraph_utils.set_solo_node(self, solo_nodetree, '', refresh_solo=True)
                    solo_nodetree.update_tag()
                    return     
            else:
                shadergraph_utils.set_solo_node(self, None, '', refresh_solo=True)      

class RendermanIntegratorsOutputNode(RendermanShadingNode):
    bl_label = 'RenderMan Integrators'
    renderman_node_type = 'integrators_output'
    bl_icon = 'MATERIAL'
    node_tree = None

    def init(self, context):
        input = self.inputs.new('RendermanNodeSocketIntegrator', 'integrator_in', identifier='Integrator')

    def draw_buttons(self, context, layout):
        return

    def draw_buttons_ext(self, context, layout):   
        return
    
    def accept_link(self, node_tree, link):
        from_node_type = getattr(link.from_socket, 'renderman_type', None)
        if not from_node_type:
            return False            
        if from_node_type != 'integrator':
            return False
        
        return True

    def update(self):
        super().update()        
        world = getattr(bpy.context, 'world', None)
        if world:
            world.update_tag()        

class RendermanSamplefiltersOutputNode(RendermanShadingNode):
    bl_label = 'RenderMan Sample Filters'
    renderman_node_type = 'samplefilters_output'
    bl_icon = 'MATERIAL'
    node_tree = None
    new_links = []

    def init(self, context):
        input = self.inputs.new('RendermanNodeSocketSampleFilter', 'samplefilter_in[0]', identifier='samplefilter[0]')
        input.hide_value = True

    def add_input(self):
        size = len(self.inputs)
        input = self.inputs.new('RendermanNodeSocketSampleFilter', 'samplefilter_in[%d]' % size, identifier='samplefilter[%d]' % size)
        input.hide_value = True

    def remove_input(self):
        socket = self.inputs[len(self.inputs)-1]
        if socket.is_linked:
            old_node = socket.links[0].from_node
            node_tree = self.id_data
            node_tree.nodes.remove(old_node)
        self.inputs.remove( socket )

    def remove_input_index(self, socket):
        self.inputs.remove( socket )   
        for i,socket in enumerate(self.inputs):
            socket.name = 'samplefilter[%d]' % i
                 

    def draw_buttons(self, context, layout):
        row = layout.row(align=True)
        col = row.column()
        col.operator('node.rman_add_samplefilter_node_socket', text='Add')
        return

    def draw_buttons_ext(self, context, layout):
        row = layout.row(align=True)
        col = row.column()
        col.operator('node.rman_add_samplefilter_node_socket', text='Add')    
        return

    def accept_link(self, node_tree, link):
        from_node_type = getattr(link.from_socket, 'renderman_type', None)
        if not from_node_type:
            return False            
        if from_node_type != 'samplefilter':
            return False
        
        return True

    def update(self):
        super().update()        
        world = getattr(bpy.context, 'world', None)
        if world:
            world.update_tag()     

class RendermanDisplayfiltersOutputNode(RendermanShadingNode):
    bl_label = 'RenderMan Display Filters'
    renderman_node_type = 'displayfilters_output'
    bl_icon = 'MATERIAL'
    node_tree = None
    def init(self, context):
        input = self.inputs.new('RendermanNodeSocketDisplayFilter', 'displayfilter_in[0]', identifier='displayflter[0]')
        input.hide_value = True

    def add_input(self):
        size = len(self.inputs)
        input = self.inputs.new('RendermanNodeSocketDisplayFilter', 'displayfilter_in[%d]' % size, identifier='displayfilter[%d]' % size)
        input.hide_value = True

    def remove_input(self):
        socket = self.inputs[len(self.inputs)-1]
        if socket.is_linked:
            old_node = socket.links[0].from_node
            node_tree = self.id_data
            node_tree.nodes.remove(old_node)
        self.inputs.remove( socket ) 

    def remove_input_index(self, socket):
        self.inputs.remove( socket )  
        for i,socket in enumerate(self.inputs):
            socket.name = 'displayfilter[%d]' % i                            

    def draw_buttons(self, context, layout):
        row = layout.row(align=True)
        col = row.column()
        col.operator('node.rman_add_displayfilter_node_socket', text='Add')    
        return

    def draw_buttons_ext(self, context, layout):
        row = layout.row(align=True)
        col = row.column()
        col.operator('node.rman_add_displayfilter_node_socket', text='Add')
        return

    def update(self):
        super().update()
        world = getattr(bpy.context, 'world', None)
        if world:
            world.update_tag()        

    def accept_link(self, node_tree, link):
        from_node_type = getattr(link.from_socket, 'renderman_type', None)
        if not from_node_type:
            return False
        if from_node_type != 'displayfilter':
            return False
        
        return True

class RendermanProjectionsOutputNode(RendermanShadingNode):
    bl_label = 'RenderMan Projections'
    renderman_node_type = 'projections_output'
    bl_icon = 'MATERIAL'
    node_tree = None
    new_links = []

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'ShaderNodeTree'
        
    def init(self, context):
        input = self.inputs.new('RendermanNodeSocketProjection', 'projection_in', identifier='Projection')

    def draw_buttons(self, context, layout):
        return

    def draw_buttons_ext(self, context, layout):   
        return
    
    def accept_link(self, node_tree, link):
        from_node_type = getattr(link.from_socket, 'renderman_type', None)
        if not from_node_type:
            return False            
        if from_node_type != 'projection':
            return False
        
        return True

    def update(self):
        super().update()        
        cam = getattr(bpy.context, 'active_object', None)
        if cam:
            cam.update_tag(refresh={'DATA'})            

class RendermanBxdfNode(RendermanShadingNode):
    bl_label = 'Bxdf'
    renderman_node_type = 'bxdf'

class RendermanDisplacementNode(RendermanShadingNode):
    bl_label = 'Displacement'
    renderman_node_type = 'displace'

class RendermanPatternNode(RendermanShadingNode):
    bl_label = 'Texture'
    renderman_node_type = 'pattern'
    bl_type = 'CUSTOM'
    bl_static_type = 'CUSTOM'
    node_tree = None

    def accept_link(self, node_tree, link):
        return super().accept_link(node_tree, link)

class RendermanLightNode(RendermanShadingNode):
    bl_label = 'Light'
    renderman_node_type = 'light'

class RendermanLightfilterNode(RendermanShadingNode):
    bl_label = 'LightFilter'
    renderman_node_type = 'lightfilter'

class RendermanDisplayfilterNode(RendermanShadingNode):
    bl_label = 'DisplayFilter'
    renderman_node_type = 'displayfilter'

class RendermanSamplefilterNode(RendermanShadingNode):
    bl_label = 'SampleFilter'
    renderman_node_type = 'samplefilter'    

class RendermanIntegratorNode(RendermanShadingNode):
    bl_label = 'Integrator'
    renderman_node_type = 'integrator'

class RendermanProjectionNode(RendermanShadingNode):
    bl_label = 'Projection'
    renderman_node_type = 'projection'   

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'ShaderNodeTree'     

classes = [
    RendermanShadingNode,
    RendermanOutputNode,
    RendermanBxdfNode,
    RendermanDisplacementNode,
    RendermanPatternNode,
    RendermanLightNode,
    RendermanLightfilterNode,
    RendermanDisplayfilterNode,
    RendermanSamplefilterNode,
    RendermanSamplefiltersOutputNode,
    RendermanDisplayfiltersOutputNode,
    RendermanIntegratorsOutputNode,
    RendermanProjectionsOutputNode,
    RendermanIntegratorNode,
    RendermanProjectionNode
]

def register():
    from ..rfb_utils import register_utils

    register_utils.rman_register_classes(classes)   

    

def unregister():
    from ..rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes)