from ..rfb_logger import rfb_log
from . import shadergraph_utils
from . import prefs_utils
from .property_utils import BlPropInfo, __LOBES_ENABLE_PARAMS__
from ..rman_constants import NODE_LAYOUT_SPLIT
from .. import rman_config
from .. import rfb_icons
import bpy
import re

def draw_indented_label(layout, label, level):
    for i in range(level):
        layout.label(text='', icon='BLANK1')
    if label:
        layout.label(text=label)

def get_open_close_icon(is_open=True):
    icon = 'DISCLOSURE_TRI_DOWN' if is_open \
        else 'DISCLOSURE_TRI_RIGHT'
    return icon

def draw_sticky_toggle(layout, node, prop_name, output_node=None):
    if not output_node:
        return
    if output_node.solo_node_name != '':
        return
    if not output_node.is_sticky_selected():
        return
    sticky_prop = '%s_sticky' % prop_name
    if hasattr(node, sticky_prop):    
        sticky_icon = 'HIDE_ON'
        if getattr(node, sticky_prop):
            sticky_icon = 'HIDE_OFF'                
        layout.prop(node, sticky_prop, text='', icon=sticky_icon, icon_only=True, emboss=False)  

def draw_dsypmeta_item(layout, node, prop_name):
    layout.label(text='Meta Data')
    row = layout.row()    
    prop_index_nm = '%s_index' % prop_name        
    row.template_list("RENDERMAN_UL_Dspy_MetaData_List", "Meta Data",
                        node, prop_name, node, prop_index_nm)
    col = row.column(align=True)
    row.context_pointer_set("node", node)
    op = col.operator('renderman.add_remove_dspymeta', icon="ADD", text="")
    op.collection = prop_name
    op.collection_index = prop_index_nm
    op.defaultname = 'key'
    op.action = 'ADD'

    col.context_pointer_set("node", node)
    op = col.operator('renderman.add_remove_dspymeta', icon="REMOVE", text="")
    op.collection = prop_name
    op.collection_index = prop_index_nm
    op.action = 'REMOVE'   

    prop_index = getattr(node, prop_index_nm, None)
    if prop_index_nm is None:
        return

    prop = getattr(node, prop_name)
    if prop_index > -1 and prop_index < len(prop):
        item = prop[prop_index]
        layout.prop(item, 'name')
        layout.prop(item, 'type')
        layout.prop(item, 'value_%s' % item.type, slider=True)

def draw_array_elem(layout, node, prop_name, bl_prop_info, nt, context, level, single_node_view=True):
    row = layout.row(align=True)
    row.enabled = not bl_prop_info.prop_disabled

    ui_prop = prop_name + "_uio"
    ui_open = getattr(node, ui_prop)
    icon = get_open_close_icon(ui_open)

    split = layout.split(factor=NODE_LAYOUT_SPLIT)
    row = split.row()
    row.enabled = not bl_prop_info.prop_disabled
    draw_indented_label(row, None, level)

    row.context_pointer_set("node", node)
    op = row.operator('node.rman_open_close_page', text='', icon=icon, emboss=False)            
    op.prop_name = ui_prop

    sub_prop_names = list(bl_prop_info.prop)

    prop_label = bl_prop_info.label
    coll_nm = '%s_collection' % prop_name
    collection = getattr(node, coll_nm)
    array_len = len(collection)
    array_label = prop_label + ' [%d]:' % array_len
    row.label(text=array_label)
    if ui_open:
        level += 1
        row = layout.row(align=True)
        col = row.column()
        row = col.row()
        draw_indented_label(row, None, level)           
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
            if socket and socket.is_linked:
                input_node = shadergraph_utils.socket_node_input(nt, socket)
                do_single_view = single_node_view and prefs_utils.single_node_view()
                if do_single_view:

                    icon = get_open_close_icon(False)
                    split = layout.split()
                    row = split.row()
                    draw_indented_label(row, None, level)  
                    row.label(text='Value (%s):' % input_node.name)
                    
                    row.context_pointer_set("node", input_node)
                    row.context_pointer_set("nodetree", nt)                                
                    row.operator('node.rman_select_nodetree_node', text='', icon=icon)                
                    rman_icon = rfb_icons.get_node_icon(input_node.bl_label)               


                    row.context_pointer_set("socket", socket)
                    row.context_pointer_set("node", node)
                    row.context_pointer_set("nodetree", nt)
                    row.menu('NODE_MT_renderman_connection_menu', text='', icon_value=rman_icon.icon_id)
                                            
                else:
                    icon = get_open_close_icon(socket.ui_open)
                    split = layout.split()
                    row = split.row()
                    draw_indented_label(row, None, level)
                    row.context_pointer_set("socket", socket)               
                    row.operator('node.rman_open_close_link', text='', icon=icon, emboss=False)                
                    rman_icon = rfb_icons.get_node_icon(input_node.bl_label)               
                    row.label(text='Value (%s):' % input_node.name)

                    row.context_pointer_set("socket", socket)
                    row.context_pointer_set("node", node)
                    row.context_pointer_set("nodetree", nt)
                    row.menu('NODE_MT_renderman_connection_menu', text='', icon_value=rman_icon.icon_id)
                                            
                    if socket.ui_open:
                        draw_node_properties_recursive(layout, context, nt,
                                                        input_node, level=level + 1)

                return 

            row.prop(item, 'value_%s' % item.type, slider=True)
            if socket:                
                row.context_pointer_set("socket", socket)
                row.context_pointer_set("node", node)
                row.context_pointer_set("nodetree", nt)
                rman_icon = rfb_icons.get_icon('rman_connection_menu')
                row.menu('NODE_MT_renderman_connection_menu', text='', icon_value=rman_icon.icon_id)            

