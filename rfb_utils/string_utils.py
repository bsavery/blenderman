from .string_expr import StringExpression
from . import filepath_utils
from ..rfb_logger import rfb_log
from bpy.app.handlers import persistent
import bpy
import os
import re

PAD_FMT = ['%d', '%01d', '%02d', '%03d', '%04d']
__SCENE_STRING_CONVERTER__ = None
# FIXME: we should get the extensions from the display driver args files
EXT_MAP = {'it': 'it', 'openexr': 'exr', 
            'tiff': 'tif', 'blender': 'exr', 
            'pointcloud': 'ptc', 'png': 'png', 
            'targa': 'tga', 'texture': 'tex', 
            'ies': 'ies', 'ptex': 'ptex'
        }

# regex to capture whitespace, '.', ':', '[', ']'
__NODE_NAME_REGEXP__ = r'\s+|\.+|:|\[|\]'        

class SceneStringConverter(object):
    """Class maintaining an up-to-date StringExpression object.
    """

    def __init__(self):
        self.expr = None

    def expand(self, string, display=None, frame=None, token_dict = dict(), asFilePath=False):
        """Expand the <tokens> in the string.

        Args:
        - string (str): The string to be expanded.

        Kwargs:
        - display (str): The display being considered. This is necessary if your
        expression contains <aov> or <ext>
        - frame (int, str): An optional frame number to expand <F>, <F4>, etc.

        Returns:
        - The expanded string
        """
        if not self.expr:
            self.update()
        else:
            # make sure OUT is updated
            self.expr.bl_scene = bpy.context.scene
            self.expr.update_out_token()    

        if token_dict:
            self.update_tokens(token_dict)

        if frame is not None:
            self.expr.set_frame_context(frame)

        if display:
            self.set_display(display)

        return self.expr.expand(string, asFilePath=asFilePath)

    def update(self, bl_scene=None):
        """Create a new StringExpression and configures it for the current state
        of the scene."""
        tk = None
        self.expr = StringExpression(tokens=tk, bl_scene=bl_scene)

    def set_display(self, display):
        """Sets the <aov> and <ext> tokens based on the display.

        Args:
        - display (str): the name of the display node.
        """

        if display in EXT_MAP.keys():
            self.expr.tokens['ext'] = EXT_MAP[display]

    def update_tokens(self, token_dict):
        for k,v in token_dict.items():
            self.set_token(k,v)


    def set_token(self, key, value):
        """Sets a token's value in the StringExpression object.

        Args:
        - key (str): the token's name
        - value (str): the token's value
        """
        if not self.expr:
            self.update()
        self.expr.tokens[key] = value

    def get_token(self, key):
        """Gets a token's value in the StringExpression object.

        Args:
        - key (str): the token's name
        """
        if not self.expr:
            self.update()
        value = ''
        if key in self.expr.tokens:
            value = self.expr.tokens[key]
        return value

def expand_string(string, display=None, glob_sequence=False, frame=None, token_dict=dict(), asFilePath=False):
    """expand a string containing tokens.

    Args:
    - string (str): a string that may or may not contain tokens.

    Kwargs:
    - display (str): the name of a display driver to update <ext> tokens.
    - frame (int, str): the frame to use for expanding. If a string, the string will be repeated by the paddning. Ex: '#' will turn to '####' for <f4>
    - token_dict (dict): dictionary of token/vals that also need to be set.
    - asFilePath (bool): treat the input string as a path. Will create directories if they don't exist

    Returns:
    - The expanded string.
    """
    global __SCENE_STRING_CONVERTER__

    def _resetStringConverter():
        try:
            __SCENE_STRING_CONVERTER__.expr = None
        except:
            pass
    
    if not string or (not '<' in string and not '$' in string):
        # get the real path
        if string and asFilePath and os.path.isabs(string):
            string = filepath_utils.get_real_path(string)
            dirname = os.path.dirname(string)
            if not os.path.exists(dirname):
                try:
                    os.makedirs(dirname, exist_ok=True)
                except PermissionError as e:
                    rfb_log().error("Cannot create path: %s (%s)" % (dirname, str(e)))
                except OSError as e:
                    rfb_log().error("Cannot create path: %s (%s)" % (dirname, str(e)))                                     
        return string

    if __SCENE_STRING_CONVERTER__ is None:
        __SCENE_STRING_CONVERTER__ = SceneStringConverter()

    if glob_sequence:
        string = re.sub(r'{(f\d*)}', '*', string)

    return __SCENE_STRING_CONVERTER__.expand(
        string, display=display, frame=frame, token_dict=token_dict, asFilePath=asFilePath)

