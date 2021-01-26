"""Classes to parse and store node descriptions.
"""

# ##### BEGIN MIT LICENSE BLOCK #####
#
# Copyright (c) 2015 - 2021 Pixar
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

# TODO: NodeDesc.node_type should be an enum.

# pylint: disable=import-error
# pylint: disable=relative-import
# pylint: disable=invalid-name
# pylint: disable=superfluous-parens

import os
import re
import subprocess
import xml.dom.minidom as mx
from collections import OrderedDict

from .filepath import FilePath
from . import json_file

VALID_TYPES = ['int', 'int2', 'float', 'float2', 'color', 'point', 'vector',
               'normal', 'matrix', 'string', 'struct', 'lightfilter',
               'message', 'displayfilter', 'samplefilter', 'bxdf']
FLOAT3 = ['color', 'point', 'vector', 'normal']
FLOATX = ['color', 'point', 'vector', 'normal', 'matrix']
DATA_TYPE_WIDTH = {'int': 1, 'float': 1,
                   'color': 3, 'point': 3, 'vector': 3, 'normal': 3,
                   'matrix': 16, 'string': 0, 'struct': 0}
OPTIONAL_ATTRS = ['URL', 'buttonText', 'conditionalVisOp', 'conditionalVisPath',
                  'conditionalVisValue',
                  'conditionalVisLeft', 'conditionalVisRight',
                  'connectable', 'digits',
                  'label', 'match', 'max', 'min', 'riattr', 'riopt',
                  'scriptText', 'sensitivity', 'slider', 'slidermax',
                  'slidermin', 'sliderMin', 'sliderMax', 'syntax', 'tag', 'units',
                  'vstructConditionalExpr', 'vstructmember', 'hidden', 'uiStruct', 'readOnly',
                  'editable', 'lockgeom']
INTERP_MAYA = {'none': 0,
               'linear': 1,
               'smooth': 2,
               'spline': 3}
INTERP_RMAN_TO_MAYA = {'linear': 1,
                       'catmull-rom': 2,
                       'bspline': 3,
                       'constant': 0,
                       'none': 0}
COND_VIS_OP = {'equalTo': '==',
               'notEqualTo': '!=',
               'greaterThan': '>',
               'greaterThanOrEqualTo': '>=',
               'lessThan': '<',
               'lessThanOrEqualTo': '<=',
               'regex': '~=',
               'in': 'in'}

DEFAULT_VALUE = {'float': 0.0, 'float2': (0.0, 0.0), 'float3': (0.0, 0.0, 0.0),
                 'int': 0, 'int2': (0, 0),
                 'color': (0.0, 0.0, 0.0), 'normal': (0.0, 0.0, 0.0),
                 'vector': (0.0, 0.0, 0.0), 'point': (0.0, 0.0, 0.0),
                 'string': '',
                 'matrix': (1.0, 0.0, 0.0, 0.0,  0.0, 1.0, 0.0, 0.0,
                            0.0, 0.0, 1.0, 0.0,  0.0, 0.0, 0.0, 1.0),
                 'message': None}
CFLOAT_REGEXP = re.compile(r'[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?f').match
PAGE_SEP = '|'
# if eval()-ed, will return a type object ("<type 'int'>") rather than "int"
PYTYPES = ['int', 'float']

def _is_alpha_string(s):
    hasAlpha = False
    for c in s:
        if (c.isalpha() or c.isspace()):
            hasAlpha = True
            break
    return hasAlpha

def osl_metadatum(metadict, name, default=None):
    """Return metadatum value, based on oslquery's return format."""
    if name in metadict:
        return metadict[name]['default']
    else:
        return default    

class NodeDescError(Exception):
    """Custom exception for NodeDesc-related errors."""

    def __init__(self, value):
        self.value = 'NodeDesc Error: %s' % value

    def __str__(self):
        return str(self.value)


class NodeDescIgnore(Exception):
    """Raised when a node description should be ignored."""

    def __init__(self, value):
        self.value = 'NodeDesc Ignore: %s' % value

    def __str__(self):
        return str(self.value)


def safe_value_eval(raw_val):
    val = raw_val
    try:
        val = eval(raw_val)
    except:
        val = raw_val
    else:
        if isinstance(val, type):
            # catch case where 'int' (or any other python type)
            # was evaled and we got a python type object.
            val = raw_val
    return val


def validate_type(pname, ptype):
    if ptype in VALID_TYPES:
        return ptype
    raise NodeDescError('param %r has invalid type: %r' % (pname, ptype))


def startup_info():
    """Returns a Windows-only object to make sure tasks launched through
    subprocess don't open a cmd window.
    NOTE: this will be moved to another module later.

    Returns:
        subprocess.STARTUPINFO -- the properly configured object if we are on
                                  Windows, otherwise None
    """
    startupinfo = None
    if os.name is 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return startupinfo


class DescFormat(object):
    """Encodes the original format of a node description.

    Attributes:
        Json (int): JSON file
        Osl (int): OSL (*.oso) object file.
        Xml (int): args file.
    """
    Xml = 0
    Osl = 1
    Json = 2


class DescPropType(object):
    """Encodes the type of property.

    Attributes:
        Attribute (str): RIB attribute attached to the node
        Output (str): Output parameter
        Param (str): Input parameter
    """
    Param = 'param'
    Output = 'output'
    Attribute = 'attr'


class DescNodeType(object):
    kBxdf = 'bxdf'
    kDisplacement = 'displacement'
    kDisplayFilter = 'displayfilter'
    kIntegrator = 'integrator'
    kLight = 'light'
    kLightFilter = 'lightfilter'
    kPattern = 'pattern'
    kProjection = 'projection'
    kSampleFilter = 'samplefilter'
    kGlobals = 'rmanglobals'
    kDisplayChannel = 'displaychannel'
    kDisplay = 'display'


OSL_TO_RIS_TYPES = {'surface': DescNodeType.kBxdf,
                    'displacement': DescNodeType.kDisplacement,
                    'volume': DescNodeType.kBxdf,
                    'shader': DescNodeType.kPattern}

