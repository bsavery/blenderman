# pylint: disable=invalid-name
import re
import time
import os
import datetime
import sys
from collections import OrderedDict
from ..rfb_logger import rfb_log
from ..rfb_utils import filepath_utils
from .prefs_utils import get_pref
import bpy

COUNTERS = None


def time_this(f):
    """Function that can be used as a decorator to time any method."""
    def timed(*args, **kw):
        global COUNTERS
        ts = time.time()
        result = f(*args, **kw)
        te = time.time()
        elapsed = (te - ts) * 1000.0
        if COUNTERS is None:
            print('  _ %0.3f ms: %r args:[%r, %r]' % (elapsed, f.__name__,
                                                      args, kw))
        else:
            if not f.__name__ in COUNTERS:
                COUNTERS[f.__name__] = (1, elapsed)
            else:
                COUNTERS[f.__name__] = (COUNTERS[f.__name__][0] + 1,
                                        COUNTERS[f.__name__][1] + elapsed)
        return result

    return timed

PAD_FMT = ['%d', '%01d', '%02d', '%03d', '%04d']

# split the token into 5 groups:
#   1 - <expr> token
#   2 - formatting for the <expr> token
#   3 - other main token
#   4 - the token formatting string
#   5 - an environment variable
#
# Examples:
#   '<expr[<f> % 10]>' -> ('<f> % 10', None, None, None, None)
#   '<expr[<f> % 10]: %04d>' -> ('<f> % 10', ': %04d', None, None, None)
#   '<shape.fogColor>'  ->  (None, None, 'shape.fogColor', None, None)
#   '<shape.fogColor:%g %g %g>'  ->  (None, None, 'shape.fogColor', ':%g %g %g', None)
#   '$RMANTREE/bin' ->  (None, None, None, None, '$RMANTREE')
#
PARSING_EXPR = re.compile(r'<expr\[(.*)\]' # <expr> token
                          r'(:[^>]+)*>|' # formatter
                          r'<([\w\:]*[\w\.]+)(\?[\w\d\._-]+)*'  # token
                          r'(:[^>]+)*>|'                        # formatter
                          r'\$\{?([A-Z0-9_]{3,})\}?')           # env var


