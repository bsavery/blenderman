from .rman_ui_base import _RManPanelHeader
from .rman_ui_base import CollectionPanel
from .rman_ui_base import PRManButtonsPanel
from ..rfb_utils.draw_utils import _draw_ui_from_rman_config, draw_nodes_properties_ui, draw_node_properties_recursive
from ..rman_constants import NODE_LAYOUT_SPLIT
from ..rfb_utils import prefs_utils
from ..rfb_utils.shadergraph_utils import find_node
from ..rfb_logger import rfb_log
from .. import rfb_icons
from bpy.types import Panel
import bpy

class RENDER_PT_renderman_render(PRManButtonsPanel, Panel):
    bl_label = "Render"

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        if context.scene.render.engine != "PRMAN_RENDER":
            return

        layout = self.layout
        rd = context.scene.render
        rm = context.scene.renderman

        if rm.is_ncr_license:
            split = layout.split(factor=0.7)
            col = split.column()
            col.label(text="NON-COMMERCIAL VERSION")
            col = split.column()
            op = col.operator('renderman.launch_webbrowser', text='Upgrade/Buy Now')
            op.url = 'https://renderman.pixar.com/store'

        if rm.is_rman_interactive_running:
            row = layout.row(align=True)
            rman_rerender_controls = rfb_icons.get_icon("rman_ipr_cancel")
            row.operator('renderman.stop_ipr', text="Stop IPR",
                            icon_value=rman_rerender_controls.icon_id)    
        elif rm.is_rman_running:
            row = layout.row(align=True)
            rman_rerender_controls = rfb_icons.get_icon("rman_ipr_cancel")
            row.operator('renderman.stop_render', text="Stop Render",
                            icon_value=rman_rerender_controls.icon_id)              

        else:
            # Render
            row = layout.row(align=True)
            rman_render_icon = rfb_icons.get_icon("rman_render") 
            row.operator("render.render", text="Render",
                        icon_value=rman_render_icon.icon_id)

            # Batch Render
            rman_batch = rfb_icons.get_icon("rman_batch")
            row.operator("render.render", text="Render Animation",
                        icon_value=rman_batch.icon_id).animation = True

        _draw_ui_from_rman_config('rman_properties_scene', 'RENDER_PT_renderman_render', context, layout, rm)  

class RENDER_PT_renderman_spooling(PRManButtonsPanel, Panel):
    bl_label = "Batch Rendering"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout
        scene = context.scene
        rm = scene.renderman

        layout.enabled = not rm.is_rman_running        

        # button
        col = layout.column()
        row = col.row(align=True)
        rman_batch = rfb_icons.get_icon("rman_batch")
        row.operator("renderman.batch_render",
                     text="Batch Render", icon_value=rman_batch.icon_id)
        rman_bake = rfb_icons.get_icon("rman_bake")                     
        row.operator("renderman.batch_bake_render",
                     text="Batch Bake Render", icon_value=rman_bake.icon_id)

        # do animation
        col.prop(rm, 'external_animation')
        col = layout.column(align=True)
        col.enabled = rm.external_animation
        col.prop(scene, "frame_start", text="Start")
        col.prop(scene, "frame_end", text="End")
        col.prop(scene, "frame_step", text="By")

class RENDER_PT_renderman_spooling_export_options(PRManButtonsPanel, Panel):
    bl_label = "Spool Options"
    bl_parent_id = 'RENDER_PT_renderman_spooling'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout
        scene = context.scene
        rm = scene.renderman  

        col = layout.column()
        _draw_ui_from_rman_config('rman_properties_scene', 'RENDER_PT_renderman_spooling_export_options', context, layout, rm)        

class RENDER_PT_renderman_world_integrators(PRManButtonsPanel, Panel):
    bl_label = "Integrator"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        world = context.scene.world
        return rd.engine == 'PRMAN_RENDER'

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False        
        layout = self.layout
        world = context.scene.world
        rman_icon = rfb_icons.get_icon('rman_graph')
        if not world.renderman.use_renderman_node:
            layout.operator('material.rman_add_integrator_nodetree', icon_value=rman_icon.icon_id)
            return        
        output = find_node(world, 'RendermanIntegratorsOutputNode')
        if not output:
            layout.operator('material.rman_add_integrator_nodetree', icon_value=rman_icon.icon_id)
            return

        rm = world.renderman
        nt = world.node_tree

        draw_nodes_properties_ui(layout, context, nt, input_name='integrator_in', output_node_type='integrators_output', single_node_view=False)