def vis_ops_func(ops, trigger_params):
    """Limited (non-recursive) implementation of conditional visibility
    parsing for katana-style hintdict.

    Args:
    - ops (dict): the conditional visibility arguments.
    - trigger_params (list): a list to be filled with param names used by
    conditional expressions
    FIXME: regex keyword not implemented.
    """
    try:
        pfx = 'conditionalVis'
        op = ops[pfx + 'Op']
        if op in ['and', 'or']:
            # find all left/right sub expressions

            # first, standard left/right
            pair_prefixes = [(ops[pfx + 'Left'], ops[pfx + 'Right'])]
            # second, any additional pairs
            i = 2
            while True:
                left2 = ops.get('%s%dLeft' % (pfx, i), None)
                if left2:
                    right2 = ops.get('%s%dRight' % (pfx, i), None)
                    pair_prefixes.append((left2, right2))
                    i += 1
                else:
                    break

            # expression string to append to...
            expr = ''

            # for each left/right prefixes
            for lpfx, rpfx in pair_prefixes:
                # left expr
                lop = ops[lpfx + 'Op']
                lattr = ops[lpfx + 'Path'].split('/')[-1]
                value = repr(ops[lpfx + 'Value']).replace("'", "")
                cond_op = COND_VIS_OP[lop]
                if value == 'NoneType':
                    lexpr = ('getattr(node, "%s") %s None' %
                            (lattr, cond_op))                    
                elif _is_alpha_string(value) or value.isalpha() or value == '' or value in VALID_TYPES:
                    lexpr = ('getattr(node, "%s") %s "%s"' %
                            (lattr, cond_op,
                            value))
                elif cond_op == 'in':
                    value = value.split(",")
                    lexpr = ('str(getattr(node, "%s")) %s %s' %
                            (lattr, cond_op,
                            str(value)))                      
                else:
                    lexpr = ('float(getattr(node, "%s")) %s float(%s)' %
                            (lattr, cond_op,
                            value))                    
                trigger_params.append(lattr)
                # right expr
                rop = ops[rpfx + 'Op']
                if rop in ['and', 'or']:
                    expr += '(%s) %s ' % (lexpr, rop)
                else:
                    rattr = ops[rpfx + 'Path'].split('/')[-1]
                    value = repr(ops[rpfx + 'Value']).replace("'", "")
                    cond_op = COND_VIS_OP[rop]
                    if value == 'NoneType':
                        rexpr = ('getattr(node, "%s") %s None' %
                                (rattr, cond_op))       
                    elif _is_alpha_string(value) or value.isalpha() or value == '' or value in VALID_TYPES:
                        rexpr = ('getattr(node, "%s") %s "%s"' %
                                (rattr, cond_op,
                                value))         
                    elif cond_op == 'in':
                        value = value.split(",")
                        lexpr = ('str(getattr(node, "%s")) %s %s' %
                                (rattr, cond_op,
                            str(value)))                               
                    else:
                        rexpr = ('float(getattr(node, "%s")) %s float(%s)' %
                                (rattr, cond_op,
                                value))
                    trigger_params.append(rattr)
                    # final expr
                    expr += '%s %s %s' % (lexpr, op, rexpr)
        else:
            # simple value check on a single param
            sattr = ops[pfx + 'Path'].split('/')[-1]
            value = repr(ops[pfx + 'Value']).replace("'", "")
            cond_op = COND_VIS_OP[op]
            if value == 'NoneType':
                expr = ('getattr(node, "%s") %s None' %
                        (sattr, cond_op))                
            elif _is_alpha_string(value) or value.isalpha() or value == '' or value in VALID_TYPES:
                expr = ('getattr(node, "%s") %s "%s"' %
                        (sattr, cond_op,
                            value))
            elif cond_op == 'in':
                value = value.split(",")
                expr = ('str(getattr(node, "%s")) %s %s' %
                        (sattr, cond_op,
                        str(value)))                                              
            else:
                expr = ('float(getattr(node, "%s")) %s float(%s)' %
                        (sattr, cond_op,
                            value))
            trigger_params.append(sattr)

        return expr
    except Exception as err:
        print('PLEASE REPORT: vis_ops_func() failed ' + '-' * 30)
        for key, val in ops.iteritems():
            print('  %r: %r' % (key, val))
        print('err = %s' % str(err))
        print('-' * 50)
        return 'True'