class StringExpression(object):

    # @time_this
    def __init__(self, tokens=None, bl_scene=None):
        self.bl_scene = bpy.context.scene
        if bl_scene:
            self.bl_scene = bl_scene
        self.tokens = {}
        self.update_temp_token()
        self.update_out_token()
        #self.update_blend_tokens()  
        self.tokens['pwd'] = ''
        ts = datetime.datetime.fromtimestamp(time.time())
        self.tokens['jobid'] = ts.strftime('%y%m%d%H%M%S')
        self.tokens['date'] = ts.strftime('%y_%m_%d')
        self.tokens['time'] = ts.strftime('%H-%M-%S')
        self.tokens['layer'] = '' 
        self.tokens['renderlayer'] = self.tokens['layer']
        self.tokens['ext'] = 'exr'
        self.tokens['aov'] = '' 
        self.tokens['aovdir'] = 'beauty'
        self.tokens['file'] = self.tokens['blend']
        self.tokens['ws'] = self.tokens['OUT']

        for k, v in self.tokens.items():
            # print '%s = %s' % (k, repr(v))
            # suppress any trailing slash or anti-slash for consistency.
            if v and v[-1] in ['/', os.sep]:
                self.tokens[k] = v[:-1]

        if tokens is not None:
            for k, v in tokens.items():
                tokens[k] = self.expand(v)
            self.tokens.update(tokens)

    def update_temp_token(self):
        if sys.platform == ("win32"):
            self.tokens['TEMP'] = 'C:/tmp'
        else:
            self.tokens['TEMP'] = '/tmp'

    def update_out_token(self):
        if 'blend' not in self.tokens:
            self.update_blend_tokens()
        dflt_path = self.expand('<TEMP>/renderman_for_blender/<blend>')
        if not self.bl_scene:
            self.tokens['OUT'] = dflt_path
        else:
            root_path = self.expand(self.bl_scene.renderman.root_path_output) 
            if not os.path.isabs(root_path):
                rfb_log().debug("Root path: %s is not absolute. Using default." % root_path)            
                root_path = dflt_path
            elif not os.path.exists(root_path):
                try:
                    os.makedirs(root_path, exist_ok=True)
                except PermissionError:
                    rfb_log().debug("Cannot create root path: %s. Using default." % root_path)            
                    root_path = dflt_path
            self.tokens['OUT'] = root_path    
            
        unsaved = True if not bpy.data.filepath else False
        scene = self.bl_scene
        rm = scene.renderman           
        if rm.blenddir_token != "":
            self.tokens['blend_dir'] = rm.blenddir_token
        elif unsaved:
            self.tokens['blend_dir'] = self.tokens['OUT']
        else:
            self.tokens['blend_dir'] = os.path.split(bpy.data.filepath)[0]     

    def update_blend_tokens(self):
        scene = self.bl_scene
        rm = scene.renderman        
        for i in range(len(rm.user_tokens)):
            user_token = rm.user_tokens[i]
            self.tokens[user_token.name] = user_token.value

        unsaved = True if not bpy.data.filepath else False
        if rm.blend_token != "":
            # check if the scene blend token is set
            # usually this is set for batch renders
            self.tokens['blend'] = rm.blend_token
        elif unsaved:
            self.tokens['blend'] = 'UNTITLED'
        else:
            self.tokens['blend'] = os.path.splitext(os.path.split(bpy.data.filepath)[1])[0]             
            
        self.tokens['scene'] = scene.name 
        self.set_frame_context(scene.frame_current)

        vp = get_pref('rman_scene_version_padding', default=3)
        tp = get_pref('rman_scene_take_padding', default=1)
        self.tokens['version'] = PAD_FMT[vp] % rm.version_token
        self.tokens['take'] = PAD_FMT[tp] % rm.take_token

    # @time_this
    def set_frame_context(self, frame):
        """Set the scene frame for the next subst() call."""

        if isinstance(frame, int):
            self.tokens['frame'] = str(frame)
            iframe = int(frame)
            self.tokens['f'] = str(iframe)
            self.tokens['f2'] = '{:0>2d}'.format(iframe)
            self.tokens['f3'] = '{:0>3d}'.format(iframe)
            self.tokens['f4'] = '{:0>4d}'.format(iframe)
            self.tokens['f5'] = '{:0>5d}'.format(iframe)
            self.tokens['F'] = str(iframe)
            self.tokens['F2'] = '{:0>2d}'.format(iframe)
            self.tokens['F3'] = '{:0>3d}'.format(iframe)
            self.tokens['F4'] = '{:0>4d}'.format(iframe)
            self.tokens['F5'] = '{:0>5d}'.format(iframe)
        elif isinstance(frame, str):
            self.tokens['frame'] = frame
            self.tokens['f'] = frame
            self.tokens['f2'] = '%s' % (frame) * 2
            self.tokens['f3'] = '%s' % (frame) * 3
            self.tokens['f4'] = '%s' % (frame) * 4
            self.tokens['f5'] = '%s' % (frame) * 5
            self.tokens['F'] = frame
            self.tokens['F2'] = '%s' % (frame) * 2
            self.tokens['F3'] = '%s' % (frame) * 3
            self.tokens['F4'] = '%s' % (frame) * 4
            self.tokens['F5'] = '%s' % (frame) * 5

    # @time_this
    def expand(self, expr, objTokens={}, asFilePath=False):
        """handle the '<token>' format"""

        # early exit: around 0.003ms
        if '<' not in expr and '$' not in expr:
            return expr

        toks = dict(self.tokens)
        toks.update(objTokens)
        # print toks
        pos = 0
        result = ''
        for m in re.finditer(PARSING_EXPR, expr):
            # print('GROUPS: %s' % str(m.groups()))
            if m.group(1):
                # this is an <expr> token
                # we need to eval() it
                tok_expr = m.group(1)
                tok_expr = self.expand(tok_expr)
                if 'expr' in objTokens:
                    # check if expr is in our objTokens
                    tok_val = objTokens['expr']
                    result += '%s%s' % (expr[pos:m.start()], tok_val)
                else:
                    # this is a regular eval()
                    try:
                        ans = eval(tok_expr)
                        if m.group(2):
                            # check for formatting
                            # remove the : and strip any whitespace
                            fmt = m.group(2)[1:].strip()
                            result += expr[pos:m.start()] + fmt % ans
                        else:
                            result += expr[pos:m.start()] + '%s' % str(ans)
                    except SyntaxError:
                        result += expr[pos: m.start()] + m.group(0)
            elif m.group(3):
                # Token case
                tok = m.group(3)
                tok_val = None
                # print('  |__ TOKEN: %02d-%02d: %s' % (m.start(), m.end(), tok))
                try:
                    tok_val = toks[tok]
                    # result += expr[pos:m.start()] + toks[tok]
                except KeyError:
                    try:
                        # forced lower-case version if first attempts failed.
                        tok_val = toks[tok.lower()]
                    except KeyError:
                        # the token REALLY doesn't exist...
                        tok_val = '<%s>' % tok

                # optional formating
                if m.group(5):
                    if isinstance(tok_val, str) and tok_val:
                        try:
                            tok_val = eval(tok_val)
                        except (NameError, SyntaxError, TypeError) as err:
                            rfb_log().debug('Eval failed: %s  -> %r', err, tok_val)
                            result += expr[pos:m.start()] +  tok_val
                        else:
                            result += expr[pos:m.start()] +  m.group(5)[1:] % tok_val
                    else:
                        result += expr[pos:m.start()] +  m.group(5)[1:] % tok_val
                else:
                    result += '%s%s' % (expr[pos:m.start()], tok_val)
            else:
                # Environment variable case
                tok = m.group(6)
                # print('  |__ ENV VAR: %02d-%02d: %s' % (m.start(), m.end(), tok))
                try:
                    result += expr[pos: m.start()] + os.environ[tok]
                except KeyError:
                    result += expr[pos: m.start()] + m.group(0)

            pos = m.end()
        # append the end of the string. If no match (despite the presence of
        # a < or $), sets result to the original expression.
        result += expr[pos:]

        
        if asFilePath:
            # If this is meant to be a file path, substitute : with _
            # Can not have ':' after the drive descriptor on windows. Allow
            # for a leading space before the drive letter
            result = re.sub(r'((?<!^[A-Z])(?<!^[ ][A-Z]))\:', '_', result)
          
            # get the real path
            result = filepath_utils.get_real_path(result)

            dirname = os.path.dirname(result)
            if not os.path.exists(dirname):
                try:
                    os.makedirs(dirname, exist_ok=True)
                except PermissionError:
                    rfb_log().error("Cannot create path: %s" % dirname)
    
        return result


def fixup_file_name(inputNm):
    result = inputNm
    # replace repeated underscores with one underscore
    # these come about if a var like <layer> is empty
    result = re.sub(r'_+', '_', result)
    # eg.  test_.0001.exr -> test.0001.exr
    result = re.sub(r'_\.', '.', result)
    # strip underscore if it's at end of string
    result = result.rstrip('_')
    return result
