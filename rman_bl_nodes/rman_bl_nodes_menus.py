from ..rfb_logger import rfb_log
from ..rfb_utils.osl_utils import readOSO
from ..rfb_utils import shadergraph_utils
from ..rman_constants import RFB_FLOAT3
from .. import rman_bl_nodes
from .. import rfb_icons
from bpy.types import Menu
from bpy.props import EnumProperty, StringProperty, CollectionProperty

class NODE_MT_renderman_param_presets_menu(Menu):
    bl_label = "Parameter Presets"
    bl_idname = "NODE_MT_renderman_param_presets_menu"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None      

    def draw(self, context):
        layout = self.layout
        nt = context.nodetree
        node = context.node
        socket = context.socket

        prop_name = socket.name
        prop_meta = node.prop_meta.get(prop_name, None)
        if prop_meta:            
            if 'presets' in prop_meta:
                for k,v in prop_meta['presets'].items():
                    layout.context_pointer_set("node", node)
                    layout.context_pointer_set("nodetree", nt)
                    layout.context_pointer_set('socket', socket)
                    op = layout.operator('node.rman_preset_set_param', text=k)
                    op.prop_name = prop_name
                    op.preset_name = k

class NODE_MT_renderman_pattern_outputs_menu(Menu):
    bl_label = "Outputs"
    bl_idname = "NODE_MT_renderman_pattern_outputs_menu"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None      

    def draw(self, context):
        layout = self.layout
        nt = context.nodetree
        node = context.node
        socket = context.socket

        link = socket.links[0]
        input_node = socket.links[0].from_node
            
        dst_socket = link.from_socket
        layout.label(text='%s' % link.from_socket.name)
                
        for o in input_node.outputs:
            if link.from_socket == o:                
                continue
            if o.renderman_type in ['float', 'color', 'normal', 'vector', 'point']:
                src_socket_type = getattr(o, 'renderman_type', '')  
                if shadergraph_utils.is_socket_same_type(dst_socket, o):
                    layout.context_pointer_set("nodetree", nt)     
                    layout.context_pointer_set("dst_socket", socket)
                    layout.context_pointer_set("link", link)
                    layout.context_pointer_set("src_socket", o)
                    op = layout.operator('node.rman_change_output', text='%s (%s)' % (o.name, src_socket_type))

class NODE_MT_renderman_node_solo_output_menu(Menu):
    bl_label = "Solo Node Output"
    bl_idname = "NODE_MT_renderman_node_solo_output_menu"

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        layout = self.layout
        nt = context.nodetree   
        node = context.node 

        solo_node = nt.nodes.get(node.solo_node_name)

        for o in solo_node.outputs:
            if o.renderman_type in ['float', 'color', 'normal', 'vector', 'point']:
                layout.context_pointer_set("node", node)
                layout.context_pointer_set("nodetree", nt)     
                op = layout.operator('node.rman_set_node_solo_output', text=o.name)
                op.solo_node_output = o.name      
                op.solo_node_name = node.solo_node_name               