class RENDER_PT_renderman_world_display_filters(PRManButtonsPanel, Panel):
    bl_label = "Display Filters"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        world = context.scene.world
        return rd.engine == 'PRMAN_RENDER'

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False           
        layout = self.layout
        world = context.scene.world
        rman_icon = rfb_icons.get_icon('rman_graph')
        if not world.renderman.use_renderman_node:
            layout.operator('material.rman_add_displayfilters_nodetree', icon_value=rman_icon.icon_id)
            return        
        output = find_node(world, 'RendermanDisplayfiltersOutputNode')
        if not output:
            layout.operator('material.rman_add_displayfilters_nodetree', icon_value=rman_icon.icon_id)  
            return           

        rm = world.renderman
        nt = world.node_tree      
        row = layout.row(align=True)
        col = row.column()
        col.operator('node.rman_add_displayfilter_node_socket', text='Add')
        layout.separator()

        for i, socket in enumerate(output.inputs):
            split = layout.split()
            row = split.row()
            col = row.column()
            col.context_pointer_set("node", output)
            col.context_pointer_set("nodetree", nt)
            col.context_pointer_set("socket", socket)                 
            op = col.operator("node.rman_remove_displayfilter_node_socket", text="", icon="REMOVE")
            op.index = i                      
            col = row.column()
            col.label(text=socket.identifier)

            if socket.is_linked:
                col = row.column()
                col.enabled = (i != 0)
                col.context_pointer_set("node", output)
                col.context_pointer_set("nodetree", nt)
                col.context_pointer_set("socket", socket)             
                op = col.operator("node.rman_move_displayfilter_node_up", text="", icon="TRIA_UP")
                op.index = i
                col = row.column()
                col.context_pointer_set("node", output)
                col.context_pointer_set("nodetree", nt)
                col.context_pointer_set("socket", socket)             
                col.enabled = (i != len(output.inputs)-1)
                op = col.operator("node.rman_move_displayfilter_node_down", text="", icon="TRIA_DOWN")
                op.index = i
                        
            layout.context_pointer_set("node", output)
            layout.context_pointer_set("nodetree", nt)
            layout.context_pointer_set("socket", socket)      
            if socket.is_linked:
                link = socket.links[0]
                node = link.from_node                 
                rman_icon = rfb_icons.get_displayfilter_icon(node.bl_label)
                layout.menu('NODE_MT_renderman_connection_menu', text='%s (%s)' % (node.name, node.bl_label), icon_value=rman_icon.icon_id)    
                layout.prop(node, "is_active")
                if node.is_active:                          
                    draw_node_properties_recursive(layout, context, nt, node, level=1)                    
            else:
                layout.menu('NODE_MT_renderman_connection_menu', text='None', icon='NODE_MATERIAL')         

