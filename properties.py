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

import bpy
import os
import sys
import xml.etree.ElementTree as ET
import time

from .util import guess_rmantree

from .util import args_files_in_path
from .shader_parameters import class_generate_properties

from bpy.props import PointerProperty, StringProperty, BoolProperty, \
    EnumProperty, IntProperty, FloatProperty, FloatVectorProperty, \
    CollectionProperty, BoolVectorProperty


# get the names of args files in rmantree/lib/ris/integrator/args
def get_integrator_names():
    rmantree = guess_rmantree()
    args_path = os.path.join(rmantree, 'lib', 'RIS', 'integrator', 'Args')
    return [(f.split('.')[0], f.split('.')[0][3:], '')
            for f in os.listdir(args_path)]


class RendermanIntegratorSettings(bpy.types.PropertyGroup):
    pass


def register_integrator_settings(scene_settings_cls):
    rmantree = guess_rmantree()
    args_path = os.path.join(rmantree, 'lib', 'RIS', 'integrator', 'Args')
    items = []
    for f in os.listdir(args_path):
        name = f.split('.')[0]
        typename = '%sIntegratorSettings' % name
        ntype = type(typename, (RendermanIntegratorSettings,), {})
        ntype.bl_label = name
        ntype.typename = typename
        # do some parsing and get props
        args_xml = ET.parse(os.path.join(args_path, f)).getroot()
        inputs = [p for p in args_xml.findall('./param')] + \
            [p for p in args_xml.findall('./page')]
        class_generate_properties(ntype, name, inputs)
        # register and add to scene_settings
        bpy.utils.register_class(ntype)
        setattr(scene_settings_cls, "%s_settings" % name,
                PointerProperty(type=ntype, name="%s Settings" % name)
                )


class RendermanCameraSettings(bpy.types.PropertyGroup):
    bl_label = "Renderman Camera Settings"
    bl_idname = 'RendermanCameraSettings'
    use_physical_camera = BoolProperty(
        name="Use Physical Camera", default=False)

    aperture_sides = IntProperty(
        name="Aperture Blades", default=0, min=0,
        description="The number of sides of the aperture. If this value is less than 3, the default behavior of a circular aperture and uniform sampling are used.")

    aperture_angle = FloatProperty(
        name="Aperture Angle", default=0.0, max=180.0, min=-180.0,
        description="The aperture polygon's orientation, in degrees from some arbitrary reference direction. (A value of 0 aligns a vertex horizontally with the center of the aperture.)")  

    aperture_roundness = FloatProperty(
        name="Aperture Angle", default=0.0, max=1.0, min=-1.0,
        description="A shape parameter, from -1 to 1. When 0, the aperture is a regular polygon with straight sides. When 1, it's a perfect circle. Values between 0 and 1 give polygons with curved edges bowed out, while values between 0 and -1 make the edges bow in.") 

    aperture_density = FloatProperty(
        name="Aperture Angle", default=0.0, max=1.0, min=-1.0,
        description="The slope, between -1 and 1, of the (linearly varying) aperture density. A value of zero gives uniform density. Negative values make the aperture brighter near the center, and positive values make it brighter near the rim.") 


def register_camera_settings():
    rmantree = guess_rmantree()
    camera_args_files = [os.path.join(rmantree, 'lib', 'RIS', 'projection',
                                      'Args', 'PxrCamera.args')]
    # do some parsing and get props
    camera_classes = []
    for f in camera_args_files:
        name = os.path.basename(f).split('.')[0]
        typename = '%sCameraSettings' % name
        ntype = type(typename, (RendermanCameraSettings,), {})
        ntype.bl_label = name
        ntype.typename = typename
        # do some parsing and get props
        args_xml = ET.parse(f).getroot()
        inputs = [p for p in args_xml.findall('./param')] + \
            [p for p in args_xml.findall('./page')]
        class_generate_properties(ntype, name, inputs)
        # add the use

        # register and add to scene_settings
        bpy.utils.register_class(ntype)
        camera_classes.append(ntype)
        setattr(RendermanCameraSettings, "%s_settings" % name,
                PointerProperty(type=ntype, name="%s Settings" % name)
                )



# Blender data
# --------------------------

context_items = [(i.identifier, i.name, "")
                 for i in bpy.types.SpaceProperties.bl_rna.properties['context'].enum_items]

# hack! this is a bit of a hack in itself, but should really be in SpaceProperties.
# However, can't be added there, it's non-ID data.
bpy.types.WindowManager.prev_context = EnumProperty(
    name="Previous Context",
    description="Previous context viewed in properties editor",
    items=context_items,
    default=context_items[0][0])


class RendermanPath(bpy.types.PropertyGroup):
    name = StringProperty(
        name="", subtype='DIR_PATH')


class RendermanInlineRIB(bpy.types.PropertyGroup):
    name = StringProperty(name="Text Block")


class RendermanGrouping(bpy.types.PropertyGroup):
    name = StringProperty(name="Group Name")


class LightLinking(bpy.types.PropertyGroup):

    def lights_list_items(self, context):
        items = [('No light chosen', 'Choose a light', '')]
        for lamp in bpy.data.lamps:
            items.append((lamp.name, lamp.name, ''))
        return items

    def update_name(self, context):
        infostr = ('(Default)', '(Forced On)', '(Forced Off)')
        valstr = ('DEFAULT', 'ON', 'OFF')

        self.name = "%s %s" % (
            self.light, infostr[valstr.index(self.illuminate)])

        from . import engine
        if engine.ipr is not None and engine.ipr.is_interactive_running:
            engine.ipr.update_light_link(context, self)

    light = StringProperty(
        name="Light",
        update=update_name)

    illuminate = EnumProperty(
        name="Illuminate",
        update=update_name,
        items=[('DEFAULT', 'Default', ''),
               ('ON', 'On', ''),
               ('OFF', 'Off', '')])


class TraceSet(bpy.types.PropertyGroup):

    def groups_list_items(self, context):
        items = [('No group chosen', 'Choose a trace set', '')]
        for grp in context.scene.renderman.grouping_membership:
            items.append((grp.name, grp.name, ''))
        return items

    def update_name(self, context):
        self.name = self.mode + ' ' + self.group

    group = EnumProperty(name="Group",
                         update=update_name,
                         items=groups_list_items
                         )
    mode = EnumProperty(name="Include/Exclude",
                        update=update_name,
                        items=[('included in', 'Include', ''),
                               ('excluded from', 'Exclude', '')]
                        )

# hmmm, re-evaluate this idea later...


