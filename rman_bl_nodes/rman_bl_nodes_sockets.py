import bpy
from bpy.props import *
from ..rfb_utils import shadergraph_utils
from ..rfb_utils import draw_utils
from ..rfb_logger import rfb_log
from ..rman_constants import BLENDER_41
from .. import rfb_icons
import time
import re

if BLENDER_41:
    from bpy.types import (
                           NodeSocketFloat,
                           NodeSocketInt,
                           NodeSocketString,
                           NodeSocketColor,
                           NodeSocketVector,
                           NodeSocketShader,
                           NodeTreeInterfaceSocket
                           )    
    from bpy.types import NodeTreeInterfaceSocketFloat as NodeSocketInterfaceFloat
    from bpy.types import NodeTreeInterfaceSocketInt as NodeSocketInterfaceInt
    from bpy.types import NodeTreeInterfaceSocketString as NodeSocketInterfaceString
    from bpy.types import NodeTreeInterfaceSocketColor as NodeSocketInterfaceColor
    from bpy.types import NodeTreeInterfaceSocketVector as NodeSocketInterfaceVector
    from bpy.types import NodeTreeInterfaceSocketShader as NodeSocketInterfaceShader
else:
    from bpy.types import (NodeSocketFloat,
                           NodeSocketInt,
                           NodeSocketString,
                           NodeSocketColor,
                           NodeSocketVector,
                           NodeSocketShader,
                           NodeSocketInterfaceFloat,
                           NodeSocketInterfaceInt,
                           NodeSocketInterfaceString,
                           NodeSocketInterfaceColor,
                           NodeSocketInterfaceVector,
                           NodeSocketInterfaceShader
                           )

# update node during ipr for a socket default_value
def update_func(self, context):
    # check if this prop is set on an input
    node = self.node if hasattr(self, 'node') else self
    node.id_data.update_tag()

__CYCLES_GROUP_NODES__ = ['ShaderNodeGroup', 'NodeGroupInput', 'NodeGroupOutput']
__SOCKET_HIDE_VALUE__ = ['bxdf', 'projection', 'light', 'integrator', 'struct', 'vstruct'
                        'samplefilter', 'displayfilter']


# list for socket registration
# each element in the list should be:
# 
# - renderman type (str)
# - renderman type label (str)
# - bpy.types.NodeSocket class to inherit from
# - tuple to represent the color for the socket
# - bool to indicate whether to hide the value
# - dictionary of any properties wanting to be set