def _draw_ui_from_rman_config(config_name, panel, context, layout, parent):
    row_dict = dict()
    row = layout.row(align=True)
    col = row.column(align=True)
    row_dict['default'] = col
    rmcfg = rman_config.__RMAN_CONFIG__.get(config_name, None)
    is_rman_interactive_running = context.scene.renderman.is_rman_interactive_running
    is_rman_running = context.scene.renderman.is_rman_running

    curr_col = col
    for param_name, ndp in rmcfg.params.items():

        if ndp.panel == panel:
            if not hasattr(parent, ndp.name):
                continue
            
            has_page = False
            page_prop = ''
            page_open = False
            page_name = ''
            ipr_editable = getattr(ndp, 'ipr_editable', False)
            is_enabled = True
            if hasattr(ndp, 'page') and ndp.page != '':       
                page_prop = ndp.page + "_uio"
                page_open = getattr(parent, page_prop, False)        
                page_name = ndp.page       
                has_page = True

            if has_page:
                # check if we've already drawn page with arrow
                if page_name not in row_dict:

                    row = layout.row(align=True)
                    icon = get_open_close_icon(page_open)
                    row.context_pointer_set("node", parent)               
                    op = row.operator('node.rman_open_close_page', text='', icon=icon, emboss=False) 
                    op.prop_name = page_prop
           
                    row.label(text=page_name)
                    
                    row = layout.row(align=True)
                    col = row.column()

                    row_dict[page_name] = col
                    curr_col = col
                else:
                    curr_col = row_dict[page_name]
            else:
                curr_col = row_dict['default']

            conditionalVisOps = getattr(ndp, 'conditionalVisOps', None)
            conditionalLockOps = getattr(ndp, 'conditionalLockOps', None)
            if conditionalVisOps:
                # eval the conditionalVisOps to see if we should be visible
                expr = conditionalVisOps.get('expr', None)
                node = parent              
                if expr and not eval(expr):
                    continue

            if conditionalVisOps and conditionalLockOps:
                # check if there is a conditionalLockOps
                expr = conditionalVisOps.get('lock_expr', None)
                if expr is None:
                    expr = conditionalVisOps.get('expr', None)
                node = parent                           
                if expr and not eval(expr):
                    is_enabled = False                        

            label = ndp.label if hasattr(ndp, 'label') else ndp.name
            row = curr_col.row()
            widget = getattr(ndp, 'widget', '')
            options = getattr(ndp, 'options', None)
            if ndp.is_array():
                if has_page:           
                    if not page_open:
                        continue      
                    row.label(text='', icon='BLANK1')          
                ui_prop = param_name + "_uio"
                ui_open = getattr(parent, ui_prop)
                icon = get_open_close_icon(ui_open)
                row.context_pointer_set("node", parent)               
                op = row.operator('node.rman_open_close_page', text='', icon=icon, emboss=False)  
                op.prop_name = ui_prop

                prop = getattr(parent, param_name)      
                prop_meta = node.prop_meta[param_name]                      
                sub_prop_names = list(prop)
                arraylen_nm = '%s_arraylen' % param_name
                arraylen = getattr(parent, arraylen_nm)
                prop_label = prop_meta.get('label', param_name)
                row.label(text=prop_label + ' [%d]:' % arraylen)
                if ui_open:
                    row2 = curr_col.row()
                    col = row2.column()
                    row3 = col.row()      
                    row3.label(text='', icon='BLANK1')                  
                    row3.prop(parent, arraylen_nm, text='Size')
                    for i in range(0, arraylen):
                        row4 = col.row()
                        row4.label(text='', icon='BLANK1')
                        row4.label(text='%s[%d]' % (prop_label, i))
                        row4.prop(parent, '%s[%d]' % (param_name, i), text='')                

                
            elif widget == 'propSearch' and options:
                # use a prop_search layout
                prop_search_parent = options.get('prop_parent')
                prop_search_name = options.get('prop_name')
                if has_page:
                    row.label(text='', icon='BLANK1')
                eval(f'row.prop_search(parent, ndp.name, {prop_search_parent}, "{prop_search_name}", text=label)')               
            else:    
                if has_page:           
                    if not page_open:
                        continue
                    row.label(text='', icon='BLANK1')
                row.prop(parent, ndp.name, text=label)         

            if is_rman_interactive_running:
                row.enabled = ipr_editable
            elif is_rman_running:
                row.enabled = False
            else:
                row.enabled = is_enabled

