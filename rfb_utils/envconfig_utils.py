from .prefs_utils import get_pref
from . import filepath_utils
from ..rfb_logger import rfb_log
from .. import rfb_logger
from .. import rman_constants
from ..rman_constants import RFB_ADDON_PATH
import os
import bpy
import json
import subprocess
import platform
import sys
import re

__PRESTINE_ENVIRON__ = os.environ.copy()

class BuildInfo(object):
    """Hold version and build infos"""

    def __init__(self, re_dict):
        self._version_string = '%s.%s%s' % (re_dict['version_major'], re_dict['version_minor'], re_dict['beta'])
        self._beta = re_dict['beta']
        self._version_major = int(re_dict['version_major'])
        self._version_minor = int(re_dict['version_minor'])
        self._id = re_dict['id']
        self._name = re_dict['name']
        self._date_string = ('%s %s %s %s at %s' %
                             (re_dict['day'], re_dict['month'], re_dict['date'], re_dict['year'], re_dict['time']))

    def version(self):
        """return the version string"""
        return self._version_string

    def full_version(self):
        """Return a full version string, i.e. '24.1b3 @ 73438742'"""
        return '%d.%d%s @ %d' % (self._version_major, self._version_minor,
                                 self._beta, self._id)

    def date(self):
        """Return the build date string"""
        return self._date_string

    def name(self):
        """Return the build name string"""
        return self._name

    def id(self):
        """Return the build id"""
        return self._id

__RMAN_ENV_CONFIG__ = None