class NODE_MT_renderman_connection_menu(Menu):
    bl_label = "Connect New"
    bl_idname = "NODE_MT_renderman_connection_menu"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None    

    def draw_output_node_menu(self, context):
        layout = self.layout
        nt = context.nodetree
        node = context.node
        socket = context.socket

        renderman_type = getattr(socket, 'renderman_type', socket.name.lower())

        if renderman_type == 'displacement':
            for n in rman_bl_nodes.__RMAN_DISPLACE_NODES__:
                layout.context_pointer_set("node", node)
                layout.context_pointer_set("nodetree", nt)
                rman_icon = rfb_icons.get_displacement_icon(n.name)
                op = layout.operator('node.rman_shading_create_node', text=n.name, icon_value=rman_icon.icon_id)
                op.node_name = n.name    
                if n.help:
                    op.node_description = n.help                 
        elif renderman_type == 'integrator':    
            for n in rman_bl_nodes.__RMAN_INTEGRATOR_NODES__:
                layout.context_pointer_set("node", node)
                layout.context_pointer_set("nodetree", nt)
                rman_icon = rfb_icons.get_integrator_icon(n.name)
                op = layout.operator('node.rman_shading_create_node', text=n.name, icon_value=rman_icon.icon_id)
                op.node_name = n.name    
                if n.help:
                    op.node_description = n.help
        elif 'samplefilter' in renderman_type:    
            for n in rman_bl_nodes.__RMAN_SAMPLEFILTER_NODES__:
                layout.context_pointer_set("node", node)
                layout.context_pointer_set("nodetree", nt)
                rman_icon = rfb_icons.get_samplefilter_icon(n.name)
                op = layout.operator('node.rman_shading_create_node', text=n.name, icon_value=rman_icon.icon_id)
                op.node_name = n.name 
                if n.help:
                    op.node_description = n.help                
        elif 'displayfilter' in renderman_type:    
            for n in rman_bl_nodes.__RMAN_DISPLAYFILTER_NODES__:
                layout.context_pointer_set("node", node)
                layout.context_pointer_set("nodetree", nt)
                rman_icon = rfb_icons.get_displayfilter_icon(n.name)
                op = layout.operator('node.rman_shading_create_node', text=n.name, icon_value=rman_icon.icon_id)
                op.node_name = n.name       
                if n.help:
                    op.node_description = n.help                  
        elif 'projection' in renderman_type:    
            for n in rman_bl_nodes.__RMAN_PROJECTION_NODES__:
                layout.context_pointer_set("node", node)
                layout.context_pointer_set("nodetree", nt)
                rman_icon = rfb_icons.get_samplefilter_icon(n.name)
                op = layout.operator('node.rman_shading_create_node', text=n.name, icon_value=rman_icon.icon_id)
                op.node_name = n.name  
                if n.help:
                    op.node_description = n.help                                                                                                          
        elif renderman_type == 'bxdf':    
            for bxdf_cat, bxdfs in rman_bl_nodes.__RMAN_NODE_CATEGORIES__['bxdf'].items():
                if not bxdfs[1]:
                    continue
                tokens = bxdf_cat.split('_')
                if len(tokens) > 2:
                    # this should be a subcategory/submenu
                    continue                
                bxdf_category = ' '.join(tokens[1:])

                layout.context_pointer_set("node", node)
                layout.context_pointer_set("nodetree", nt)
                layout.context_pointer_set('socket', socket)
                layout.menu('NODE_MT_renderman_connection_submenu_%s' % bxdf_cat, text=bxdf_category.capitalize())    

        layout.separator()
        layout.label(text='__EXISTING__')
        for n in nt.nodes:
            if socket.is_linked and socket.links[0].from_node == n:
                continue
            if n == node:
                continue            
            for output in n.outputs:
                output_renderman_type = getattr(output, 'renderman_type', output.name.lower())
                if output_renderman_type == renderman_type:
                    op = layout.operator('node.rman_shading_connect_existing_node', text='_%s_' % n.name)
                    op.node_name = n.name       
                    break                 

    def draw_patterns_menu(self, context):
        layout = self.layout
        nt = context.nodetree
        node = context.node
        socket = context.socket
        prop_name = socket.name
        prop = getattr(node, prop_name, None)
        if prop_name in node.prop_meta:
            prop_meta = node.prop_meta[prop_name]
            renderman_type = prop_meta.get('renderman_type', 'pattern')
            renderman_type = prop_meta.get('renderman_array_type', renderman_type)
            struct_name = prop_meta.get('struct_name', '')
        else:
            prop_meta = dict()
            renderman_type = getattr(socket, 'renderman_type', 'pattern')
            struct_name = ''

        terminal_node = None

        if hasattr(prop_meta, 'vstruct') or prop_name == 'inputMaterial':
            for n in rman_bl_nodes.__RMAN_PATTERN_NODES__:
                for node_desc_param in n.outputs:
                    vstruct = getattr(node_desc_param, 'vstruct', None)
                    if vstruct:
                        layout.context_pointer_set("node", node)
                        layout.context_pointer_set("nodetree", nt)
                        rman_icon = rfb_icons.get_pattern_icon(n.name)
                        op = layout.operator('node.rman_shading_create_node', text=n.name, icon_value=rman_icon.icon_id)
                        op.node_name = rman_bl_nodes.__BL_NODES_MAP__.get(n.name) 
                        if n.help:
                            op.node_description = n.help                        
                        break                                   

        elif renderman_type == 'bxdf':
            output_node = shadergraph_utils.find_node_from_nodetree(nt, 'RendermanOutputNode')
            terminal_node = output_node.inputs[0].links[0].from_node
            for bxdf_cat, bxdfs in rman_bl_nodes.__RMAN_NODE_CATEGORIES__['bxdf'].items():
                if not bxdfs[1]:
                    continue
                tokens = bxdf_cat.split('_')
                if len(tokens) > 2:
                    # this should be a subcategory/submenu
                    continue
                bxdf_category = ' '.join(tokens[1:])

                layout.context_pointer_set("node", node)
                layout.context_pointer_set("nodetree", nt)
                layout.context_pointer_set('socket', socket)
                layout.menu('NODE_MT_renderman_connection_submenu_%s' % bxdf_cat, text=bxdf_category.capitalize())                     

        else:    
            for pattern_cat, patterns in rman_bl_nodes.__RMAN_NODE_CATEGORIES__['pattern'].items():
                if not patterns[1]:
                    continue
                tokens = pattern_cat.split('_')
                if len(tokens) > 2:
                    # this should be a subcategory/submenu
                    continue                
                pattern_category = ' '.join(tokens[1:])
                has_any = False
                for n in patterns[1]:
                    for node_desc_param in n.outputs:     
                        vstruct = getattr(node_desc_param, 'vstruct', None)
                        if vstruct:               
                            break               
                        if node_desc_param.type == renderman_type:
                            if node_desc_param.type == 'struct':
                                if node_desc_param.struct_name != struct_name:
                                    continue
                            has_any = True
                            break
                        elif node_desc_param.type in RFB_FLOAT3 and renderman_type in RFB_FLOAT3:
                            has_any = True
                            break           
                if has_any:
                    layout.context_pointer_set("node", node)
                    layout.context_pointer_set("nodetree", nt)
                    layout.context_pointer_set('socket', socket)
                    layout.menu('NODE_MT_renderman_connection_submenu_%s' % pattern_cat, text=pattern_category.capitalize())       

        prop_name = socket.name
        prop_meta = node.prop_meta.get(prop_name, None)
        if prop_meta:            
            if 'presets' in prop_meta:
                layout.separator()
                layout.label(text='PRESETS')
                layout.context_pointer_set("node", node)
                layout.context_pointer_set("nodetree", nt)
                layout.context_pointer_set('socket', socket)        
                layout.menu('NODE_MT_renderman_param_presets_menu', text='Presets')

        layout.separator()
        layout.label(text='__EXISTING__')
        for n in nt.nodes:
            if socket.is_linked and socket.links[0].from_node == n:
                continue
            if n == node:
                continue
            if n == terminal_node:
                continue
            for output in n.outputs:
                if not hasattr(output, 'renderman_type'):
                    continue                
                if shadergraph_utils.is_socket_same_type(socket, output):
                    op = layout.operator('node.rman_shading_connect_existing_node', text='_%s_' % n.name)
                    op.node_name = n.name
                    break                    


    def draw_patterns_all_menu(self, context):
        layout = self.layout
        nt = getattr(context, 'nodetree', None)
        node = getattr(context, 'node', None)
        socket = getattr(context, 'socket', None)
        prop_name = getattr(socket, 'name', '')
  
        for pattern_cat, patterns in rman_bl_nodes.__RMAN_NODE_CATEGORIES__['pattern'].items():
            if not patterns[1]:
                continue
            tokens = pattern_cat.split('_')
            if len(tokens) > 2:
                # this should be a subcategory/submenu
                continue            
            pattern_category = ' '.join(tokens[1:])

            layout.context_pointer_set("node", node)
            layout.context_pointer_set("nodetree", nt)
            layout.context_pointer_set('socket', socket)
            layout.menu('NODE_MT_renderman_connection_submenu_%s' % pattern_cat, text=pattern_category.capitalize())       

        if node:
            layout.separator()
            layout.label(text='__EXISTING__')
            for n in nt.nodes:
                if socket.is_linked and socket.links[0].from_node == n:
                    continue
                if n == node:
                    continue
                op = layout.operator('node.rman_shading_connect_existing_node', text='_%s_' % n.name)

    def draw(self, context):
        layout = self.layout
        nt = getattr(context, 'nodetree', None)
        node = getattr(context, 'node', None)
        socket = getattr(context, 'socket', None)

        if not node and not socket:
            self.draw_patterns_all_menu(context)
            return 

        if socket and socket.is_linked:
            link = socket.links[0]
            input_node = link.from_node
            rman_icon = rfb_icons.get_node_icon(input_node.bl_label)
            layout.label(text='%s (%s)' % (input_node.name, link.from_socket.name), icon_value=rman_icon.icon_id)
            layout.separator()
            layout.context_pointer_set("node", node)
            layout.context_pointer_set("nodetree", nt)
            layout.context_pointer_set("socket", socket)
            if len(input_node.outputs) > 1:
                layout.menu('NODE_MT_renderman_pattern_outputs_menu', text='Outputs')            
                        
            layout.operator('node.rman_shading_disconnect', text='Disconnect')
            layout.operator('node.rman_shading_remove', text='Remove')

        is_output_node = node.bl_idname in ['RendermanOutputNode', 
                                'RendermanSamplefiltersOutputNode', 
                                'RendermanDisplayfiltersOutputNode', 
                                'RendermanIntegratorsOutputNode',
                                'RendermanProjectionsOutputNode']

        # Solo menu
        if not is_output_node and socket.is_linked:
            from_node = socket.links[0].from_node
            if shadergraph_utils.is_soloable_node(from_node):
                out_node = shadergraph_utils.find_node_from_nodetree(nt, 'RendermanOutputNode')
                layout.context_pointer_set("node", out_node)
                layout.context_pointer_set("nodetree", nt)      
                rman_icon = rfb_icons.get_icon('rman_solo_on')
                op = layout.operator('node.rman_set_node_solo', text='Solo Input Node', icon_value=rman_icon.icon_id)
                op.refresh_solo = False
                op.solo_node_name = from_node.name                 

        if is_output_node:
            layout.separator()                                
            self.draw_output_node_menu(context)
        else:
            layout.separator()   
            if hasattr(node, 'prop_meta'):
                self.draw_patterns_menu(context)
            else:
                self.draw_patterns_all_menu(context)