def draw_prop(node, prop_name, layout, level=0, nt=None, context=None, sticky=False, single_node_view=True):
    prop_meta = node.prop_meta[prop_name]
    bl_prop_info = BlPropInfo(node, prop_name, prop_meta)
    if bl_prop_info.prop is None:
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

    if bl_prop_info.conditionalLockOps and bl_prop_info.lock_expr:
        try:
            locked = not eval(bl_prop_info.lock_expr)
            bl_prop_info.prop_disabled = locked
        except Exception as err:                        
            rfb_log().error("Error handling conditionalVisOp: %s" % str(err))
            pass        

    if bl_prop_info.prop_hidden:
        return

    # links
    layout.context_pointer_set("socket", bl_prop_info.socket)
    if bl_prop_info.is_linked:
        input_node = shadergraph_utils.socket_node_input(nt, bl_prop_info.socket)
        do_single_view = single_node_view and prefs_utils.single_node_view()
        if do_single_view:
            icon = get_open_close_icon(False)

            split = layout.split()
            row = split.row()
            draw_indented_label(row, None, level)                         
            label = prop_meta.get('label', prop_name)
            
            rman_icon = rfb_icons.get_node_icon(input_node.bl_label)               
            row.label(text=label + ' (%s):' % input_node.name)
            if sticky:
                return

            row.context_pointer_set("node", input_node)
            row.context_pointer_set("nodetree", nt)        
            row.operator('node.rman_select_nodetree_node', text='', icon=icon)
            row.context_pointer_set("socket", bl_prop_info.socket)
            row.context_pointer_set("node", node)
            row.context_pointer_set("nodetree", nt)
            row.menu('NODE_MT_renderman_connection_menu', text='', icon_value=rman_icon.icon_id)            
        else:
            icon = get_open_close_icon(bl_prop_info.socket.ui_open)

            split = layout.split()
            row = split.row()
            draw_indented_label(row, None, level)
            row.context_pointer_set("socket", bl_prop_info.socket)               
            
            row.operator('node.rman_open_close_link', text='', icon=icon, emboss=False)
            
            label = prop_meta.get('label', prop_name)
            
            rman_icon = rfb_icons.get_node_icon(input_node.bl_label)               
            row.label(text=label + ' (%s):' % input_node.name)
            if sticky:
                return

            row.context_pointer_set("socket", bl_prop_info.socket)
            row.context_pointer_set("node", node)
            row.context_pointer_set("nodetree", nt)
            row.menu('NODE_MT_renderman_connection_menu', text='', icon_value=rman_icon.icon_id)
                                    
            if bl_prop_info.socket.ui_open:
                draw_node_properties_recursive(layout, context, nt,
                                                input_node, level=level + 1, single_node_view=single_node_view)
        return

    elif bl_prop_info.renderman_type == 'page':
        row = layout.row(align=True)
        row.enabled = not bl_prop_info.prop_disabled
        ui_prop = prop_name + "_uio"
        ui_open = getattr(node, ui_prop)
        icon = get_open_close_icon(ui_open)

        split = layout.split(factor=NODE_LAYOUT_SPLIT)
        row = split.row()
        row.enabled = not bl_prop_info.prop_disabled
        draw_indented_label(row, None, level)

        row.context_pointer_set("node", node)               
        op = row.operator('node.rman_open_close_page', text='', icon=icon, emboss=False)            
        op.prop_name = ui_prop

        # sub_prop_names are all of the property names
        # that are under this page
        sub_prop_names = list(bl_prop_info.prop)
        if shadergraph_utils.has_lobe_enable_props(node):
            # remove the enable lobe param from sub_prop_names
            # we already draw these next to open/close page arrow below, just
            # before we recursively call draw_props
            for pn in sub_prop_names:
                if pn in __LOBES_ENABLE_PARAMS__:
                    row.prop(node, pn, text='')
                    sub_prop_names.remove(pn)
                    break

        page_label = bl_prop_info.label
        row.label(text=page_label)

        if ui_open:
            draw_props(node, sub_prop_names, layout, level=level + 1, nt=nt, context=context, draw_ui_structs=False, single_node_view=single_node_view)
        return

    elif bl_prop_info.renderman_type == 'array':
        draw_array_elem(layout, node, prop_name, bl_prop_info, nt, context, level, single_node_view=single_node_view)
        return

    elif bl_prop_info.widget == 'colorramp':
        node_group = node.rman_fake_node_group_ptr 
        if not node_group:
            row = layout.row(align=True)
            row.context_pointer_set("node", node)
            row.operator('node.rman_fix_ramp') 
            row.operator('node.rman_fix_all_ramps')
            return

        ramp_name =  bl_prop_info.prop
        ramp_node = node_group.nodes[ramp_name]
        layout.enabled = (nt.library is None)
        layout.template_color_ramp(
                ramp_node, 'color_ramp')               
        return       
    elif bl_prop_info.widget == 'floatramp':
        node_group = node.rman_fake_node_group_ptr 
        if not node_group:
            row = layout.row(align=True)
            row.context_pointer_set("node", node)
            row.operator('node.rman_fix_ramp')
            
        ramp_name =  bl_prop_info.prop
        ramp_node = node_group.nodes[ramp_name]
        layout.enabled = (nt.library is None)
        layout.template_curve_mapping(
                ramp_node, 'mapping') 
        
        interp_name = '%s_Interpolation' % prop_name
        if hasattr(node, interp_name):
            layout.prop(node, interp_name, text='Ramp Interpolation')
        return     

    elif bl_prop_info.widget == 'displaymetadata':
        draw_dsypmeta_item(layout, node, prop_name) 
        return                            
    
    row = layout.row(align=True)
    row.enabled = not bl_prop_info.prop_disabled                  
    draw_indented_label(row, None, level)
    
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
    elif bl_prop_info.renderman_type in ['struct', 'bxdf', 'vstruct']:
        row.label(text=bl_prop_info.label)
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
    else:
        row.prop(node, prop_name, slider=True)

    if bl_prop_info.has_input:
        row.context_pointer_set("socket", bl_prop_info.socket)
        row.context_pointer_set("node", node)
        row.context_pointer_set("nodetree", nt)
        rman_icon = rfb_icons.get_icon('rman_connection_menu')
        row.menu('NODE_MT_renderman_connection_menu', text='', icon_value=rman_icon.icon_id)

    if bl_prop_info.is_texture:
        prop_val = getattr(node, prop_name)
        if prop_val != '':
            from . import texture_utils
            from . import scene_utils
            if texture_utils.get_txmanager().is_file_src_tex(node, prop_name):
                return            
            colorspace_prop_name = '%s_colorspace' % prop_name
            if not hasattr(node, colorspace_prop_name):
                return
            row = layout.row(align=True)
            if texture_utils.get_txmanager().does_file_exist(prop_val):
                row.enabled = not bl_prop_info.prop_disabled
                draw_indented_label(row, None, level)
                row.prop(node, colorspace_prop_name, text='Color Space')
                rman_icon = rfb_icons.get_icon('rman_txmanager')
                id = scene_utils.find_node_owner(node)
                nodeID = texture_utils.generate_node_id(node, prop_name, ob=id)
                op = row.operator('rman_txmgr_list.open_txmanager', text='', icon_value=rman_icon.icon_id)  
                op.nodeID = nodeID     
            else:
                draw_indented_label(row, None, level)
                row.label(text="Input mage does not exists.", icon='ERROR')   
                   

