import os
import bpy
import sys

RFB_ADDON_VERSION_MAJOR = 25
RFB_ADDON_VERSION_MINOR = 0
RFB_ADDON_VERSION_PATCH = 0
RFB_ADDON_VERSION = (RFB_ADDON_VERSION_MAJOR, RFB_ADDON_VERSION_MINOR, RFB_ADDON_VERSION_PATCH)
RFB_ADDON_VERSION_STRING = '%d.%d.%d' % (RFB_ADDON_VERSION_MAJOR, RFB_ADDON_VERSION_MINOR, RFB_ADDON_VERSION_PATCH)
RFB_ADDON_PATH = os.path.dirname(os.path.abspath(__file__))

BLENDER_VERSION_MAJOR = bpy.app.version[0]
BLENDER_VERSION_MINOR = bpy.app.version[1]
BLENDER_VERSION_PATCH = bpy.app.version[2]

BLENDER_VERSION = bpy.app.version

# Starting with Blender 3.5, the bgl module is considered deprecated
# addons are to use the gpu module
USE_GPU_MODULE = BLENDER_VERSION >= (3, 5, 0)

# Starting with Blender 3.6, Blender will now hand us metaballs in the depsgraph as meshes
# we can ignore "META" objects
META_AS_MESH = BLENDER_VERSION >= (3, 6, 0)

# curve nodes were added in Blender 3.3
BLENDER_HAS_CURVES_NODE = BLENDER_VERSION >= (3, 3, 0) 

# Check if we are using Blender 4.1
BLENDER_41 = BLENDER_VERSION >= (4, 1, 0)

BLENDER_SUPPORTED_VERSION_MAJOR = 2
BLENDER_SUPPORTED_VERSION_MINOR = 93
BLENDER_SUPPORTED_VERSION_PATCH = 0
BLENDER_SUPPORTED_VERSION = (BLENDER_SUPPORTED_VERSION_MAJOR, BLENDER_SUPPORTED_VERSION_MINOR, BLENDER_SUPPORTED_VERSION_PATCH)

pyver = sys.version_info
BLENDER_PYTHON_VERSION_MAJOR = pyver.major
BLENDER_PYTHON_VERSION_MINOR = pyver.minor
BLENDER_PYTHON_VERSION = '%s.%s' % (pyver.major, pyver.minor)

RMAN_SUPPORTED_VERSION_MAJOR = 26
RMAN_SUPPORTED_VERSION_MINOR = 1
RMAN_SUPPORTED_VERSION_BETA = ''
RMAN_SUPPORTED_VERSION = (RMAN_SUPPORTED_VERSION_MAJOR, RMAN_SUPPORTED_VERSION_MINOR, RMAN_SUPPORTED_VERSION_BETA)
RMAN_SUPPORTED_VERSION_STRING = '%d.%d%s' % (RMAN_SUPPORTED_VERSION_MAJOR, RMAN_SUPPORTED_VERSION_MINOR, RMAN_SUPPORTED_VERSION_BETA)

RFB_SCENE_VERSION_MAJOR = RMAN_SUPPORTED_VERSION_MAJOR
RFB_SCENE_VERSION_MINOR = RMAN_SUPPORTED_VERSION_MINOR
RFB_SCENE_VERSION_PATCH = 0
RFB_SCENE_VERSION_STRING = '%d.%d.%d' % (RFB_SCENE_VERSION_MAJOR, RFB_SCENE_VERSION_MINOR, RFB_SCENE_VERSION_PATCH)

RFB_ADDON_DESCRIPTION = 'RenderMan %d.%d integration' % (RMAN_SUPPORTED_VERSION_MAJOR, RMAN_SUPPORTED_VERSION_MINOR)

NODE_LAYOUT_SPLIT = 0.5
RFB_ARRAYS_MAX_LEN = 50
RFB_MAX_USER_TOKENS = 10
RFB_VIEWPORT_MAX_BUCKETS = 10
RFB_PREFS_NAME = __name__.split('.')[0]
RMAN_RENDERMAN_BLUE = (0.0, 0.498, 1.0, 1.0)
RMAN_FAKE_NODEGROUP = '.__RMAN_FAKE_NODEGROUP__'
RMAN_GLOBAL_VOL_AGGREGATE = 'globalVolumeAggregate'

RFB_HELP_URL = "https://rmanwiki.pixar.com/display/RFB%s" % RMAN_SUPPORTED_VERSION_MAJOR