class NodeDescParam(object):
    """A base class for parameter descriptions. It has only 2 mandatory attributes:
    name and type. Defaults, array and ui configuration attributes are all
    optional.

    Attributes:
        name (str): the parameter's name
        type (TYPE): the parameter's data type
    """

    staticCondVisAttributes = ['%sPath', '%sValue',
                               '%sLeft', '%sRight']
    dynCondVisAttributes = ['%sOp', '%sPath', '%sValue']

    def __init__(self):
        self._name = None
        self.type = None
        self.default = None
        self.has_ui_struct = False

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        """attributes can take the form 'visibility:camera'. This is not a legal
        maya name, so we adopt the old rfm format for backward compatibility."""
        self._name = value
        if value and ':' in value:
            if value == "visibility:camera":
                # primaryVisibility is the standard maya attr that means
                # the same as visibility:camera, so go with that rather than
                # having two attrs that should do the same thing.
                self._name = 'primaryVisibility'
            else:
                self._name = 'rman__riattr__' + '_'.join(value.split(':'))

    def get_help(self):
        """Returns the help string or a minimal parameter description (type and
        name) if not available.
        NOTE: the help string may have been re-formated during description
        parsing.

        Returns:
            str: The help string.
        """
        try:
            return self.help
        except:
            return '%s %s' % (self.type, self.name)

    def is_array(self):
        # pylint: disable=no-member
        return self.size is not None

    def finalize(self):
        """Post-process the description data:
        - make some attribute types non-connectable (int, matrix)
        - escapes some characters for maya consumption.
        - processes conditional visibility.

        Returns:
            None
        """
        if self.default is None:
            self.default = DEFAULT_VALUE.get(self.type, None)

        # pylint: disable=no-member
        # if self.type in ['int', 'matrix']:
        #     # these are NEVER connectable
        #     self.connectable = False
        # else:
        if hasattr(self, 'connectable'):
            # make it a boolean value
            if str(self.connectable) == 'false':
                self.connectable = False
            elif str(self.connectable) == 'true':
                self.connectable = True
            else:
                self.connectable = bool(self.connectable)

        if hasattr(self, 'help'):
            self.help = self.help.replace('"', "'")

        if self.type in ['float', 'int']:
            if hasattr(self, 'min'):
                # set a slidermax if not defined.
                if not hasattr(self, 'max') and not hasattr(self, 'slidermax'):
                    setattr(self, 'slidermax', max(self.default, 1.0))
            elif hasattr(self, 'slider'):
                # set a 0->1 soft limit if none defined.
                if not hasattr(self, 'min') and not hasattr(self, 'slidermin'):
                    setattr(self, 'slidermin', min(self.default, 0.0))
                if not hasattr(self, 'max') and not hasattr(self, 'slidermax'):
                    setattr(self, 'slidermax', max(self.default, 1.0))

        # Parse conditional visibility
        # What a mess. They can appear in a hintdict or as separate attributes.
        # Pack the data in the conditionalVisOps dict.
        if hasattr(self, 'conditionalVisOp'):
            setattr(self, 'conditionalVisOps', {})

            ops = ['conditionalVis']
            self.conditionalVisOps['conditionalVisOp'] = getattr(self, 'conditionalVisOp')
            while len(ops):
                op = ops.pop()
                for fmt in self.staticCondVisAttributes:
                    key = fmt % op
                    try:
                        self.conditionalVisOps[key] = getattr(self, key)
                    except AttributeError:
                        pass
                for side in ['%sLeft' % op, '%sRight' % op]:
                    if side in self.conditionalVisOps:
                        val = self.conditionalVisOps[side]
                        ops.append(val)
                        for fmt in self.dynCondVisAttributes:
                            key = fmt % val
                            try:
                                self.conditionalVisOps[key] = getattr(self, key)
                            except AttributeError:
                                pass

        if hasattr(self, 'conditionalVisOps'):
            self.parse_vis_ops()

    def cond_vis_trigger_params(self):
        try:
            return self.triggerParams
        except:
            return []

    def parse_vis_ops(self):
        """Limited (non-recursive) implementation of conditional visibility
        parsing for katana-style hintdict.
        FIXME: regex keyword not implemented.
        """
        # we accumulate a list of param names the visibility depends on to be
        # able to to have them trigger a refresh.
        # pylint: disable=no-member
        if not hasattr(self, 'triggerParams'):
            self.triggerParams = []

        ops = self.conditionalVisOps
        self.conditionalVisOps['expr'] = vis_ops_func(ops, self.triggerParams)

    def _format_help(self):
        self.help = '%s (%s)' % (self.name, self.type)

    def __str__(self):
        """Encodes the data in a human-readable form.
        Used for serialisation.

        Returns:
            str: A readble version of the object's contents.
        """
        s = 'Param: %s\n' % self.name
        d = vars(self)
        for k, v in d.items():
            s += '| %s: %s\n' % (k, repr(v))
        return s

    def __repr__(self):
        return '%s object at %s (name: %s)' % (self.__class__, hex(id(self)),
                                               self.name)