class RendermanPass(bpy.types.PropertyGroup):

    name = StringProperty(name="")
    type = EnumProperty(name="Pass Type",
                        items=[
                            ('SHADOW_MAPS_ALL', 'All Shadow Map',
                             'Single shadow map'),
                            ('SHADOW_MAP', 'Shadow Map',
                             'Single shadow map'),
                            ('POINTCLOUD', 'Point Cloud', '')],
                        default='SHADOW_MAPS_ALL')
    motion_blur = BoolProperty(name="Motion Blur")
    surface_shaders = BoolProperty(
        name="Surface Shaders", description="Render surface shaders")
    displacement_shaders = BoolProperty(
        name="Displacement Shaders", description="Render displacement shaders")
    light_shaders = BoolProperty(
        name="Light Shaders", description="Render light shaders")


class RendermanAOV(bpy.types.PropertyGroup):

    def built_in_channel_types(self, context):
        items = [('custom', 'Custom', 'Custom Type'),
                 ("lpe:C<.D%G>[S]+<L.%LG>", "Caustics", "Caustics"),
                 ("lpe:shadows;C[<.D%G><.S%G>]<L.%LG>", "Shadows", "Shadows"),
                 ("lpe:C<RS%G>([DS]+<L.%LG>)|([DS]*O)",
                  "Reflection", "Reflection"),
                 ("lpe:C<.D%G><L.%LG>", "Diffuse", "Diffuse"),
                 ("lpe:(C<RD%G>[DS]+<L.%LG>)|(C<RD%G>[DS]*O)",
                  "Indirectdiffuse", "IndirectDiffuse"),
                 ("lpe:C<.S%G><L.%LG>", "Specular", "Specular"),
                 ("lpe:(C<RS%G>[DS]+<L.%LG>)|(C<RS%G>[DS]*O)",
                  "Indirectspecular", "Indirectspecular"),
                 ("lpe:(C<TD%G>[DS]+<L.%LG>)|(C<TD%G>[DS]*O)",
                  "Subsurface", "Subsurface"),
                 ("lpe:(C<T[S]%G>[DS]+<L.%LG>)|(C<T[S]%G>[DS]*O)",
                  "Refraction", "Refraction"),
                 ]
        return items

    def update_type(self, context):
        types = self.built_in_channel_types(context)
        for item in types:
            if self.channel_type == item[0] and self.channel_type != 'custom':
                self.name = 'Custom_' + item[1]

    show_advanced = BoolProperty(name='Advanced', default=False)

    channel_type = EnumProperty(name="Channel type",
                                description="The type for this aov, setting to custom will allow a custom LPE",
                                items=built_in_channel_types, update=update_type)
    name = StringProperty(
        name="Channel Name",
        description="Name for the Channel in the output file")
    custom_lpe = StringProperty(
        name="lpe String",
        description="Custom lpe code")

    lpe_group = StringProperty(
        name="lpe Group",
        description="Object Group to use for this channel (default is all)",
        default=""
    )

    lpe_light_group = StringProperty(
        name="lpe Light Group",
        description="Light Group to use for this channel (default is all)",
        default=""
    )

    exposure_gain = FloatProperty(
        name="Gain",
        description="The gain of the exposure.",
        default=1.0)

    exposure_gamma = FloatProperty(
        name="Gamma",
        description="The gamma of the exposure.",
        default=1.0)

    remap_a = FloatProperty(
        name="a",
        description="A value for remap.",
        default=0.0)

    remap_b = FloatProperty(
        name="b",
        description="B value for remap.",
        default=0.0)

    remap_c = FloatProperty(
        name="c",
        description="C value for remap.",
        default=0.0)
        
class RendermanAOVList(bpy.types.PropertyGroup):
    render_layer = StringProperty()
    custom_aovs = CollectionProperty(type=RendermanAOV,
                                     name='Custom AOVs')
    custom_aov_index = IntProperty(min=-1, default=-1)