RFB_FLOAT3 = ['color', 'point', 'vector', 'normal']
RFB_FLOATX = ['color', 'point', 'vector', 'normal', 'matrix']

# 
# Version for the preset browser asset
#
# 1.0: no version 
# 2.0: added version key, export all light rigs as Y-up
RFB_ASSET_VERSION_KEY = '__rman_asset_version__'
RFB_ASSET_VERSION = 2.0

RMAN_STYLIZED_FILTERS = [
    "PxrStylizedHatching",
    "PxrStylizedLines",
    "PxrStylizedToon"
]    

# These lights should be set as Blender AREA light type.
# This allows for target aiming using Shift + T.
# All other lights are set to be POINT light types.
RMAN_AREA_LIGHT_TYPES = [
    "PxrRectLight",
    "PxrDiskLight",
    "PxrDistantLight"
]

RMAN_STYLIZED_PATTERNS = ["PxrStylizedControl"]
RMAN_UTILITY_PATTERN_NAMES = [
                            "utilityPattern",
                            "userColor",
                            "inputAOV",
                            "utilityInteger"]

# special string to indicate an empty string
# necessary for EnumProperty because it cannot
# take an empty string as an item value
__RMAN_EMPTY_STRING__ = '__empty__'

# these are reserved property names for Blender's nodes
__RESERVED_BLENDER_NAMES__ = {
    'dimensions' : 'rman_dimensions',
    'inputs': 'rman_inputs',
    'outputs': 'rman_outputs',
    'resolution': 'rman_resolution',
    'name': 'rman_name'
}

# Map ramp interpolation types between RenderMan and Blender
# Blender doesn't have an equvialent to catmull-rom, so use cardinal
# as catmull-rom
RMAN_INTERP_MAP = { 'bspline':'B_SPLINE' , 'linear': 'LINEAR', 'constant': 'CONSTANT', 'catmull-rom': 'CARDINAL'}
BLENDER_INTERP_MAP = { 'B_SPLINE': 'bspline', 'LINEAR': 'linear', 'CONSTANT': 'constant', 'CARDINAL': 'catmull-rom'}

CYCLES_NODE_MAP = {
    'ShaderNodeAttribute': 'node_attribute',
    'ShaderNodeBlackbody': 'node_blackbody',
    'ShaderNodeTexBrick': 'node_brick_texture',
    'ShaderNodeBrightContrast': 'node_brightness',
    'ShaderNodeTexChecker': 'node_checker_texture',
    'ShaderNodeBump': 'node_bump',
    'ShaderNodeCameraData': 'node_camera',
    'ShaderNodeTexChecker': 'node_checker_texture',
    'ShaderNodeCombineHSV': 'node_combine_hsv',
    'ShaderNodeCombineRGB': 'node_combine_rgb',
    'ShaderNodeCombineXYZ': 'node_combine_xyz',
    'ShaderNodeTexEnvironment': 'node_environment_texture',
    'ShaderNodeFresnel': 'node_fresnel',
    'ShaderNodeGamma': 'node_gamma',
    'ShaderNodeNewGeometry': 'node_geometry',
    'ShaderNodeTexGradient': 'node_gradient_texture',
    'ShaderNodeHairInfo': 'node_hair_info',
    'ShaderNodeInvert': 'node_invert',
    'ShaderNodeHueSaturation': 'node_hsv',
    'ShaderNodeTexImage': 'node_image_texture',
    'ShaderNodeHueSaturation': 'node_hsv',
    'ShaderNodeLayerWeight': 'node_layer_weight',
    'ShaderNodeLightFalloff': 'node_light_falloff',
    'ShaderNodeLightPath': 'node_light_path',
    'ShaderNodeTexMagic': 'node_magic_texture',
    'ShaderNodeMapping': 'node_mapping',
    'ShaderNodeMath': 'node_math',
    'ShaderNodeMixRGB': 'node_mix',
    'ShaderNodeTexMusgrave': 'node_musgrave_texture',
    'ShaderNodeTexNoise': 'node_noise_texture',
    'ShaderNodeNormal': 'node_normal',
    'ShaderNodeNormalMap': 'node_normal_map',
    'ShaderNodeObjectInfo': 'node_object_info',
    'ShaderNodeParticleInfo': 'node_particle_info',
    'ShaderNodeRGBCurve': 'node_rgb_curves',
    'ShaderNodeValToRGB': 'node_rgb_ramp',
    'ShaderNodeSeparateHSV': 'node_separate_hsv',
    'ShaderNodeSeparateRGB': 'node_separate_rgb',
    'ShaderNodeSeparateXYZ': 'node_separate_xyz',
    'ShaderNodeTexSky': 'node_sky_texture',
    'ShaderNodeTangent': 'node_tangent',
    'ShaderNodeTexCoord': 'node_texture_coordinate',
    'ShaderNodeUVMap': 'node_uv_map',
    'ShaderNodeValue': 'node_value',
    'ShaderNodeVectorCurves': 'node_vector_curves',
    'ShaderNodeVectorMath': 'node_vector_math',
    'ShaderNodeVectorTransform': 'node_vector_transform',
    'ShaderNodeTexVoronoi': 'node_voronoi_texture',
    'ShaderNodeTexWave': 'node_wave_texture',
    'ShaderNodeWavelength': 'node_wavelength',
    'ShaderNodeWireframe': 'node_wireframe',
    'ShaderNodeDisplacement': 'node_displacement'
}

