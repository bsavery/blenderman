from ..rman_constants import RFB_ARRAYS_MAX_LEN, __RMAN_EMPTY_STRING__, __RESERVED_BLENDER_NAMES__
from ..rfb_logger import rfb_log
from .property_callbacks import *
from ..rman_properties.rman_properties_misc import RendermanArrayGroup
from collections import OrderedDict
from bpy.props import *
from copy import deepcopy
import math
import bpy
import sys
import os

def update_colorspace_name(self, context, param_name):
    from . import texture_utils
    from . import scene_utils

    node = self.node if hasattr(self, 'node') else self

    param_colorspace = '%s_colorspace'  % param_name
    ociconvert = getattr(node, param_colorspace)
    if ociconvert != '0':
        # tell txmanager the new colorspace requested by the user
        ob = scene_utils.find_node_owner(node, context=context)
        txfile = texture_utils.get_txmanager().get_txfile(node, param_name, ob=ob)

        if txfile:
            params = txfile.params.as_dict()     
            if params['ocioconvert'] != ociconvert:
                texture_utils.update_txfile_colorspace(txfile, ociconvert)
                bpy.ops.rman_txmgr_list.refresh('EXEC_DEFAULT')  

def colorspace_names_list():
    from . import texture_utils

    items = []
    try:
        mdict = texture_utils.get_txmanager().txmanager.color_manager.colorspace_names()
        for nm in mdict:
            items.append((nm, nm, ""))
    except AttributeError:
        pass                
    return items

def generate_string_enum(sp, param_label, param_default, param_help, set_function, get_function, update_function):
    prop = None
    if 'ocio_colorspaces' in sp.options:
        def colorspace_names_options(self, context):
            items = []
            items.append(('Disabled', 'Disabled', ''))
            items.extend(colorspace_names_list())
            return items

        prop = EnumProperty(name=param_label,
                            description=param_help,
                            items=colorspace_names_options,
                            set=set_function,
                            get=get_function,
                            update=update_function)                
    else:            
        items = []
        
        if param_default == '' or param_default == "''":
            param_default = __RMAN_EMPTY_STRING__

        in_items = False

        if isinstance(sp.options, list):
            for v in sp.options:
                if v == '' or v == "''":
                    v = __RMAN_EMPTY_STRING__
                items.append((str(v), str(v), ''))         
                if param_default == str(v):
                    in_items = True
        else:                
            for k,v in sp.options.items():
                if v == '' or v == "''":
                    v = __RMAN_EMPTY_STRING__
                items.append((str(v), str(k), ''))         
                if param_default == str(v):
                    in_items = True

        if in_items:
            prop = EnumProperty(name=param_label,
                                default=param_default, description=param_help,
                                items=items,
                                set=set_function,
                                get=get_function,
                                update=update_function)
        else:
            # for strings, assume the first item is the default
            k = items[0][1]
            items[0] = (param_default, k, '' )
            prop = EnumProperty(name=param_label,
                                default=param_default, description=param_help,
                                items=items,
                                set=set_function,
                                get=get_function,
                                update=update_function)      

    return prop     

def generate_colorspace_menu(node, param_name):
    '''Generate a colorspace enum property for the incoming parameter name

    Arguments:
        node (ShadingNode) - shading node
        parm_name (str) - the string parameter name
    '''      
    def colorspace_names(self, context):
        items = []
        items.append(('0', '', ''))
        items.extend(colorspace_names_list())
        return items

    ui_label = "%s_colorspace" % param_name
    node.__annotations__[ui_label] = EnumProperty(name=ui_label, items=colorspace_names,update=lambda s,c: update_colorspace_name(s,c, param_name))    