classes = [
    NODE_MT_renderman_node_solo_output_menu,
    NODE_MT_renderman_param_presets_menu,
    NODE_MT_renderman_connection_menu,
    NODE_MT_renderman_pattern_outputs_menu
]

def register_renderman_bxdf_node_submenus():
    global classes

    def draw(self, context):
        layout = self.layout  
        nt = getattr(context, 'nodetree', None)
        node = getattr(context, 'node', None)
        socket = getattr(context, 'socket', None)

        # add submenus for subcategories
        for bxdf_cat, bxdfs in rman_bl_nodes.__RMAN_NODE_CATEGORIES__['bxdf'].items():
            if self.bl_label == bxdf_cat:
                continue
            if self.bl_label in bxdf_cat:
                if not bxdfs[1]:
                    continue
                tokens = bxdf_cat.split('_')
                bxdf_category = ' '.join(tokens[1:])                
                layout.menu('NODE_MT_renderman_connection_submenu_%s' % bxdf_cat, text=bxdf_category.capitalize())                   

        for bxdf_cat, bxdfs in rman_bl_nodes.__RMAN_NODE_CATEGORIES__['bxdf'].items():
            tokens = bxdf_cat.split('_')
            bxdf_category = ' '.join(tokens[1:])
            if bxdf_cat != self.bl_label:
                continue        
            for n in bxdfs[1]:
                rman_icon = rfb_icons.get_bxdf_icon(n.name)
                op = layout.operator('node.rman_shading_create_node', text=n.name, icon_value=rman_icon.icon_id)
                op.node_name = n.name
                if n.help:
                    op.node_description = n.help

    for bxdf_cat, ((desc, items), lst) in rman_bl_nodes.__RMAN_NODE_CATEGORIES__['bxdf'].items():
        if not items:
            continue
        typename = 'NODE_MT_renderman_connection_submenu_%s' % bxdf_cat
        ntype = type(typename, (Menu,), {})
        ntype.bl_label = bxdf_cat
        ntype.bl_idname = typename
        if "__annotations__" not in ntype.__dict__:
            setattr(ntype, "__annotations__", {})        
        ntype.draw = draw
        classes.append(ntype)    