def draw_ui_struct(layout, node, prop_name, bl_prop_info, nt, context, level):
    row = layout.row(align=True)
    row.enabled = not bl_prop_info.prop_disabled

    ui_prop = prop_name + "_uio"
    ui_open = getattr(node, ui_prop)
    icon = get_open_close_icon(ui_open)

    split = layout.split(factor=NODE_LAYOUT_SPLIT)
    row = split.row()
    row.enabled = not bl_prop_info.prop_disabled
    draw_indented_label(row, None, level)

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
        draw_indented_label(row, None, level+1)
        row.prop(node, arraylen_nm, text=bl_prop_info.label)
        ui_structs = getattr(node, 'ui_structs', dict())
        ui_struct_members = ui_structs.get(prop_name)
        for i in range(arraylen):
            row = layout.row(align=True)
            draw_indented_label(row, prop_label + ' [%d]:' % i, level)
            for nm in ui_struct_members:
                prop_name = '%s[%d]' % (nm, i)
                draw_prop(node, prop_name, layout, level=level+1, nt=nt, context=context)
                
def draw_props(node, prop_names, layout, level=0, nt=None, context=None, draw_ui_structs=True, single_node_view=True):
    layout.context_pointer_set("node", node)
    if nt:
        layout.context_pointer_set("nodetree", nt)

    ui_structs = getattr(node, 'ui_structs', dict())
    ui_struct_members = []

    if ui_structs:
        for prop_name,v in node.ui_structs.items():
            prop_meta = node.prop_meta[prop_name]
            bl_prop_info = BlPropInfo(node, prop_name, prop_meta)
            if draw_ui_structs:
                draw_ui_struct(layout, node, prop_name, bl_prop_info, nt, context, level)
            ui_struct_members += v
            pass 

    for prop_name in prop_names:
        if prop_name in ui_structs:
            continue
        if prop_name in ui_struct_members:
            continue
        draw_prop(node, prop_name, layout, level=level, nt=nt, context=context, single_node_view=single_node_view)