class RmanEnvConfig(object):

    def __init__(self):
        self.rmantree = ''
        self.rmantree_from_json = False
        self.build_info = None
        self.rman_it_path = ''
        self.rman_lq_path = ''
        self.rman_tractor_path = ''
        self.rman_license_app_path = ''
        self.feature_version = ''
        self.is_ncr_license = False
        self.is_valid_license = False
        self.license_info = None
        self.has_xpu_license = False
        self.has_stylized_license = False
        self.has_rps_license = False

    def config_environment(self):

        self.setenv('RMANTREE', self.rmantree)
        self._append_to_path(os.path.join(self.rmantree, 'bin'))
        self._set_it_path()
        self._set_localqueue_path()
        self._set_license_app_path()
        self._set_ocio()
        self._get_license_info()

    def getenv(self, k, default=None):
        return os.environ.get(k, default)

    def setenv(self, k, val):
        os.environ[k] = val

    def unsetenv(self, k):
        os.environ.pop(k)

    def copyenv(self):
        return os.environ.copy()
    
    def set_qn_env_vars(self, bl_scene):
        rm = bl_scene.renderman
        diff_spec_only = not rm.blender_ipr_aidenoiser_cheapFirstPass
        self.setenv('RMAN_QN_DIFFSPEC_ONLY', str(diff_spec_only))
        self.setenv('RMAN_QN_MIN_SAMPLES', str(rm.blender_ipr_aidenoiser_minSamples))
        self.setenv('RMAN_QN_INTERVAL', str(rm.blender_ipr_aidenoiser_interval))

    def set_qn_dspy(self, dspy, immediate_close=True):
        ext = '.so'
        if sys.platform == ("win32"):
                ext = '.dll'
        d = os.path.join(self.rmantree, 'lib', 'plugins', 'd_%s%s' % (dspy, ext))
        self.setenv('RMAN_QN_DISPLAY', d)
        if immediate_close:
            self.setenv('RMAN_QN_IMMEDIATE_CLOSE', '1')
        else:
            self.unsetenv('RMAN_QN_IMMEDIATE_CLOSE')       

    def get_qn_dspy(self, dspy, immediate_close=True):
        ext = '.so'
        if sys.platform == ("win32"):
                ext = '.dll'
        d = os.path.join(self.rmantree, 'lib', 'plugins', 'd_%s%s' % (dspy, ext))
        return d


    def read_envvars_file(self):
        bl_config_path = bpy.utils.user_resource('CONFIG')
        jsonfile = ''
        try:
            for f in os.listdir(bl_config_path):
                if not f.endswith('.json'):
                    continue
                if f == 'rfb_envvars.json':
                    jsonfile = os.path.join(bl_config_path, f)
                    break
        except FileNotFoundError as e:
            rfb_log().debug("%s" % str(e))
            pass
        if jsonfile == '':
            return        
        
        rfb_log().warning("Reading rfb_envvars.json")
        jdata = json.load(open(jsonfile))
        environment = jdata.get('environment', list())

        for var, val in environment.items():
            rfb_log().warning("Setting envvar %s to: %s" % (var, val['value']))  
            self.setenv(var, val['value'])  
            if var == 'RMANTREE':
                self.rmantree_from_json = True
                
        # Re-init the log level in case RFB_LOG_LEVEL was set
        rfb_logger.init_log_level()

        # Also, set logger file, if any
        rfb_log_file = self.getenv('RFB_LOG_FILE')
        if rfb_log_file:
            rfb_logger.set_file_logger(rfb_log_file)

    def get_shader_registration_paths(self):
        paths = []
        rmantree = self.rmantree
        paths.append(os.path.join(rmantree, 'lib', 'shaders'))    
        paths.append(os.path.join(rmantree, 'lib', 'plugins', 'Args'))
        paths.append(os.path.join(RFB_ADDON_PATH, 'Args'))

        RMAN_SHADERPATH = self.getenv('RMAN_SHADERPATH', '')
        for p in RMAN_SHADERPATH.split(os.path.pathsep):
            paths.append(p)

        RMAN_RIXPLUGINPATH = self.getenv('RMAN_RIXPLUGINPATH', '')
        for p in RMAN_RIXPLUGINPATH.split(os.path.pathsep):
            paths.append(os.path.join(p, 'Args'))

        return paths        

    def config_pythonpath(self):
        python_vers = 'python%s' % rman_constants.BLENDER_PYTHON_VERSION
        rfb_log().debug("Blender Python Version: %s" % rman_constants.BLENDER_PYTHON_VERSION)
        if platform.system() == 'Windows':
            rman_packages = os.path.join(self.rmantree, 'lib', python_vers, 'Lib', 'site-packages')
        else:
            rman_packages = os.path.join(self.rmantree, 'lib', python_vers, 'site-packages')
        if not os.path.exists(rman_packages):
            return False

        sys.path.append(rman_packages)        
        sys.path.append(os.path.join(self.rmantree, 'bin'))
        pythonbindings = os.path.join(self.rmantree, 'bin', 'pythonbindings')
        sys.path.append(pythonbindings)     
   
        if platform.system() == 'Windows':
            # apparently, we need to do this for windows app versions
            # of Blender, otherwise the rman python modules don't load
            os.add_dll_directory(rman_packages)
            os.add_dll_directory(os.path.join(self.rmantree, 'bin'))
            os.add_dll_directory(pythonbindings)
            os.add_dll_directory(os.path.join(self.rmantree, 'lib'))    

        return True                        

    def _append_to_path(self, path):        
        if path is not None:
            self.setenv('PATH', path + os.pathsep + self.getenv('PATH'))

    def _set_it_path(self):

        if platform.system() == 'Windows':
            self.rman_it_path = os.path.join(self.rmantree, 'bin', 'it.exe')
        elif platform.system() == 'Darwin':
            self.rman_it_path = os.path.join(
                self.rmantree, 'bin', 'it.app', 'Contents', 'MacOS', 'it')
        else:
            self.rman_it_path = os.path.join(self.rmantree, 'bin', 'it')

    def _set_localqueue_path(self):
        if platform.system() == 'Windows':
            self.rman_lq_path = os.path.join(self.rmantree, 'bin', 'LocalQueue.exe')
        elif platform.system() == 'Darwin':
            self.rman_lq_path = os.path.join(
                self.rmantree, 'bin', 'LocalQueue.app', 'Contents', 'MacOS', 'LocalQueue')
        else:
            self.rman_lq_path= os.path.join(self.rmantree, 'bin', 'LocalQueue')

    def _set_license_app_path(self):
        if platform.system() == 'Windows':
            self.rman_license_app_path = os.path.join(self.rmantree, 'bin', 'LicenseApp.exe')
        elif platform.system() == 'Darwin':
            self.rman_license_app_path = os.path.join(
                self.rmantree, 'bin', 'LicenseApp.app', 'Contents', 'MacOS', 'LicenseApp')
        else:
            self.rman_license_app_path= os.path.join(self.rmantree, 'bin', 'LicenseApp')            

    def _set_tractor_path(self):
        base = ""
        if platform.system() == 'Windows':
            # default installation path
            base = r'C:\Program Files\Pixar'

        elif platform.system() == 'Darwin':
            base = '/Applications/Pixar'

        elif platform.system() == 'Linux':
            base = '/opt/pixar'

        latestver = 0.0
        guess = ''
        for d in os.listdir(base):
            if "Tractor" in d:
                vstr = d.split('-')[1]
                vf = float(vstr)
                if vf >= latestver:
                    latestver = vf
                    guess = os.path.join(base, d)
        tractor_dir = guess

        if tractor_dir:
            self.rman_tractor_path = os.path.join(tractor_dir, 'bin', 'tractor-spool')

    def get_blender_ocio_config(self):
        # return rman's version filmic-blender OCIO config
        ocioconfig = os.path.join(self.rmantree, 'lib', 'ocio', 'filmic-blender', 'config.ocio')

        return ocioconfig            

    def _set_ocio(self):
        # make sure we set OCIO env var
        # so that "it" will also get the correct configuration
        path = self.getenv('OCIO', '')
        if path == '':
            self.setenv('OCIO', self.get_blender_ocio_config())

    def _get_license_info(self):
        from rman_utils import license as rman_license_info

        self.license_info = rman_license_info.get_license_info(self.rmantree)
        self.is_ncr_license = self.license_info.is_ncr_license
        self.is_valid_license = self.license_info.is_valid_license
        if self.is_valid_license:
            self.feature_version = '%d.0' % self.build_info._version_major
            status = self.license_info.is_feature_available(feature_name='RPS-Stylized', feature_version=self.feature_version)
            self.has_stylized_license = status.found
            status = self.license_info.is_feature_available(feature_name='RPS-XPU', feature_version=self.feature_version)
            self.has_xpu_license =  status.found    
            status = self.license_info.is_feature_available(feature_name='RPS', feature_version=self.feature_version)
            self.has_rps_license =  status.found    

    def _is_prman_license_available(self):
        # Return true if there is PhotoRealistic-RenderMan a feature
        # in our license and there seats available
        status = self.license_info.is_feature_available(feature_name='PhotoRealistic-RenderMan', force_reread=True)
        if status.found and status.is_available:
            return True
        return False

    def get_prman_license_status(self):
        status = self.license_info.is_feature_available(feature_name='PhotoRealistic-RenderMan', force_reread=True)
        return status

