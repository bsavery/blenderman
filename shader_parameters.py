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

# BBM addition end
shader_ext = 'sdl'

indent = 0


# dictionary of lamp parameters to take from blender
# if a shader requests these parameters,
# take them from blender's built in equivalents
exclude_lamp_params = {'intensity': 'energy',
                       'lightcolor': 'color',
                       'from': '',
                       'to': '',
                       'coneangle': 'spot_size',
                       }

reserved_words = ('and', 'assert', 'break', 'class', 'continue',
                  'def', 'del', 'elif', 'else', 'except',
                  'exec', 'finally', 'for', 'from', 'global',
                  'if', 'import', 'in', 'is', 'lambda',
                  'not', 'or', 'pass',	'print', 'raise',
                  'return', 'try', 'while')


def tex_source_path(tex, blender_frame):
    rm = tex.renderman
    anim = rm.anim_settings

    path = get_sequence_path(rm.file_path, blender_frame, anim)
    if path == '':
        return path
    else:
        return os.path.normpath(bpy.path.abspath(path))


def tex_optimised_path(tex, frame):
    path = tex_source_path(tex, frame)

    return os.path.splitext(path)[0] + '.tif'

# return the file path of the optimised version of
# the image texture file stored in Texture datablock


def get_texture_optpath(name, frame):
    try:
        tex = bpy.data.textures[name]
        return tex_optimised_path(tex, frame)
    except KeyError:
        return ""


def sp_optionmenu_to_string(options):
    return [(opt.attrib['value'], opt.attrib['name'],
             '') for opt in options.findall('string')]


# Custom socket type
class RendermanNodeSocket(bpy.types.NodeSocket):
    bl_idname = 'RendermanNodeSocket'
    bl_label = 'Renderman Node'

    default_value = None
    value = None
    ui_open = None
    is_array = False

    # Optional function for drawing the socket input value
    def draw(self, context, layout, node, text):
        if self.is_output or self.is_linked:
            layout.label(text)
        else:
            layout.prop(self, "value", text=text)

    def draw_color(self, context, node):
        return (0.8, 0.8, 0.5, 1)

# some args have 1.0f, some dont.  Python doesn't know what to do!


def parse_float(fs):
    return float(fs[:-1]) if 'f' in fs else float(fs)


def generate_page(sp, node):
    param_names = []
    prop_meta = {}
    props = []
    # don't add the sub group to prop names,
    # they'll be gotten through recursion
    for sub_param in sp.findall('param') + sp.findall('page'):
        if sub_param.tag == 'page':
            sub_names, sub_meta, sub_props = generate_page(sub_param, node)
            props.append(sub_names)
            props.append(sub_props)
            prop_meta.update(sub_meta)
            prop_meta[sub_param.attrib['name']] = {'renderman_type': 'page'}
            param_names.append(sub_param.attrib['name'])
            ui_label = "%s_ui_open" % sub_param.attrib['name']
            setattr(node, ui_label, BoolProperty(name=ui_label,
                                                 default=False))
            for i in range(len(sub_names)):
                setattr(node, sub_names[i], sub_props[i])
        else:
            name, meta, prop = generate_property(sub_param)
            # another fix for sloppy args files
            if name == sp.attrib['name']:
                name = name + '_prop'
            param_names.append(name)
            prop_meta[name] = meta
            props.append(prop)

    return param_names, prop_meta, props