class NodeDescParamXML(NodeDescParam):
    """A parameter description from an args/XML file.
    """

    def __init__(self, pdata):
        """Parse the xml data and store it.

        Args:
            pdata (xml): A xml element.
        """
        super(NodeDescParamXML, self).__init__()
        self.name = pdata.getAttribute('name')
        self.type = validate_type(self.name, self._set_type(pdata))
        self._set_optional_attributes(pdata)
        self.finalize()

    def _set_type(self, pdata):
        """Sets the data type of the parameter. It may return None if the type
        could not be found.

        Args:
            pdata (xml): A xml element.

        Returns:
            str: The data type ('float', 'color', etc)
        """
        if pdata.hasAttribute('type'):
            return pdata.getAttribute('type')
        else:
            tags = pdata.getElementsByTagName('tags')
            if tags:
                tag = tags[0].getElementsByTagName('tag')
                for t in tag:
                    if t.hasAttribute('value'):
                        return t.getAttribute('value')
            else:
                # some args files have something like:
                # <output name="outColor" tag="color|vector|normal|point"/>
                tag = pdata.getAttribute('tag')
                if tag:
                    tags = tag.split('|')
                    if tags:
                        for t in tags:
                            return t
        return None

    def _set_size(self, pdata):
        """Sets the attribute size:
        * None: this is a simple non-array attribute.
        * -1: this is a dynamic array.
        * [0-9]+: this is a fixed size array.

        Args:
            pdata (cml): A xml element

        Returns:
            int or None: The size of the array.
        """
        if pdata.hasAttribute('isDynamicArray'):
                # dynamic array
            if pdata.getAttribute('isDynamicArray') != '0':
                self.size = - 1
            elif pdata.hasAttribute('arraySize'):
                self.size = int(pdata.getAttribute('arraySize'))
        elif pdata.hasAttribute('arraySize'):
            # fixed-size array
            self.size = int(pdata.getAttribute('arraySize'))
        else:
            # non-array
            self.size = None

    def _set_default(self, pdata):
        """Store default value(s).

        Array storage format is as follow:
        float: [v0, v1, ...]
        float3: [(v0, v1, v2), ...]
        matrices: [(v0, v1, ..., v15), ...]

        Args:
            pdata (xml): xml element

        Returns:
            any: a list, list of tuples or single variable
        """
        if not pdata.hasAttribute('default'):
            return
        if self.type == 'struct':
            self.default = ""
            return
        pdefault = pdata.getAttribute('default')
        pdefault = self._handle_c_style_floats(pdefault)
        if 'string' not in self.type:
            psize = getattr(self, 'size', None)
            if psize is None:
                # non-array numerical values
                self.default = eval(pdefault.replace(' ', ','))
            else:
                # arrays
                vals = pdefault.split()
                strToNum = float
                if self.type == 'int':
                    strToNum = int
                twidth = DATA_TYPE_WIDTH[self.type]
                self.default = []
                if twidth > 1:
                    for i in range(0, len(vals), twidth):
                        t = []
                        for j in range(twidth):
                            t.append(strToNum(vals[i + j]))
                        self.default.append(tuple(t))
                else:
                    for v in vals:
                        self.default.append(strToNum(v))
                # conform defaults to array size
                if len(self.default) == 1 and psize > 0:
                    self.default = self.default * psize
        else:
            # strings: there is no provision for string array defaults
            # in katana.
            self.default = pdefault

    def _set_page(self, pdata):
        """Store the page path for this param.
        The page will be stored as a path: specular/Advanced/Anisotropy

        Args:
            pdata (xml): xml element
        """
        self.page = ''
        p_node = pdata.parentNode
        # consider the open state only for the innermost page.
        if p_node.hasAttribute('open'):
            self.page_open = (
                str(p_node.getAttribute('open')).lower() == 'true')
        # go up the page hierarchy to build the full path to this page.
        while p_node.tagName == 'page':
            self.page = p_node.getAttribute('name') + PAGE_SEP + self.page
            p_node = p_node.parentNode
        if self.page[-1:] == PAGE_SEP:
            self.page = self.page[:-1]

    def _set_help(self, pdata):
        has_help = True
        help_node = pdata.getElementsByTagName('help')
        if help_node:
            self.help = help_node[0].firstChild.data.strip('"')
        elif pdata.hasAttribute('help'):
            self.help = pdata.getAttribute('help').strip('"')
        else:
            has_help = False
        if has_help:
            self.help = re.sub(r'\n\s+', ' ', self.help.strip())
        # self._format_help()

    def _set_widget(self, pdata):

        # support popup options defined as:
        #   options="first option|second option|third option"
        # as well as dicts:
        #   options="one:1|two:2|three:3"
        if pdata.hasAttribute('options'):
            tmp = pdata.getAttribute('options')
            self.options = OrderedDict()
            if ':' in tmp:
                for w in tmp.split('|'):
                    kw = w.split(':')
                    try:
                        self.options[kw[0]] = kw[1]
                    except ValueError:
                        self.options[kw[0]] = kw[0]
            elif '|' in tmp:
                for o in tmp.split('|'):
                    self.options[o] = o
            else:
                self.options[tmp] = tmp

        if pdata.hasAttribute('widget'):
            self.widget = pdata.getAttribute('widget')
            if self.widget == 'null' and self.name.endswith('_Interpolation'):
                # Store an enum with maya-compatible values.
                self.interpEnum = {
                    k: INTERP_RMAN_TO_MAYA[k] for k in self.options}
                self.interpDefault = INTERP_RMAN_TO_MAYA[self.default]

        # or as hintlist:
        # # <hintlist name = "options" >
        #     <string value="0.0"/>
        #     <string value="0.5"/>
        # </hintlist>
        # NOTE: in the example above, the result will be:
        #   self.options = ['0.0', '0.5']
        # because the list members are defined as 'string' values.
        hintlist = pdata.getElementsByTagName('hintlist')
        for hl in hintlist:
            hname = hl.getAttribute('name')
            elmts = hl.getElementsByTagName('*')
            val_list = []
            for e in elmts:
                etype = e.tagName
                raw_val = e.getAttribute('value')
                val = raw_val
                if etype in FLOATX:
                    val = tuple([float(v) for v in raw_val.split()])
                elif etype != 'string':
                    val = safe_value_eval(raw_val)
                val_list.append(val)
            setattr(self, hname, val_list)

        # hintdict is a special case because it is not a simple attribute.
        # support multiple hintdicts and store them under their name.
        # This includes 'options', 'conditionalVisOps', etc
        hintdict = pdata.getElementsByTagName('hintdict')
        for hd in hintdict:
            dict_name = hd.getAttribute('name')
            setattr(self, dict_name, OrderedDict())
            elmts = hd.getElementsByTagName('*')
            this_attr = eval('self.' + dict_name)
            for e in elmts:
                elmt_type = e.tagName
                # print('elmt_type = %s' % elmt_type)
                key = e.getAttribute('name')
                raw_val = e.getAttribute('value')
                val = raw_val
                if elmt_type in FLOATX:
                    val = tuple([float(v) for v in raw_val.split()])
                elif elmt_type not in PYTYPES:
                    val = safe_value_eval(raw_val)
                this_attr[key] = val

        if pdata.hasAttribute('widget'):
            self.widget = pdata.getAttribute('widget')
            if self.widget == 'null' and self.name.endswith('_Interpolation'):
                # Store an enum with maya-compatible values.
                if not isinstance(self.options, list):
                    # We are expecting a list, so turn this into a list of size 1.
                    self.options = [self.options]

    def _set_optional_attributes(self, pdata):
        self._set_size(pdata)
        self._set_default(pdata)
        self._set_widget(pdata)
        self._set_page(pdata)
        self._set_help(pdata)
        # optional attributes
        for attr in OPTIONAL_ATTRS:
            if pdata.hasAttribute(attr):
                val = pdata.getAttribute(attr)
                val = self._handle_c_style_floats(val)
                if self.type in FLOAT3 and self.size is None:
                    if 'min' in attr or 'max' in attr:  # 'min' or 'slidermin'
                        val = tuple([float(v) for v in val.split()])
                try:
                    val = eval(val)
                except:
                    pass
                setattr(self, attr, val)

        def __setAttrNamed(attr):
            if pdata.hasAttribute(attr):
                val = pdata.getAttribute(attr)
                try:
                    val = eval(val)
                except:
                    pass
                setattr(self, attr, val)

        ops = []
        if hasattr(self, 'conditionalVisOp'):
            ops.append('conditionalVis')

        while len(ops):
            cv = ops.pop()
            __setAttrNamed(cv+"Value")
            __setAttrNamed(cv+"Path")
            __setAttrNamed(cv+"Left")
            __setAttrNamed(cv+"Right")
            if hasattr(self,'%sLeft' % cv):
                leftAttrName = getattr(self,'%sLeft' % cv,None)
                __setAttrNamed(leftAttrName+"Op")
                if hasattr(self, leftAttrName+"Op"):
                    ops.append(leftAttrName)

            if hasattr(self,'%sRight' % cv):
                rightAttrName = getattr(self,'%sRight' % cv,None)
                __setAttrNamed(rightAttrName+"Op")
                if hasattr(self, rightAttrName+"Op"):
                    ops.append(rightAttrName)

        # check if float param used as vstruct port
        tags = pdata.getElementsByTagName('tags')
        if len(tags):
            elmts = tags[0].getElementsByTagName('*')
            for e in elmts:
                if e.hasAttribute('value'):
                    if e.getAttribute('value') == 'vstruct':
                        self.vstruct = True
                        break

        # widget sanity check
        # Katana doesn't support widget variants (e.g. int->checkBox) for array
        # attributes, so we will set the widget to "default" instead of
        # dynamicArray.
        try:
            # there is no garantee a widget attribute exists.
            if self.widget == 'dynamicArray':
                self.widget = 'default'
        except:
            pass

        # mark for desc
        if getattr(self, 'uiStruct', None):
            self.has_ui_struct = True

    def __str__(self):
        return super(NodeDescParamXML, self).__str__()

    def __repr__(self):
        return '%s object at %s (name: %s)' % (self.__class__, hex(id(self)),
                                               self.name)

    def _handle_c_style_floats(self, val):
        """
        Make sure a float value from an args file doesn't contain a 'f',
        like in '0.001f'.
        """
        if CFLOAT_REGEXP(str(val)):
            return val.replace('f', '')
        else:
            return val


