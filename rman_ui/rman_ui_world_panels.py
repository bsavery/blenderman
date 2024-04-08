from .rman_ui_base import ShaderPanel
from bpy.props import (PointerProperty, StringProperty, BoolProperty,
                       EnumProperty, IntProperty, FloatProperty, FloatVectorProperty,
                       CollectionProperty)

from .rman_ui_base import CollectionPanel   
from .rman_ui_base import PRManButtonsPanel 
from ..rfb_utils.draw_utils import draw_node_properties_recursive, draw_nodes_properties_ui
from ..rfb_utils.shadergraph_utils import find_node
from .. import rfb_icons
from ..rman_cycles_convert import do_cycles_convert
from bpy.types import Panel
import bpy

class DATA_PT_renderman_world(ShaderPanel, Panel):
    bl_context = "world"
    bl_label = "World"
    shader_type = 'world'

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        world = context.scene.world
        #return rd.engine == 'PRMAN_RENDER' and not world.renderman.use_renderman_node    

        output = find_node(world, 'RendermanDisplayfiltersOutputNode')  
        return rd.engine == 'PRMAN_RENDER' and not output

    def draw(self, context):
        layout = self.layout
        world = context.scene.world

        output = find_node(world, 'RendermanDisplayfiltersOutputNode')  
        if not world.renderman.use_renderman_node:
            layout.prop(world, 'color')
            row = layout.row(align=True)
            col = row.column()
            rman_icon = rfb_icons.get_icon('rman_graph')
            if do_cycles_convert():
                col.operator('material.rman_add_rman_nodetree', icon_value=rman_icon.icon_id).idtype = 'world'
        
class DATA_PT_renderman_world_integrators(ShaderPanel, Panel):
    bl_label = "Integrator"
    bl_context = 'world'

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        world = context.scene.world
        return rd.engine == 'PRMAN_RENDER' and world.renderman.use_renderman_node

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False        
        layout = self.layout
        world = context.scene.world
        rm = world.renderman
        nt = world.node_tree

        draw_nodes_properties_ui(layout, context, nt, input_name='integrator_in', output_node_type='integrators_output')

class DATA_PT_renderman_world_display_filters(ShaderPanel, Panel):
    bl_label = "Display Filters"
    bl_context = 'world'

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        world = context.scene.world
        return rd.engine == 'PRMAN_RENDER' and world.renderman.use_renderman_node

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False           
        layout = self.layout
        world = context.scene.world
        rm = world.renderman
        nt = world.node_tree

        output = find_node(world, 'RendermanDisplayfiltersOutputNode')
        if not output:
            return
      
        row = layout.row(align=True)
        col = row.column()
        col.operator('node.rman_add_displayfilter_node_socket', text='Add')
        layout.separator()

        for i, socket in enumerate(output.inputs):
            row = layout.row()
            col = row.column()
            col.context_pointer_set("node", output)
            col.context_pointer_set("nodetree", nt)
            col.context_pointer_set("socket", socket)                 
            op = col.operator("node.rman_remove_displayfilter_node_socket", text="", icon="REMOVE")
            op.index = i            
            col = row.column()
            col.label(text=socket.name)

            layout.context_pointer_set("node", output)
            layout.context_pointer_set("nodetree", nt)
            layout.context_pointer_set("socket", socket)      
            if socket.is_linked:
                link = socket.links[0]
                node = link.from_node                 
                rman_icon = rfb_icons.get_displayfilter_icon(node.bl_label)
                layout.menu('NODE_MT_renderman_connection_menu', text=node.bl_label, icon_value=rman_icon.icon_id)    
                layout.prop(node, "is_active")
                if node.is_active:                          
                    draw_node_properties_recursive(layout, context, nt, node, level=1)                    
            else:
                layout.menu('NODE_MT_renderman_connection_menu', text='None', icon='NODE_MATERIAL')         

class DATA_PT_renderman_world_sample_filters(ShaderPanel, Panel):
    bl_label = "Sample Filters"
    bl_context = 'world'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        world = context.scene.world
        return rd.engine == 'PRMAN_RENDER' and world.renderman.use_renderman_node

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False           
        layout = self.layout
        world = context.scene.world
        rm = world.renderman
        nt = world.node_tree

        output = find_node(world, 'RendermanSamplefiltersOutputNode')
        if not output:
            return   

        row = layout.row(align=True)
        col = row.column()
        col.operator('node.rman_add_samplefilter_node_socket', text='Add')
        layout.separator()

        for i, socket in enumerate(output.inputs):
            row = layout.row()
            col = row.column()
            col.context_pointer_set("node", output)
            col.context_pointer_set("nodetree", nt)
            col.context_pointer_set("socket", socket)                 
            op = col.operator("node.rman_remove_samplefilter_node_socket", text="", icon="REMOVE")
            op.index = i               
            col = row.column()
            col.label(text=socket.name)        

            layout.context_pointer_set("socket", socket)
            layout.context_pointer_set("node", output)
            layout.context_pointer_set("nodetree", nt)            
            if socket.is_linked:
                link = socket.links[0]
                node = link.from_node                 
                rman_icon = rfb_icons.get_samplefilter_icon(node.bl_label)
                layout.menu('NODE_MT_renderman_connection_menu', text=node.bl_label, icon_value=rman_icon.icon_id)
                layout.prop(node, "is_active")
                if node.is_active:                
                    draw_node_properties_recursive(layout, context, nt, node, level=1)                    
            else:
                layout.menu('NODE_MT_renderman_connection_menu', text='None', icon='NODE_MATERIAL')   
    
classes = [
    DATA_PT_renderman_world,
    #DATA_PT_renderman_world_integrators,
    #DATA_PT_renderman_world_display_filters,
    #DATA_PT_renderman_world_sample_filters
]


def register():
    from ..rfb_utils import register_utils

    register_utils.rman_register_classes(classes) 

def unregister():
    from ..rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes) 