def class_generate_properties(node, parent_name, shaderparameters):
    prop_names = []
    prop_meta = {}
    i = 0
    for sp in shaderparameters:
        if sp.tag == 'page':
            if parent_name == "PxrOSL" or parent_name == "PxrSeExpr":
                pass
            else:
                sub_param_names, sub_params_meta, sub_props = generate_page(
                    sp, node)
                prop_names.append(sp.attrib['name'])
                prop_meta[sp.attrib['name']] = {'renderman_type': 'page'}
                setattr(node, sp.attrib['name'], sub_param_names)
                ui_label = "%s_ui_open" % sp.attrib['name']
                setattr(node, ui_label, BoolProperty(name=ui_label,
                                                     default=False))
                prop_meta.update(sub_params_meta)
                for i in range(len(sub_param_names)):
                    setattr(node, sub_param_names[i], sub_props[i])
                    if sub_param_names[i] == "filename":
                        optionsNames, optionsMeta, optionsProps = \
                            generate_txmake_options(parent_name)
                        # make texoptions hider
                        prop_names.append("texoptions")
                        prop_meta["texoptions"] = {'renderman_type': 'page'}
                        setattr(node, "texoptions", optionsNames)
                        ui_label = "%s_ui_open" % "texoptions"
                        setattr(node, ui_label, BoolProperty(name=ui_label,
                                                             default=False))
                        prop_meta.update(optionsMeta)
                        for Texname in optionsNames:
                            setattr(node, Texname + "_ui_open",
                                    optionsProps[Texname])
                            setattr(node, Texname, optionsProps[Texname])
        else:
            if (parent_name == "PxrOSL" and i == 0) or (parent_name == "PxrSeExpr" and i == 0):
                #Enum for internal, external type selection
                EnumName = "codetypeswitch"
                EnumProp = EnumProperty(items=(('EXT', "External", ""),
                                               ('INT', "Internal", "")),
                                        name="Shader Location", default='INT')
                EnumMeta = {'renderman_name': 'filename',
                            'name': 'codetypeswitch',
                            'renderman_type': 'string',
                            'default': '', 'label': 'codetypeswitch',
                            'type': 'enum', 'options': '',
                            'widget': 'mapper', 'connectable': 'false'}
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
                                'widget': 'fileinput', 'connectable': 'false'}
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
                            'widget': 'fileinput', 'connectable': 'false'}
                setattr(node, codeName, codeProp)
                prop_names.append(codeName)
                prop_meta[codeName] = codeMeta
                if parent_name == "PxrSeExpr":
                    name, meta, prop = generate_property(sp)
                    prop_names.append(name)
                    prop_meta[name] = meta
                    setattr(node, name, prop)
                #else:
                 #   getLocation = bpy.context.scene.OSLProps
                #    mataterial = 
                #    for 
                #    setattr(node, name, prop)
            else:
                name, meta, prop = generate_property(sp)
                prop_names.append(name)
                prop_meta[name] = meta
                setattr(node, name, prop)
                # If a texture is involved and not an environment texture add
                # options
                if name == "filename":
                    optionsNames, optionsMeta, optionsProps = \
                        generate_txmake_options(parent_name)
                    # make texoptions hider
                    prop_names.append("txmake_options")
                    prop_meta["txmake_options"] = {'renderman_type': 'page'}
                    setattr(node, "txmake_options", optionsNames)
                    ui_label = "%s_ui_open" % "txmake_options"
                    setattr(node, ui_label, BoolProperty(name=ui_label,
                                                         default=False))
                    prop_meta.update(optionsMeta)
                    for Texname in optionsNames:
                        setattr(
                            node, Texname + "_ui_open", optionsProps[Texname])
                        setattr(node, Texname, optionsProps[Texname])
        i += 1
    setattr(node, 'prop_names', prop_names)
    setattr(node, 'prop_meta', prop_meta)


