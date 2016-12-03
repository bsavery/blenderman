# ##### BEGIN MIT LICENSE BLOCK #####
#
# Copyright (c) 2015 Brian Savery
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
#
# ##### END MIT LICENSE BLOCK #####

import os
import subprocess
import bpy
import re
import sys

from .util import init_env
from .util import get_path_list
from .util import path_list_convert
from .util import path_win_to_unixy
from .util import user_path
from .util import get_sequence_path

from .util import args_files_in_path
from bpy.props import *


def sp_optionmenu_to_string(options):
    return [(opt.attrib['value'], opt.attrib['name'],
             '') for opt in options.findall('string')]


def parse_float(fs):
    if fs is None:
        return 0.0
    return float(fs[:-1]) if 'f' in fs else float(fs)


def generate_page(sp, node, parent_name, first_level=False):
    prop_names = []
    prop_meta = {}
    # don't add the sub group to prop names,
    # they'll be gotten through recursion
    if first_level:
        param_name = 'enable' + parent_name.replace(' ', '')
        prop_names.append(param_name)
        prop_meta[param_name] = {
            'renderman_type': 'enum', 'renderman_name': param_name}
        default = parent_name == 'Diffuse'
        prop = BoolProperty(name="Enable " + parent_name,
                            default=bool(default),
                            update=update_func_with_inputs)
        setattr(node, param_name, prop)

    for sub_param in sp.findall('param') + sp.findall('page'):
        if sub_param.tag == 'page':
            name = parent_name + '.' + sub_param.attrib['name']
            sub_names, sub_meta = generate_page(sub_param, node, name)
            setattr(node, name, sub_names)
            # props.append(sub_props)
            prop_meta.update(sub_meta)
            prop_meta[name] = {'renderman_type': 'page'}
            prop_names.append(name)
            ui_label = "%s_ui_open" % name
            setattr(node, ui_label, BoolProperty(name=ui_label,
                                                 default=False))
        else:

            name, meta, prop = generate_property(sub_param)
            if name is None:
                continue

            prop_names.append(name)
            prop_meta[name] = meta
            setattr(node, name, prop)
            # If a texture is involved and not an environment texture add
            # options
            if name == "filename":
                optionsNames, optionsMeta, optionsProps = \
                    generate_txmake_options(parent_name)
                # make texoptions hider
                prop_names.append("TxMake Options")
                prop_meta["TxMake Options"] = {'renderman_type': 'page'}
                setattr(node, "TxMake Options", optionsNames)
                ui_label = "%s_ui_open" % "TxMake Options"
                setattr(node, ui_label, BoolProperty(name=ui_label,
                                                     default=False))
                prop_meta.update(optionsMeta)
                for Texname in optionsNames:
                    setattr(
                        node, Texname + "_ui_open", optionsProps[Texname])
                    setattr(node, Texname, optionsProps[Texname])

            # if name == sp.attrib['name']:
            #    name = name + '_prop'

    return prop_names, prop_meta