class RendermanSceneSettings(bpy.types.PropertyGroup):
    aov_lists = CollectionProperty(type=RendermanAOVList,
                                   name='Custom AOVs')
    aov_list_index = IntProperty(min=-1, default=-1)

    pixelsamples_x = IntProperty(
        name="Pixel Samples X",
        description="Number of AA samples to take in X dimension",
        min=0, max=16, default=2)
    pixelsamples_y = IntProperty(
        name="Pixel Samples Y",
        description="Number of AA samples to take in Y dimension",
        min=0, max=16, default=2)

    pixelfilter = EnumProperty(
        name="Pixel Filter",
        description="Filter to use to combine pixel samples",
        items=[('box', 'Box', ''),
               ('sinc', 'Sinc', ''),
               ('gaussian', 'Gaussian', '')],
        default='gaussian')
    pixelfilter_x = IntProperty(
        name="Filter Size X",
        description="Size of the pixel filter in X dimension",
        min=0, max=16, default=2)
    pixelfilter_y = IntProperty(
        name="Filter Size Y",
        description="Size of the pixel filter in Y dimension",
        min=0, max=16, default=2)

    pixel_variance = FloatProperty(
        name="Pixel Variance",
        description=" Sets a maximum for the estimated variance of the pixel value from the true value of the pixel.",
        min=0, max=1, default=.005)

    light_localization = BoolProperty(
        name="Light Localized Sampling",
        description="Localized sampling can give much less noisy renders with similar render times, and may in fact be faster with many lights.",
        default=True)

    min_samples = IntProperty(
        name="Min Samples",
        description="The minimum number of camera samples per pixel",
        min=0, default=4)
    max_samples = IntProperty(
        name="Max Samples",
        description="The maximum number of camera samples per pixel",
        min=0, default=128)

    bucket_shape = EnumProperty(
        name="Bucket Order",
        description="Order buckets are rendered in",
        items=[('HORIZONTAL', 'Horizontal', 'Render scanline from top to bottom'),
               ('VERTICAL', 'Vertical',
                'Render scanline from left to right'),
               ('ZIGZAG-X', 'Reverse Horizontal',
                'Exactly the same as Horizontal but reverses after each scan'),
               ('ZIGZAG-Y', 'Reverse Vertical',
                'Exactly the same as Vertical but reverses after each scan'),
               ('SPACEFILL', 'Hilber spacefilling curve',
                'Renders the buckets along a hilbert spacefilling curve'),
               ('SPIRAL', 'Spiral rendering',
                'Renders in a spiral from the center of the image or a custom defined point'),
               ('RANDOM', 'Random', 'Renders buckets in a random order WARNING: Inefficient memory footprint')],
        default='HORIZONTAL')

    bucket_sprial_x = IntProperty(
        name="X",
        description="X coordinate of bucket spiral start",
        min=-1, default=-1)

    bucket_sprial_y = IntProperty(
        name="Y",
        description="Y coordinate of bucket spiral start",
        min=-1, default=-1)

    shadingrate = FloatProperty(
        name="Shading Rate",
        description="Maximum distance between shading samples (lower = more detailed shading)",
        default=1.0)

    motion_blur = BoolProperty(
        name="Motion Blur",
        description="Enable motion blur",
        default=False)
    motion_segments = IntProperty(
        name="Motion Segments",
        description="Number of motion segments to take for multi-segment motion blur",
        min=1, max=16, default=1)
    shutter_open = FloatProperty(
        name="Shutter Open",
        description="Shutter open time (in frame time)",
        default=0.0)
    shutter_close = FloatProperty(
        name="Shutter Close",
        description="Shutter close time (in frame time)",
        default=1.0)

    shutter_efficiency_open = FloatProperty(
        name="Shutter open speed",
        description="Shutter open efficiency - controls the speed of the shutter opening (in shutter opening).  0 means instantaneous.",
        default=0.0)
    shutter_efficiency_close = FloatProperty(
        name="Shutter close speed",
        description="Shutter close efficiency - controls the speed of the shutter closing (in shutter opening).  1 means instantaneous.",
        default=1.0)

    depth_of_field = BoolProperty(
        name="Depth of Field",
        description="Enable depth of field blur",
        default=False)
    fstop = FloatProperty(
        name="F-Stop",
        description="Aperture size for depth of field",
        default=4.0)

    threads = IntProperty(
        name="Rendering Threads",
        description="Number of processor threads to use.  Note, 0 uses all cores, -1 uses all cores but one.",
        min=-32, max=32, default=-1)
    max_trace_depth = IntProperty(
        name="Max Trace Depth",
        description="Maximum number of ray bounces (0 disables ray tracing)",
        min=0, max=32, default=4)
    max_specular_depth = IntProperty(
        name="Max Specular Depth",
        description="Maximum number of specular ray bounces",
        min=0, max=32, default=2)
    max_diffuse_depth = IntProperty(
        name="Max Diffuse Depth",
        description="Maximum number of diffuse ray bounces",
        min=0, max=32, default=1)
    max_eye_splits = IntProperty(
        name="Max Eye Splits",
        description="Maximum number of times a primitive crossing the eye plane is split before being discarded",
        min=0, max=32, default=6)
    trace_approximation = FloatProperty(
        name="Raytrace Approximation",
        description="Threshold for using approximated geometry during ray tracing. Higher values use more approximated geometry.",
        min=0.0, max=1024.0, default=10.0)
    use_statistics = BoolProperty(
        name="Statistics",
        description="Print statistics to /tmp/stats.txt after render",
        default=False)
    editor_override = StringProperty(
        name="Text Editor",
        description="The editor to open RIB file in (Overrides system default!)",
        default="")
    statistics_level = IntProperty(
        name="Statistics Level",
        description="Verbosity level of output statistics",
        min=0, max=3, default=1)

    # RIB output properties

    path_rib_output = StringProperty(
        name="RIB Output Path",
        description="Path to generated .rib files",
        subtype='FILE_PATH',
        default=os.path.join('$OUT','{scene}.rib'))

    path_object_archive_static = StringProperty(
        name="Object archive RIB Output Path",
        description="Path to generated rib file for a non-deforming objects' geometry",
        subtype='FILE_PATH',
        default=os.path.join('$ARC','static','{object}.rib'))

    path_object_archive_animated = StringProperty(
        name="Object archive RIB Output Path",
        description="Path to generated rib file for an animated objects geometry",
        subtype='FILE_PATH',
        default=os.path.join('$ARC','####','{object}.rib'))

    path_texture_output = StringProperty(
        name="Teture Output Path",
        description="Path to generated .tex files",
        subtype='FILE_PATH',
        default=os.path.join('$OUT','textures'))

    out_dir = StringProperty(
        name="Shader Output Path",
        description="Path to compiled .oso files",
        subtype='FILE_PATH',
        default="./shaders")

    output_action = EnumProperty(
        name="Action",
        description="Action to take when rendering",
        items=[('EXPORT_RENDER', 'Export RIB and Render', 'Generate RIB file and render it with the renderer'),
               ('EXPORT', 'Export RIB Only', 'Generate RIB file only')],
        default='EXPORT_RENDER')

    lazy_rib_gen = BoolProperty(
        name="Cache Rib Generation",
        description="On unchanged objects, don't re-emit rib.  Will result in faster spooling of renders.",
        default=True)

    always_generate_textures = BoolProperty(
        name="Always Recompile Textures",
        description="Recompile used textures at export time to the current rib folder. Leave this unchecked to speed up re-render times",
        default=False)
    # preview settings
    preview_pixel_variance = FloatProperty(
        name="Preview Pixel Variance",
        description=" Sets a maximum for the estimated variance of the pixel value from the true value of the pixel.",
        min=0, max=1, default=.01)

    preview_bucket_order = EnumProperty(
        name="Preview Bucket Order",
        description="Bucket order to use when rendering",
        items=[('HORIZONTAL', 'Horizontal', 'Render scanline from top to bottom'),
               ('VERTICAL', 'Vertical',
                'Render scanline from left to right'),
               ('ZIGZAG-X', 'Reverse Horizontal',
                'Exactly the same as Horizontal but reverses after each scan'),
               ('ZIGZAG-Y', 'Reverse Vertical',
                'Exactly the same as Vertical but reverses after each scan'),
               ('SPACEFILL', 'Hilber spacefilling curve',
                'Renders the buckets along a hilbert spacefilling curve'),
               ('SPIRAL', 'Spiral rendering',
                'Renders in a spiral from the center of the image or a custom defined point'),
               ('RANDOM', 'Random', 'Renders buckets in a random order WARNING: Inefficient memory footprint')],
        default='SPIRAL')

    preview_min_samples = IntProperty(
        name="Preview Min Samples",
        description="The minimum number of camera samples per pixel",
        min=0, default=0)
    preview_max_samples = IntProperty(
        name="Preview Max Samples",
        description="The maximum number of camera samples per pixel",
        min=0, default=16)

    preview_max_specular_depth = IntProperty(
        name="Max Preview Specular Depth",
        description="Maximum number of specular ray bounces",
        min=0, max=32, default=2)
    preview_max_diffuse_depth = IntProperty(
        name="Max Preview Diffuse Depth",
        description="Maximum number of diffuse ray bounces",
        min=0, max=32, default=1)
    
    def display_driver_items(self, context):
        items = [('openexr', 'OpenEXR', 'Render to a OpenEXR file, to be read back into Blender\'s Render Result'),
                 ('tiff', 'Tiff',
                  'Render to a TIFF file, to be read back into Blender\'s Render Result'),
                 ('it', 'it', 'External framebuffer display (must have RMS installed)')]
        return items

    display_driver = EnumProperty(
        name="Display Driver",
        description="File Type for output pixels, 'it' will send to an external framebuffer",
        items=display_driver_items)

    do_denoise = BoolProperty(
        name="Denoise Post-Process",
        description="Denoise the image.  This will let set your sampling values low and get faster render times and runs denoise to remove the noise as a post process.",
        default=False)

    path_display_driver_image = StringProperty(
        name="Display Image",
        description="Render output path to export as the Display in the RIB file. When later rendering the RIB file manually, this will be the raw render result directly from the renderer, and won't pass through blender's render pipeline",
        subtype='FILE_PATH',
        default=os.path.join('$OUT', 'images', '{scene}_####.{file_type}'))

    update_frequency = FloatProperty(
        name="Update frequency",
        description="Number of seconds between display update when rendering to Blender",
        min=0.0, default=5.0)

    # Hider properties
    hider = EnumProperty(
        name="Hider",
        description="Algorithm to use for determining hidden surfaces",
        items=[('raytrace', 'Raytrace', 'Use ray tracing on the first hit'),

               ],
        default='raytrace')

    hidden_depthfilter = EnumProperty(
        name="Depth Filter",
        description="Method used for determining sample depth",
        items=[('min', 'Min',
                'Minimum z value of all the sub samples in a given pixel'),
               ('max', 'Max',
                'Maximum z value of all the sub samples in a given pixel'),
               ('average', 'Average',
                'Average all sub samples’ z values in a given pixel'),
               ('midpoint', 'Midpoint',
                'For each sub sample in a pixel, the renderer takes the average z value of the two closest surfaces')],
        default='min')

    hidden_jitter = BoolProperty(
        name="Jitter",
        description="Use a jittered grid for sampling",
        default=True)

    hidden_samplemotion = BoolProperty(
        name="Sample Motion",
        description="Disabling this will not render motion blur, but still preserve motion vector information (dPdtime)",
        default=True)

    hidden_extrememotiondof = BoolProperty(
        name="Extreme Motion/DoF",
        description="Use a more accurate, but slower algorithm to sample motion blur and depth of field effects. This is useful to fix artifacts caused by extreme amounts of motion or DoF",
        default=False)

    hidden_midpointratio = FloatProperty(
        name="Midpoint Ratio",
        description="Amount of blending between the z values of the first two samples when using the midpoint depth filter",
        default=0.5)

    hidden_maxvpdepth = IntProperty(
        name="Max Visible Point Depth",
        description="The number of visible points to be composited in the hider or included in deep shadow map creation. Putting a limit on the number of visible points can accelerate deep shadow map creation for depth-complex scenes. The default value of -1 means no limit",
        min=-1, max=1024, default=-1)

    raytrace_progressive = BoolProperty(
        name="Progressive Rendering",
        description="Enables progressive rendering. This is only visible with some display drivers (such as it)",
        default=False)
    integrator = EnumProperty(
        name="Integrator",
        description="Integrator for rendering",
        items=get_integrator_names(),
        default='PxrPathTracer')

    show_integrator_settings = BoolProperty(
        name="Integration Settings",
        description="Show Integrator Settings",
        default=False
    )

    # Rib Box Properties
    bty_inlinerib_texts = CollectionProperty(
        type=RendermanInlineRIB, name="Beauty-pass Inline RIB")
    bty_inlinerib_index = IntProperty(min=-1, default=-1)

    # Trace Sets (grouping membership)
    grouping_membership = CollectionProperty(
        type=RendermanGrouping, name="Trace Sets")
    grouping_membership_index = IntProperty(min=-1, default=-1)

    use_default_paths = BoolProperty(
        name="Use 3Delight default paths",
        description="Includes paths for default shaders etc. from 3Delight install",
        default=True)
    use_builtin_paths = BoolProperty(
        name="Use built in paths",
        description="Includes paths for default shaders etc. from Blender->3Delight exporter",
        default=False)

    path_rmantree = StringProperty(
        name="RMANTREE Path",
        description="Path to RenderManProServer installation folder",
        subtype='DIR_PATH',
        default=guess_rmantree())
    path_renderer = StringProperty(
        name="Renderer Path",
        description="Path to renderer executable",
        subtype='FILE_PATH',
        default="prman")
    path_shader_compiler = StringProperty(
        name="Shader Compiler Path",
        description="Path to shader compiler executable",
        subtype='FILE_PATH',
        default="shader")
    path_shader_info = StringProperty(
        name="Shader Info Path",
        description="Path to shaderinfo executable",
        subtype='FILE_PATH',
        default="sloinfo")
    path_texture_optimiser = StringProperty(
        name="Texture Optimiser Path",
        description="Path to tdlmake executable",
        subtype='FILE_PATH',
        default="txmake")

    render_passes = CollectionProperty(
        type=RendermanPass, name="Render Passes")
    render_passes_index = IntProperty(min=-1, default=-1)