def panel_node_draw(layout, context, id_data, output_type, input_name):
    ntree = id_data.node_tree

    node = shadergraph_utils.find_node(id_data, output_type)
    if not node:
        layout.label(text="No output node")
    else:
        input =  shadergraph_utils.find_node_input(node, input_name)
        draw_nodes_properties_ui(layout, context, ntree)

    return True

def draw_nodes_properties_ui(layout, context, nt, input_name='bxdf_in',
                             output_node_type="output",
                             single_node_view=True):
    output_node = next((n for n in nt.nodes
                        if hasattr(n, 'renderman_node_type') and n.renderman_node_type == output_node_type), None)
    if output_node is None:
        return

    socket = output_node.inputs[input_name]
    node = shadergraph_utils.socket_node_input(nt, socket)

    layout.context_pointer_set("nodetree", nt)
    layout.context_pointer_set("node", output_node)
    layout.context_pointer_set("socket", socket)

    if input_name not in ['light_in', 'lightfilter_in']:
        split = layout.split(factor=0.35)
        split.label(text=socket.identifier + ':')

        do_single_view = single_node_view and prefs_utils.single_node_view()
        if do_single_view:
            split.context_pointer_set("socket", socket)
            split.context_pointer_set("node", output_node)
            split.context_pointer_set("nodetree", nt)                 
            if input_name in ['integrator_in']:
                if socket.is_linked:
                    rman_icon = rfb_icons.get_node_icon(node.bl_label)            
                    split.menu('NODE_MT_renderman_connection_menu', text='%s (%s)' % (node.name, node.bl_label), icon_value=rman_icon.icon_id)
                else:
                    split.menu('NODE_MT_renderman_connection_menu', text='None', icon='NODE_MATERIAL')
            else:
                if socket.is_linked:
                    rman_icon = rfb_icons.get_node_icon(node.bl_label)            
                    split.label(text='%s (%s)' % (node.name, node.bl_label), icon_value=rman_icon.icon_id)
                else:
                    split.menu('NODE_MT_renderman_connection_menu', text='None', icon='NODE_MATERIAL')   

            layout.separator()                     

            if node is not None:
                selected_node = None
                for n in nt.nodes:
                    if n.select:
                        selected_node = n
                        break

                if selected_node and shadergraph_utils.check_if_connected(selected_node, node):
                    
                    row = layout.row()
                    rman_icon = rfb_icons.get_node_icon(selected_node.bl_label)
                    row.label(text="%s (%s)" % (selected_node.name, selected_node.bl_label), icon_value=rman_icon.icon_id)
                    split = layout.split(factor=0.0)
                    row = split.row()
                    col = row.column()
                    col.context_pointer_set("node", selected_node)
                    col.context_pointer_set("nodetree", nt)            
                    col.menu("PRMAN_MT_Select_Nodetree_Downstream", text="", icon="TRIA_LEFT")
                    
                    col = row.column()
                    col.context_pointer_set("node", node)
                    col.context_pointer_set("nodetree", nt)            
                    col.operator("node.rman_select_nodetree_reset", icon="HOME")

                    col = row.column()
                    col.context_pointer_set("node", selected_node)
                    col.context_pointer_set("nodetree", nt)            
                    col.menu("PRMAN_MT_Select_Nodetree_Upstream", text="", icon="TRIA_RIGHT")
                    layout.separator()  

                    node = selected_node

        else:        
            split.context_pointer_set("socket", socket)
            split.context_pointer_set("node", output_node)
            split.context_pointer_set("nodetree", nt)            
            if socket.is_linked:
                rman_icon = rfb_icons.get_node_icon(node.bl_label)            
                split.menu('NODE_MT_renderman_connection_menu', text='%s (%s)' % (node.name, node.bl_label), icon_value=rman_icon.icon_id)
            else:
                split.menu('NODE_MT_renderman_connection_menu', text='None', icon='NODE_MATERIAL')                           
            layout.separator()                     

    if node is not None:
        draw_node_properties_recursive(layout, context, nt, node)

