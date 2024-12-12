from ..rfb_utils.rfb_node_desc_utils.rfb_node_desc_param import RfbNodeDescParamJSON
from ..rfb_utils.rfb_node_desc_utils.conditional_visibility import build_condvis_expr
from ..rfb_utils.prefs_utils import get_pref
from ..rfb_utils import filepath_utils
from ..rfb_utils.envconfig_utils import envconfig
from ..rfb_logger import rfb_log
from bpy.props import StringProperty, BoolProperty
import json
import os
import types

__RMAN_CONFIG__ = dict()
__RMAN_CHANNELS_DEF_FILE__ = 'rman_dspychan_definitions.json'
__RFB_CONFIG_FILE__ = 'rfb.json'
__RFB_CONFIG_DICT__ = dict()
__RMAN_DISPLAY_CHANNELS__ = dict()
__RMAN_DISPLAY_TEMPLATES__ = dict()

__OPTIONAL_ATTRS__ = {
    'bl_width_default',
    'bl_width_min',
    'bl_width_max',
    'bl_height_default',
    'bl_height_min',
    'bl_height_max'
}

class RmanBasePropertyGroup:
    """Base class that can be inhreited for custom PropertyGroups
    who want to use the JSON config files to dynamically add their properties.
    _add_properties should be called before the class is registerd. For example:

    classes = [         
        MyWonderfulSettings
    ]   

    for cls in classes:
        cls._add_properties(cls, 'my_wonderful_settings')
        bpy.utils.register_class(cls)      

    Attributes:

    """

    @staticmethod
    def _add_properties(cls, rman_config_name):
        """Dynamically add properties to a PropertyGroup class

        Args:
            cls (class) - class to add the properties
            rman_config_name (str) - Config name to use to add properties from
        """

        if not rman_config_name in __RMAN_CONFIG__:
            return

        from ..rfb_utils import generate_property_utils            

        config = __RMAN_CONFIG__[rman_config_name]

        prop_names = []
        prop_meta = {}
        page_names = []

        def addpage(ndp):
            if hasattr(ndp, 'page') and ndp.page != '':
                page_name = ndp.page
                if page_name not in page_names:
                    page_names.append(page_name)
                    ui_label = "%s_uio" % page_name
                    dflt = getattr(ndp, 'page_open', True)                
                    cls.__annotations__[ui_label] = BoolProperty(name=ui_label, default=dflt)            

        for param_name, ndp in config.params.items():
            update_func = None
            set_func = None
            get_func = None
            if hasattr(ndp, 'update_function'):
                # this code tries to dynamically add a function to cls
                # don't ask me why this works.
                lcls = locals()
                exec(ndp.update_function, globals(), lcls)
                exec('update_func = %s' % ndp.update_function_name, globals(), lcls)
                update_func = lcls['update_func']
                setattr(cls, ndp.update_function_name, update_func)
            elif hasattr(ndp, 'update_function_name'):
                update_func = ndp.update_function_name

            if hasattr(ndp, 'set_function'):
                lcls = locals()
                exec(ndp.set_function, globals(), lcls)
                exec('set_func = %s' % ndp.set_function_name, globals(), lcls)
                set_func = lcls['set_func']
                setattr(cls, ndp.set_function_name, set_func)
            elif hasattr(ndp, 'set_function_name'):
                set_func = ndp.set_function_name

            if hasattr(ndp, 'get_function'):
                lcls = locals()
                exec(ndp.get_function, globals(), lcls)
                exec('get_func = %s' % ndp.get_function_name, globals(), lcls)
                get_func = lcls['get_func']
                setattr(cls, ndp.get_function_name, get_func)
            elif hasattr(ndp, 'get_function_name'):
                get_func = ndp.get_function_name                

            if ndp.is_array():
                if generate_property_utils.generate_array_property(cls, prop_names, prop_meta, ndp):
                    addpage(ndp)
                    continue
            name, meta, prop = generate_property_utils.generate_property(cls, ndp, update_function=update_func, set_function=set_func, get_function=get_func)
            if prop:
                cls.__annotations__[ndp._name] = prop
                prop_names.append(ndp.name)
                prop_meta[ndp.name] = meta

            addpage(ndp)

        setattr(cls, 'prop_names', prop_names)
        setattr(cls, 'prop_meta', prop_meta)