class RendermanMaterialSettings(bpy.types.PropertyGroup):

    nodetree = StringProperty(
        name="Node Tree",
        description="Name of the shader node tree for this material",
        default="")

    displacementbound = FloatProperty(
        name="Displacement Bound",
        description="Maximum distance the displacement shader can displace vertices",
        precision=4,
        default=0.5)

    preview_render_type = EnumProperty(
        name="Preview Render Type",
        description="Object to display in material preview",
        items=[('SPHERE', 'Sphere', ''),
               ('CUBE', 'Cube', '')],
        default='SPHERE')

    preview_render_shadow = BoolProperty(
        name="Display Shadow",
        description="Render a raytraced shadow in the material preview",
        default=True)


class RendermanAnimSequenceSettings(bpy.types.PropertyGroup):
    animated_sequence = BoolProperty(
        name="Animated Sequence",
        description="Interpret this texture as an animated sequence (converts #### in file path to frame number)",
        default=False)
    sequence_in = IntProperty(
        name="Sequence In Point",
        description="The first numbered image file to use",
        default=1)
    sequence_out = IntProperty(
        name="Sequence Out Point",
        description="The last numbered image file to use",
        default=24)
    blender_start = IntProperty(
        name="Blender Start Frame",
        description="The frame in Blender to begin playing back the sequence",
        default=1)
    '''
    extend_in = EnumProperty(
                name="Extend In",
                items=[('HOLD', 'Hold', ''),
                    ('LOOP', 'Loop', ''),
                    ('PINGPONG', 'Ping-pong', '')],
                default='HOLD')
    extend_out = EnumProperty(
                name="Extend In",
                items=[('HOLD', 'Hold', ''),
                    ('LOOP', 'Loop', ''),
                    ('PINGPONG', 'Ping-pong', '')],
                default='HOLD')
    '''