class NodeDescParamOSL(NodeDescParam):

    def __init__(self, pdata):
        super(NodeDescParamOSL, self).__init__()
        metadict = {d['name']: d for d in pdata['metadata']}        
        self.category = self._set_category(pdata)
        self.name = self._set_name(pdata)
        self.type = validate_type(self.name, self._set_type(pdata))
        self._set_optional_attributes(pdata, metadict)
        if hasattr(self, 'sliderMin'):
            self.slidermin = self.sliderMin
        if hasattr(self, 'sliderMax'):
            self.slidermax = self.sliderMax
        self.finalize()

    def _set_category(self, pdata):
        # NOTE: can we support attributes in OSL metadata ?
        if pdata['isoutput']:
            # this is a struct parameter
            return DescPropType.Output
        else:
            return DescPropType.Param



    def _set_name(self, pdata):
        return pdata['name']


    def _set_type(self, pdata):
        if pdata['isstruct']:
            self.struct_name = pdata['structname']
            return 'struct'
        return pdata['type'].split('[')[0]        

    def _set_size(self, pdata):
        if pdata['varlenarray']:
            self.size = len(pdata['default'])
        elif pdata['arraylen'] > 0:
            self.size = pdata['arraylen']
        else:
            self.size = None        

    def _set_default(self, pdata):
        self.default = pdata['default']        

    def _set_page(self, metadict):
        # NOTE: no provision for the page's open state at startup in OSL.
        if 'page' in metadict:
            self.page = osl_metadatum(metadict, 'page', None).replace('.', PAGE_SEP)
            # the page's open state at startup in OSL.
            # Should be set on the first param of the page.
            self.page_open = osl_metadatum(metadict, 'page_open', False)        

    def _set_help(self, metadict):
        self.help = osl_metadatum(metadict, 'help', '').replace('  ', ' ')
        self._format_help()        

    def _set_widget(self, metadict):
        # hintdict
        if 'options' in metadict:
            self.options = OrderedDict()
            olist = osl_metadatum(metadict, 'options').split('|')
            key = None
            val = None
            for opt in olist:
                if ':' in opt:
                    key, val = opt.rsplit(':', 1)  # consider only first ':'
                else:
                    key = opt
                    val = opt
                try:
                    self.options[key] = safe_value_eval(val)
                except BaseException:
                    self.options[key] = val

        if 'presets' in metadict:
            self.presets = OrderedDict()
            plist = osl_metadatum(metadict, 'presets').split('|')
            for preset in plist:
                key, val = preset.split(':')
                if self.type in FLOATX:
                    self.presets[key] = tuple([float(v) for v in val.split()])
                elif self.type == 'string':
                    self.presets[key] = val
                else:
                    self.presets[key] = safe_value_eval(val)

        self.widget = osl_metadatum(metadict, 'widget', 'default')        

    def _set_optional_attributes(self, pdata, metadict):
        self._set_size(pdata)
        self._set_default(pdata)
        self._set_widget(metadict)
        self._set_page(metadict)
        self._set_help(metadict)

        def __setAttrNamed(attr_name):
            func = None
            if isinstance(attr_name, tuple):
                attr_name, func = attr_name
            if attr_name not in metadict:
                return
            val = metadict[attr_name]['default']
            # val = safe_value_eval(val)
            setattr(self, attr_name, val if not func else func(val))

        for attr in OPTIONAL_ATTRS:
            __setAttrNamed(attr)

        ops = []
        if hasattr(self, 'conditionalVisOp'):
            ops.append('conditionalVis')

        while len(ops):
            cv = ops.pop()
            __setAttrNamed(cv+"Value")
            __setAttrNamed(cv+"Path")
            __setAttrNamed(cv+"Left")
            __setAttrNamed(cv+"Right")
            if hasattr(self,'%sLeft' % cv):
                leftAttrName = getattr(self,'%sLeft' % cv,None)
                __setAttrNamed(leftAttrName+"Op")
                if hasattr(self, leftAttrName+"Op"):
                    ops.append(leftAttrName)

            if hasattr(self,'%sRight' % cv):
                rightAttrName = getattr(self,'%sRight' % cv,None)
                __setAttrNamed(rightAttrName+"Op")
                if hasattr(self, rightAttrName+"Op"):
                    ops.append(rightAttrName)

        if hasattr(self,'tag'):
            tag = getattr(self, 'tag', None)
            if tag == 'vstruct':
                self.vstruct = True

    def __str__(self):
        return super(NodeDescParamOSL, self).__str__()

    def __repr__(self):
        return '%s object at %s (name: %s)' % (self.__class__, hex(id(self)),
                                               self.name)