def show_node_sticky_params(layout, node, prop_names, context, nt, output_node, node_label_drawn=False):
    label_drawn = node_label_drawn
    ui_structs = getattr(node, 'ui_structs', dict())
    for prop_name in prop_names:
        prop_meta = node.prop_meta[prop_name]
        bl_prop_info = BlPropInfo(node, prop_name, prop_meta)
        renderman_type = prop_meta.get('renderman_type', '')
        if renderman_type == 'page':
            prop = getattr(node, prop_name)
            sub_prop_names = list(prop)
            label_drawn = show_node_sticky_params(layout, node, sub_prop_names, context, nt, output_node, label_drawn)
        else:
            sticky_prop = '%s_sticky' % prop_name
            if not getattr(node, sticky_prop, False):
                continue
            row = layout.row(align=True)
            if not label_drawn:
                row = layout.row(align=True)
                rman_icon = rfb_icons.get_node_icon(node.bl_label)
                row.label(text='%s (%s)' % (node.name, node.bl_label), icon_value=rman_icon.icon_id)
                label_drawn = True
                row = layout.row(align=True)
            inputs = getattr(node, 'inputs', dict())
            socket =  inputs.get(prop_name, None)
            
            draw_sticky_toggle(row, node, prop_name, output_node)
            if prop_name in ui_structs:
                draw_ui_struct(layout, node, prop_name, bl_prop_info, nt, context, level=0)
            else:
                draw_prop(node, prop_name, row, level=1, nt=nt, context=context, sticky=True)

    return label_drawn