class RendermanTextureSettings(bpy.types.PropertyGroup):
    # animation settings

    anim_settings = PointerProperty(
        type=RendermanAnimSequenceSettings,
        name="Animation Sequence Settings")

    # texture optimiser settings
    '''
    type = EnumProperty(
                name="Data type",
                description="Type of external file",
                items=[('NONE', 'None', ''),
                    ('IMAGE', 'Image', ''),
                    ('POINTCLOUD', 'Point Cloud', '')],
                default='NONE')
    '''
    format = EnumProperty(
        name="Format",
        description="Image representation",
        items=[('TEXTURE', 'Texture Map', ''),
               ('ENV_LATLONG', 'LatLong Environment Map', '')
               ],
        default='TEXTURE')
    auto_generate_texture = BoolProperty(
        name="Auto-Generate Optimized",
        description="Use the texture optimiser to convert image for rendering",
        default=False)
    file_path = StringProperty(
        name="Source File Path",
        description="Path to original image",
        subtype='FILE_PATH',
        default="")
    wrap_s = EnumProperty(
        name="Wrapping S",
        items=[('black', 'Black', ''),
               ('clamp', 'Clamp', ''),
               ('periodic', 'Periodic', '')],
        default='clamp')
    wrap_t = EnumProperty(
        name="Wrapping T",
        items=[('black', 'Black', ''),
               ('clamp', 'Clamp', ''),
               ('periodic', 'Periodic', '')],
        default='clamp')
    flip_s = BoolProperty(
        name="Flip S",
        description="Mirror the texture in S",
        default=False)
    flip_t = BoolProperty(
        name="Flip T",
        description="Mirror the texture in T",
        default=False)

    filter_type = EnumProperty(
        name="Downsampling Filter",
        items=[('DEFAULT', 'Default', ''),
               ('box', 'Box', ''),
               ('triangle', 'Triangle', ''),
               ('gaussian', 'Gaussian', ''),
               ('sinc', 'Sinc', ''),
               ('catmull-rom', 'Catmull-Rom', ''),
               ('bessel', 'Bessel', '')],
        default='DEFAULT',
        description='Downsampling filter for generating mipmaps')
    filter_window = EnumProperty(
        name="Filter Window",
        items=[('DEFAULT', 'Default', ''),
               ('lanczos', 'Lanczos', ''),
               ('hamming', 'Hamming', ''),
               ('hann', 'Hann', ''),
               ('blackman', 'Blackman', '')],
        default='DEFAULT',
        description='Downsampling filter window for infinite support filters')

    filter_width_s = FloatProperty(
        name="Filter Width S",
        description="Filter diameter in S",
        min=0.0, soft_max=1.0, default=1.0)
    filter_width_t = FloatProperty(
        name="Filter Width T",
        description="Filter diameter in T",
        min=0.0, soft_max=1.0, default=1.0)
    filter_blur = FloatProperty(
        name="Filter Blur",
        description="Blur factor: > 1.0 is blurry, < 1.0 is sharper",
        min=0.0, soft_max=1.0, default=1.0)

    input_color_space = EnumProperty(
        name="Input Color Space",
        items=[('srgb', 'sRGB', ''),
               ('linear', 'Linear RGB', ''),
               ('GAMMA', 'Gamma', '')],
        default='srgb',
        description='Color space of input image')
    input_gamma = FloatProperty(
        name="Input Gamma",
        description="Gamma value of input image if using gamma color space",
        min=0.0, soft_max=3.0, default=2.2)

    output_color_depth = EnumProperty(
        name="Output Color Depth",
        items=[('UBYTE', '8-bit unsigned', ''),
               ('SBYTE', '8-bit signed', ''),
               ('USHORT', '16-bit unsigned', ''),
               ('SSHORT', '16-bit signed', ''),
               ('FLOAT', '32 bit float', '')],
        default='UBYTE',
        description='Color depth of output image')

    output_compression = EnumProperty(
        name="Output Compression",
        items=[('LZW', 'LZW', ''),
               ('ZIP', 'Zip', ''),
               ('PACKBITS', 'PackBits', ''),
               ('LOGLUV', 'LogLUV (float only)', ''),
               ('UNCOMPRESSED', 'Uncompressed', '')],
        default='ZIP',
        description='Compression of output image data')

    generate_if_nonexistent = BoolProperty(
        name="Generate if Non-existent",
        description="Generate if optimised image does not exist in the same folder as source image path",
        default=True)
    generate_if_older = BoolProperty(
        name="Generate if Optimised is Older",
        description="Generate if optimised image is older than corresponding source image",
        default=True)