def generate_uistruct_property(node, name, prop_names, prop_meta):
    prop_meta[name] = {'renderman_type': '', 
                            'renderman_array_type': '',
                            'renderman_name':  name,
                            'label': name,
                            'type': 'int',
                            'widget': 'default',
                            '__noconnection': True,
                            'is_ui_struct': True,
                            }
    prop_names.append(name)

    ui_label = "%s_sticky" % name
    node.__annotations__[ui_label] = BoolProperty(name=ui_label, default=False)


    ui_label = "%s_uio" % name
    node.__annotations__[ui_label] = BoolProperty(name=ui_label, default=False)

    arraylen_nm = '%s_arraylen' % name
    prop = IntProperty(name=arraylen_nm, 
                        default=0, min=0, max=RFB_ARRAYS_MAX_LEN,
                        description="Number of %s" % name,
                        update=update_array_size_func)
    node.__annotations__[arraylen_nm] = prop    
    
def generate_array_property(node, prop_names, prop_meta, node_desc_param, update_function=None):
    '''Generate the necessary properties for an array parameter and
    add it to the node

    Arguments:
        node (ShadingNode) - shading node
        prop_names (list) - the current list of property names for the shading node
        prop_meta (dict) - dictionary of the meta data for the properties for the node
        node_desc_param (NodeDescParam) - NodeDescParam object
        update_function (FunctionType) - callback function for when an array element changes

    Returns:
        bool - True if succeeded. False if not.
    
    '''  
    def is_array(ndp):          
        ''' A simple function to check if we indeed need to handle this parameter or should just ignore
        it. Color and float ramps are handled generate_property()
        '''
        haswidget = hasattr(ndp, 'widget')
        if haswidget:
            if ndp.widget.lower() in ['none', 'null', 'colorramp', 'floatramp', '__remove__']:
                return False

        if hasattr(ndp, 'options'):
            for k,v in ndp.options.items():
                if k in ['colorramp', 'floatramp']:
                    return False

        return True

    if not is_array(node_desc_param):
        return False

    param_name = node_desc_param._name
    param_label = getattr(node_desc_param, 'label', param_name)
    noconnection = False
    if hasattr(node_desc_param, 'connectable') and not node_desc_param.connectable:
        noconnection = True

    prop_meta[param_name] = {'renderman_type': 'array', 
                            'renderman_array_type': node_desc_param.type,
                            'renderman_name':  param_name,
                            'label': param_label,
                            'type': node_desc_param.type,
                            '__noconnection': noconnection,
                            'is_ui_struct': False
                            }
    prop_names.append(param_name)

    ui_label = "%s_sticky" % param_name
    node.__annotations__[ui_label] = BoolProperty(name=ui_label, default=False)


    ui_label = "%s_uio" % param_name
    node.__annotations__[ui_label] = BoolProperty(name=ui_label, default=False)
    sub_prop_names = []
    
    coll_nm = '%s_collection' % param_name
    prop = CollectionProperty(name=coll_nm, type=RendermanArrayGroup)
    node.__annotations__[coll_nm] = prop

    coll_idx_nm = '%s_collection_index' % param_name
    prop = IntProperty(name=coll_idx_nm, default=0)
    node.__annotations__[coll_idx_nm] = prop    

    ## Not used
    arraylen_nm = '%s_arraylen' % param_name
    prop = IntProperty(name=arraylen_nm, 
                        default=0, min=0, max=RFB_ARRAYS_MAX_LEN,
                        description="Size of array",
                        update=update_array_size_func)
    node.__annotations__[arraylen_nm] = prop  
            
    setattr(node, param_name, sub_prop_names)   
    return True  