def class_generate_properties(node, parent_name, shaderparameters):
    prop_names = []
    prop_meta = {}
    output_meta = {}

    # pxr osl and seexpr need these to find the code
    if parent_name in ["PxrOSL", "PxrSeExpr"]:
        # Enum for internal, external type selection
        EnumName = "codetypeswitch"
        if parent_name == 'PxrOSL':
            EnumProp = EnumProperty(items=(('EXT', "External", ""),
                                           ('INT', "Internal", "")),
                                    name="Shader Location", default='INT')
        else:
            EnumProp = EnumProperty(items=(('NODE', "Node", ""),
                                           ('INT', "Internal", "")),
                                    name="Expr Location", default='NODE')

        EnumMeta = {'renderman_name': 'filename',
                    'name': 'codetypeswitch',
                    'renderman_type': 'string',
                    'default': '', 'label': 'codetypeswitch',
                    'type': 'enum', 'options': '',
                    'widget': 'mapper', '__noconnection': True}
        setattr(node, EnumName, EnumProp)
        prop_names.append(EnumName)
        prop_meta[EnumName] = EnumMeta
        # Internal file search prop
        InternalName = "internalSearch"
        InternalProp = StringProperty(name="Shader to use",
                                      description="Storage space for internal text data block",
                                      default="")
        InternalMeta = {'renderman_name': 'filename',
                        'name': 'internalSearch',
                        'renderman_type': 'string',
                        'default': '', 'label': 'internalSearch',
                        'type': 'string', 'options': '',
                        'widget': 'fileinput', '__noconnection': True}
        setattr(node, InternalName, InternalProp)
        prop_names.append(InternalName)
        prop_meta[InternalName] = InternalMeta
        # External file prop
        codeName = "shadercode"
        codeProp = StringProperty(name='External File', default='',
                                  subtype="FILE_PATH", description='')
        codeMeta = {'renderman_name': 'filename',
                    'name': 'ShaderCode', 'renderman_type': 'string',
                    'default': '', 'label': 'ShaderCode',
                    'type': 'string', 'options': '',
                    'widget': 'fileinput', '__noconnection': True}
        setattr(node, codeName, codeProp)
        prop_names.append(codeName)
        prop_meta[codeName] = codeMeta

    for sp in shaderparameters:
        if sp.tag == 'page':
            page_name = sp.attrib['name']
            first_level = parent_name == 'PxrSurface' and 'Globals' not in page_name
            sub_prop_names, sub_params_meta = generate_page(
                sp, node, page_name, first_level=first_level)
            prop_names.append(page_name)
            prop_meta[page_name] = {'renderman_type': 'page'}
            ui_label = "%s_ui_open" % page_name
            setattr(node, ui_label, BoolProperty(name=ui_label,
                                                 default=False))
            prop_meta.update(sub_params_meta)
            setattr(node, page_name, sub_prop_names)

        elif sp.tag == 'output':
            tag = sp.find('*/tag')
            renderman_type = tag.attrib['value']

            output_meta[sp.attrib['name']] = sp.attrib
            output_meta[sp.attrib['name']]['renderman_type'] = renderman_type
        else:

            name, meta, prop = generate_property(sp)
            if name is None:
                continue
            prop_names.append(name)
            prop_meta[name] = meta
            setattr(node, name, prop)
            # If a texture is involved and not an environment texture add
            # options
            if name == "filename":
                optionsNames, optionsMeta, optionsProps = \
                    generate_txmake_options(parent_name)
                # make texoptions hider
                prop_names.append("TxMake Options")
                prop_meta["TxMake Options"] = {'renderman_type': 'page'}
                setattr(node, "TxMake Options", optionsNames)
                ui_label = "%s_ui_open" % "TxMake Options"
                setattr(node, ui_label, BoolProperty(name=ui_label,
                                                     default=False))
                prop_meta.update(optionsMeta)
                for Texname in optionsNames:
                    setattr(
                        node, Texname + "_ui_open", optionsProps[Texname])
                    setattr(node, Texname, optionsProps[Texname])

    setattr(node, 'prop_names', prop_names)
    setattr(node, 'prop_meta', prop_meta)
    setattr(node, 'output_meta', output_meta)


def update_conditional_visops(node):
    for param_name, prop_meta in getattr(node, 'prop_meta').items():
        if 'conditionalVisOp' in prop_meta:
            prop_meta['hidden'] = not eval(prop_meta['conditionalVisOp'])
            if hasattr(node, 'inputs') and param_name in node.inputs:
                node.inputs[param_name].hide = not eval(prop_meta['conditionalVisOp'])

def update_func_with_inputs(self, context):
    # check if this prop is set on an input
    node = self.node if hasattr(self, 'node') else self

    if node.renderman_node_type == 'lightfilter' and context and hasattr(context, 'lamp'):
        context.lamp.renderman.update_filter_shape()

    from . import engine
    if engine.is_ipr_running():
        engine.ipr.issue_shader_edits(node=node)

    if context and hasattr(context, 'material'):
        mat = context.material
        if mat:
            node.update_mat(mat)

    # update the conditional_vis_ops
    update_conditional_visops(node)

    if node.bl_idname in ['PxrLayerPatternNode', 'PxrSurfaceBxdfNode']:
        node_add_inputs(node, node.name, node.prop_names)
    else:
        update_inputs(node)

    # set any inputs that are visible and param is hidden to hidden
    prop_meta = getattr(node, 'prop_meta')
    if hasattr(node, 'inputs'):
        for input_name, socket in node.inputs.items():
            if 'hidden' in prop_meta[input_name]:
                socket.hide = prop_meta[input_name]['hidden']