class RendermanLightSettings(bpy.types.PropertyGroup):

    # do this to keep the nice viewport update
    def update_light_type(self, context):
        lamp = context.lamp
        if lamp.renderman.renderman_type in ['SKY', 'ENV']:
            lamp.type = 'HEMI'
        elif lamp.renderman.renderman_type == 'DIST':
            lamp.type = 'SUN'
        else:
            lamp.type = lamp.renderman.renderman_type

        light_type = lamp.renderman.renderman_type
        # use pxr area light for everything but env, sky
        light_shader = 'PxrStdAreaLightLightNode'
        if light_type == 'ENV':
            light_shader = 'PxrStdEnvMapLightLightNode'
        elif light_type == 'SKY':
            light_shader = 'PxrStdEnvDayLightLightNode'
        elif light_type == 'AREA':
            try:
                lamp.size = 1.0
                lamp.size_y = 1.0
            except:
                pass

        # find the existing or make a new light shader node
        nt = bpy.data.node_groups[lamp.renderman.nodetree]
        output = None
        for node in nt.nodes:
            if node.renderman_node_type == 'output':
                output = node
                break
        for node in nt.nodes:
            if hasattr(node, 'typename') and node.typename == light_shader:
                nt.links.remove(output.inputs['Light'].links[0])
                nt.links.new(node.outputs[0], output.inputs['Light'])
                break
        else:
            light = nt.nodes.new(light_shader)
            light.location = output.location
            light.location[0] -= 300
            nt.links.remove(output.inputs['Light'].links[0])
            nt.links.new(light.outputs[0], output.inputs['Light'])

    def update_area_shape(self, context):
        lamp = context.lamp
        
        # find the existing or make a new light shader node
        nt = bpy.data.node_groups[lamp.renderman.nodetree]
        output = None
        for node in nt.nodes:
            if node.renderman_node_type == 'output':
                output = node
                break
        if output and output.inputs['Light'].is_linked:
            light_shader = output.inputs['Light'].links[0].from_node
            if hasattr(light_shader, 'rman__Shape'):
                light_shader.rman__Shape = self.area_shape

    renderman_type = EnumProperty(
        name="Light Type",
        update=update_light_type,
        items=[('AREA', 'Area', 'Area Light'),
               ('ENV', 'Environment', 'Environment Light'),
               ('SKY', 'Sky', 'Simulated Sky'),
               ('DIST', 'Distant', 'Distant Light'),
               ('SPOT', 'Spot', 'Spot Light'),
               ('POINT', 'Point', 'Point Light')],
        default='AREA'
    )

    area_shape =  EnumProperty(
        name="Area Shape",
        update=update_area_shape,
        items=[('rect', 'Rectangle', 'Rectangle'),
               ('disk', 'Disk', 'Disk'),
               ('sphere', 'Sphere', 'Sphere'),
               ('cylinder', 'Cylinder', 'Cylinder')],
        default='rect'
    )

    nodetree = StringProperty(
        name="Node Tree",
        description="Name of the shader node tree for this light",
        default="")

    shadingrate = FloatProperty(
        name="Light Shading Rate",
        description="Shading Rate for lights.  Keep this high unless needed for using detailed maps",
        default=100.0)

    # Rib Box Properties
    shd_inlinerib_texts = CollectionProperty(
        type=RendermanInlineRIB, name='Shadow map pass Inline RIB')
    shd_inlinerib_index = IntProperty(min=-1, default=-1)

    # illuminate
    illuminates_by_default = BoolProperty(
        name="Illuminates by default",
        description="Illuminates by default",
        default=True)


class RendermanMeshPrimVar(bpy.types.PropertyGroup):
    name = StringProperty(
        name="Variable Name",
        description="Name of the exported renderman primitive variable")
    data_name = StringProperty(
        name="Data Name",
        description="Name of the Blender data to export as the primitive variable")
    data_source = EnumProperty(
        name="Data Source",
        description="Blender data type to export as the primitive variable",
        items=[('VERTEX_GROUP', 'Vertex Group', ''),
               ('VERTEX_COLOR', 'Vertex Color', ''),
               ('UV_TEXTURE', 'UV Texture', '')
               ]
    )


class RendermanParticlePrimVar(bpy.types.PropertyGroup):
    name = StringProperty(
        name="Variable Name",
        description="Name of the exported renderman primitive variable")
    data_source = EnumProperty(
        name="Data Source",
        description="Blender data type to export as the primitive variable",
        items=[('SIZE', 'Size', ''),
               ('VELOCITY', 'Velocity', ''),
               ('ANGULAR_VELOCITY', 'Angular Velocity', ''),
               ('AGE', 'Age', ''),
               ('BIRTH_TIME', 'Birth Time', ''),
               ('DIE_TIME', 'Die Time', ''),
               ('LIFE_TIME', 'Lifetime', '')
              ]   # XXX: Would be nice to have particle ID, needs adding in RNA
    )


class oslProps(bpy.types.PropertyGroup):
    shaderString = StringProperty(
        name="Shader",
        description="OSL shader to use",
        default="")


class RendermanParticleSettings(bpy.types.PropertyGroup):

    material_id = IntProperty(
        name="Material",
        description="Material ID to use for particle shading",
        default=1)

    use_object_material = BoolProperty(
        name="Use Master Object's Material",
        description="Use the master object's material for instancing",
        default=False
    )

    particle_type_items = [('particle', 'Particle', 'Point primitive'),
                           ('blobby', 'Blobby',
                            'Implicit Surface (metaballs)'),
                           ('sphere', 'Sphere', 'Two-sided sphere primitive'),
                           ('disk', 'Disk', 'One-sided disk primitive'),
                           ('OBJECT', 'Object',
                            'Instanced objects at each point')
                           ]

    particle_type = EnumProperty(
        name="Point Type",
        description="Geometric primitive for points to be rendered as",
        items=particle_type_items,
        default='particle')
    particle_instance_object = StringProperty(
        name="Instance Object",
        description="Object to instance on every particle",
        default="")

    constant_width = BoolProperty(
        name="Constant Width",
        description="Override particle sizes with constant width value",
        default=True)

    base_width = FloatProperty(
        name="Base Width",
        description="The width of the base of hair",
        precision=4,
        default=.01)

    tip_width = FloatProperty(
        name="Tip Width",
        description="The width of the tip of hair",
        precision=4,
        default=0.00)

    width = FloatProperty(
        name="Width",
        description="With used for constant width across all particles",
        precision=4,
        default=0.01)

    width_offset = FloatProperty(
        name="Width Offset",
        description="Offset from the root to start the thickness variation",
        precision=4,
        default=0.00)

    export_default_size = BoolProperty(
        name="Export Default size",
        description="Export the particle size as the default 'width' primitive variable",
        default=True)

    export_scalp_st = BoolProperty(
        name="Export Emitter UV",
        description="On hair, export the u/v from the emitter where the hair originates.  Use the variables 'scalpS' and 'scalpT' in your manifold node.",
        default=False
        )

    prim_vars = CollectionProperty(
        type=RendermanParticlePrimVar, name="Primitive Variables")
    prim_vars_index = IntProperty(min=-1, default=-1)


class RendermanMeshGeometrySettings(bpy.types.PropertyGroup):
    export_default_uv = BoolProperty(
        name="Export Default UVs",
        description="Export the active UV set as the default 'st' primitive variable",
        default=True)
    export_default_vcol = BoolProperty(
        name="Export Default Vertex Color",
        description="Export the active Vertex Color set as the default 'Cs' primitive variable",
        default=True)
    export_smooth_normals = BoolProperty(
        name="Export Smooth Normals",
        description="Export smooth per-vertex normals for PointsPolygons Geometry",
        default=False)

    prim_vars = CollectionProperty(
        type=RendermanMeshPrimVar, name="Primitive Variables")
    prim_vars_index = IntProperty(min=-1, default=-1)