def converter_validity_check():
    global __SCENE_STRING_CONVERTER__
    if __SCENE_STRING_CONVERTER__ is None:
        __SCENE_STRING_CONVERTER__ = SceneStringConverter()

def set_var(nm, val):
    # This is needed so that we can update the scripting variable state
    # before evaluating a string.
    converter_validity_check()
    __SCENE_STRING_CONVERTER__.set_token(nm, val)

def get_var(nm):
    converter_validity_check()
    return __SCENE_STRING_CONVERTER__.get_token(nm)

def update_frame_token(frame):
    converter_validity_check()
    __SCENE_STRING_CONVERTER__.expr.set_frame_context(frame)

def get_tokenized_openvdb_file(frame_filepath, grids_frame):
    openvdb_file = filepath_utils.get_real_path(frame_filepath)
    f = os.path.basename(frame_filepath)
    frame = '%d' % grids_frame
    expr = re.compile(r'(\d+)%s' % frame)
    m = expr.search(f)
    if m and m.groups():
        s = m.groups()[0]
        strlen = len(s) + len(frame)
        if strlen < 5:
            openvdb_file = frame_filepath.replace(s+frame, '<f%d>' % strlen)    

    return openvdb_file

def get_unique_group_name(group_node):
    group_node_name = group_node.name

    for k,v in bpy.data.node_groups.items():
        if group_node.id_data == v:
            group_node_name = k
            break    
    return group_node_name

@persistent
def update_blender_tokens_cb(bl_scene):
    from ..rman_config import __RFB_CONFIG_DICT__ as rfb_config

    scene = bl_scene
    if not scene or not isinstance(scene, bpy.types.Scene):
        scene = bpy.context.scene

    global __SCENE_STRING_CONVERTER__
    converter_validity_check()
    
    # add user tokens specified in rfb.json
    user_tokens = rfb_config.get('user tokens', list())

    for nm in user_tokens:
        found = False
        for user_token in scene.renderman.user_tokens:
            if user_token.name == nm:
                found = True
                break
        if not found:
            user_token = scene.renderman.user_tokens.add()
            user_token.name = nm

    __SCENE_STRING_CONVERTER__.update(bl_scene=scene)

def check_frame_sensitive(s):
    # check if the sting has any frame token
    # ex: <f>, <f4>, <F4> etc.
    # if it does, it means we need to issue a material
    # update if the frame changes
    pat = re.compile(r'<[f|F]\d*>')
    m = pat.search(s)
    if m:
        return True
    return False    

def _format_time_(seconds):
    hours = seconds // (60 * 60)
    seconds %= (60 * 60)
    minutes = seconds // 60
    seconds %= 60
    return "%02i:%02i:%02i" % (hours, minutes, seconds)

def convert_val(v, type_hint=None):
    import mathutils

    converted_val = v

    # float, int
    if type_hint == 'color':
        if isinstance(v, float) or isinstance(v, int):
            converted_val = (float(v), float(v), float(v))
        else:
            converted_val = list(v)[:3]

    elif type(v) in (mathutils.Vector, mathutils.Color) or\
            v.__class__.__name__ == 'bpy_prop_array'\
            or v.__class__.__name__ == 'Euler':
        converted_val = list(v)

    elif type(v) == str and v.startswith('['):
        converted_val = eval(v)

    elif type(v) == list:
        converted_val = v

    # matrix
    elif type(v) == mathutils.Matrix:
        converted_val = [v[0][0], v[1][0], v[2][0], v[3][0],
                v[0][1], v[1][1], v[2][1], v[3][1],
                v[0][2], v[1][2], v[2][2], v[3][2],
                v[0][3], v[1][3], v[2][3], v[3][3]]
    elif type_hint == 'int':
        converted_val = int(v)
    elif type_hint == 'float':
        converted_val = float(v)

    if type_hint == 'string':
        if isinstance(converted_val, list):
            for i in range(len(converted_val)):
                converted_val[i] = expand_string(converted_val[i], asFilePath=True)
        else:
            converted_val = expand_string(converted_val, asFilePath=True)
    
    return converted_val

def getattr_recursive(ptr, attrstring):
    for attr in attrstring.split("."):
        ptr = getattr(ptr, attr)

    return ptr    

def sanitize_node_name(node):
    global __NODE_NAME_REGEXP__
    return re.sub(__NODE_NAME_REGEXP__, '_', node)