# send updates to ipr if running
def update_func(self, context):
    # check if this prop is set on an input
    node = self.node if hasattr(self, 'node') else self

    if node.renderman_node_type == 'lightfilter' and context and hasattr(context, 'lamp'):
        context.lamp.renderman.update_filter_shape()

    from . import engine
    if engine.is_ipr_running():
        engine.ipr.issue_shader_edits(node=node)

    if context and hasattr(context, 'material'):
        mat = context.material
        if mat:
            node.update_mat(mat)

    # update the conditional_vis_ops
    update_conditional_visops(node)

    # set any inputs that are visible and param is hidden to hidden
    prop_meta = getattr(node, 'prop_meta')
    if hasattr(node, 'inputs'):
        for input_name, socket in node.inputs.items():
            if 'hidden' in prop_meta[input_name] \
                    and prop_meta[input_name]['hidden'] and not socket.hide:
                socket.hide = True


def update_inputs(node):
    if node.bl_idname == 'PxrMeshLightLightNode':
        return
    for page_name in node.prop_names:
        if node.prop_meta[page_name]['renderman_type'] == 'page':
            for prop_name in getattr(node, page_name):
                if prop_name.startswith('enable'):
                    recursive_enable_inputs(node, getattr(
                        node, page_name), getattr(node, prop_name))
                    break


def recursive_enable_inputs(node, prop_names, enable=True):
    for prop_name in prop_names:
        if type(prop_name) == str and node.prop_meta[prop_name]['renderman_type'] == 'page':
            recursive_enable_inputs(node, getattr(node, prop_name), enable)
        elif prop_name in node.inputs.keys():
            node.inputs[prop_name].hide = not enable
        else:
            continue

# take a set of condtional visops and make a python string


def parse_conditional_visop(hintdict):
    op_map = {
        'notEqualTo': "!=",
        'equalTo': '==',
        'greaterThan': '>',
        'lessThan': '<'
    }
    visop = hintdict.find("string[@name='conditionalVisOp']").attrib['value']
    if visop == 'and':
        vis1op = hintdict.find(
            "string[@name='conditionalVis1Op']").attrib['value']
        vis1path = hintdict.find(
            "string[@name='conditionalVis1Path']").attrib['value']
        vis1Value = hintdict.find(
            "string[@name='conditionalVis1Value']").attrib['value']
        vis2op = hintdict.find(
            "string[@name='conditionalVis2Op']").attrib['value']
        vis2path = hintdict.find(
            "string[@name='conditionalVis2Path']").attrib['value']
        vis2Value = hintdict.find(
            "string[@name='conditionalVis2Value']").attrib['value']

        vis1 = ''
        vis2 = ''
        if vis1Value.isalpha():
            vis1 = "getattr(node, '%s') %s '%s'" % \
                (vis1path.rsplit('/', 1)[-1], op_map[vis1op], vis1Value)
        else:
            vis1 = "float(getattr(node, '%s')) %s float(%s)" % \
                (vis1path.rsplit('/', 1)[-1], op_map[vis1op], vis1Value)

        if vis2Value.isalpha():
            vis2 = "getattr(node, '%s') %s '%s'" % \
                (vis2path.rsplit('/', 1)[-1], op_map[vis2op], vis2Value)
        else:
            vis2 = "float(getattr(node, '%s')) %s float(%s)" % \
                (vis2path.rsplit('/', 1)[-1], op_map[vis2op], vis2Value)

        return "%s and %s" % (vis1, vis2)
    else:
        vispath = hintdict.find(
            "string[@name='conditionalVisPath']").attrib['value']
        visValue = hintdict.find(
            "string[@name='conditionalVisValue']").attrib['value']
        if visValue.isalpha() or not visValue:
            return "getattr(node, '%s') %s '%s'" % \
                (vispath.rsplit('/', 1)[-1], op_map[visop], visValue)
        else:
            return "float(getattr(node, '%s')) %s float(%s)" % \
                (vispath.rsplit('/', 1)[-1], op_map[visop], visValue)