class RENDER_PT_renderman_world_sample_filters(PRManButtonsPanel, Panel):
    bl_label = "Sample Filters"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        world = context.scene.world
        return rd.engine == 'PRMAN_RENDER'

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False           
        layout = self.layout
        world = context.scene.world
        rman_icon = rfb_icons.get_icon('rman_graph')
        if not world.renderman.use_renderman_node:
            layout.operator('material.rman_add_samplefilters_nodetree', icon_value=rman_icon.icon_id)
            return
        output = find_node(world, 'RendermanSamplefiltersOutputNode')
        if not output:
            layout.operator('material.rman_add_samplefilters_nodetree', icon_value=rman_icon.icon_id)            
            return

        rm = world.renderman
        nt = world.node_tree

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
            col.label(text=socket.identifier)       

            if socket.is_linked:
                col = row.column()
                col.enabled = (i != 0)
                col.context_pointer_set("node", output)
                col.context_pointer_set("nodetree", nt)
                col.context_pointer_set("socket", socket)             
                op = col.operator("node.rman_move_samplefilter_node_up", text="", icon="TRIA_UP")
                op.index = i
                col = row.column()
                col.context_pointer_set("node", output)
                col.context_pointer_set("nodetree", nt)
                col.context_pointer_set("socket", socket)             
                col.enabled = (i != len(output.inputs)-1)
                op = col.operator("node.rman_move_samplefilter_node_down", text="", icon="TRIA_DOWN")
                op.index = i             

            layout.context_pointer_set("socket", socket)
            layout.context_pointer_set("node", output)
            layout.context_pointer_set("nodetree", nt)            
            if socket.is_linked:
                link = socket.links[0]
                node = link.from_node                 
                rman_icon = rfb_icons.get_samplefilter_icon(node.bl_label)
                layout.menu('NODE_MT_renderman_connection_menu', text='%s (%s)' % (node.name, node.bl_label), icon_value=rman_icon.icon_id)
                layout.prop(node, "is_active")
                if node.is_active:                
                    draw_node_properties_recursive(layout, context, nt, node, level=1)                    
            else:
                layout.menu('NODE_MT_renderman_connection_menu', text='None', icon='NODE_MATERIAL')           

class RENDER_PT_renderman_sampling(PRManButtonsPanel, Panel):
    bl_label = "Sampling"

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout
        scene = context.scene
        rm = scene.renderman

        col = layout.column()
        row = col.row(align=True)

        '''
        row.menu("PRMAN_MT_presets", text=bpy.types.WM_MT_operator_presets.bl_label)
        row.operator("render.renderman_preset_add", text="", icon='ADD')
        row.operator("render.renderman_preset_add", text="",icon='REMOVE').remove_active = True
        '''

        _draw_ui_from_rman_config('rman_properties_scene', 'RENDER_PT_renderman_sampling', context, layout, rm)

class RENDER_PT_renderman_motion_blur(PRManButtonsPanel, Panel):
    bl_label = "Motion Blur"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        rm = context.scene.renderman
        layout = self.layout
        _draw_ui_from_rman_config('rman_properties_scene', 'RENDER_PT_renderman_motion_blur', context, layout, rm)   

class RENDER_PT_renderman_baking(PRManButtonsPanel, Panel):
    bl_label = "Baking"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False        
        layout = self.layout
        scene = context.scene
        rm = scene.renderman        
        layout.enabled = not rm.is_rman_interactive_running           
        row = layout.row()
        rman_batch = rfb_icons.get_icon("rman_bake")
        row.operator("renderman.bake",
                     text="Bake", icon_value=rman_batch.icon_id)  

        _draw_ui_from_rman_config('rman_properties_scene', 'RENDER_PT_renderman_baking', context, layout, rm)      

class RENDER_PT_renderman_advanced_settings(PRManButtonsPanel, Panel):
    bl_label = "Advanced"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout
        scene = context.scene
        rm = scene.renderman

        _draw_ui_from_rman_config('rman_properties_scene', 'RENDER_PT_renderman_advanced_settings', context, layout, rm)  
                
class RENDER_PT_renderman_custom_options(PRManButtonsPanel, Panel):
    bl_label = "Custom Options"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout
        scene = context.scene
        rm = scene.renderman

        _draw_ui_from_rman_config('rman_properties_scene', 'RENDER_PT_renderman_custom_options', context, layout, rm)

classes = [
    RENDER_PT_renderman_render,
    RENDER_PT_renderman_spooling,
    RENDER_PT_renderman_spooling_export_options,    
    RENDER_PT_renderman_sampling,
    RENDER_PT_renderman_baking,
    RENDER_PT_renderman_world_integrators,
    RENDER_PT_renderman_world_display_filters,
    RENDER_PT_renderman_world_sample_filters,    
    RENDER_PT_renderman_motion_blur,    
    RENDER_PT_renderman_advanced_settings,   
    RENDER_PT_renderman_custom_options
]

def register():
    from ..rfb_utils import register_utils

    register_utils.rman_register_classes(classes) 

def unregister():
    from ..rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes) 