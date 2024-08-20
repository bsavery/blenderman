from .rman_ui_base import _RManPanelHeader
from .rman_ui_base import CollectionPanel
from .rman_ui_base import PRManButtonsPanel
from ..rfb_utils.draw_utils import _draw_ui_from_rman_config, draw_nodes_properties_ui
from ..rfb_utils.draw_utils import draw_node_properties_recursive, panel_node_draw
from ..rfb_utils.draw_utils import show_node_sticky_params, show_node_match_params
from ..rfb_utils import prefs_utils
from ..rman_constants import NODE_LAYOUT_SPLIT
from .. import rfb_icons
from ..rfb_utils import object_utils
from ..rfb_utils.prefs_utils import get_pref
from ..rfb_utils.shadergraph_utils import is_renderman_nodetree, gather_nodes
from ..rman_cycles_convert import do_cycles_convert
from bpy.types import Panel
import bpy

class OBJECT_PT_renderman_object_render(CollectionPanel, Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Shading and Visibility"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        if context.object.type in ['CAMERA', 'LIGHT']:
            return False        
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw_item(self, layout, context, item):
        ob = context.object
        rm = bpy.data.objects[ob.name].renderman
        ll = rm.light_linking
        index = rm.light_linking_index

        col = layout.column()
        col.prop(item, "group")
        col.prop(item, "mode")

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout
        ob = context.object
        rm = ob.renderman

        col = layout.column()
        _draw_ui_from_rman_config('rman_properties_object', 'OBJECT_PT_renderman_object_render', context, layout, rm)           

class OBJECT_PT_renderman_object_raytracing(CollectionPanel, Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Ray Tracing"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        if context.object.type in ['CAMERA', 'LIGHT']:
            return False        
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw_item(self, layout, context, item):
        col = layout.column()
        col.prop(item, "group")
        col.prop(item, "mode")

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout
        ob = context.object
        rm = ob.renderman

        col = layout.column()
        _draw_ui_from_rman_config('rman_properties_object', 'OBJECT_PT_renderman_object_raytracing', context, layout, rm)        

class OBJECT_PT_renderman_object_geometry(Panel, CollectionPanel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "RenderMan Geometry"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw_item(self, layout, context, item):
        col = layout.column()
        col.prop(item, "name")
        col.prop(item, "type")

    def draw_props(self, layout, context):
        ob = context.object
        rm = ob.renderman
        active = context.active_object
        rman_type = object_utils._detect_primitive_(active)

        rman_interactive_running = context.scene.renderman.is_rman_interactive_running

        col = layout.column()
        col.enabled = not rman_interactive_running          

        _draw_ui_from_rman_config('rman_properties_object', 'OBJECT_PT_renderman_object_geometry', context, layout, rm)

        if rm.bl_object_type != 'EMPTY':
            col = layout.column()
            col.enabled = not rman_interactive_running
            col.menu('VIEW3D_MT_RM_Add_Export_Menu', icon_value=bpy.types.VIEW3D_MT_RM_Add_Export_Menu.get_icon_id())

        col = layout.column()

    def draw_camera_props(self, layout, context):
        ob = context.object
        rm = ob.renderman        
        col = layout.column()
        col.prop(rm, "motion_segments_override")
        col = layout.column()
        col.active = rm.motion_segments_override
        col.prop(rm, "motion_segments")         

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout
 
        if context.object.type == 'CAMERA':
            self.draw_camera_props(layout, context)
        else:
            self.draw_props(layout, context)

class OBJECT_PT_renderman_object_material_override(Panel, CollectionPanel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "RenderMan Material"
    bl_options = {'DEFAULT_CLOSED'}    

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return (context.object and rd.engine in {'PRMAN_RENDER'} )

    def draw(self, context):
        layout = self.layout
        layout.prop(context.object.renderman, 'rman_material_override')

        mat = context.object.renderman.rman_material_override
        if not mat:
            layout.operator('node.rman_new_material_override', text='New Material')
            return

class MATERIAL_PT_renderman_object_shader_surface(Panel, CollectionPanel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Bxdf"
    bl_parent_id = "OBJECT_PT_renderman_object_material_override"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        mat = context.object.renderman.rman_material_override
        if not mat:            
            return False
        return (context.object and rd.engine in {'PRMAN_RENDER'} )    

    def draw(self, context):
        layout = self.layout
        mat = context.object.renderman.rman_material_override
        if mat.renderman and mat.node_tree:
            layout.context_pointer_set("material", mat)
            nt = mat.node_tree
            rman_output_node = is_renderman_nodetree(mat)

            if rman_output_node:
                if rman_output_node.solo_node_name != '':
                    solo_node = nt.nodes.get(rman_output_node.solo_node_name, None)
                    if solo_node:

                        split = layout.split(factor=0.25)
                        split.context_pointer_set("nodetree", nt)  
                        split.context_pointer_set("node", rman_output_node)  
                        rman_icon = rfb_icons.get_icon('rman_solo_on')   
                        split.label(text=rman_output_node.solo_node_name , icon_value=rman_icon.icon_id)  
                        
                        split = split.split(factor=0.95)
                        split.menu('NODE_MT_renderman_node_solo_output_menu', text='Select Output')
                        op = split.operator('node.rman_set_node_solo', text='', icon='FILE_REFRESH')
                        op.refresh_solo = True 
                        layout.separator()
                        
                        layout.separator()
                        draw_node_properties_recursive(layout, context, nt, solo_node, level=0)

                        return

                # Filter Toggle
                split = layout.split(factor=0.05)
                col = split.column()
                filter_icon = 'FILTER'
                filter_parameters = getattr(rman_output_node, 'bxdf_filter_parameters', False)
                filter_method = getattr(rman_output_node, 'bxdf_filter_method', 'NONE')
                col.context_pointer_set('node', rman_output_node)
                pressed = filter_parameters
                op = col.operator('node.rman_toggle_filter_params', depress=pressed, icon=filter_icon, text='')
                op.prop_name = 'bxdf_filter_parameters'

                if filter_parameters:
                    col = split.column()
                    col.prop(rman_output_node, 'bxdf_filter_method', text='')

                    if filter_method == 'MATCH':
                        col = split.column()
                        col.prop(rman_output_node, 'bxdf_match_expression', text='') 
                        col = split.column() 
                        col.prop(rman_output_node, 'bxdf_match_on', text='')  
                else:
                    col = split.column()
                    col = split.column()                                
                
                layout.separator()
                input_name = 'bxdf_in'
                if not rman_output_node.inputs[input_name].is_linked:
                    panel_node_draw(layout, context, mat,
                                    'RendermanOutputNode', 'Bxdf')  
                elif not filter_parameters or filter_method == 'NONE':
                    panel_node_draw(layout, context, mat,
                                    'RendermanOutputNode', 'Bxdf')                      
                elif filter_method == 'STICKY':
                    bxdf_node = rman_output_node.inputs[input_name].links[0].from_node
                    nodes = gather_nodes(bxdf_node)
                    for node in nodes:
                        prop_names = getattr(node, 'prop_names', list())
                        show_node_sticky_params(layout, node, prop_names, context, nt, rman_output_node)   
                elif filter_method == 'MATCH':
                    expr = rman_output_node.bxdf_match_expression
                    if expr == '':
                        return
                    bxdf_node = rman_output_node.inputs[input_name].links[0].from_node
                    nodes = gather_nodes(bxdf_node)
                    for node in nodes:
                        prop_names = getattr(node, 'prop_names', list())
                        show_node_match_params(layout, node, expr, rman_output_node.bxdf_match_on,
                                            prop_names, context, nt)      
                else:   
                    panel_node_draw(layout, context, mat,
                                    'RendermanOutputNode', 'Bxdf')                
            else:
                if not panel_node_draw(layout, context, mat, 'ShaderNodeOutputMaterial', 'Surface'):
                    layout.prop(mat, "diffuse_color")
            layout.separator()

        else:
            rm = mat.renderman

            row = layout.row()
            row.prop(mat, "diffuse_color")

            layout.separator()
        if mat and not is_renderman_nodetree(mat):
            layout.context_pointer_set("material", mat)
            rm = mat.renderman
            row = layout.row()
            
            row = layout.row(align=True)
            col = row.column()
            rman_icon = rfb_icons.get_icon('rman_graph')
            col.operator(
                'material.rman_add_rman_nodetree', icon_value=rman_icon.icon_id).idtype = "material"
            if do_cycles_convert():
                col = row.column()                
                op = col.operator('material.rman_convert_cycles_shader').idtype = "material"
                if not mat.grease_pencil:
                    layout.operator('material.rman_convert_all_cycles_shaders')

class MATERIAL_PT_renderman_object_shader_displacement(Panel, CollectionPanel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Displacement"
    bl_parent_id = "OBJECT_PT_renderman_object_material_override"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        ob = context.object
        if ob.type != 'EMPTY':
            return False
        if ob.is_instancer:
            return False
        mat = context.object.renderman.rman_material_override
        if not mat:            
            return False
        return (context.object and rd.engine in {'PRMAN_RENDER'} )             

    def draw(self, context):
        layout = self.layout
        mat = context.object.renderman.rman_material_override
        if mat.renderman and mat.node_tree:
            layout.context_pointer_set("material", mat)
            nt = mat.node_tree
            rman_output_node = is_renderman_nodetree(mat)
            if not rman_output_node:
                return

            # Filter Toggle
            split = layout.split(factor=0.05)
            col = split.column()
            filter_icon = 'FILTER'
            filter_parameters = getattr(rman_output_node, 'disp_filter_parameters', False)
            filter_method = getattr(rman_output_node, 'disp_filter_method', 'NONE')
            col.context_pointer_set('node', rman_output_node)
            pressed = filter_parameters
            op = col.operator('node.rman_toggle_filter_params', depress=pressed, icon=filter_icon, text='')
            op.prop_name = 'disp_filter_parameters'

            if filter_parameters:
                col = split.column()
                col.prop(rman_output_node, 'disp_filter_method', text='')

                if filter_method == 'MATCH':
                    col = split.column()
                    col.prop(rman_output_node, 'disp_match_expression', text='') 
                    col = split.column() 
                    col.prop(rman_output_node, 'disp_match_on', text='')  
                else:
                    col = split.column()
                    col = split.column()

            shader_type = 'Displacement'
            input_name = 'displace_in'
            if not rman_output_node.inputs[input_name].is_linked:
                draw_nodes_properties_ui(
                    layout, context, nt, input_name=input_name)
            elif not filter_parameters or filter_method == 'NONE':
                draw_nodes_properties_ui(
                    layout, context, nt, input_name=input_name)                 
            elif filter_method == 'STICKY':
                disp_node = rman_output_node.inputs[input_name].links[0].from_node
                nodes = gather_nodes(disp_node)
                for node in nodes:
                    prop_names = getattr(node, 'prop_names', list())
                    show_node_sticky_params(layout, node, prop_names, context, nt, rman_output_node)
            elif filter_method == 'MATCH':
                expr = rman_output_node.disp_match_expression
                if expr == '':
                    return                
                disp_node = rman_output_node.inputs[input_name].links[0].from_node
                nodes = gather_nodes(disp_node)
                for node in nodes:
                    prop_names = getattr(node, 'prop_names', list())
                    show_node_match_params(layout, node, expr, rman_output_node.disp_match_on,
                                        prop_names, context, nt)
            else:
                draw_nodes_properties_ui(
                    layout, context, nt, input_name=input_name)                  

class OBJECT_PT_renderman_object_geometry_quadric(Panel, CollectionPanel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Quadric"
    bl_parent_id = "OBJECT_PT_renderman_object_geometry"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        rm = context.object.renderman
        if context.object.type in ['LIGHT']:
            return False
        if rm.primitive != 'QUADRIC':
            return False
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw_item(self, layout, context, item):
        col = layout.column()
        col.prop(item, "name")
        col.prop(item, "type")

    def draw(self, context):

        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout        
        ob = context.object
        rm = ob.renderman
        active = context.active_object
        rman_type = object_utils._detect_primitive_(active)

        col = layout.column()       
        col = layout.column(align = True)   
        _draw_ui_from_rman_config('rman_properties_object', 'OBJECT_PT_renderman_object_geometry_quadric', context, layout, rm)      

class OBJECT_PT_renderman_object_geometry_runprogram(Panel, CollectionPanel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Run Program"
    bl_parent_id = "OBJECT_PT_renderman_object_geometry"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        rm = context.object.renderman
        if context.object.type in ['LIGHT']:
            return False
        if rm.primitive != 'PROCEDURAL_RUN_PROGRAM':
            return False
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw_item(self, layout, context, item):
        col = layout.column()
        col.prop(item, "name")
        col.prop(item, "type")

    def draw(self, context):

        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout        
        ob = context.object
        rm = ob.renderman
        active = context.active_object
        rman_type = object_utils._detect_primitive_(active)

        col = layout.column() 
        col = layout.column(align = True)   
        _draw_ui_from_rman_config('rman_properties_object', 'OBJECT_PT_renderman_object_geometry_runprogram', context, layout, rm)                     

class OBJECT_PT_renderman_object_geometry_dynamic_load_dso(Panel, CollectionPanel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Dynamic Load DSO"
    bl_parent_id = "OBJECT_PT_renderman_object_geometry"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        rm = context.object.renderman
        if context.object.type in ['LIGHT']:
            return False
        if rm.primitive != 'DYNAMIC_LOAD_DSO':
            return False
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw_item(self, layout, context, item):
        col = layout.column()
        col.prop(item, "name")
        col.prop(item, "type")

    def draw(self, context):

        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout        
        ob = context.object
        rm = ob.renderman
        active = context.active_object
        rman_type = object_utils._detect_primitive_(active)

        col = layout.column()     
        col = layout.column(align = True)   
        _draw_ui_from_rman_config('rman_properties_object', 'OBJECT_PT_renderman_object_geometry_dynamic_load_dso', context, layout, rm)                     

class OBJECT_PT_renderman_object_geometry_rib_archive(Panel, CollectionPanel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "RIB Archive"
    bl_parent_id = "OBJECT_PT_renderman_object_geometry"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        rm = context.object.renderman
        if context.object.type in ['LIGHT']:
            return False
        if rm.primitive != 'DELAYED_LOAD_ARCHIVE':
            return False
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw_item(self, layout, context, item):
        col = layout.column()
        col.prop(item, "name")
        col.prop(item, "type")

    def draw(self, context):

        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout        
        ob = context.object
        rm = ob.renderman
        anim = rm.archive_anim_settings
        active = context.active_object
        rman_type = object_utils._detect_primitive_(active)
        rman_interactive_running = context.scene.renderman.is_rman_interactive_running

        col = layout.column()
        col.enabled = not rman_interactive_running        
        col = layout.column(align = True)   
        _draw_ui_from_rman_config('rman_properties_object', 'OBJECT_PT_renderman_object_geometry_rib_archive', context, layout, rm)
class OBJECT_PT_renderman_object_geometry_points(Panel, CollectionPanel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Points"
    bl_parent_id = "OBJECT_PT_renderman_object_geometry"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        rm = context.object.renderman
        if context.object.type in ['LIGHT']:
            return False
        if rm.primitive != 'POINTS':
            return False
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw_item(self, layout, context, item):
        col = layout.column()
        col.prop(item, "name")
        col.prop(item, "type")

    def draw(self, context):

        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout        
        ob = context.object
        rm = ob.renderman
        active = context.active_object
        rman_type = object_utils._detect_primitive_(active)
        rman_interactive_running = context.scene.renderman.is_rman_interactive_running

        col = layout.column()
        col.enabled = not rman_interactive_running        
        col = layout.column(align = True)   
        _draw_ui_from_rman_config('rman_properties_object', 'OBJECT_PT_renderman_object_geometry_points', context, layout, rm)                     

class OBJECT_PT_renderman_object_geometry_volume(Panel, CollectionPanel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Volume"
    bl_parent_id = "OBJECT_PT_renderman_object_geometry"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        rm = context.object.renderman
        if context.object.type in ['LIGHT']:
            return False
        rman_type = object_utils._detect_primitive_(context.object)
        if rman_type not in ['OPENVDB', 'RI_VOLUME']:
            return False
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw_item(self, layout, context, item):
        col = layout.column()
        col.prop(item, "name")
        col.prop(item, "type")

    def draw(self, context):

        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout        
        ob = context.object
        rm = ob.renderman
        active = context.active_object
        rman_type = object_utils._detect_primitive_(active)
        rman_interactive_running = context.scene.renderman.is_rman_interactive_running

        col = layout.column()
        col.enabled = not rman_interactive_running        
        col = layout.column(align = True)   
        _draw_ui_from_rman_config('rman_properties_object', 'OBJECT_PT_renderman_object_geometry_volume', context, layout, rm)        

class OBJECT_PT_renderman_object_geometry_brickmap(Panel, CollectionPanel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Brickmap"
    bl_parent_id = "OBJECT_PT_renderman_object_geometry"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        rm = context.object.renderman
        if context.object.type in ['LIGHT']:
            return False
        if rm.primitive != 'BRICKMAP':
            return False
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw_item(self, layout, context, item):
        col = layout.column()
        col.prop(item, "name")
        col.prop(item, "type")

    def draw(self, context):

        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout        
        ob = context.object
        rm = ob.renderman
        active = context.active_object
        rman_type = object_utils._detect_primitive_(active)

        col = layout.column()  
        col = layout.column(align = True)   
        _draw_ui_from_rman_config('rman_properties_object', 'OBJECT_PT_renderman_object_geometry_brickmap', context, layout, rm)       

class OBJECT_PT_renderman_object_geometry_alembic(Panel, CollectionPanel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Alembic Archive"
    bl_parent_id = "OBJECT_PT_renderman_object_geometry"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        rm = context.object.renderman
        if context.object.type in ['LIGHT']:
            return False
        if rm.primitive != 'ALEMBIC':
            return False
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw_item(self, layout, context, item):
        col = layout.column()
        col.prop(item, "name")
        col.prop(item, "type")

    def draw(self, context):

        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout        
        ob = context.object
        rm = ob.renderman
        active = context.active_object
        rman_type = object_utils._detect_primitive_(active)

        col = layout.column()      
        col = layout.column(align = True)   
        _draw_ui_from_rman_config('rman_properties_object', 'OBJECT_PT_renderman_object_geometry_alembic', context, layout, rm)                                 


class OBJECT_PT_renderman_object_geometry_attributes(Panel, CollectionPanel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Attributes"
    bl_parent_id = "OBJECT_PT_renderman_object_geometry"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        if context.object.type in ['LIGHT']:
            return False
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw_item(self, layout, context, item):
        col = layout.column()
        col.prop(item, "name")
        col.prop(item, "type")

    def draw(self, context):

        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout        
        ob = context.object
        rm = ob.renderman
        active = context.active_object
        rman_type = object_utils._detect_primitive_(active)

        col = layout.column()   
        col = layout.column(align = True)   
        _draw_ui_from_rman_config('rman_properties_object', 'OBJECT_PT_renderman_object_geometry_attributes', context, layout, rm)               

class OBJECT_PT_renderman_object_baking(Panel, _RManPanelHeader):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Baking"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        if context.object.type in ['CAMERA', 'LIGHT']:
            return False        
        return (context.object and rd.engine in {'PRMAN_RENDER'})    

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout
        ob = context.object
        rm = ob.renderman

        col = layout.column()
        _draw_ui_from_rman_config('rman_properties_object', 'OBJECT_PT_renderman_object_baking', context, layout, rm)             



class OBJECT_PT_renderman_object_custom_primvars(CollectionPanel, Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Custom Primvars"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        if context.object.type in ['CAMERA', 'LIGHT']:
            return False        
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout
        ob = context.object
        rm = ob.renderman

        col = layout.column()
        row = col.row()
 
        _draw_ui_from_rman_config('rman_properties_object', 'OBJECT_PT_renderman_object_custom_primvars', context, layout, rm)     

class OBJECT_PT_renderman_object_custom_attributes(CollectionPanel, Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Custom Attributes"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        if context.object.type in ['CAMERA', 'LIGHT']:
            return False        
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout
        ob = context.object
        rm = ob.renderman

        layout.label(text='User Attributes')
        row = layout.row()  
        prop_name = 'user_attributes'  
        prop_index_nm = '%s_index' % prop_name        
        row.template_list("RENDERMAN_UL_UserAttributes_List", "User Attributes",
                            rm, prop_name, rm, prop_index_nm)
        col = row.column(align=True)
        op = col.operator('renderman.add_remove_user_attributes', icon="ADD", text="")
        op.collection = prop_name
        op.collection_index = prop_index_nm
        op.defaultname = 'key'
        op.action = 'ADD'

        op = col.operator('renderman.add_remove_user_attributes', icon="REMOVE", text="")
        op.collection = prop_name
        op.collection_index = prop_index_nm
        op.action = 'REMOVE'   

        prop_index = getattr(rm, prop_index_nm, None)
        if prop_index_nm is None:
            return

        prop = getattr(rm, prop_name)
        if prop_index > -1 and prop_index < len(prop):
            item = prop[prop_index]
            layout.prop(item, 'name')
            layout.prop(item, 'namespace')
            layout.prop(item, 'type')
            layout.prop(item, 'value_%s' % item.type, slider=True)        

        col = layout.column()
        _draw_ui_from_rman_config('rman_properties_object', 'OBJECT_PT_renderman_object_custom_attributes', context, layout, rm)             

class OBJECT_PT_renderman_object_matteid(Panel, _RManPanelHeader):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Matte ID"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        if context.object.type in ['CAMERA', 'LIGHT']:
            return False        
        return (context.object and rd.engine in {'PRMAN_RENDER'})    

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        layout = self.layout
        ob = context.object
        rm = ob.renderman

        col = layout.column()
        _draw_ui_from_rman_config('rman_properties_object', 'OBJECT_PT_renderman_object_matteid', context, layout, rm)             

classes = [
    OBJECT_PT_renderman_object_geometry,

    OBJECT_PT_renderman_object_material_override,
    MATERIAL_PT_renderman_object_shader_surface,
    MATERIAL_PT_renderman_object_shader_displacement,

    OBJECT_PT_renderman_object_geometry_quadric,
    OBJECT_PT_renderman_object_geometry_runprogram,
    OBJECT_PT_renderman_object_geometry_dynamic_load_dso,
    OBJECT_PT_renderman_object_geometry_rib_archive,
    OBJECT_PT_renderman_object_geometry_points,
    OBJECT_PT_renderman_object_geometry_volume,
    OBJECT_PT_renderman_object_geometry_brickmap,
    OBJECT_PT_renderman_object_geometry_alembic,
    OBJECT_PT_renderman_object_geometry_attributes,
    OBJECT_PT_renderman_object_render,
    OBJECT_PT_renderman_object_raytracing,
    OBJECT_PT_renderman_object_baking,
    OBJECT_PT_renderman_object_custom_primvars,
    OBJECT_PT_renderman_object_custom_attributes,
    OBJECT_PT_renderman_object_matteid    
]

def register():
    from ..rfb_utils import register_utils

    register_utils.rman_register_classes(classes) 

def unregister():
    from ..rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes)    