def parse_conditional_visop_attrib(attrib):
    op_map = {
        'notEqualTo': "!=",
        'equalTo': '==',
        'greaterThan': '>',
        'lessThan': '<'
    }

    visop = attrib['conditionalVisOp']
    vispath = attrib['conditionalVisPath']
    visValue = attrib['conditionalVisValue']
    if visValue.isalpha() or not visValue:
        return "getattr(node, '%s') %s '%s'" % \
            (vispath.rsplit('/', 1)[-1], op_map[visop], visValue)
    else:
        return "float(getattr(node, '%s')) %s float(%s)" % \
            (vispath.rsplit('/', 1)[-1], op_map[visop], visValue)


# map args params to props
def generate_property(sp):
    options = {'ANIMATABLE'}
    param_name = sp.attrib['name']
    renderman_name = param_name
    # blender doesn't like names with __ but we save the
    # "renderman_name with the real one"
    if param_name[0] == '_':
        param_name = param_name[1:]
    if param_name[0] == '_':
        param_name = param_name[1:]

    param_label = sp.attrib['label'] if 'label' in sp.attrib else param_name
    param_widget = sp.attrib['widget'].lower() if 'widget' in sp.attrib \
        else 'default'
    # if param_widget == 'null':
    #    return (None, None, None)

    param_type = 'float'  # for default. Some args files are sloppy
    if 'type' in sp.attrib:
        param_type = sp.attrib['type']
    tags = sp.find('tags')

    param_help = ""
    param_default = sp.attrib['default'] if 'default' in sp.attrib else None

    prop_meta = sp.attrib
    if tags and tags.find('tag').attrib['value'] == "vstruct":
        param_type = 'struct'
        prop_meta['is_vstruct'] = True
    renderman_type = param_type

    update_function = update_func_with_inputs if 'enable' in param_name else update_func

    prop = None

    # set this prop as non connectable
    if 'widget' in sp.attrib.keys() and sp.attrib['widget'] in ['null', 'checkBox', 'switch']:
        prop_meta['__noconnection'] = True
    tags = sp.find('tags')
    if tags and tags.find('tag').attrib['value'] == "__nonconnection" or \
        ("connectable" in sp.attrib and
            sp.attrib['connectable'].lower() == 'false'):
        prop_meta['__noconnection'] = True

    # if has conditionalVisOps parse them
    if sp.find("hintdict[@name='conditionalVisOps']"):
        prop_meta['conditionalVisOp'] = parse_conditional_visop(
            sp.find("hintdict[@name='conditionalVisOps']"))

    # sigh, some visops are in attrib:
    elif 'conditionalVisOp' in sp.attrib:
        prop_meta['conditionalVisOp'] = parse_conditional_visop_attrib(
            sp.attrib)

    for s in sp:
        if s.tag == 'help' and s.text:
            param_help = s.text

    if 'float' in param_type:
        if 'arraySize' in sp.attrib.keys():
            if "," in sp.attrib['default']:
                param_default = tuple(float(f) for f in
                                      sp.attrib['default'].split(','))
            else:
                param_default = tuple(float(f) for f in
                                      sp.attrib['default'].split())
            prop = FloatVectorProperty(name=param_label,
                                       default=param_default, precision=3,
                                       size=len(param_default),
                                       description=param_help,
                                       update=update_function)

        else:
            param_default = parse_float(param_default)
            if param_widget == 'checkbox' or param_widget == 'switch':
                prop = BoolProperty(name=param_label,
                                    default=bool(param_default),
                                    description=param_help, update=update_function)

            elif param_widget == 'mapper':
                prop = EnumProperty(name=param_label,
                                    items=sp_optionmenu_to_string(
                                        sp.find("hintdict[@name='options']")),
                                    default=sp.attrib['default'],
                                    description=param_help, update=update_function)

            else:
                param_min = parse_float(sp.attrib['min']) if 'min' \
                    in sp.attrib else (-1.0 * sys.float_info.max)
                param_max = parse_float(sp.attrib['max']) if 'max' \
                    in sp.attrib else sys.float_info.max
                param_min = parse_float(sp.attrib['slidermin']) if 'slidermin' \
                    in sp.attrib else param_min
                param_max = parse_float(sp.attrib['slidermax']) if 'slidermax' \
                    in sp.attrib else param_max
                prop = FloatProperty(name=param_label,
                                     default=param_default, precision=3,
                                     soft_min=param_min, soft_max=param_max,
                                     description=param_help, update=update_function)
        renderman_type = 'float'

    elif param_type == 'int' or param_type == 'integer':
        if 'arraySize' in sp.attrib.keys():
            if "," in sp.attrib['default']:
                param_default = tuple(int(f) for f in
                                      sp.attrib['default'].split(','))
            else:
                param_default = tuple(int(f) for f in
                                      sp.attrib['default'].split())
            prop = IntVectorProperty(name=param_label,
                                     default=param_default,
                                     size=len(param_default),
                                     description=param_help,
                                     update=update_function)
        else:
            param_default = int(param_default) if param_default else 0
            # make invertT default 0
            if param_name == 'invertT':
                param_default = 0

            if param_widget == 'checkbox' or param_widget == 'switch':
                prop = BoolProperty(name=param_label,
                                    default=bool(param_default),
                                    description=param_help, update=update_function)

            elif param_widget == 'mapper':
                prop = EnumProperty(name=param_label,
                                    items=sp_optionmenu_to_string(
                                        sp.find("hintdict[@name='options']")),
                                    default=sp.attrib['default'],
                                    description=param_help, update=update_function)
            else:
                param_min = int(sp.attrib['min']) if 'min' in sp.attrib else 0
                param_max = int(
                    sp.attrib['max']) if 'max' in sp.attrib else 2 ** 31 - 1
                prop = IntProperty(name=param_label,
                                   default=param_default,
                                   soft_min=param_min,
                                   soft_max=param_max,
                                   description=param_help, update=update_function)
        renderman_type = 'int'

    elif param_type == 'color':
        if 'arraySize' in sp.attrib.keys():
            return (None, None, None)
        if param_default == 'null' or param_default is None:
            param_default = '0 0 0'
        param_default = [float(c) for c in
                         param_default.replace(',', ' ').split()]
        prop = FloatVectorProperty(name=param_label,
                                   default=param_default, size=3,
                                   subtype="COLOR",
                                   soft_min=0.0, soft_max=1.0,
                                   description=param_help, update=update_function)
        renderman_type = 'color'
    elif param_type == 'shader':
        param_default = ''
        prop = StringProperty(name=param_label,
                              default=param_default,
                              description=param_help, update=update_function)
        renderman_type = 'string'

    elif param_type == 'string' or param_type == 'struct':
        if param_default is None:
            param_default = ''
        # if '__' in param_name:
        #    param_name = param_name[2:]
        if param_widget == 'fileinput' or param_widget == 'assetidinput':
            prop = StringProperty(name=param_label,
                                  default=param_default, subtype="FILE_PATH",
                                  description=param_help, update=update_function)
        elif param_widget == 'mapper':
            prop = EnumProperty(name=param_label,
                                default=param_default, description=param_help,
                                items=sp_optionmenu_to_string(
                                    sp.find("hintdict[@name='options']")),
                                update=update_function)
        elif param_widget == 'popup':
            options = [(o, o, '') for o in sp.attrib['options'].split('|')]
            prop = EnumProperty(name=param_label,
                                default=param_default, description=param_help,
                                items=options, update=update_function)
        else:
            prop = StringProperty(name=param_label,
                                  default=param_default,
                                  description=param_help, update=update_function)
        renderman_type = param_type

    elif param_type == 'vector' or param_type == 'normal':
        if param_default is None:
            param_default = '0 0 0'
        param_default = [float(v) for v in param_default.split()]
        prop = FloatVectorProperty(name=param_label,
                                   default=param_default, size=3,
                                   subtype="EULER",
                                   description=param_help, update=update_function)
    elif param_type == 'point':
        if param_default is None:
            param_default = '0 0 0'
        param_default = [float(v) for v in param_default.split()]
        prop = FloatVectorProperty(name=param_label,
                                   default=param_default, size=3,
                                   subtype="XYZ",
                                   description=param_help, update=update_function)
        renderman_type = param_type
    elif param_type == 'int[2]':
        param_type = 'int'
        param_default = tuple(int(i) for i in sp.attrib['default'].split(','))
        is_array = 2
        prop = IntVectorProperty(name=param_label,
                                 default=param_default, size=2,
                                 description=param_help, update=update_function)
        renderman_type = 'int'
        prop_meta['arraySize'] = 2

    prop_meta['renderman_type'] = renderman_type
    prop_meta['renderman_name'] = renderman_name
    return (param_name, prop_meta, prop)