class NodeDescParamJSON(NodeDescParam):

    @staticmethod
    def valid_keyword(kw):
        """Return True if the keyword is in the list of known tokens."""
        keywords = ['URL', 'buttonText', 'conditionalVisOp',
                    'conditionalVisOps', 'conditionalVisPath',
                    'conditionalVisValue', 'connectable', 'default', 'digits',
                    'editable', 'help', 'hidden', 'label', 'match', 'max',
                    'min', 'name', 'options', 'page', 'page_open', 'presets',
                    'primvar', 'riattr', 'riopt', 'scriptText', 'shortname',
                    'size', 'slidermax', 'slidermin', 'syntax', 'type', 'units',
                    'widget', '_name', 'uiStruct', 'panel', 'inheritable', 
                    'inherit_true_value', 'update_function_name', 'update_function']
        return (kw in keywords)

    def __init__(self, pdata):
        super(NodeDescParamJSON, self).__init__()
        self.name = None
        self.type = None
        self.size = None
        for k, v in pdata.items():
            if not self.valid_keyword(k):
                print('NodeDescParamJSON: unknown keyword: %s' % k)
            setattr(self, k, v)

        # mark for desc
        if getattr(self, 'uiStruct', None):
            self.has_ui_struct = True

        self._postprocess_page()
        self.finalize()

        self._postprocess_default()
        self._postprocess_options()
        self._add_ramp_attributes()

        # format help message
        #self._format_help()

    def _postprocess_page(self):
        """The JSON syntax uses '/' to describe the page hierarchy but
        internally we use '|' to allow args file to use '/' in page names.
        This method will replace any '/' with '|'.
        """
        this_page = getattr(self, 'page', None)
        if this_page:
            setattr(self, 'page', this_page.replace('/', PAGE_SEP))

    def _postprocess_options(self):
        """check for script-based widget options
        this is a JSON-only feature.
        """
        if hasattr(self, 'options') and isinstance(self.options, (str)):
            opts = self.options.split('|')
            self.options = OrderedDict()
            if ':' in opts[0]:
                for opt in opts:
                    k, v = opt.split(':')
                    try:
                        self.options[k] = eval(v)
                    except:
                        self.options[k] = v
            else:
                for k in opts:
                    self.options[k] = k
            # print('%s options=%s' % (self.name, repr(self.options)))

    def _postprocess_default(self):
        """If a fixed length array has only 1 default value, assume it is valid
        for all array members."""
        if self.size and self.size > 0 and len(self.default) == 1:
            self.default = self.default * self.size

    def _add_ramp_attributes(self):
        """create extra attributes for ramp widgets."""
        wgt = getattr(self, 'widget', None)
        if wgt == 'null' and self.name.endswith('_Interpolation'):
            # Store an enum with maya-compatible values.
            self.interpEnum = {k: INTERP_RMAN_TO_MAYA[k] for k in self.options}
            self.interpDefault = INTERP_RMAN_TO_MAYA[self.default]

    def __str__(self):
        return super(NodeDescParamJSON, self).__str__()

    def __repr__(self):
        return '%s object at %s (name: %s)' % (self.__class__, hex(id(self)),
                                               self.name)

    def as_dict(self):
        d = dict(vars(self))
        if '_name' in d:
            d['name'] = d['_name']
            del d['_name']
        return d