def _parse_version(s):
    major_vers, minor_vers = s.split('.')
    vers_modifier = ''
    for v in ['b', 'rc']:
        if v in minor_vers:
            i = minor_vers.find(v)
            vers_modifier = minor_vers[i:]
            minor_vers = minor_vers[:i]
            break
    return int(major_vers), int(minor_vers), vers_modifier                  

def _get_build_info(rmantree):

    try:        
        prman = 'prman.exe' if platform.system() == 'Windows' else 'prman'
        exe = os.path.join(rmantree, 'bin', prman)
        desc = subprocess.check_output(
            [exe, "-version"], stderr=subprocess.STDOUT)
    
        pat = re.compile(
            r'(?P<version_major>\d{2})\.(?P<version_minor>\d+)(?P<beta>[b0-9]*)'
            r'\s+\w+\s(?P<day>[A-Za-z]{,3})\s(?P<month>[A-Za-z]+)\s+'
            r'(?P<date>\d{1,2})\s(?P<time>[0-9\:]+)\s(?P<year>\d{4})\s.*\s'
            r'(?P<id>@\d+|<unknown_buildid>)\s+\w+\s(?P<name>[\w\.-]+)',
            re.MULTILINE)
        match = pat.search(str(desc, 'ascii'))
        if match:
            """
            match.groupdict() should return a dictionary looking like:
            {'version_major': 'xx', 'version_minor': 'x', 'beta': '',
               'day': 'unknown', 'month': 'unknown', 'date': 'xx',
               'year': 'xxxx', 'time': 'xx:xx:xx', 'id': 'xxxxxxxx',
               'name': 'unknown'}
            """
            return BuildInfo(match.groupdict()) 

        return None

    except Exception as e:       
        rfb_log().error('Exception trying to get rman version: %s' % str(e)) 
        return None