def generate_txmake_options(parent_name):
    optionsMeta = {}
    optionsProps = {}
    txmake = txmake_options()
    for option in txmake.index:
        optionObject = getattr(txmake, option)
        if optionObject['type'] == "bool":
            optionsMeta[optionObject["name"]] = {'renderman_name': 'ishouldnotexport',  # Proxy Meta information for the UI system. DO NOT USE FOR ANYTHING!
                                                 'name': optionObject["name"],
                                                 'renderman_type': 'bool',
                                                 'default': '',
                                                 'label': optionObject["dispName"],
                                                 'type': 'bool',
                                                 'options': '',
                                                 'widget': 'mapper',
                                                 '__noconnection': True}
            optionsProps[optionObject["name"]] = bpy.props.BoolProperty(name=optionObject[
                                                                        'dispName'], default=optionObject['default'], description=optionObject['help'])
        elif optionObject['type'] == "enum":
            optionsProps[optionObject["name"]] = EnumProperty(name=optionObject["dispName"],
                                                              default=optionObject[
                                                                  "default"],
                                                              description=optionObject[
                                                                  "help"],
                                                              items=optionObject["items"])
            optionsMeta[optionObject["name"]] = {'renderman_name': 'ishouldnotexport',
                                                 'name': optionObject["name"],
                                                 'renderman_type': 'enum',
                                                 'default': '',
                                                 'label': optionObject["dispName"],
                                                 'type': 'enum',
                                                 'options': '',
                                                 'widget': 'mapper',
                                                 '__noconnection': True}
        elif optionObject['type'] == "float":
            optionsMeta[optionObject["name"]] = {'renderman_name': 'ishouldnotexport',
                                                 'name': optionObject["name"],
                                                 'renderman_type': 'float',
                                                 'default': '',
                                                 'label': optionObject["dispName"],
                                                 'type': 'float',
                                                 'options': '',
                                                 'widget': 'mapper',
                                                 '__noconnection': True}
            optionsProps[optionObject["name"]] = FloatProperty(name=optionObject["dispName"],
                                                               default=optionObject[
                                                                   "default"],
                                                               description=optionObject["help"])
    return txmake.index, optionsMeta, optionsProps