# map types in args files to socket types
__RMAN_SOCKET_MAP__ = {
    'float': 'RendermanNodeSocketFloat',
    'color': 'RendermanNodeSocketColor',
    'string': 'RendermanNodeSocketString',
    'int': 'RendermanNodeSocketInt',
    'integer': 'RendermanNodeSocketInt',
    'struct': 'RendermanNodeSocketStruct',
    'normal': 'RendermanNodeSocketNormal',
    'vector': 'RendermanNodeSocketVector',
    'point': 'RendermanNodeSocketPoint',
    'void': 'RendermanNodeSocketStruct',
    'vstruct': 'RendermanNodeSocketVStruct',
    'bxdf': 'RendermanNodeSocketBxdf'
}

RMAN_BL_NODE_DESCRIPTIONS = {
    # Lights
    'PxrRectLight': "This one-sided area light simulates a rectangular shaped light source.\nIts usage includes illuminating objects, simulating soft boxes used in photography, linear lights, fluorescent lights, and light panels. This is also used for adding bounce lighting off the walls.",
    'PxrCylinderLight': "This tube-shape area light simulates a fluorescent or similar shaped light source.\nIts usage includes illuminating objects, simulating commercial lighting used in many buildings, linear lights, fluorescent lights, and light panels. This is also used for making lightsabers.",
    'PxrDiskLight': "This one-sided area light simulates a disk-shaped light source.\nIts usage includes illuminating objects, simulating soft boxes used in photography, linear lights, fluorescent lights, and light panels. This is also used for adding bounce lighting off the walls.",
    'PxrDomeLight': "This light simulates environment lighting.\nIt works via Image Base lighting (IBL) to illuminate sets and characters with an environment map. Note that scaling and translation for this light will be ignored as it's considered nearly infinite or at least very far away. Only rotation matters so you can position your lighting accordingly. You may also have more than one in a scene for flexible lighting and linking to objects and portal lights.",
    'PxrEnvDayLight': "An environment light that uses a simple physical model for terrestrial daylight under clear or hazy skies. The sky model is based on A Practical Analytic Model for Daylight by A.J. Preetham, Peter Shirley, and Brian Smits. The solar disk model is adapted from H.C. Hottel's A Simple Model for Estimating the Transmittance of Direct Solar Radiation Through Clear Atmospheres, with parameters curve fitted for turbidity from physical data and a simple limb darkening model.",
    'PxrSphereLight': "This area light simulates point and spherical shaped light sources, like light bulbs, headlamps, and more!",
    'PxrDistantLight': "This infinite light simulates a bright distant light source like from the sun or moon. This light bathes the entire scene and treats the light as-if the rays are parallel by default",
    'PxrPortalLight': "Although a portal light is a rectangular shape, it is not interchangeable nor replaceable by a PxrRectLight because we get the illumination from the 3D environment using a PxrDomeLight. PxrPortalLight is one-sided. That is, there is no illumination behind the portal. If we need to illuminate the back side, we can create another portal facing the reverse direction.",
    'PxrAovLight': "Allows a lighting artist to output an AOV mask. Since it is a 'light', we can use light linking as well as light filter(s) to modify the output mask. This is a very handy 'utility' light to output shot-specific masks without needing to request them from the shading artists.",
    
    # Light Filters
    'PxrBarnLightFilter': "PxrBarnLightFilter allows us to create physically accurate window barns to simulate the real set lighting with correct shadowing. Its other usage include controlling bounce lights in a large scene. In addition to the physical mode, it also provides an analytic mode.",
    'PxrBlockerLightFilter': "PxrBlockerLightFilter uses a 'rod' like object to block light. The blocker can be shaped into an irregular shape. This blocker is then placed next to the object where we want to block the light. In this way it can float freely around your scene even if the light is static. In this example the blocker is placed on the statue on the pedestal.\nPxrBlockerLightFilter is a simple version of PxrRodLightFilter",
    'PxrCookieLightFilter': "PxrCookieLightFilter projects a painted texture in front of the light.\nThis light filter is a more extensive version of PxrGoboLightFilter",
    'PxrGoboLightFilter': "PxrGoboLightFilter projects a painted texture in front of the light.\nThis light filter is a simple version of PxrCookieLightFilter.",
    'PxrIntMultLightFilter': "PxrIntMultLightFilter is a light filter that allows you to multiply the intensity/exposure of the light. This is very useful when you want to isolate a particular asset(s) from the rest of the scene that has different intensity/exposure. This is via linking the objects to the PxrIntMultLightFilter. You can now guide your viewer using light intensity!",
    'PxrRampLightFilter': "PxrRampLightFilter uses a ramp to control the light. It may also be useful to artificially and artistically control light decay.",
    'PxrRodLightFilter': "PxrRodLightFilter uses a 'rod' like object to block light. The rod can be shaped into an irregular shape. This rod is then placed next to the object where we want to block the light.\nThis light filter is a more extensive version of PxrBlockerLightFilter.",
    'PxrCheatShadowLightFilter': "PxrCheatShadowLightFilter provides independent control over shadow positions without affecting the direction of illumination. Use translate for finite light sources (e.g. disk, rect, sphere, etc) and use rotation for infinite light sources (e.g. distant, sun halo, etc)",

    # Integrators
    'PxrPathTracer': "PxrPathTracer is a core final-quality integrator in RenderMan. It implements the forward path tracing algorithm, which excels in outdoor, highly specular scenes. The simplicity of the algorithm generally makes it easy to use and to implement. Shortcomings may include slow convergence speeds, especially for scenes with significant caustic illumination.",
    'PxrVCM': "PxrVCM is a core final-quality integrator in RenderMan. It combines bidirectional path tracing with progressive photon mapping (also known as vertex merging). Each of these techniques brings the ability to capture a certain range of light transport paths more efficiently than a pure forward path tracing algorithm.",
    'PxrUnified': "PxrUnified is the integrator Pixar relies on for its own film and animated shorts. It implements both the forward path tracing algorithm and bidirectional choices along with faster caustics using the Manifold Next Event Estimation technique here called Manifold Walk. We also include the options for Indirect Guiding that improves indirect lighting by sampling from the better lit or more important areas of the scene. ",
    'PxrOcclusion': "PxrOcclusion is a non-photorealistic integrator that can be used to render ambient occlusion, among other effects.",
    'PxrDirectLighting': "This is a debugging or 'draft-quality' integrator that implements only the direct lighting portion of the light transport. It is not designed to produce 'final-quality' images. Since it doesn't implement indirect lighting paths it cannot produce reflections, refractions, or other global illumination effects, nor can it handle any effects that require a volume integrator.",
    'PxrDefault': "Even simpler than PxrDirectLighting, the default integrator places a virtual light at the camera (the 'headlamp integrator''). No shadows or indirect lighting are evaluated. A good option when all is black - this integrator can help narrow down where a problem is occurring (for example, when the fault is in the lighting, particularly). Like PxrDirectLighting, it is not designed to produce 'final-quality' images.",
    'PxrDebugShadingContext': "This integrator is used to visualize data in the shading context, such as normals and texture coordinates. It is not designed to produce 'final-quality' images.",
    'PxrValidateBxdf': "This integrator serves mainly as a debugging tool to authors of Bxdf plugins.",
    'PxrVisualizer': "PxrVisualizer is a utility integrator that can be used to navigate large scenes and inspect geometry during Interactive re-rendering. It allows different styles of viewing, including shaded, flat, normals, st, wireframe.",

}