def _guess_rmantree():
    '''
    Try to figure out what RMANTREE should be set.
    
    First, we consult the rfb_envvars.json file to see if it's been set there. If not, we look at the 
    rmantree_method preference. The preference can be set to either:

    ENV = Get From RMANTREE Environment Variable
    DETECT = Choose a version based on what's installed on the local machine (looks in the default install path)
    MANUAL =  Use the path that is manually set in the preferences.

    '''

    global __RMAN_ENV_CONFIG__

    rmantree_method = get_pref('rmantree_method', 'ENV')
    choice = get_pref('rmantree_choice')

    rmantree = ''
    buildinfo = None

    __RMAN_ENV_CONFIG__ = RmanEnvConfig()
    
    if not __RMAN_ENV_CONFIG__.getenv('RFB_IGNORE_ENVVARS_JSON'):
        __RMAN_ENV_CONFIG__.read_envvars_file()

    if __RMAN_ENV_CONFIG__.rmantree_from_json:
        rmantree = __RMAN_ENV_CONFIG__.getenv('RMANTREE', '')

    if rmantree != '':
        buildinfo = _get_build_info(rmantree)
        if not buildinfo:
            rfb_log().error('RMANTREE from rfb_envvars.json is not valid. Fallback to preferences setting.')  
            rmantree = ''    
        else:
            rfb_log().debug("Using RMANTREE from rfb_envvars.json")

    # Try and set RMANTREE depending on preferences
    if rmantree == '':      

        if rmantree_method == 'MANUAL':
            rmantree = get_pref('path_rmantree')
            buildinfo = _get_build_info(rmantree)

        if rmantree_method == 'DETECT' and choice != 'NEWEST':
            rmantree = choice
            buildinfo = _get_build_info(rmantree)

        if (rmantree != '' and not buildinfo) or rmantree_method == 'ENV':
            # Fallback to RMANTREE env var
            if not buildinfo:
                rfb_log().debug('Fallback to using RMANTREE.')
            rmantree = __PRESTINE_ENVIRON__.get('RMANTREE', '') 
            if rmantree != '':
                rfb_log().info('RMANTREE: %s' % rmantree)
                buildinfo = _get_build_info(rmantree)

        if rmantree == '' or not buildinfo:
            if rmantree_method == 'ENV':
                choice = 'NEWEST'
                rfb_log().debug('Getting RMANTREE from environment failed. Fallback to autodetecting newest.')
                    
            if choice == 'NEWEST':
                # get from detected installs (at default installation path)
                latest = (0, 0, '')
                for vstr, d_rmantree in get_installed_rendermans():
                    d_version = _parse_version(vstr)
                    if d_version > latest:
                        latest = d_version
                        rmantree = d_rmantree
                        buildinfo = _get_build_info(rmantree)      
                if rmantree:
                     rfb_log().info('Newest RMANTREE: %s' % rmantree)     

        if not buildinfo:
            buildinfo = _get_build_info(rmantree)

        # check rmantree valid
        if not buildinfo:
            rfb_log().error(
                "Error loading addon.  RMANTREE %s is not valid.  Correct RMANTREE setting in addon preferences." % rmantree)
            __RMAN_ENV_CONFIG__ = None
            return None

        # check if the major version of RenderMan is supported
        if buildinfo._version_major < rman_constants.RMAN_SUPPORTED_VERSION_MAJOR:
            rfb_log().error("Error loading addon using RMANTREE=%s.  The major version found (%d) is not supported. Minimum version supported is %s." % (rmantree, buildinfo._version_major, rman_constants.RMAN_SUPPORTED_VERSION_STRING))
            __RMAN_ENV_CONFIG__ = None
            return None

        # check if the minor version of RenderMan is supported
        if buildinfo._version_major == rman_constants.RMAN_SUPPORTED_VERSION_MAJOR and buildinfo._version_minor < rman_constants.RMAN_SUPPORTED_VERSION_MINOR:
            rfb_log().error("Error loading addon using RMANTREE=%s.  The minor version found (%s) is not supported. Minimum version supported is %s." % (rmantree, buildinfo._version_minor, rman_constants.RMAN_SUPPORTED_VERSION_STRING))
            __RMAN_ENV_CONFIG__ = None
            return None             

        rfb_log().debug("Guessed RMANTREE: %s" % rmantree)

    # Create an RmanEnvConfig object
    __RMAN_ENV_CONFIG__.rmantree = rmantree
    __RMAN_ENV_CONFIG__.build_info = buildinfo

    # configure python path
    if not __RMAN_ENV_CONFIG__.config_pythonpath():
        rfb_log().error("The Python version this Blender uses (%s) is not supported by this version of RenderMan (%s)" % (rman_constants.BLENDER_PYTHON_VERSION, rman_constants.RMAN_SUPPORTED_VERSION_STRING))
        __RMAN_ENV_CONFIG__ = None
        return None   

    __RMAN_ENV_CONFIG__.config_environment()

    return __RMAN_ENV_CONFIG__

def get_installed_rendermans():
    base = {'Windows': r'C:\Program Files\Pixar',
            'Darwin': '/Applications/Pixar',
            'Linux': '/opt/pixar'}[platform.system()]
    rendermans = []

    try:
        for d in os.listdir(base):
            if "RenderManProServer" in d:
                try:
                    vstr = d.split('-')[1]
                    rendermans.append((vstr, os.path.join(base, d)))
                except:
                    pass
    except:
        pass

    return rendermans    

def reload_envconfig():
    global __RMAN_ENV_CONFIG__
    if not _guess_rmantree():
        return None
    return __RMAN_ENV_CONFIG__    

def envconfig():

    global __RMAN_ENV_CONFIG__
    if not __RMAN_ENV_CONFIG__:
        if not _guess_rmantree():
            return None
    return __RMAN_ENV_CONFIG__

    