# map types in args files to socket types
socket_map = {
    'float': 'RendermanNodeSocketFloat',
    'color': 'RendermanNodeSocketColor',
    'string': 'RendermanNodeSocketString',
    'int': 'RendermanNodeSocketInt',
    'integer': 'RendermanNodeSocketInt',
    'struct': 'RendermanNodeSocketStruct',
    'normal': 'RendermanNodeSocketVector',
    'vector': 'RendermanNodeSocketVector',
    'void': 'RendermanNodeSocketStruct',
    'vstruct': 'RendermanNodeSocketStruct',
}

# To add aditional options simply add an option name to index and then define it.
# Supported types are bool, enum and float


class txmake_options():
    index = ["smode", "tmode", "format", "dataType",
             "resize", "pattern", "sblur", "tblur"]
    smode = {'name': "smode", 'type': "enum", "default": "periodic",
             "items": [("periodic", "Periodic", ""), ("clamp", "Clamp", "")],
             "dispName": "Smode", "help": "The X dimension tiling",
             "exportType": "name"}
    tmode = {'name': "tmode", 'type': "enum", "default": "periodic",
             "items": [("periodic", "Periodic", ""), ("clamp", "Clamp", "")],
             "dispName": "Tmode", "help": "The Y dimension tiling",
             "exportType": "name"}
    format = {'name': "format", 'type': "enum", "default": "tiff",
              "items": [("pixar", "Pixar", ""), ("openexr", "OpenEXR", ""),
                        ("tiff", "TIFF", "")],
              "dispName": "Out File Type",
              "help": "The type of output image that txmake creates",
              "exportType": "name"}
    dataType = {'name': "dataType", 'type': "enum", "default": "float",
                "items": [("float", "Float", ""), ("byte", "Byte", ""),
                          ("short", "Short", ""), ("half", "Half", "")],
                "dispName": "Data Type",
                "help": "The data storage txmake uses",
                "exportType": "noname"}
    resize = {'name': "resize", 'type': "enum", "default": "up-",
              "items": [("up", "Up", ""), ("down", "Down", ""),
                        ("up-", "Up-(0-1)", ""), ("down-", "Down-(0-1)", ""),
                        ("round", "Round", ""), ("round-", "Round-(0-1)", ""),
                        ("none", "None", "")],
              "dispName": "Type of resizing",
              "help": "The type of resizing flag to pass to txmake",
              "exportType": "name"}

    sblur = {'name': "sblur", 'type': "float", 'default': 1.0, 'dispName': "Sblur",
             'help': "Amount of X blur applied to texture.",
             'exportType': "name"}
    tblur = {'name': "tblur", 'type': "float", 'default': 1.0, 'dispName': "Tblur",
             'help': "Amount of Y blur applied to texture.",
             'exportType': "name"}
    pattern = {'name': "pattern", 'type': "enum", 'default': "diagonal",
               'items': [("diagonal", "Diagonal", ""), ("single", "Single", ""),
                         ("all", "All", "")],
               'dispName': "Pattern Type",
               'help': "Used to control the set of filtered texture resolutions that are generation by txmake",
               "exportType": "name"}