class NodeDesc(object):
    """A class that reads node descriptions from args or oso files.

    Attributes:
    - name (str): Surface, PxrBlackBody, etc.
    - node_type (str): bxdf, pattern, light, etc.
    - rman_node_type (str): usually name except for metashaders.
    - params (list): list of NodeDescParam objects.
    - outputs (list): list of NodeDescParam objects.
    - attributes (list): list of NodeDescParam objects.
    - classification (str): maya's node classification.
    - rfh_classification (str): houdini's tab submenu.
    - nodeid (int): unique node identifier for maya. Can be none if not a maya \
    node
    - onCreate (list): callback to be executed on node creation.
    - textured_params (list): names of textured params. Used by the texture \
    manager.
    """

    def __init__(self, filepath):
        """Takes a file path to a file of a known format (args, OSL, JSON),
        parses it and stores the data for later retrieval.

        Arguments:
            filepath {FilePath} -- full path to args or oso file.
        """
        self._name = None
        self.node_type = None
        self.path = os.path.normpath(filepath.os_path())
        self.rman_node_type = None
        self.params = []
        self.outputs = []
        self.attributes = []
        self.param_dict = None
        self.attribute_dict = None
        self.output_dict = None
        self.classification = None
        self.rfh_classification = None
        self.nodeid = None
        self.onCreate = []
        self.textured_params = []
        self.pages_condvis_dict = {}
        self.pages_trigger_params = []
        self.ui_structs = {}
        self.ui_struct_membership = {}
        self._parse_node(filepath)
        self._ctlname = None

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        self._ctlname = re.sub(r'[^\w]', '', value)

    @property
    def ctlname(self):
        if self._ctlname is None and self._name is not None:
            self._ctlname = re.sub(r'[^\w]', '', self._name)
        return self._ctlname

    def is_maya_node(self):
        """Return True if the node description has a valid node id. The node id
        is used by Maya as a unique identifier for the node.

        Returns:
            boolean: True if it can be instanced as a maya node.
        """
        return (self.nodeid is not None)

    def get_param_desc(self, pname):
        if self.param_dict is None:
            self.param_dict = {d.name: d for d in self.params}
        try:
            return self.param_dict[pname]
        except KeyError:
            return None

    def get_output_desc(self, pname):
        if self.output_dict is None:
            self.output_dict = {d.name: d for d in self.outputs}
        try:
            return self.output_dict[pname]
        except KeyError:
            return None

    def get_attribute_desc(self, pname):
        if self.attribute_dict is None:
            self.attribute_dict = {d.name: d for d in self.attributes}
        try:
            return self.attribute_dict[pname]
        except KeyError:
            return None

    def is_unique(self):
        """Return True if there must be only one instance on this node type in
        the scene."""
        # pylint: disable=no-member
        try:
            return self.unique
        except:
            return False

    def _parse_node(self, filepath):
        """Directs the incoming file toward the appropriate parsing method.

        Args:
            filepath (FilePath): Description
        """
        if filepath[-5:] == '.args':
            try:
                xmldoc = mx.parse(filepath.os_path())
            except Exception as err:
                #rfm_log().warning('XML parsing error in %r (%s)', filepath.os_path(), err)
                print('XML parsing error in %r (%s)' % (filepath.os_path(), err))
            else:
                self._parse_args_xml(xmldoc, filepath)
        elif filepath[-4:] == '.oso':
            self._parse_oso_file(filepath)
        elif filepath[-5:] == '.json':
            self._parse_json_file(filepath)
        # else:
        #     print('WARNING: unknown file type: %s' % filepath)

        # weed out 'notes' string attributes that are just a studio artifact.
        for i in range(len(self.params)):
            if self.params[i].name == 'notes' and self.params[i].type == 'string':
                del self.params[i]
                break

        # Always add the lightfilters plug to light nodes.
        if self.node_type == 'light':
            self.attributes.append(NodeDescParamJSON({"name": "rman__lightfilters",
                                                      "label": "Light Filters",
                                                      "type": "color",
                                                      "size": -1,
                                                      "widget": "mayaLink",
                                                      "options": "classification:rendernode/RenderMan/lightfilter",
                                                      "default": [[0, 0, 0]]}))

        # collect parameters triggering conditional visibility evaluation, as
        # well as arrays of structs
        # NOTE: page conditional visibility is only implemented in args files
        #       because there is no syntax (yet) for JSON and OSL.
        trigger_params_list = self.pages_trigger_params
        for p in self.params:
            trigger_params_list += p.cond_vis_trigger_params()
            if p.has_ui_struct:
                struct_name = p.uiStruct
                if not struct_name in self.ui_structs:
                    self.ui_structs[struct_name] = []
                self.ui_structs[struct_name].append(p.name)
                self.ui_struct_membership[p.name] = struct_name

        # loop through the params again to tag those who may trigger a
        # conditional visibility evaluation.
        trigger_params_list = list(set(trigger_params_list))
        # if trigger_params_list:
        #     print('%s triggers: %s' % (self.name, trigger_params_list)
        for p in self.params:
            if p.name in trigger_params_list:
                setattr(p, 'conditionalVisTrigger', True)

    def _parse_args_xml(self, xml, xmlfile):
        """Parse the xml contents of an args file. All parameters and outputs
        will be stored as NodeDescParam objects.

        Arguments:
            xml {xml} -- the xml document object
            xmlfile {FilePath} -- the full file path to the xml file

        Raises:
            NodeDescError: if the shaderType can not be found.
        """

        # the node name is based on the file Name
        self.name = xmlfile.basename().split('.')[0]

        # get the node type (bxdf, pattern, etc)
        # we expected only one shaderType element containing a single
        # tag element. Anything else will make this code explode.
        #
        shaderTypes = xml.getElementsByTagName('shaderType')
        if len(shaderTypes) == 0:
            # some args files use 'typeTag'... which one is correct ?
            shaderTypes = xml.getElementsByTagName('typeTag')
        if len(shaderTypes):
            tags = shaderTypes.item(0).getElementsByTagName('tag')
            if len(tags):
                self.node_type = tags.item(0).getAttribute('value')
            else:
                err = 'No "tag" element in "shaderType" ! : %s' % xmlfile
                raise NodeDescError(err)
        else:
            err = 'No "shaderType" element in args file ! : %s' % xmlfile
            raise NodeDescError(err)

        # node help
        for node in xml.firstChild.childNodes:
            if node.nodeName == 'help':
                self.help = node.firstChild.data.strip()

        # in RIS, displacement should translate to displace
        # FIXME: is this still useful now that REYES is gone ?
        if self.node_type == 'displacement':
            self.node_type = 'displace'

        # get the rfmdata blob ------------------------------------------------
        #
        rfmdata = xml.getElementsByTagName('rfmdata')
        try:
            # some nodes don't have a nodeid and will not appear as maya nodes.
            self.nodeid = rfmdata[0].getAttribute('nodeid')
        except:
            self.nodeid = None

        if self.nodeid is not None:
            self.classification = rfmdata[0].getAttribute('classification')
        # Display drivers MUST register a file extension. Display drivers that
        # don't write to a file should not register a file extension.
        try:
            self.fileExtension = rfmdata[0].getAttribute('fileextension')
        except:
            pass

        # is this a metashader, i.e. an args file referencing a node
        # with a different name ?
        self.rman_node_type = self.name
        metashader = xml.getElementsByTagName('metashader')
        if len(metashader):
            self.rman_node_type = metashader.item(0).getAttribute('shader')

        # get the node parameters
        #
        params = xml.getElementsByTagName('param')
        for p in params:
            obj = NodeDescParamXML(p)
            self.params.append(obj)
            self._mark_if_textured(obj)

        outputs = xml.getElementsByTagName('output')
        for o in outputs:
            obj = NodeDescParamXML(o)
            self.outputs.append(obj)

        attributes = xml.getElementsByTagName('attribute')
        for a in attributes:
            obj = NodeDescParamXML(a)
            self.attributes.append(obj)

        pages = xml.getElementsByTagName('page')
        for p in pages:
            page_name = p.getAttribute('name')
            if p.hasAttribute('conditionalVisOp'):
                self.pages_condvis_dict[page_name] = {
                    'conditionalVisOp': p.getAttribute('conditionalVisOp'),
                    'conditionalVisPath': p.getAttribute('conditionalVisPath'),
                    'conditionalVisValue': eval(p.getAttribute('conditionalVisValue'))
                }
                self.pages_condvis_dict[page_name]['expr'] = vis_ops_func(
                    self.pages_condvis_dict[page_name], self.pages_trigger_params)
                # print('%s ------------------' % page_name)
                # print('  |_ conditionalVisOp = %r' % self.pages_condvis_dict[page_name]['conditionalVisOp'])
                # print('  |_ conditionalVisPath = %r' % self.pages_condvis_dict[page_name]['conditionalVisPath'])
                # print('  |_ conditionalVisValue = %r' % self.pages_condvis_dict[page_name]['conditionalVisValue'])
            # elif self.name == 'PxrBarnLightFilter':
            #     print('%s ------------------' % page_name)

    def _parse_oso_file(self, oso):
        """Parse an OSL object file with the help of oslinfo. All params and
        outputs wil be stored as NodeDescParam objects.

        Arguments:
            oso {FilePath} -- full path of the *.oso file.
        """
        if not os.path.exists(oso.os_path()):
            print("OSO not found: %s", oso.os_path())
            return

        # open shader
        import oslquery as oslq
        oinfo = oslq.OslQuery()
        oinfo.open(oso)

        self._parsed_data = oinfo
        self._parsed_data_type = 'oso'

        # get name and type
        self.name = oinfo.shadername()
        self.rman_node_type = self.name
        self.node_type = OSL_TO_RIS_TYPES[oinfo.shadertype()]
        if self.node_type != DescNodeType.kPattern:
            print("WARNING: OSL %s not supported by RIS (%s)",
                             self.node_type, self.name)

        meta = {p['name']: p for p in oinfo.shadermetadata()}
        self.classification = osl_metadatum(meta, 'rfm_classification')
        # categorize osl shaders as patterns by default, if metadata didn't
        # say.
        if not self.classification:
            self.classification = 'rendernode/RenderMan/pattern/'
        self.help = osl_metadatum(meta, 'help')                             

        # parse params
        for i in range(oinfo.nparams()):
            param_data = oinfo.getparam(i)

            # try:
            obj = NodeDescParamOSL(param_data)
            # except BaseException as err:
            #     logger().error('Parsing failed on: %s (%s)', param_data, err)

            # struct members appear as struct.member: ignore.
            if '.' in obj.name:
                #logger().warning("not adding struct param %s" % obj.name)
                continue

            if obj.category == DescPropType.Param:
                if getattr(obj, 'lockgeom', True):
                    self.params.append(obj)
                    self._mark_if_textured(obj)
            elif obj.category == DescPropType.Output:
                self.outputs.append(obj)
            elif obj.category == DescPropType.Attribute:
                self.attributes.append(obj)
            else:
                print('WARNING: unknown category ! %s',
                                 str(obj.category))        

    @staticmethod
    def _invalid_json_file_warning(validator, json_file):
        """output a descriptive warning when a json file is not a node file.

        Args:
        - validator (str): the contents of the json file's "$schema" field.
        - json_file (FilePath): the path to the json file
        """
        msg = 'Unknown json file type: %r' % validator
        if 'aovsSchema' in validator:
            msg = 'aov files should be inside a "config" directory.'
        elif 'rfmSchema' in validator:
            msg = 'rfm config files should be inside a "config" directory.'
        elif 'menuSchema' in validator:
            msg = 'menu config files should be inside a "config" directory.'
        elif 'shelfSchema' in validator:
            msg = 'shelf config files should be inside a "config" directory.'
        elif validator == '':
            fname = json_file.basename()
            if fname in ['extensions.json', 'mayaTranslation.json', 'syntaxDefinition.json']:
                dirnm = json_file.dirname()
                if dirnm.basename() == 'nodes':
                    dirnm = dirnm.dirname()
                msg = 'this file should be inside %s/config' % json_file.dirname()
        #rfm_log().warning('Skipping non-node file "%s": %s', json_file.os_path(), msg)
        print('Skipping non-node file "%s": %s' % (json_file.os_path(), msg))

    def _parse_json_file(self, jsonfile):
        """Load and parse the json file. We check for a number of mandatory
        attributes, as json files will typically be used to build rfm nodes
        like render globals, displays, etc.
        We only expect params for now.

        Args:
        * jsonfile (FilePath): fully qualified path.
        """
        jdata = json_file.load(jsonfile.os_path())
        # print(jdata)

        # Do not parse validation schemas and json files without an appropriate
        # validation schema.
        validator = jdata.get('$schema', '')
        if validator == 'http://json-schema.org/schema#':
            # silently ignore schemas
            raise NodeDescIgnore('Schema file: %s' % jsonfile.os_path())
        elif not 'rmanNodeSchema' in validator:
            # warn the user and try to output an informative message
            self._invalid_json_file_warning(validator, jsonfile)
            raise NodeDescIgnore('Not a node file: %s' % jsonfile.os_path())

        # set mandatory attributes.
        mandatoryAttrList = ['name', 'node_type', 'rman_node_type', 'nodeid',
                             'classification']
        for attr in mandatoryAttrList:
            setattr(self, attr, jdata[attr])

        optionalAttrList = ['onCreate', 'unique', 'params_only_AE']
        for attr in optionalAttrList:
            try:
                setattr(self, attr, jdata[attr])
            except:
                pass

        if 'params' in jdata:
            for pdata in jdata['params']:
                try:
                    param = NodeDescParamJSON(pdata)
                except:
                    print('FAILED to parse param: %s' % pdata)
                    raise
                self.params.append(param)
                self._mark_if_textured(param)

    def _mark_if_textured(self, obj):
        try:
            opt = obj.options # {"texture":"texture"}
        except:
            pass
        else:
            # from txmanager.txparams import TXMAKE_PRESETS
            txmake_presets_keys = ['texture', 'env', 'imageplane']
            if isinstance(opt, dict):
                for k,v in opt.items():
                    if k in txmake_presets_keys:
                        self.textured_params.append(obj)

    def __str__(self):
        """debugging method

        Returns:
            str -- a human-readable dump of the node.
        """
        s = 'ShadingNode: %s ------------------------------\n' % self.name
        s += 'node_type: %s\n' % self.node_type
        s += 'rman_node_type: %s\n' % self.rman_node_type
        s += 'nodeid: %s\n' % self.nodeid
        s += 'classification: %s\n' % self.classification
        if hasattr(self, 'help'):
            s += 'help: %s\n' % self.help
        s += '\nINPUTS:\n'
        for p in self.params:
            s += '  %s\n' % p
        s += '\nOUTPUTS\n:'
        for p in self.outputs:
            s += '%s\n' % p
        s += '\nATTRIBUTES:\n'
        for p in self.attributes:
            s += '%s\n' % p
        s += '-' * 79
        return s

    def __repr__(self):
        return '%s object at %s (name: %s)' % (self.__class__, hex(id(self)),
                                               self.name)