# LaMa nodes that need a LamaSurface
RFB_LAMA_NODES = [
    'LamaAdd', 
    'LamaConductor', 
    'LamaDielectric', 
    'LamaDiffuse', 
    'LamaEmission', 
    'LamaGeneralizedSchlick', 
    'LamaHairChiang', 
    'LamaIridescence', 
    'LamaLPE', 
    'LamaLayer', 
    'LamaMix', 
    'LamaSSS', 
    'LamaSheen',
    'LamaTranslucent', 
    'LamaTricolorSSS'
]

'''
Dictionary that contains restrictions on shader connections
ex: LamaSurface should not be an input to LamaMix

{ node_type {
    'outputs': {
        name_of_output: (list of node types)
    }
    'inputs': {
        name_of_inputs: (list of node types)
    }
}

}
'''
RFB_SHADER_ALLOWED_CONNECTIONS = {
    'LamaSurface': {
        'outputs': {
            'bxdf_out': ['RendermanOutputNode']
        },
        'inputs': {
            'materialFront': ['LamaAdd', 'LamaConductor', 'LamaDielectric', 'LamaDiffuse', 'LamaEmission', 
                              'LamaGeneralizedSchlick', 'LamaHairChiang', 'LamaIridescence', 
                              'LamaLPE', 'LamaLayer', 'LamaMix', 'LamaSSS', 'LamaSheen',
                              'LamaTranslucent', 'LamaTricolorSSS'
                              ],
            'materialBack': ['LamaAdd', 'LamaConductor', 'LamaDielectric', 'LamaDiffuse', 'LamaEmission', 
                              'LamaGeneralizedSchlick', 'LamaHairChiang', 'LamaIridescence', 
                              'LamaLPE', 'LamaLayer', 'LamaMix', 'LamaSSS', 'LamaSheen',
                              'LamaTranslucent', 'LamaTricolorSSS'
                              ],
        }          
    },
    'LamaAdd': {
        'outputs': {},
        'inputs': {
            'material1': ['LamaAdd', 'LamaConductor', 'LamaDielectric', 'LamaDiffuse', 'LamaEmission', 
                              'LamaGeneralizedSchlick', 'LamaHairChiang', 'LamaIridescence', 
                              'LamaLPE', 'LamaLayer', 'LamaMix', 'LamaSSS', 'LamaSheen',
                              'LamaTranslucent', 'LamaTricolorSSS'
                              ],
            'material2': ['LamaAdd', 'LamaConductor', 'LamaDielectric', 'LamaDiffuse', 'LamaEmission', 
                              'LamaGeneralizedSchlick', 'LamaHairChiang', 'LamaIridescence', 
                              'LamaLPE', 'LamaLayer', 'LamaMix', 'LamaSSS', 'LamaSheen',
                              'LamaTranslucent', 'LamaTricolorSSS'
                              ],            
        }
    },
    'LamaMix': {
        'outputs': {},
        'inputs': {
            'material1': ['LamaAdd', 'LamaConductor', 'LamaDielectric', 'LamaDiffuse', 'LamaEmission', 
                              'LamaGeneralizedSchlick', 'LamaHairChiang', 'LamaIridescence', 
                              'LamaLPE', 'LamaLayer', 'LamaMix', 'LamaSSS', 'LamaSheen',
                              'LamaTranslucent', 'LamaTricolorSSS'
                              ],
            'material2': ['LamaAdd', 'LamaConductor', 'LamaDielectric', 'LamaDiffuse', 'LamaEmission', 
                              'LamaGeneralizedSchlick', 'LamaHairChiang', 'LamaIridescence', 
                              'LamaLPE', 'LamaLayer', 'LamaMix', 'LamaSSS', 'LamaSheen',
                              'LamaTranslucent', 'LamaTricolorSSS'
                              ],            
        }
    },
    'LamaLayer': {
        'outputs': {},
        'inputs': {
            'materialTop': ['LamaAdd', 'LamaConductor', 'LamaDielectric', 'LamaDiffuse', 'LamaEmission', 
                              'LamaGeneralizedSchlick', 'LamaHairChiang', 'LamaIridescence', 
                              'LamaLPE', 'LamaLayer', 'LamaMix', 'LamaSSS', 'LamaSheen',
                              'LamaTranslucent', 'LamaTricolorSSS'
                              ],
            'materialBase': ['LamaAdd', 'LamaConductor', 'LamaDielectric', 'LamaDiffuse', 'LamaEmission', 
                              'LamaGeneralizedSchlick', 'LamaHairChiang', 'LamaIridescence', 
                              'LamaLPE', 'LamaLayer', 'LamaMix', 'LamaSSS', 'LamaSheen',
                              'LamaTranslucent', 'LamaTricolorSSS'
                              ],            
        }
    },        
}