class RendermanCurveGeometrySettings(bpy.types.PropertyGroup):
    export_default_uv = BoolProperty(
        name="Export Default UVs",
        description="Export the active UV set as the default 'st' primitive variable",
        default=True)
    export_default_vcol = BoolProperty(
        name="Export Default Vertex Color",
        description="Export the active Vertex Color set as the default 'Cs' primitive variable",
        default=True)
    export_smooth_normals = BoolProperty(
        name="Export Smooth Normals",
        description="Export smooth per-vertex normals for PointsPolygons Geometry",
        default=True)

    prim_vars = CollectionProperty(
        type=RendermanMeshPrimVar, name="Primitive Variables")
    prim_vars_index = IntProperty(min=-1, default=-1)


class RendermanObjectSettings(bpy.types.PropertyGroup):

    # for some odd reason blender truncates this as a float
    update_timestamp = IntProperty(
        name="Update Timestamp", default=int(time.time()),
        description="Used for telling if an objects rib archive is dirty", subtype='UNSIGNED'
    )

    do_holdout = BoolProperty(
        name="Holdout Object",
        description="Collect holdout data for this object",
        default=False)

    lpe_group = StringProperty(
        name="Holdout Group",
        description="Group name for collecting holdouts.",
        default="collector")

    geometry_source = EnumProperty(
        name="Geometry Source",
        description="Where to get the geometry data for this object",
        items=[('BLENDER_SCENE_DATA', 'Blender Scene Data', 'Exports and renders blender scene data directly from memory'),
               ('ARCHIVE', 'Archive',
                'Renders a prevously exported RIB archive'),
               ('DELAYED_LOAD_ARCHIVE', 'Delayed Load Archive',
                'Loads and renders geometry from an archive only when its bounding box is visible'),
               ('PROCEDURAL_RUN_PROGRAM', 'Procedural Run Program',
                'Generates procedural geometry at render time from an external program'),
               ('DYNAMIC_LOAD_DSO', 'Dynamic Load DSO',
                'Generates procedural geometry at render time from a dynamic shared object library')
               ],
        default='BLENDER_SCENE_DATA')

    archive_anim_settings = PointerProperty(
        type=RendermanAnimSequenceSettings,
        name="Animation Sequence Settings")

    path_archive = StringProperty(
        name="Archive Path",
        description="Path to archive file",
        subtype='FILE_PATH',
        default="")

    procedural_bounds = EnumProperty(
        name="Procedural Bounds",
        description="The bounding box of the renderable geometry",
        items=[('BLENDER_OBJECT', 'Blender Object', "Use the blender object's bounding box for the archive's bounds"),
               ('MANUAL', 'Manual',
                'Manually enter the bounding box coordinates')
               ],
        default="BLENDER_OBJECT")

    path_runprogram = StringProperty(
        name="Program Path",
        description="Path to external program",
        subtype='FILE_PATH',
        default="")
    path_runprogram_args = StringProperty(
        name="Program Arguments",
        description="Command line arguments to external program",
        default="")
    path_dso = StringProperty(
        name="DSO Path",
        description="Path to DSO library file",
        subtype='FILE_PATH',
        default="")
    path_dso_initial_data = StringProperty(
        name="DSO Initial Data",
        description="Parameters to send the DSO",
        default="")
    procedural_bounds_min = FloatVectorProperty(
        name="Min Bounds",
        description="Minimum corner of bounding box for this procedural geometry",
        size=3,
        default=[0.0, 0.0, 0.0])
    procedural_bounds_max = FloatVectorProperty(
        name="Max Bounds",
        description="Maximum corner of bounding box for this procedural geometry",
        size=3,
        default=[1.0, 1.0, 1.0])

    primitive = EnumProperty(
        name="Primitive Type",
        description="Representation of this object's geometry in the renderer",
        items=[('AUTO', 'Automatic', 'Automatically determine the object type from context and modifiers used'),
               ('POLYGON_MESH', 'Polygon Mesh', 'Mesh object'),
               ('SUBDIVISION_MESH', 'Subdivision Mesh',
                'Smooth subdivision surface formed by mesh cage'),
               ('POINTS', 'Points',
                'Renders object vertices as single points'),
               ('SPHERE', 'Sphere', 'Parametric sphere primitive'),
               ('CYLINDER', 'Cylinder', 'Parametric cylinder primitive'),
               ('CONE', 'Cone', 'Parametric cone primitive'),
               ('DISK', 'Disk', 'Parametric 2D disk primitive'),
               ('TORUS', 'Torus', 'Parametric torus primitive')
               ],
        default='AUTO')

    export_archive = BoolProperty(
        name="Export as Archive",
        description="At render export time, store this object as a RIB archive",
        default=False)
    export_archive_path = StringProperty(
        name="Archive Path",
        description="Location and name to give archive.",
        subtype='FILE_PATH',
        default="")

    export_mat = BoolProperty(
        name="Export Material",
        description="Do you want to export the material?",
        default=False)
        
    export_all_frames = BoolProperty(
        name="Export All Frames",
        description="Export entire animation time frame",
        default=False)
    
    material_in_archive = BoolProperty(
        name="Material in archive",
        description="Use material in archive if present",
        default=False)
    
    primitive_radius = FloatProperty(
        name="Radius",
        default=1.0)
    primitive_zmin = FloatProperty(
        name="Z min",
        description="Minimum height clipping of the primitive",
        default=-1.0)
    primitive_zmax = FloatProperty(
        name="Z max",
        description="Maximum height clipping of the primitive",
        default=1.0)
    primitive_sweepangle = FloatProperty(
        name="Sweep Angle",
        description="Angle of clipping around the Z axis",
        default=360.0)
    primitive_height = FloatProperty(
        name="Height",
        description="Height offset above XY plane",
        default=0.0)
    primitive_majorradius = FloatProperty(
        name="Major Radius",
        description="Radius of Torus ring",
        default=2.0)
    primitive_minorradius = FloatProperty(
        name="Minor Radius",
        description="Radius of Torus cross-section circle",
        default=0.5)
    primitive_phimin = FloatProperty(
        name="Minimum Cross-section",
        description="Minimum angle of cross-section circle",
        default=0.0)
    primitive_phimax = FloatProperty(
        name="Maximum Cross-section",
        description="Maximum angle of cross-section circle",
        default=360.0)
    primitive_point_type = EnumProperty(
        name="Point Type",
        description="Geometric primitive for points to be rendered as",
        items=[('particle', 'Particle', 'Point primitive'),
               ('blobby', 'Blobby', 'Implicit Surface (metaballs)'),
               ('sphere', 'Sphere', 'Two-sided sphere primitive'),
               ('disk', 'Disk', 'One-sided disk primitive')
               ],
        default='particle')
    primitive_point_width = FloatProperty(
        name="Point Width",
        description="Size of the rendered points",
        default=0.1)

    shading_override = BoolProperty(
        name="Override Default Shading Rate",
        description="Override the default shading rate for this object.",
        default=False)
    shadingrate = FloatProperty(
        name="Shading Rate",
        description="Maximum distance between shading samples (lower = more detailed shading)",
        default=1.0)
    geometric_approx_motion = FloatProperty(
        name="Motion Approximation",
        description="Shading Rate is scaled up by motionfactor/16 times the number of pixels of motion",
        default=1.0)
    geometric_approx_focus = FloatProperty(
        name="Focus Approximation",
        description="Shading Rate is scaled proportionally to the radius of DoF circle of confusion, multiplied by this value",
        default=-1.0)

    motion_segments_override = BoolProperty(
        name="Override Motion Segments",
        description="Override the global number of motion segments for this object",
        default=False)
    motion_segments = IntProperty(
        name="Motion Segments",
        description="Number of motion segments to take for multi-segment motion blur",
        min=1, max=16, default=1)

    shadinginterpolation = EnumProperty(
        name="Shading Interpolation",
        description="Method of interpolating shade samples across micropolygons",
        items=[('constant', 'Constant', 'Flat shaded micropolygons'),
               ('smooth', 'Smooth', 'Gourard shaded micropolygons')],
        default='smooth')

    matte = BoolProperty(
        name="Matte Object",
        description="Render the object as a matte cutout (alpha 0.0 in final frame)",
        default=False)
    visibility_camera = BoolProperty(
        name="Visible to Camera Rays",
        description="Visibility to Camera Rays",
        default=True)
    visibility_trace_indirect = BoolProperty(
        name="All Indirect Rays",
        description="Sets all the indirect transport modes at once (specular & diffuse)",
        default=True)
    visibility_trace_transmission = BoolProperty(
        name="Visible to Transmission Rays",
        description="Visibility to Transmission Rays (eg. shadow() and transmission())",
        default=True)

    raytrace_override = BoolProperty(
        name="Ray Trace Override",
        description="Override default Renderman ray tracing behavior. Recommended for advanced users only.",
        default=False)
    raytrace_maxdiffusedepth = IntProperty(
        name="Max Diffuse Depth",
        description="Limit the number of diffuse bounces",
        min=1, max=16, default=1)
    raytrace_maxspeculardepth = IntProperty(
        name="Max Specular Depth",
        description="Limit the number of specular bounces",
        min=1, max=16, default=2)
    raytrace_tracedisplacements = BoolProperty(
        name="Trace Displacements",
        description="Ray Trace true displacement in rendered results",
        default=True)
    raytrace_autobias = BoolProperty(
        name="Ray Origin Auto Bias",
        description="Bias value is automatically computed",
        default=True)
    raytrace_bias = FloatProperty(
        name="Ray Origin Bias Amount",
        description="Offset applied to the ray origin, moving it slightly away from the surface launch point in the ray direction",
        default=0.01)
    raytrace_samplemotion = BoolProperty(
        name="Sample Motion Blur",
        description="Motion blur of other objects hit by rays launched from this object will be used",
        default=False)
    raytrace_decimationrate = IntProperty(
        name="Decimation Rate",
        description="Specifies the tessellation decimation for ray tracing. The most useful values are 1, 2, 4, and 16",
        default=1)
    raytrace_intersectpriority = IntProperty(
        name="Intersect Priority",
        description="Dictates a priority used when ray tracing overlapping materials",
        default=0)

    trace_displacements = BoolProperty(
        name="Trace Displacements",
        description="Enable high resolution displaced geometry for ray tracing",
        default=True)

    trace_samplemotion = BoolProperty(
        name="Trace Motion Blur",
        description="Rays cast from this object can intersect other motion blur objects",
        default=False)

    export_coordsys = BoolProperty(
        name="Export Coordinate System",
        description="Export a named coordinate system set to this object's name",
        default=False)
    coordsys = StringProperty(
        name="Coordinate System Name",
        description="Export a named coordinate system with this name",
        default="CoordSys")

    # Light-Linking
    light_linking = CollectionProperty(type=LightLinking, name='Light Linking')
    light_linking_index = IntProperty(min=-1, default=-1)

    # Trace Sets
    trace_set = CollectionProperty(type=TraceSet, name='Trace Set')
    trace_set_index = IntProperty(min=-1, default=-1)