def show_node_match_params(layout, node, expr, match_on, prop_names, context, nt, node_label_drawn=False):
    pattern = re.compile(expr)
    if match_on in ['NODE_NAME', 'NODE_TYPE', 'NODE_LABEL']:
        haystack = node.name
        if match_on == 'NODE_TYPE':
            haystack = node.bl_label
        elif match_on == 'NODE_LABEL':
            haystack = node.label
        if not re.match(pattern, haystack):
            return node_label_drawn

    label_drawn = node_label_drawn
    for prop_name in prop_names:
        prop_meta = node.prop_meta[prop_name]
        prop_label = prop_meta.get('label', prop_name)
        renderman_type = prop_meta.get('renderman_type', '')
        if renderman_type == 'page':
            prop = getattr(node, prop_name)
            sub_prop_names = list(prop)
            label_drawn = show_node_match_params(layout, node, expr, match_on, sub_prop_names, context, nt, label_drawn)
        else:
            if match_on in ['PARAM_LABEL', 'PARAM_NAME']:
                haystack = prop_name
                if match_on == 'PARAM_LABEL':
                    haystack = prop_label
                if not re.match(pattern, haystack):
                    continue               

            row = layout.row(align=True)
            if not label_drawn:
                row = layout.row(align=True)
                rman_icon = rfb_icons.get_node_icon(node.bl_label)
                row.label(text='%s (%s)' % (node.name, node.bl_label), icon_value=rman_icon.icon_id)
                label_drawn = True
                row = layout.row(align=True)
            inputs = getattr(node, 'inputs', dict())
            socket =  inputs.get(prop_name, None)
            
            draw_prop(node, prop_name, row, level=1, nt=nt, context=context, sticky=True)
            
    return label_drawn

def draw_node_properties_recursive(layout, context, nt, node, level=0, single_node_view=True):

    # if this is a cycles node do something different
    if not hasattr(node, 'plugin_name') or node.bl_idname == 'PxrOSLPatternNode':
        node.draw_buttons(context, layout)
        for input in node.inputs:
            if input.is_linked:
                input_node = shadergraph_utils.socket_node_input(nt, input)
                do_single_view = single_node_view and prefs_utils.single_node_view()
                if do_single_view:                
                    icon = get_open_close_icon(False)

                    split = layout.split()
                    row = split.row()
                    draw_indented_label(row, None, level)                         
                    label = input.name
                    
                    rman_icon = rfb_icons.get_node_icon(input_node.bl_label)               
                    row.label(text=label + ' (%s):' % input_node.name)

                    row.context_pointer_set("node", input_node)
                    row.context_pointer_set("nodetree", nt)        
                    row.operator('node.rman_select_nodetree_node', text='', icon=icon)                
                    row.context_pointer_set("socket", input)
                    row.context_pointer_set("node", node)
                    row.context_pointer_set("nodetree", nt)
                    row.menu('NODE_MT_renderman_connection_menu', text='', icon_value=rman_icon.icon_id)                  
                else:
                    icon = get_open_close_icon(input.show_expanded)

                    split = layout.split(factor=NODE_LAYOUT_SPLIT)
                    row = split.row()
                    draw_indented_label(row, None, level)

                    label = input.name                
                    rman_icon = rfb_icons.get_node_icon(input_node.bl_label)
                    row.prop(input, "show_expanded", icon=icon, text='',
                            icon_only=True, emboss=False)                                   
                    row.label(text=label + ' (%s):' % input_node.name)
                    row.context_pointer_set("socket", input)
                    row.context_pointer_set("node", node)
                    row.context_pointer_set("nodetree", nt)
                    row.menu('NODE_MT_renderman_connection_menu', text='', icon_value=rman_icon.icon_id)           

                    if input.show_expanded:
                        draw_node_properties_recursive(layout, context, nt,
                                                    input_node, level=level + 1, single_node_view=single_node_view)                                        
            else:
                row = layout.row(align=True)              
                draw_indented_label(row, None, level)
                # indented_label(row, socket.name+':')
                # don't draw prop for struct type
                if input.hide_value:
                    row.label(text=input.name)
                else:
                    row.prop(input, 'default_value',
                             slider=True, text=input.name)

                row.context_pointer_set("socket", input)
                row.context_pointer_set("node", node)
                row.context_pointer_set("nodetree", nt)
                rman_icon = rfb_icons.get_icon('rman_connection_menu')
                row.menu('NODE_MT_renderman_connection_menu', text='', icon_value=rman_icon.icon_id)

    else:
        draw_props(node, node.prop_names, layout, level, nt=nt, context=context, single_node_view=single_node_view)
    layout.separator()