# send updates to ipr if running
def update_func(self, context):
    from . import engine
    if engine.ipr is not None and engine.ipr.is_interactive_running:
        engine.ipr.issue_shader_edits(node=self)
    
    if context and 'material' and hasattr(context, 'material'):
        mat = context.material
        if mat:
            self.update_mat(mat)


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

    param_type = 'float'  # for default. Some args files are sloppy
    if 'type' in sp.attrib:
        param_type = sp.attrib['type']
    param_help = ""
    param_default = sp.attrib['default'] if 'default' in sp.attrib else None

    prop_meta = sp.attrib
    renderman_type = param_type
    prop = None

    if 'coshaderPort' in prop_meta and prop_meta['coshaderPort'] == 'True':
        param_type = 'shader'

    # I guess multiline tooltips never worked
    for s in sp:
        if s.tag == 'help' and s.text:
            lines = s.text.split('\n')
            for line in lines:
                param_help = param_help + line.strip(' \t\n\r')

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
                                       update=update_func)

        else:
            param_default = parse_float(param_default)
            if param_widget == 'checkbox':
                prop = BoolProperty(name=param_label,
                                    default=bool(param_default),
                                    description=param_help, update=update_func)

            elif param_widget == 'mapper':
                prop = EnumProperty(name=param_label,
                                    items=sp_optionmenu_to_string(
                                        sp.find("hintdict[@name='options']")),
                                    default=sp.attrib['default'],
                                    description=param_help, update=update_func)

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
                                     min=param_min, max=param_max,
                                     description=param_help, update=update_func)
        renderman_type = 'float'

    elif param_type == 'int' or param_type == 'integer':
        param_default = int(param_default) if param_default else 0
        if param_widget == 'checkbox':
            prop = BoolProperty(name=param_label,
                                default=bool(param_default),
                                description=param_help, update=update_func)

        elif param_widget == 'mapper':
            prop = EnumProperty(name=param_label,
                                items=sp_optionmenu_to_string(
                                    sp.find("hintdict[@name='options']")),
                                default=sp.attrib['default'],
                                description=param_help, update=update_func)
        else:
            param_min = int(sp.attrib['min']) if 'min' in sp.attrib else 0
            param_max = int(
                sp.attrib['max']) if 'max' in sp.attrib else 2 ** 31 - 1
            prop = IntProperty(name=param_label,
                               default=param_default,
                               min=param_min,
                               max=param_max,
                               description=param_help, update=update_func)
        renderman_type = 'int'

    elif param_type == 'color':
        if param_default == 'null':
            param_default = '0 0 0'
        param_default = [float(c) for c in
                         param_default.replace(',', ' ').split()]
        prop = FloatVectorProperty(name=param_label,
                                   default=param_default, size=3,
                                   subtype="COLOR",
                                   soft_min=0.0, soft_max=1.0,
                                   description=param_help, update=update_func)
        renderman_type = 'color'
    elif param_type == 'shader':
        param_default = ''
        prop = StringProperty(name=param_label,
                              default=param_default,
                              description=param_help, update=update_func)
        renderman_type = 'string'

    elif param_type == 'string' or param_type == 'struct':
        if param_default is None:
            param_default = ''
        # if '__' in param_name:
        #    param_name = param_name[2:]
        if param_widget == 'fileinput':
            prop = StringProperty(name=param_label,
                                  default=param_default, subtype="FILE_PATH",
                                  description=param_help, update=update_func)
        elif param_widget == 'mapper':
            prop = EnumProperty(name=param_label,
                                default=param_default, description=param_help,
                                items=sp_optionmenu_to_string(
                                    sp.find("hintdict[@name='options']")),
                                update=update_func)
        elif param_widget == 'popup':
            options = [(o, o, '') for o in sp.attrib['options'].split('|')]
            prop = EnumProperty(name=param_label,
                                default=param_default, description=param_help,
                                items=options, update=update_func)
        else:
            prop = StringProperty(name=param_label,
                                  default=param_default,
                                  description=param_help, update=update_func)
        renderman_type = param_type

    elif param_type == 'vector' or param_type == 'normal':
        if param_default is None:
            param_default = '0 0 0'
        param_default = [float(v) for v in param_default.split()]
        prop = FloatVectorProperty(name=param_label,
                                   default=param_default, size=3,
                                   subtype="EULER",
                                   description=param_help, update=update_func)
        renderman_type = param_type
    elif param_type == 'int[2]':
        param_type = 'int'
        param_default = tuple(int(i) for i in sp.attrib['default'].split(','))
        is_array = 2
        prop = IntVectorProperty(name=param_label,
                                 default=param_default, size=2,
                                 description=param_help, update=update_func)
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
            optionsMeta[optionObject["name"]] = {'renderman_name' : 'filename', #Proxy Meta information for the UI system. DO NOT USE FOR ANYTHING!
                                                 'name' : optionObject["name"], 
                                                 'renderman_type' : 'bool' , 
                                                 'default' : '', 
                                                 'label' : optionObject["dispName"], 
                                                 'type': 'bool', 
                                                 'options': '', 
                                                 'widget' : 'mapper', 
                                                 'connectable' : 'false'}
            optionsProps[optionObject["name"]] = bpy.props.BoolProperty(name = optionObject['dispName'], default = optionObject['default'], description = optionObject['help'])
        elif optionObject['type'] == "enum":
            optionsProps[optionObject["name"]] = EnumProperty(name=optionObject["dispName"],
                                                              default=optionObject["default"], 
                                                              description=optionObject["help"],
                                                              items=optionObject["items"])
            optionsMeta[optionObject["name"]] = {'renderman_name': 'filename', 
                                                 'name': optionObject["name"],
                                                 'renderman_type': 'enum',
                                                 'default': '',
                                                 'label': optionObject["dispName"],
                                                 'type': 'enum', 
                                                 'options': '',
                                                 'widget': 'mapper',
                                                 'connectable': 'false'}
        elif optionObject['type'] == "float":
            optionsMeta[optionObject["name"]] = {'renderman_name': 'filename', 
                                                 'name': optionObject["name"],
                                                 'renderman_type': 'float',
                                                 'default': '',
                                                 'label': optionObject["dispName"],
                                                 'type': 'float', 
                                                 'options': '',
                                                 'widget': 'mapper',
                                                 'connectable': 'false'}
            optionsProps[optionObject["name"]] = FloatProperty(name=optionObject["dispName"],
                                                               default=optionObject["default"],
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
    'void': 'RendermanNodeSocketStruct'
}