def generate_property(node, sp, update_function=None, set_function=None, get_function=None):
    options = set()
    if sp.bl_prop_options != '':
        for op in sp.bl_prop_options.split(','):
            options.add(op)
    param_name = sp._name
    renderman_name = param_name
    param_widget = sp.widget.lower() if hasattr(sp,'widget') and sp.widget else 'default'

    if param_widget == '__remove__':
        return (None, None, None)      

    # blender doesn't like names with __ but we save the
    # "renderman_name with the real one"
    if param_name[0] == '_':
        param_name = param_name[1:]
    if param_name[0] == '_':
        param_name = param_name[1:]

    param_name = __RESERVED_BLENDER_NAMES__.get(param_name, param_name)        

    param_label = sp.label if hasattr(sp,'label') else param_name    
    param_type = sp.type 

    prop_meta = dict()
    param_default = sp.default
    if hasattr(sp, 'vstruct') and sp.vstruct:
        param_type = 'vstruct'
        prop_meta['vstruct'] = True
    else:
        param_type = sp.type
    renderman_type = param_type

    prop_stepsize = 3
    if hasattr(sp, 'sensitivity'):
        prop_stepsize = -int(math.log10(sp.sensitivity))
    prop_precision = getattr(sp, 'digits', 3)          

    prop = None

    prop_meta['label'] = param_label
    prop_meta['widget'] = param_widget
    prop_meta['options'] = getattr(sp, 'options', OrderedDict())
    prop_meta['is_ui_struct'] = False

    if hasattr(sp, 'connectable') and not sp.connectable:
        prop_meta['__noconnection'] = True

    if isinstance(prop_meta['options'], OrderedDict):
        for k,v in prop_meta['options'].items():
            if k in ['colorramp', 'floatramp']:
                return (None, None, None)

    # set this prop as non connectable
    if param_widget in ['null', 'checkbox', 'switch', 'colorramp', 'floatramp']:
        prop_meta['__noconnection'] = True        

    param_help = ''
    if hasattr(sp, 'help'):
        param_help = sp.help

    for nm in ['vstructmember',
        'vstructConditionalExpr',
        'conditionalVisOps',
        'conditionalLockOps',
        'riopt',
        'riattr',
        'primvar',
        'inheritable',
        'inherit_true_value',
        'presets',
        'readOnly',
        'hideInput',
        'struct_name',
        'always_write']:
        if hasattr(sp, nm):
            prop_meta[nm] = getattr(sp, nm)

    page_name = getattr(sp, 'page', '')
    prop_meta['page'] = page_name

    param_min = None
    param_max = None
    slider_min = None
    slider_max = None

    if param_type in ["float", "float2"]:
        param_min = sp.min if hasattr(sp, 'min') else (-1.0 * sys.float_info.max)
        param_max = sp.max if hasattr(sp, 'max') else sys.float_info.max
        slider_min = sp.slidermin if hasattr(sp, 'slidermin') else param_min
        slider_max = sp.slidermax if hasattr(sp, 'slidermax') else param_max                  

    elif param_type in ["int", "int2"]:
        param_min = int(sp.min) if hasattr(sp, 'min') else 0
        param_max = int(sp.max) if hasattr(sp, 'max') else 2 ** 31 - 1   
        slider_min = int(sp.slidermin) if hasattr(sp, 'slidermin') else param_min
        slider_max = int(sp.slidermax) if hasattr(sp, 'slidermax') else param_max      

    # check if there's a slidermin/slidermax, but no min/max
    '''
    if hasattr(sp, 'slidermin') and not hasattr(sp, 'min'):
        param_min = slider_min          

    if hasattr(sp, 'slidermax') and not hasattr(sp, 'max'):
        param_max = slider_max                 
    '''

    if isinstance(update_function, str):
        lcls = locals()
        exec('update_func = %s' % update_function, globals(), lcls)
        update_function = lcls['update_func']        

    if isinstance(set_function, str):
        lcls = locals()
        exec('set_func = %s' % set_function, globals(), lcls)
        set_function = lcls['set_func']            

    if param_widget == 'colorramp':
        from ..rman_properties.rman_properties_misc import RendermanBlColorRamp

        renderman_type = 'colorramp'
        prop = StringProperty(name=param_label, default='')
        rman_ramps = node.__annotations__.get('__COLOR_RAMPS__', [])
        rman_ramps.append(param_name)
        node.__annotations__['__COLOR_RAMPS__'] = rman_ramps 

        bl_ramp_name = '%s_bl_ramp' % param_name
        bl_ramp_prop = CollectionProperty(name=bl_ramp_name, type=RendermanBlColorRamp)
        node.__annotations__[bl_ramp_name] = bl_ramp_prop

    elif param_widget == 'floatramp':
        from ..rman_properties.rman_properties_misc import RendermanBlFloatRamp

        renderman_type = 'floatramp'
        prop = StringProperty(name=param_label, default='')
        rman_ramps = node.__annotations__.get('__FLOAT_RAMPS__', [])
        rman_ramps.append(param_name)
        node.__annotations__['__FLOAT_RAMPS__'] = rman_ramps    

        bl_ramp_name = '%s_bl_ramp' % param_name
        bl_ramp_prop = CollectionProperty(name=bl_ramp_name, type=RendermanBlFloatRamp)
        node.__annotations__[bl_ramp_name] = bl_ramp_prop                   

    elif param_type == 'float':
        if sp.is_array():
            prop = FloatProperty(name=param_label,
                                       default=0.0, precision=prop_precision,
                                       step=prop_stepsize,
                                       description=param_help,
                                       set=set_function,
                                       get=get_function,
                                       options=options,
                                       update=update_function)       
        else:
            if param_widget in ['checkbox', 'switch']:
                
                prop = BoolProperty(name=param_label,
                                    default=bool(param_default),
                                    options=options,
                                    description=param_help, set=set_function, get=get_function, update=update_function)
            elif param_widget == 'mapper':
                items = []
                in_items = False
                if isinstance(sp.options, list):
                    for v in sp.options:
                        items.append((str(v), v, ''))
                        if float(v) == float(param_default):
                            in_items = True
                else:                    
                    for k,v in sp.options.items():
                        items.append((str(v), k, ''))
                        if float(v) == float(param_default):
                            in_items = True
                
                bl_default = ''
                for item in items:
                    if float(item[0]) == float(param_default):
                        bl_default = item[0]
                        break                

                if in_items:
                    prop = EnumProperty(name=param_label,
                                        items=items,
                                        default=bl_default,
                                        options=options,
                                        description=param_help, set=set_function, get=get_function, update=update_function)
                else: 
                    prop = FloatProperty(name=param_label,
                                        default=param_default, precision=prop_precision,
                                        min = param_min,
                                        max = param_max,
                                        soft_min=slider_min,
                                        soft_max=slider_max,
                                        step=prop_stepsize,
                                        options=options,
                                        description=param_help, set=set_function, get=get_function, update=update_function)

            else:
                prop = FloatProperty(name=param_label,
                                     default=param_default, precision=prop_precision,
                                     min = param_min,
                                     max = param_max,
                                     soft_min=slider_min,
                                     soft_max=slider_max,
                                     step=prop_stepsize,
                                     options=options,
                                     description=param_help, set=set_function, get=get_function, update=update_function)


        renderman_type = 'float'

    elif param_type in ['int', 'integer']:
        if sp.is_array(): 
            prop = IntProperty(name=param_label,
                                default=0,
                                options=options,
                                description=param_help, set=set_function, get=get_function, update=update_function)            
        else:
            param_default = int(param_default) if param_default else 0

            if param_widget in ['checkbox', 'switch']:
                prop = BoolProperty(name=param_label,
                                    default=bool(param_default),
                                    options=options,
                                    description=param_help, set=set_function, get=get_function, update=update_function)

            elif param_widget == 'displaymetadata':
                from ..rman_bl_nodes.rman_bl_nodes_props import RendermanDspyMetaGroup
                prop = CollectionProperty(name="Meta Data",
                                    type=RendermanDspyMetaGroup,
                                    options=options,
                                    description=param_help)

                dspy_meta_index = '%s_index' % param_name
                node.__annotations__[dspy_meta_index] = IntProperty(name=dspy_meta_index, default=-1)                                    

            elif param_widget == 'mapper':
                items = []
                in_items = False
                if isinstance(sp.options, list):
                    for k in sp.options:
                        v = str(k)
                        items.append((v, k, ''))
                        if v == str(param_default):
                            in_items = True                    
                else:
                    for k,v in sp.options.items():
                        v = str(v)
                        if len(v.split(':')) > 1:
                            tokens = v.split(':')
                            v = tokens[1]
                            k = '%s:%s' % (k, tokens[0])
                        items.append((str(v), k, ''))
                        if v == str(param_default):
                            in_items = True
                
                bl_default = ''
                for item in items:
                    if item[0] == str(param_default):
                        bl_default = item[0]
                        break

                if in_items:
                    prop = EnumProperty(name=param_label,
                                        items=items,
                                        default=bl_default,
                                        options=options,
                                        description=param_help, set=set_function, get=get_function, update=update_function)
                else:
                    prop = IntProperty(name=param_label,
                                    default=param_default,
                                    min = param_min,
                                    max = param_max,
                                    soft_min=slider_min,
                                    soft_max=slider_max,
                                    options=options,
                                    description=param_help, set=set_function, get=get_function, update=update_function)

            else:
                prop = IntProperty(name=param_label,
                                   default=param_default,
                                   min = param_min,
                                   max = param_max,
                                   soft_min=slider_min,
                                   soft_max=slider_max,
                                   options=options,
                                   description=param_help, set=set_function, get=get_function, update=update_function)
        renderman_type = 'int'

    elif param_type == 'color':
        if sp.is_array():
            prop = FloatVectorProperty(name=param_label,
                                    default=(1.0, 1.0, 1.0), size=3,
                                    subtype="COLOR",
                                    soft_min=0.0, soft_max=1.0,
                                    options=options,
                                    description=param_help, set=set_function, get=get_function, update=update_function)
        else:
            if param_default == 'null' or param_default is None:
                param_default = (0.0,0.0,0.0)
            prop = FloatVectorProperty(name=param_label,
                                    default=param_default, size=3,
                                    subtype="COLOR",
                                    soft_min=0.0, soft_max=1.0,
                                    options=options,
                                    description=param_help, set=set_function, get=get_function, update=update_function)
        renderman_type = 'color'
    elif param_type == 'shader':
        param_default = ''
        prop = StringProperty(name=param_label,
                              default=param_default,
                              options=options,
                              description=param_help, set=set_function, get=get_function, update=update_function)
        renderman_type = 'string'
    elif param_type in ['string', 'struct', 'vstruct', 'bxdf']:
        if param_default is None:
            param_default = ''
        #else:
        #    param_default = str(param_default)

        if '__' in param_name:
            param_name = param_name[2:]

        if (param_widget in ['fileinput','assetidinput','assetidoutput']):
            is_ies =  ('ies' in prop_meta['options'])

            if is_ies:
                prop = StringProperty(name=param_label,
                                    default=param_default, subtype="FILE_PATH",
                                    description=param_help, set=set_function, get=get_function, update=update_function)
            else:
                prop = StringProperty(name=param_label,
                                    default=param_default, subtype="FILE_PATH",
                                    description=param_help, update=lambda s,c: assetid_update_func(s,c, param_name))                

            if (param_widget in ['fileinput','assetidinput']):
                # FIXME: Need a better way to figure out what parameters
                # need the colorspace dropdown
                if not is_ies:
                    generate_colorspace_menu(node, param_name)
        
        elif param_widget == 'dirinput':
            prop = StringProperty(name=param_label,
                                  default=param_default, subtype="DIR_PATH",
                                  options=options,
                                  description=param_help)            

        elif param_widget in ['mapper', 'popup']:
            prop = generate_string_enum(sp, param_label, param_default, param_help, set_function, get_function, update_function)

        elif param_widget == 'bl_scenegraphlocation':
            reference_type = eval(sp.options['nodeType'])
            prop = PointerProperty(name=param_label, 
                        description=param_help,
                        options=options,
                        type=reference_type)      
        elif param_widget == 'null' and hasattr(sp, 'options'):
            prop = generate_string_enum(sp, param_label, param_default, param_help, set_function, get_function, update_function)
        else:
            prop = StringProperty(name=param_label,
                                default=str(param_default),
                                options=options,
                                description=param_help, set=set_function, get=get_function, update=update_function)            
        renderman_type = param_type

    elif param_type in ['vector', 'normal']:
        if param_default is None:
            param_default = '0 0 0'
        prop = FloatVectorProperty(name=param_label,
                                   default=param_default, size=3,
                                   subtype="NONE",
                                   precision=prop_precision,
                                   options=options,
                                   description=param_help, set=set_function, get=get_function, update=update_function)
        renderman_type = param_type
    elif param_type == 'point':
        if param_default is None:
            param_default = '0 0 0'
        prop = FloatVectorProperty(name=param_label,
                                   default=param_default, size=3,
                                   precision=prop_precision,
                                   subtype="XYZ",
                                   options=options,
                                   description=param_help, set=set_function, get=get_function, update=update_function)
        renderman_type = param_type
    elif param_type == 'int2':
        param_type = 'int'
        is_array = 2
        if param_widget == 'mapper':
            items = []
            in_items = False
            if isinstance(sp.options, list):
                for k in sp.options:
                    v = str(k)
                    items.append((v, k, ''))
                    if v == str(param_default):
                        in_items = True                    
            else:
                for k,v in sp.options.items():
                    v = str(v)
                    if len(v.split(':')) > 1:
                        tokens = v.split(':')
                        v = tokens[1]
                        k = '%s:%s' % (k, tokens[0])
                    items.append((str(v), k, ''))
                    if v == str(param_default):
                        in_items = True
            
            bl_default = ''
            for item in items:
                if item[0] == str(param_default):
                    bl_default = item[0]
                    break

            if in_items:
                prop = EnumProperty(name=param_label,
                                    items=items,
                                    default=bl_default,
                                    options=options,
                                    description=param_help, set=set_function, update=update_function)
        else:        
            prop = IntVectorProperty(name=param_label,
                                    default=param_default, size=2,
                                    min = param_min,
                                    max = param_max,
                                    soft_min=slider_min,
                                    soft_max=slider_max,                                    
                                    options=options,
                                    description=param_help, set=set_function, update=update_function)
        renderman_type = 'int'
        prop_meta['arraySize'] = 2   

    elif param_type == 'float2':
        param_type = 'float'
        is_array = 2
        if param_widget == 'mapper':
            items = []
            in_items = False
            if isinstance(sp.options, list):
                for k in sp.options:
                    v = str(k)
                    items.append((v, k, ''))
                    if v == str(param_default):
                        in_items = True                    
            else:
                for k,v in sp.options.items():
                    v = str(v)
                    if len(v.split(':')) > 1:
                        tokens = v.split(':')
                        v = tokens[1]
                        k = '%s:%s' % (k, tokens[0])
                    items.append((str(v), k, ''))
                    if v == str(param_default):
                        in_items = True
            
            bl_default = ''
            for item in items:
                if item[0] == str(param_default):
                    bl_default = item[0]
                    break

            if in_items:
                prop = EnumProperty(name=param_label,
                                    items=items,
                                    default=bl_default,
                                    options=options,
                                    description=param_help, set=set_function, update=update_function)
        else:        
            prop = FloatVectorProperty(name=param_label,
                                    default=param_default, size=2,
                                    step=prop_stepsize,
                                    min = param_min,
                                    max = param_max,
                                    soft_min=slider_min,
                                    soft_max=slider_max,                                    
                                    precision=prop_precision,
                                    options=options,
                                    description=param_help, set=set_function, update=update_function)
        renderman_type = 'float'
        prop_meta['arraySize'] = 2      

    # bool property to represent whether this property
    # should be hidden. Needed for conditionalVisOps.
    hidden_prop_name = '%s_hidden' % param_name
    node.__annotations__[hidden_prop_name] = BoolProperty(name=hidden_prop_name, default=False)

    # bool property to represent whether this property
    # should be disabled. Needed for conditionalLockOps.
    disabled_prop_name = '%s_disabled' % param_name
    node.__annotations__[disabled_prop_name] = BoolProperty(name=disabled_prop_name, default=False)    

    # add a property to represent if this property should be stickied
    sticky_prop_name = "%s_sticky" % param_name
    node.__annotations__[sticky_prop_name] = BoolProperty(name=sticky_prop_name, default=False)            

    prop_meta['renderman_type'] = renderman_type
    prop_meta['renderman_name'] = renderman_name
    prop_meta['label'] = param_label
    prop_meta['type'] = param_type
    prop_meta['default_value'] = param_default

    return (param_name, prop_meta, prop)