# This option will conflict with the option in the args file do not enable unless needed.
#   filter = {'name': "filter", 'type': "enum", 'default': "catmull-rom",
#              'items': [("point","Point",""),("box","Box",""),
#                        ("triangle","Triangle",""),("sinc","Sinc",""),
#                        ("gaussian","Gaussian",""),("catmull-rom","Catmullrom",""),
#                        ("mitchell","Mitchell",""),("cubic","Cubic",""),
#                        ("lanczos","Lanczos",""),("blackman-harris","Blackmanharris",""),
#                        ("bessel","Bessel",""),("gaussian-soft","Gaussian-soft","")],
#              'dispName': "Filter Type",
#              'help': "Type of filter to use when resizing",
#              'exportType': "name"}

def find_enable_param(params):
    for prop_name in params:
        if prop_name.startswith('enable'):
            return prop_name

# add input sockets


def node_add_inputs(node, node_name, prop_names, first_level=True, label_prefix='', remove=False):
    for name in prop_names:
        meta = node.prop_meta[name]
        param_type = meta['renderman_type']

        if name in node.inputs.keys() and remove:
            node.inputs.remove(node.inputs[name])
            continue
        elif name in node.inputs.keys():
            continue

        # if this is a page recursively add inputs
        if 'renderman_type' in meta and meta['renderman_type'] == 'page':
            if first_level and node.bl_idname in ['PxrLayerPatternNode', 'PxrSurfaceBxdfNode'] and name != 'Globals':
                # add these
                enable_param = find_enable_param(getattr(node, name))
                if enable_param and getattr(node, enable_param):
                    node_add_inputs(node, node_name, getattr(node, name),
                                    label_prefix=name + ' ',
                                    first_level=False)
                else:
                    node_add_inputs(node, node_name, getattr(node, name),
                                    label_prefix=name + ' ',
                                    first_level=False, remove=True)
                continue

            else:
                node_add_inputs(node, node_name, getattr(node, name),
                                first_level=first_level,
                                label_prefix=label_prefix, remove=remove)
                continue

        if remove:
            continue
        # # if this is not connectable don't add socket
        if param_type not in socket_map:
            continue
        if '__noconnection' in meta and meta['__noconnection']:
            continue

        param_name = name

        param_label = label_prefix + meta.get('label', param_name)

        socket = node.inputs.new(
            socket_map[param_type], param_name, param_label)
        socket.link_limit = 1

        if param_type in ['struct', 'normal', 'vector', 'vstruct', 'void']:
            socket.hide_value = True

    update_inputs(node)


# add output sockets
def node_add_outputs(node):
    for name, meta in node.output_meta.items():
        rman_type = meta['renderman_type']
        if rman_type in socket_map and 'vstructmember' not in meta:
            socket = node.outputs.new(socket_map[rman_type], name)
            socket.label = name