class RmanConfig:
    """A class to reprsent a json config file.

    Attributes:
        jsonfile (str): Path to JSON file on disk
        params (RfbNodeDescParamJSON): Dictionary of parm names to RfbNodeDescParamJSON objects
    """
    def __init__(self, jsonfile):
        self.jsonfile = jsonfile
        self.params = dict()
        self._parse_json_file()

    def _parse_json_file(self):

        jdata = json.load(open(self.jsonfile))
        mandatoryAttrList = ['name']
        for attr in mandatoryAttrList:
            setattr(self, attr, jdata[attr])

        for attr in __OPTIONAL_ATTRS__:
            val = jdata.get(attr, None)
            if val:
                setattr(self, attr, val)

        if 'params' in jdata:
            for pdata in jdata['params']:
                try:
                    param = RfbNodeDescParamJSON(pdata, build_condvis_expr)
                except:
                    rfb_log().error('FAILED to parse param: %s' % pdata)
                    raise
                self.params[param.name] = param

def _uniquify_list(seq):
    """Remove duplicates while preserving order."""
    seen = set()
    seen_add = seen.add
    try:
        # this will fail if the list contains dicts
        return [x for x in seq if not (x in seen or seen_add(x))]
    except TypeError:
        return seq

def recursive_updater(in_dict, out_dict):
    """Recursively update a out_dict with in_dict.

    WARNING: if you change this code, update rfm2/unit_tests/ut_rfm_json.py.

    - dicts are recursively updated, i.e.:
      - new val will replace old val for the same key.
      - new key will be added if it doesn't exist in that dict.
    - lists are merged, i.e.:
        - new list is prepended to old list.
          merge ['c'] in ['a', 'b'] -> ['c', 'a', 'b']
        - duplicates are removed while preserving the original order:
          merge ['c', 'd'] in ['a', 'b', 'c'] -> ['c', 'd', 'a', 'b']

    Args:
    - in_dict (dict): what will be merged in out_dict.
    - out_dict (dict): the final output.

    Returns:
    - a dict.
    """

    for key, val in in_dict.items():
        if isinstance(val, dict):
            nested = recursive_updater(val, out_dict.get(key, {}))
            out_dict[key] = nested
        #elif isinstance(val, list):
        #    out_dict[key] = _uniquify_list(val + out_dict.get(key, []))
        else:
            out_dict[key] = in_dict[key]
    return out_dict

def read_rfbconfig_file(fpath, config_dict):
    """Read rfb.json and update the config_dict with its contents.

    Args:
    - fpath (str): file path to rfb.json file.
    - config_dict (dict): the dict we will update with the file's contents.
    """
    fdict = {}
    with open(fpath, 'r') as fhdl:
        try:
            fdict = json.load(fhdl)
        except ValueError as err:
            __log__.error('failed to parse json file %s: %s' %
                          (fpath, err))
            fdict = None
    if fdict:
        config_dict = recursive_updater(fdict, config_dict)    

def configure_channels(jsonfile):
    jdata = json.load(open(jsonfile))

    if 'channels' in jdata:
        __RMAN_DISPLAY_CHANNELS__.update(jdata['channels'])  
    else:
        rfb_log().error("Could not find 'channels' list in JSON file: %s" % jsonfile)

    if 'displays' in jdata:
        __RMAN_DISPLAY_TEMPLATES__.update(jdata['displays'])


def get_factory_config_path():
    """Get the factory config path.

    Returns:
        str: The path to the factory config files
    """

    cur_dir = os.path.dirname(os.path.realpath(__file__))
    config_dir = os.path.join(cur_dir, 'config')

    return config_dir

def get_factory_overrides_config_path():
    """Get the factory overrides config path.

    Returns:
        str: The path to the factory overrides config files
    """

    cur_dir = os.path.dirname(os.path.realpath(__file__))
    config_dir = os.path.join(cur_dir, 'config', 'overrides')

    return config_dir    

def get_override_paths():
    """Get the override config path(s). Consults the envrionment vairiable
    RFB_SITE_PATH, RFB_SHOW_PATH, and RFB_USER_PATH

    Returns:
        str: The path(s) to the override config files
    """    

    paths = []

    prefs_path = get_pref('rman_config_dir', default='')
    if prefs_path:
        prefs_path = filepath_utils.get_real_path(prefs_path)
        if os.path.exists(prefs_path):
            paths.append(prefs_path)    

    # first, RFB_SITE_PATH
    RFB_SITE_PATH = envconfig().getenv('RFB_SITE_PATH')
    if RFB_SITE_PATH:
        for path in RFB_SITE_PATH.split(os.path.pathsep):
            paths.append(path)

    # next, RFB_SHOW_PATH
    RFB_SHOW_PATH = envconfig().getenv('RFB_SHOW_PATH')
    if RFB_SHOW_PATH:
        for path in RFB_SHOW_PATH.split(os.path.pathsep):
            paths.append(path)

    # finally, RFB_USER_PATH
    RFB_USER_PATH = envconfig().getenv('RFB_USER_PATH')
    if RFB_USER_PATH:
        for path in RFB_USER_PATH.split(os.path.pathsep):
            paths.append(path)                        

    return paths