# collection of property group classes that need to be registered on
# module startup
classes = [RendermanPath,
           RendermanInlineRIB,
           RendermanGrouping,
           LightLinking,
           TraceSet,
           RendermanPass,
           RendermanMeshPrimVar,
           RendermanParticlePrimVar,
           RendermanMaterialSettings,
           RendermanAnimSequenceSettings,
           RendermanTextureSettings,
           RendermanLightSettings,
           RendermanParticleSettings,
           RendermanIntegratorSettings,
           RendermanAOV,
           RendermanAOVList,
           RendermanCameraSettings,
           RendermanSceneSettings,
           RendermanMeshGeometrySettings,
           RendermanCurveGeometrySettings,
           RendermanObjectSettings
           ]


def register():

    # dynamically find integrators from args
    register_integrator_settings(RendermanSceneSettings)
    # dynamically find camera from args
    register_camera_settings()

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.renderman = PointerProperty(
        type=RendermanSceneSettings, name="Renderman Scene Settings")
    bpy.types.Material.renderman = PointerProperty(
        type=RendermanMaterialSettings, name="Renderman Material Settings")
    bpy.types.Texture.renderman = PointerProperty(
        type=RendermanTextureSettings, name="Renderman Texture Settings")
    bpy.types.Lamp.renderman = PointerProperty(
        type=RendermanLightSettings, name="Renderman Light Settings")
    bpy.types.ParticleSettings.renderman = PointerProperty(
        type=RendermanParticleSettings, name="Renderman Particle Settings")
    bpy.types.Mesh.renderman = PointerProperty(
        type=RendermanMeshGeometrySettings,
        name="Renderman Mesh Geometry Settings")
    bpy.types.Curve.renderman = PointerProperty(
        type=RendermanCurveGeometrySettings,
        name="Renderman Curve Geometry Settings")
    bpy.types.Object.renderman = PointerProperty(
        type=RendermanObjectSettings, name="Renderman Object Settings")
    bpy.types.Camera.renderman = PointerProperty(
        type=RendermanCameraSettings, name="Renderman Camera Settings")


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.utils.unregister_module(__name__)