# To add aditional options simply add an option name to index and then define it.
# Supported types are bool, enum and float
class txmake_options():
    index = ["smode", "tmode", "format", "dataType", "resize", "pattern", "sblur", "tblur"]
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
    resize = {'name': "resize", 'type':"enum", "default": "up-",
              "items": [("up", "Up", ""), ("down", "Down", ""),
                        ("up-", "Up-(0-1)", ""), ("down-", "Down-(0-1)", ""),
                        ("round", "Round", ""), ("round-", "Round-(0-1)", ""),
                        ("none", "None", "")],
              "dispName": "Type of resizing",
              "help": "The type of resizing flag to pass to txmake",
              "exportType": "name"}


    sblur = {'name': "sblur" , 'type': "float", 'default': 1.0, 'dispName': "Sblur",
             'help': "Amount of X blur applied to texture.",
             'exportType': "name"}
    tblur = {'name': "tblur" , 'type': "float", 'default': 1.0, 'dispName': "Tblur",
             'help': "Amount of Y blur applied to texture.",
             'exportType': "name"}
    pattern = {'name': "pattern", 'type': "enum", 'default': "diagonal",
               'items': [("diagonal","Diagonal",""), ("single","Single",""),
                         ("all","All","")],
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

    

# add input sockets
def node_add_inputs(node, node_name, shaderparameters):
    for sp in shaderparameters:
        # if this is a page recursively add inputs
        if sp.tag == 'page':
            node_add_inputs(node, node_name, sp.findall('param') + sp.findall('page'))
            continue
        # if this is not connectable don't add socket
        tags = sp.find('tags')
        if tags and tags.find('tag').attrib['value'] == "__nonconnection" or \
            ("connectable" in sp.attrib and
                sp.attrib['connectable'].lower() == 'false'):
            continue

        param_type = 'float'
        if 'type' in sp.attrib.keys():
            param_type = sp.attrib['type']
        param_name = sp.attrib['name']
        socket = node.inputs.new(socket_map[param_type], param_name)
        socket.link_limit = 1

        # for struct type look for the type of connection
        if param_type == 'struct' and tags:
            tag = tags.findall('tag')[-1]
            if 'and' in tag.attrib['value']:
                socket.struct_type = tag.attrib['value'].split()[-1]
            else:
                socket.struct_type = tag.attrib['value']


# add output sockets
def node_add_outputs(node, shaderparameters):

    # Generate RNA properties for each shader parameter
    for sp in shaderparameters:
        param_name = sp.attrib['name']
        tag = sp.find('*/tag')
        socket = node.outputs.new(socket_map[tag.attrib['value']], param_name)

        # for struct type look for the type of connection
        if tag.attrib['value'] == 'struct':
            socket.struct_type = sp.findall('*/tag')[-1].attrib['value']