# only allow these attrs to be overriden
__ALLOWABLE_ATTR_OVERRIDES__ = [
    'default', 
    'label', 
    'help', 
    'min', 
    'max', 
    'slidermin',
    'slidermax',
    'options', 
    'page_open', 
    'connectable', 
    'widget', 
    'readOnly',
    'always_write',
    'arraySize',
    'type'
]

def apply_args_overrides(name, node_desc):
    """Apply overrides on an NodeDesc object. Only certian attributes will be overridden. See
    __ALLOWABLE_ATTR_OVERRIDES__ above.

    Args:
        name (str): Args filename ex: PxrVolume.args
        node_desc (RfbNodeDesc): NodeDesc object to apply overrides to.
    """

    rman_config = __RMAN_CONFIG__.get(name, None)
    if not rman_config:
        return

    for ndp_org in node_desc.params:
        ndp = rman_config.params.get(ndp_org.name, None)
        if ndp:        
            for attr in __ALLOWABLE_ATTR_OVERRIDES__:
                val = getattr(ndp, attr, None)
                if val is not None:
                    if attr == "arraySize" and val == "__REMOVE__":
                        setattr(ndp_org, "size", None)
                        continue
                    setattr(ndp_org, attr, val)

    for nm in __OPTIONAL_ATTRS__:
        val = getattr(rman_config, nm, None)
        if val:
            setattr(node_desc, nm, val)

def apply_overrides(rman_config_org, rman_config_override):
    """Given two RmanConfig objects, apply the overrides from the second
    one to the first one. Only certian attributes will be overridden. See
    __ALLOWABLE_ATTR_OVERRIDES__ above.

    Args:
        rman_config_org (RmanConfig): The original RmanConfig object
        rman_config_override (RmanConfig): The second RmanConfig object with overrides
    """     

    for param_name, ndp in rman_config_override.params.items():
        if param_name in rman_config_org.params:
            ndp_org = rman_config_org.params[param_name]
            for attr in __ALLOWABLE_ATTR_OVERRIDES__:
                if hasattr(ndp, attr):
                    setattr(ndp_org, attr, getattr(ndp, attr))
        else:
            # if it doesn't exist, add it
            rman_config_org.params[param_name] = ndp

    for nm in __OPTIONAL_ATTRS__:
        val = getattr(rman_config_override, nm, None)
        if val:
            setattr(rman_config_org, nm, val)            

def register():

    paths = [get_factory_config_path(), get_factory_overrides_config_path()]

    for config_path in paths:
        for f in os.listdir(config_path):
            if not f.endswith('.json'):
                continue
            jsonfile = os.path.join(config_path, f)
            rfb_log().debug("Reading factory json file: %s" % jsonfile)
            if f == __RMAN_CHANNELS_DEF_FILE__:
                # this is our channels config file
                configure_channels(jsonfile)
            elif f == __RFB_CONFIG_FILE__:
                read_rfbconfig_file(jsonfile, __RFB_CONFIG_DICT__)
            else:
                # this is a regular properties config file
                rman_config = RmanConfig(jsonfile)
                __RMAN_CONFIG__[rman_config.name] = rman_config

    # Look for overrides
    override_paths = get_override_paths()
    for path in override_paths:
        for f in os.listdir(path):
            if not f.endswith('.json'):
                continue
            jsonfile = os.path.join(path, f)
            rfb_log().debug("Reading override json file: %s" % jsonfile)
            if f == __RMAN_CHANNELS_DEF_FILE__:
                configure_channels(jsonfile)
            elif f == __RFB_CONFIG_FILE__:
                read_rfbconfig_file(jsonfile, __RFB_CONFIG_DICT__)
            else:
                rman_config_override = RmanConfig(jsonfile)
                if rman_config_override.name in __RMAN_CONFIG__:
                    rman_config_original = __RMAN_CONFIG__[rman_config_override.name]
                    apply_overrides(rman_config_original, rman_config_override)
                    __RMAN_CONFIG__[rman_config_override.name] = rman_config_original
                else:
                    __RMAN_CONFIG__[rman_config_override.name] = rman_config_override