__RENDERMAN_TYPES_SOCKETS__ = [
     ('float', 'Float', NodeSocketFloat, (0.5, 0.5, 0.5, 1.0), False,
       {
            'default_value': FloatProperty(update=update_func),
        }
    ),
    ('int', 'Int', NodeSocketFloat, (1.0, 1.0, 1.0, 1.0), False,
        {
            'default_value': IntProperty(update=update_func),
        }
    ),
    ('string', 'String', NodeSocketString, (0.25, 1.0, 0.25, 1.0), False,
        {
            'default_value': StringProperty(update=update_func),
            'is_texture': BoolProperty(default=False)
        }
    ),    
    ('struct', 'Struct', NodeSocketShader, (1.0, 0.344, 0.0, 1.0), True,
        {
            'default_value': StringProperty(default=''),
            'struct_name': StringProperty(default='')
        }
    ),  
    ('vstruct', 'VStruct', NodeSocketShader, (1.0, 0.0, 1.0, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),      
    ('bxdf', 'Bxdf', NodeSocketShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),      
    ('color', 'Color', NodeSocketColor, (1.0, 1.0, .5, 1.0), False,
        {
            'default_value': FloatVectorProperty(size=4, subtype="COLOR", update=update_func),
        }
    ),     
    ('vector', 'Vector', NodeSocketVector, (.25, .25, .75, 1.0), False,
        {
            'default_value':FloatVectorProperty(size=3, subtype="EULER", update=update_func),
        }
    ),      
    ('normal', 'Normal', NodeSocketVector, (.25, .25, .75, 1.0), False,
        {
            'default_value':FloatVectorProperty(size=3, subtype="EULER", update=update_func),
        }
    ), 
    ('point', 'Point', NodeSocketVector, (.25, .25, .75, 1.0), False,
        {
            'default_value':FloatVectorProperty(size=3, subtype="EULER", update=update_func),
        }
    ),     
    ('light', 'Light', NodeSocketShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),    
    ('lightfilter', 'LightFilter', NodeSocketShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),        
    ('displacement', 'Displacement', NodeSocketShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),       
    ('samplefilter', 'SampleFilter', NodeSocketShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),     
    ('displayfilter', 'DisplayFilter', NodeSocketShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),    
    ('integrator', 'Integrator', NodeSocketShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),      
    ('shader', 'Shader', NodeSocketShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),  
    ('projection', 'Projection', NodeSocketString, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),                    
]

# list for socket interface registration
# each element in the list should be:
# 
# - renderman type (str)
# - renderman type label (str)
# - bpy.types.NodeSocketInterface class to inherit from
# - tuple to represent the color for the socket
# - bool to indicate whether to hide the value
# - dictionary of any properties wanting to be set

__RENDERMAN_TYPES_SOCKET_INTERFACES__ =[
     ('float', 'Float', NodeSocketInterfaceFloat, (0.5, 0.5, 0.5, 1.0), False,
        {
            'default_value': FloatProperty(update=update_func) 
        }
    ),
    ('int', 'Int', NodeSocketInterfaceFloat, (1.0, 1.0, 1.0, 1.0), False,
        {
            'default_value': IntProperty(update=update_func)
        }
    ),
    ('struct', 'Struct', NodeSocketInterfaceShader, (1.0, 0.344, 0.0, 1.0), True,
        {
            'default_value': StringProperty(default=''),
            'struct_name': StringProperty(default='')
        }
    ),  
    ('vstruct', 'VStruct', NodeSocketInterfaceShader, (1.0, 0.0, 1.0, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),      
    ('bxdf', 'Bxdf', NodeSocketInterfaceShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),       
    ('color', 'Color', NodeSocketInterfaceColor, (1.0, 1.0, .5, 1.0), False,
        {
            'default_value': FloatVectorProperty(size=4, subtype="COLOR", update=update_func),
        }
    ),      
    ('vector', 'Vector', NodeSocketInterfaceVector, (.25, .25, .75, 1.0), False,
        {
            'default_value': FloatVectorProperty(size=3, subtype="EULER", update=update_func)
        }
    ),         
    ('normal', 'Normal', NodeSocketInterfaceVector, (.25, .25, .75, 1.0), False,
        {
            'default_value': FloatVectorProperty(size=3, subtype="EULER", update=update_func)
        }
    ),       
    ('point', 'Point', NodeSocketInterfaceVector, (.25, .25, .75, 1.0), False,
        {
            'default_value': FloatVectorProperty(size=3, subtype="EULER", update=update_func)
        }
    ),             
    ('light', 'Light', NodeSocketInterfaceShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),      
    ('lightfilter', 'LightFilter', NodeSocketInterfaceShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),     
    ('displacement', 'Displacement', NodeSocketInterfaceShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),     
    ('samplefilter', 'SampleFilter', NodeSocketInterfaceShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),    
    ('displayfilter', 'DisplayFilter', NodeSocketInterfaceShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),             
    ('integrator', 'Integrator', NodeSocketInterfaceShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),         
    ('shader', 'Shader', NodeSocketInterfaceShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ), 
    ('projection', 'Projection', NodeSocketInterfaceShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),           
]

class RendermanSocket:
    ui_open: BoolProperty(name='UI Open', default=True)
    rman_label: StringProperty(name="rman_label", default="")

    def get_pretty_name(self, node):
        if node.bl_idname in __CYCLES_GROUP_NODES__:
            return self.name
        elif self.rman_label != '':
            return self.rman_label
        else:
            return self.identifier

    def get_value(self, node):
        if node.bl_idname in __CYCLES_GROUP_NODES__ or not hasattr(node, self.name):
            return self.default_value
        else:
            return getattr(node, self.name)
        
    @classmethod
    def draw_color_simple(cls):
        return (0.25, 1.0, 0.25, 1.0)           

    def draw_color(self, context, node):
        return (0.25, 1.0, 0.25, 1.0)

    def draw_value(self, context, layout, node):
        layout.prop(node, self.identifier)

    def draw(self, context, layout, node, text):

        renderman_type = getattr(self, 'renderman_type', '')
        split = layout.split()
        row = split.row()
        if self.hide and self.hide_value:
            pass
        elif self.hide_value:
            row.label(text=self.get_pretty_name(node))
        elif self.is_output:
            if self.is_array:
                row.label(text='%s[]' % (self.get_pretty_name(node)))
            else:
                row.label(text=self.get_pretty_name(node))
        elif self.is_linked or self.is_output:
            row.label(text=self.get_pretty_name(node))
        elif node.bl_idname in __CYCLES_GROUP_NODES__ or node.bl_idname == "PxrOSLPatternNode":
            row.prop(self, 'default_value',
                        text=self.get_pretty_name(node), slider=True)
        elif renderman_type in __SOCKET_HIDE_VALUE__:
            row.label(text=self.get_pretty_name(node))                        
        elif hasattr(node, self.name):
            row.prop(node, self.name,
                        text=self.get_pretty_name(node), slider=True)
        else:
            # check if this is an array element
            expr = re.compile(r'.*(\[\d+\])')
            m = expr.match(self.name)
            if m and m.groups():
                group = m.groups()[0]
                coll_nm = self.name.replace(group, '')
                collection = getattr(node, '%s_collection' % coll_nm)
                elem = None
                for e in collection:
                    if e.name == self.name:
                        elem = e
                        break
                if elem:               
                    row.prop(elem, 'value_%s' % elem.type, text=elem.name, slider=True)
                else:
                    row.label(text=self.get_pretty_name(node))
            else:
                row.label(text=self.get_pretty_name(node))

        renderman_node_type = getattr(node, 'renderman_node_type', '')
        if not self.hide and context.region.type == 'UI' and renderman_node_type != 'output':            
            nt = context.space_data.edit_tree
            row.context_pointer_set("socket", self)
            row.context_pointer_set("node", node)
            row.context_pointer_set("nodetree", nt)
            rman_icon = rfb_icons.get_icon('rman_connection_menu')
            row.menu('NODE_MT_renderman_connection_menu', text='', icon_value=rman_icon.icon_id)                
            
        mat = getattr(context, 'material')
        if mat:
            output_node = shadergraph_utils.is_renderman_nodetree(mat)
            if not output_node:
                return
            if not self.is_linked and not self.is_output:
                draw_utils.draw_sticky_toggle(layout, node, self.name, output_node)

class RendermanSocketInterface:

    def draw_color(self, context):
        return (0.25, 1.0, 0.25, 1.0)

    def draw(self, context, layout):
        layout.label(text=self.name)

    def from_socket(self, node, socket):
        if socket is None:
            return
        if type(self) == type(socket):
            if hasattr(self, 'default_value'):             
                self.default_value = socket.get_value(node)
            if hasattr(self, 'struct_name'):
                self.struct_name = socket.struct_name         
            if hasattr(self, 'is_texture'):
                self.is_texture = socket.is_texture
            self.name = socket.name

    def init_socket(self, node, socket, data_path):
        if socket is None:
            return
        time.sleep(.01)
        socket.name = self.name
        if hasattr(self, 'default_value'):
            socket.default_value = self.default_value
        if hasattr(self, 'struct_name'):
            socket.struct_name = self.struct_name   
        if hasattr(self, 'is_texture'):
            socket.is_texture = self.is_texture                     

classes = []

def register_socket_classes():
    global classes

    def draw_color(self, context, node):
        return self.socket_color

    for socket_info in __RENDERMAN_TYPES_SOCKETS__:
        renderman_type = socket_info[0]
        label = socket_info[1]
        typename = 'RendermanNodeSocket%s' % label
        ntype = type(typename, (socket_info[2], RendermanSocket,), {})
        ntype.bl_label = 'RenderMan %s Socket' % label
        ntype.bl_idname = typename
        if "__annotations__" not in ntype.__dict__:
            setattr(ntype, "__annotations__", {})        
        ntype.draw_color = draw_color
        ntype.socket_color = socket_info[3]
        ntype.__annotations__['renderman_type'] = StringProperty(default='%s' % renderman_type)
        if socket_info[4]:
            ntype.__annotations__['hide_value'] = True
        ann_dict = socket_info[5]
        for k, v in ann_dict.items():
            ntype.__annotations__[k] = v
        ntype.__annotations__['is_array'] = BoolProperty(default=False)
        ntype.__annotations__['array_size'] = IntProperty(default=-1)
        ntype.__annotations__['array_elem'] = IntProperty(default=-1)

        classes.append(ntype)

def register_socket_interface_classes():
    global classes

    def draw_socket_color(self, context):
        return self.socket_color
    
    for socket_info in __RENDERMAN_TYPES_SOCKET_INTERFACES__:
        renderman_type = socket_info[0]
        label = socket_info[1]
        typename = 'RendermanNodeSocketInterface%s' % label
        ntype = type(typename, (socket_info[2], RendermanSocketInterface,), {})        
        # bl_socket_idname needs to correspond to the RendermanNodeSocket class
        ntype.bl_socket_idname = 'RendermanNodeSocket%s' % label
        if "__annotations__" not in ntype.__dict__:
            setattr(ntype, "__annotations__", {})        
        ntype.draw_color = draw_socket_color
        ntype.socket_color = socket_info[3]
        if socket_info[4]:
            ntype.__annotations__['hide_value'] = True        
        ann_dict = socket_info[5]
        for k, v in ann_dict.items():
            ntype.__annotations__[k] = v

        classes.append(ntype)            

class RendermanNodeSocketFloat(NodeSocketFloat, RendermanSocket):
    bl_idname = 'RendermanNodeSocketFloat'
    bl_label = "Renderman Float"

    renderman_type: StringProperty(default='float')
    is_array: BoolProperty(default=False)
    array_elem: IntProperty(default=-1)
    default_value: FloatProperty(update=update_func)
        
    @classmethod
    def draw_color_simple(cls):
        return (0.5, 0.5, 0.5, 1.0)         

    def draw_color(self, context, node):
        return (0.5, 0.5, 0.5, 1.0) 
    
class RendermanNodeSocketInt(NodeSocketFloat, RendermanSocket):
    bl_idname = 'RendermanNodeSocketInt'
    bl_label = "Renderman Int"

    renderman_type: StringProperty(default='float')
    is_array: BoolProperty(default=False)
    array_elem: IntProperty(default=-1)
    default_value: IntProperty(default=0, update=update_func)
        
    @classmethod
    def draw_color_simple(cls):
        return (1.0, 1.0, 1.0, 1.0)       

    def draw_color(self, context, node):
        return (1.0, 1.0, 1.0, 1.0) 

class RendermanNodeSocketString(NodeSocketString, RendermanSocket):
    bl_idname = 'RendermanNodeSocketString'
    bl_label = "Renderman String"

    renderman_type: StringProperty(default='float')
    is_array: BoolProperty(default=False)
    array_elem: IntProperty(default=-1)
    default_value: StringProperty(default='', update=update_func)
    is_texture: BoolProperty(default=False)
        
    @classmethod
    def draw_color_simple(cls):
        return (0.25, 1.0, 0.25, 1.0)    

    def draw_color(self, context, node):
        return (0.25, 1.0, 0.25, 1.0)
    
class RendermanNodeSocketStruct(NodeSocketShader, RendermanSocket):
    bl_idname = 'RendermanNodeSocketStruct'
    bl_label = "Renderman Struct"

    renderman_type: StringProperty(default='struct')
    is_array: BoolProperty(default=False)
    array_elem: IntProperty(default=-1)
    default_value: StringProperty(default='')
    struct_name: StringProperty(default='')
        
    @classmethod
    def draw_color_simple(cls):
        return (1.0, 0.344, 0.0, 1.0)

    def draw_color(self, context, node):
        return (1.0, 0.344, 0.0, 1.0)
    

class RendermanNodeSocketVStruct(NodeSocketShader, RendermanSocket):
    bl_idname = 'RendermanNodeSocketVStruct'
    bl_label = "Renderman VStruct"

    renderman_type: StringProperty(default='vstruct')
    is_array: BoolProperty(default=False)
    array_elem: IntProperty(default=-1)
    default_value: IntProperty(default=0)

    @classmethod
    def draw_color_simple(cls):
        return (1.0, 0.0, 1.0, 1.0)

    def draw_color(self, context, node):
        return (1.0, 0.0, 1.0, 1.0)

class RendermanNodeSocketColor(NodeSocketColor, RendermanSocket):
    bl_idname = 'RendermanNodeSocketColor'
    bl_label = "Renderman Color"

    renderman_type: StringProperty(default='color')
    is_array: BoolProperty(default=False)
    array_elem: IntProperty(default=-1)
    default_value: FloatVectorProperty(size=4, subtype="COLOR", update=update_func)
        
    @classmethod
    def draw_color_simple(cls):
        return (1.0, 1.0, .5, 1.0)       

    def draw_color(self, context, node):
        return (1.0, 1.0, .5, 1.0)
    
class RendermanNodeSocketVector(NodeSocketVector, RendermanSocket):
    bl_idname = 'RendermanNodeSocketVector'
    bl_label = "Renderman Vector"

    renderman_type: StringProperty(default='vector')
    is_array: BoolProperty(default=False)
    array_elem: IntProperty(default=-1)
    default_value: FloatVectorProperty(size=3, subtype="EULER", update=update_func)
        
    @classmethod
    def draw_color_simple(cls):
        return  (.25, .25, .75, 1.0)

    def draw_color(self, context, node):
        return  (.25, .25, .75, 1.0)    
    
class RendermanNodeSocketNormal(NodeSocketVector, RendermanSocket):
    bl_idname = 'RendermanNodeSocketNormal'
    bl_label = "Renderman Normal"

    renderman_type: StringProperty(default='normal')
    is_array: BoolProperty(default=False)
    array_elem: IntProperty(default=-1)
    default_value: FloatVectorProperty(size=3, subtype="EULER", update=update_func)
        
    @classmethod
    def draw_color_simple(cls):
        return  (.25, .25, .75, 1.0)

    def draw_color(self, context, node):
        return  (.25, .25, .75, 1.0)

class RendermanNodeSocketPoint(NodeSocketVector, RendermanSocket):
    bl_idname = 'RendermanNodeSocketPoint'
    bl_label = "Renderman Point"

    renderman_type: StringProperty(default='point')
    is_array: BoolProperty(default=False)
    array_elem: IntProperty(default=-1)
    default_value: FloatVectorProperty(size=3, subtype="EULER", update=update_func)
        
    @classmethod
    def draw_color_simple(cls):
        return  (.25, .25, .75, 1.0)

    def draw_color(self, context, node):
        return  (.25, .25, .75, 1.0)
    
class RendermanNodeSocketLight(NodeSocketShader, RendermanSocket):
    bl_idname = 'RendermanNodeSocketLight'
    bl_label = "Renderman Light"

    renderman_type: StringProperty(default='light')
    is_array: BoolProperty(default=False)
    array_elem: IntProperty(default=-1)
    default_value: StringProperty(default='')
        
    @classmethod
    def draw_color_simple(cls):
        return (0.25, 1.0, 0.25, 1.0)      

    def draw_color(self, context, node):
        return (0.25, 1.0, 0.25, 1.0)       
    
class RendermanNodeSocketLightFilter(NodeSocketShader, RendermanSocket):
    bl_idname = 'RendermanNodeSocketLightFilter'
    bl_label = "Renderman Light Filter"

    renderman_type: StringProperty(default='lightfilter')
    is_array: BoolProperty(default=False)
    array_elem: IntProperty(default=-1)
    default_value: StringProperty(default='')
        
    @classmethod
    def draw_color_simple(cls):
        return (0.25, 1.0, 0.25, 1.0)      

    def draw_color(self, context, node):
        return (0.25, 1.0, 0.25, 1.0)       

class RendermanNodeSocketSampleFilter(NodeSocketShader, RendermanSocket):
    bl_idname = 'RendermanNodeSocketSampleFilter'
    bl_label = "Renderman Sample Filter"

    renderman_type: StringProperty(default='samplefilter')
    is_array: BoolProperty(default=False)
    array_elem: IntProperty(default=-1)
    default_value: StringProperty(default='')
        
    @classmethod
    def draw_color_simple(cls):
        return (0.25, 1.0, 0.25, 1.0)      

    def draw_color(self, context, node):
        return (0.25, 1.0, 0.25, 1.0)  

class RendermanNodeSocketDisplayFilter(NodeSocketShader, RendermanSocket):
    bl_idname = 'RendermanNodeSocketDisplayFilter'
    bl_label = "Renderman Display Filter"

    renderman_type: StringProperty(default='displayfilter')
    is_array: BoolProperty(default=False)
    array_elem: IntProperty(default=-1)
    default_value: StringProperty(default='')
        
    @classmethod
    def draw_color_simple(cls):
        return (0.25, 1.0, 0.25, 1.0)      

    def draw_color(self, context, node):
        return (0.25, 1.0, 0.25, 1.0)              
    
class RendermanNodeSocketIntegrator(NodeSocketShader, RendermanSocket):
    bl_idname = 'RendermanNodeSocketIntegrator'
    bl_label = "Renderman Integrator"

    renderman_type: StringProperty(default='integrator')
    is_array: BoolProperty(default=False)
    array_elem: IntProperty(default=-1)
    default_value: StringProperty(default='')
        
    @classmethod
    def draw_color_simple(cls):
        return (0.25, 1.0, 0.25, 1.0)      

    def draw_color(self, context, node):
        return (0.25, 1.0, 0.25, 1.0)           
    
class RendermanNodeSocketProjection(NodeSocketShader, RendermanSocket):
    bl_idname = 'RendermanNodeSocketProjection'
    bl_label = "Renderman Projection"

    renderman_type: StringProperty(default='projection')
    is_array: BoolProperty(default=False)
    array_elem: IntProperty(default=-1)
    default_value: StringProperty(default='')
        
    @classmethod
    def draw_color_simple(cls):
        return (0.25, 1.0, 0.25, 1.0)      

    def draw_color(self, context, node):
        return (0.25, 1.0, 0.25, 1.0)               

class RendermanNodeSocketBxdf(NodeSocketShader, RendermanSocket):
    bl_idname = 'RendermanNodeSocketBxdf'
    bl_label = "Renderman Bxdf"

    renderman_type: StringProperty(default='bxdf')
    is_array: BoolProperty(default=False)
    array_elem: IntProperty(default=-1)
    default_value: StringProperty(default='')
        
    @classmethod
    def draw_color_simple(cls):
        return (0.25, 1.0, 0.25, 1.0)      

    def draw_color(self, context, node):
        return (0.25, 1.0, 0.25, 1.0)   
    
class RendermanNodeSocketDisplacement(NodeSocketShader, RendermanSocket):
    bl_idname = 'RendermanNodeSocketDisplacement'
    bl_label = "Renderman Displacement"

    renderman_type: StringProperty(default='displacement')
    is_array: BoolProperty(default=False)
    array_elem: IntProperty(default=-1)
    default_value: StringProperty(default='')
        
    @classmethod
    def draw_color_simple(cls):
        return (0.25, 1.0, 0.25, 1.0)      

    def draw_color(self, context, node):
        return (0.25, 1.0, 0.25, 1.0)   

class RendermanNodeSocketInterfaceFloat(NodeSocketInterfaceFloat, RendermanSocketInterface):
    bl_socket_idname = 'RendermanNodeSocketFloat'

    default_value: bpy.props.FloatProperty(default=1.0, update=update_func)

class RendermanNodeSocketInterfaceInt(NodeSocketInterfaceFloat, RendermanSocketInterface):
    bl_socket_idname = 'RendermanNodeSocketInt'

    default_value: bpy.props.IntProperty(default=0, update=update_func)

class RendermanNodeSocketInterfaceStruct(NodeSocketInterfaceShader, RendermanSocketInterface):
    bl_socket_idname = 'RendermanNodeSocketStruct'

    default_value: bpy.props.StringProperty(default='')
    struct_name: bpy.props.StringProperty(default='')

class RendermanNodeSocketInterfaceVStruct(NodeSocketInterfaceShader, RendermanSocketInterface):
    bl_socket_idname = 'RendermanNodeSocketVStruct'

    default_value: bpy.props.StringProperty(default='')

class RendermanNodeSocketInterfaceColor(NodeSocketInterfaceColor, RendermanSocketInterface):
    bl_socket_idname = 'RendermanNodeSocketColor'

    default_value: bpy.props.FloatVectorProperty(size=4, subtype="COLOR", update=update_func)

class RendermanNodeSocketInterfaceVector(NodeSocketInterfaceVector, RendermanSocketInterface):
    bl_socket_idname = 'RendermanNodeSocketVector'

    default_value: bpy.props.FloatVectorProperty(size=3, subtype="EULER", update=update_func)
class RendermanNodeSocketInterfaceNormal(NodeSocketInterfaceVector, RendermanSocketInterface):
    bl_socket_idname = 'RendermanNodeSocketNormal'

    default_value: bpy.props.FloatVectorProperty(size=3, subtype="EULER", update=update_func)

class RendermanNodeSocketInterfacePoint(NodeSocketInterfaceVector, RendermanSocketInterface):
    bl_socket_idname = 'RendermanNodeSocketPoint'

    default_value: bpy.props.FloatVectorProperty(size=3, subtype="EULER", update=update_func)

class RendermanNodeSocketInterfaceLight(NodeSocketInterfaceShader, RendermanSocketInterface):
    bl_socket_idname = 'RendermanNodeSocketLight'

    default_value: bpy.props.StringProperty(default='')

class RendermanNodeSocketInterfaceLightFilter(NodeSocketInterfaceShader, RendermanSocketInterface):
    bl_socket_idname = 'RendermanNodeSocketLightFilter'

    default_value: bpy.props.StringProperty(default='')    

class RendermanNodeSocketInterfaceSampleFilter(NodeSocketInterfaceShader, RendermanSocketInterface):
    bl_socket_idname = 'RendermanNodeSocketSampleFilter'

    default_value: bpy.props.StringProperty(default='')  

class RendermanNodeSocketInterfaceDisplayFilter(NodeSocketInterfaceShader, RendermanSocketInterface):
    bl_socket_idname = 'RendermanNodeSocketDisplayFilter'

    default_value: bpy.props.StringProperty(default='')      

class RendermanNodeSocketInterfaceIntegrator(NodeSocketInterfaceShader, RendermanSocketInterface):
    bl_socket_idname = 'RendermanNodeSocketIntegrator'

    default_value: bpy.props.StringProperty(default='') 

class RendermanNodeSocketInterfaceProjection(NodeSocketInterfaceShader, RendermanSocketInterface):
    bl_socket_idname = 'RendermanNodeSocketProjection'

    default_value: bpy.props.StringProperty(default='')         

class RendermanNodeSocketInterfaceBxdf(NodeSocketInterfaceShader, RendermanSocketInterface):
    bl_socket_idname = 'RendermanNodeSocketBxdf'

    default_value: bpy.props.StringProperty(default='')

class RendermanNodeSocketInterfaceDisplacement(NodeSocketInterfaceShader, RendermanSocketInterface):
    bl_socket_idname = 'RendermanNodeSocketDisplacement'

    default_value: bpy.props.StringProperty(default='')

def register():
    from ..rfb_utils import register_utils

    if BLENDER_41:
        # Blender 4.x doesn't seem to like dynamic classes for custom NodeSockets
        # i.e.: Blender crashes when it tries to create a node group out of our
        # nodes
        classes.extend([RendermanNodeSocketFloat,
                        RendermanNodeSocketInt,
                        RendermanNodeSocketString,
                        RendermanNodeSocketStruct,
                        RendermanNodeSocketVStruct,
                        RendermanNodeSocketColor,
                        RendermanNodeSocketVector,
                        RendermanNodeSocketNormal,
                        RendermanNodeSocketPoint,
                        RendermanNodeSocketLight,
                        RendermanNodeSocketLightFilter,
                        RendermanNodeSocketSampleFilter,
                        RendermanNodeSocketDisplayFilter,
                        RendermanNodeSocketIntegrator,
                        RendermanNodeSocketProjection,
                        RendermanNodeSocketBxdf,
                        RendermanNodeSocketDisplacement,
                        RendermanNodeSocketInterfaceFloat,
                        RendermanNodeSocketInterfaceInt,
                        RendermanNodeSocketInterfaceStruct,
                        RendermanNodeSocketInterfaceVStruct,
                        RendermanNodeSocketInterfaceColor,
                        RendermanNodeSocketInterfaceVector,
                        RendermanNodeSocketInterfaceNormal,
                        RendermanNodeSocketInterfacePoint,
                        RendermanNodeSocketInterfaceLight,
                        RendermanNodeSocketInterfaceLightFilter,
                        RendermanNodeSocketInterfaceSampleFilter,
                        RendermanNodeSocketInterfaceDisplayFilter,
                        RendermanNodeSocketInterfaceIntegrator,
                        RendermanNodeSocketInterfaceProjection,
                        RendermanNodeSocketInterfaceBxdf,
                        RendermanNodeSocketInterfaceDisplacement,
                        ])
    else:
        register_socket_interface_classes()
        register_socket_classes()

    register_utils.rman_register_classes(classes)

def unregister():
    from ..rfb_utils import register_utils

    # NOTE, for some reason we crash Blender on close if we try to unregister our socket classes
    # Comment this out for now until we figure out what's going on here.

    # register_utils.rman_unregister_classes(classes)