#
# tests -----------------------------------------------------------------------


def save_ref(idx_list, save=True):
    """Takes a number of test files, load them and serialize our representation
    to disk for later comparison in unit tests.

    Args:
        idx_list (list): list of file indices
        save (bool, optional): Save the file or not. used for debugging.
    """
    # print('\n\n')
    test_dir = FilePath(
        '/Users/plp/src/plp_hellhound_rman_main/rat/apps/rfm')
    test_files = [
        test_dir.join('test_files', 'PxrArgsTest.args'),
        test_dir.join('test_files', 'PxrOSLTest.oso'),
        test_dir.join('test_files', 'PxrMayaBulge.args'),
        test_dir.join('test_files', 'PxrProjectionLayer.args'),
        test_dir.join('test_files', 'PxrSurface.args'),
        test_dir.join('test_files', 'PxrDomeLight.args'),
        test_dir.join('test_files', 'PxrLayer.oso'),
        test_dir.join('scripts', 'rfm2', 'nodes', 'rmanDisplay.json'),
        FilePath('/Users/plp/Desktop/PxrNaturalHairColor.oso'),
        FilePath('/Users/plp/src/perforce-plp/rmanprod/rman/plugins/shading/'
                 'pattern/color/PxrVary.args')]

    for i in idx_list:
        # print('\n\n+ %s\n' % test_files[i])
        s = NodeDesc(test_files[i])
        # print('MESSAGES\n')
        # print(str(s)[: 5000] + '\n')
        # print(s)
        # print
        if save:
            ref = test_files[i] + '.ref'
            fh = open(ref, mode='w')
            fh.write(str(s))
            fh.close()
            print('written: %s.ref' % test_files[i])