def register_renderman_pattern_node_submenus():

    global classes

    def draw_rman(self, context):
        layout = self.layout  
        nt = getattr(context, 'nodetree', None)
        node = getattr(context, 'node', None)
        socket = getattr(context, 'socket', None)       
        prop_name = getattr(socket, 'name', '')         
        prop = getattr(node, prop_name, None)
        if hasattr(node, 'prop_meta'):
            if prop_name in node.prop_meta:
                prop_meta = node.prop_meta[prop_name]
                renderman_type = prop_meta.get('renderman_type', 'pattern')
                renderman_type = prop_meta.get('renderman_array_type', renderman_type)
            else:
                prop_meta = dict()
                renderman_type = getattr(socket, 'renderman_type', 'pattern')
        else:
            renderman_type = 'pattern'

        # add submenus for subcategories
        for pattern_cat, patterns in rman_bl_nodes.__RMAN_NODE_CATEGORIES__['pattern'].items():
            if self.bl_label == pattern_cat:
                continue
            if self.bl_label in pattern_cat:
                if not patterns[1]:
                    continue
                tokens = pattern_cat.split('_')
                pattern_category = ' '.join(tokens[1:])               
                layout.menu('NODE_MT_renderman_connection_submenu_%s' % pattern_cat, text=pattern_category.capitalize())                
      
        for pattern_cat, patterns in rman_bl_nodes.__RMAN_NODE_CATEGORIES__['pattern'].items():
            if not patterns[1]:
                continue
            tokens = pattern_cat.split('_')
            pattern_category = ' '.join(tokens[1:])
            if pattern_cat != self.bl_label:
                continue

            for n in patterns[1]:
                for node_desc_param in n.outputs:     
                    vstruct = getattr(node_desc_param, 'vstruct', None)
                    if vstruct:               
                        break
                    if renderman_type == 'pattern' or node_desc_param.type == renderman_type or (node_desc_param.type in RFB_FLOAT3 and renderman_type in RFB_FLOAT3):
                        rman_icon = rfb_icons.get_pattern_icon(n.name)
                        label = n.name
                        op = layout.operator('node.rman_shading_create_node', text=label, icon_value=rman_icon.icon_id)
                        op.node_name = n.name 
                        if n.help:
                            op.node_description = n.help
                        break   


    for pattern_cat, patterns in rman_bl_nodes.__RMAN_NODE_CATEGORIES__['pattern'].items():
        typename = 'NODE_MT_renderman_connection_submenu_%s' % pattern_cat
        ntype = type(typename, (Menu,), {})
        ntype.bl_label = pattern_cat
        ntype.bl_idname = typename
        if "__annotations__" not in ntype.__dict__:
            setattr(ntype, "__annotations__", {})        
        ntype.draw = draw_rman
        classes.append(ntype)

def register_submenus():
    '''Register a blender menu per shading node category. We do this
    because Blender doesn't allow you to set properties on a menu class when drawing
    them, otherwise we would be able to filter the items in a menu dynamically
    '''    
    register_renderman_bxdf_node_submenus()
    register_renderman_pattern_node_submenus()

def register():
    register_submenus()

    from ..rfb_utils import register_utils

    register_utils.rman_register_classes(classes)

def unregister():
    from ..rfb_utils import register_utils
    
    register_utils.rman_unregister_classes(classes)        