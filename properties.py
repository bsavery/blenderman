# ##### BEGIN MIT LICENSE BLOCK #####
#
# Copyright (c) 2015 - 2017 Pixar
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
from mathutils import Vector

from .util import guess_rmantree

from .util import args_files_in_path
from .shader_parameters import class_generate_properties

from bpy.props import PointerProperty, StringProperty, BoolProperty, \
    EnumProperty, IntProperty, FloatProperty, FloatVectorProperty, \
    CollectionProperty, BoolVectorProperty

from . import engine
from bpy.app.handlers import persistent

integrator_names = []

projection_names = [('none', 'None', 'None')]


class RendermanCameraSettings(bpy.types.PropertyGroup):
    bl_label = "RenderMan Camera Settings"
    bl_idname = 'RendermanCameraSettings'

    def get_projection_name(self):
        return self.projection_type.replace('_settings', '')

    def get_projection_node(self):
        return getattr(self, self.projection_type + '_settings')

    projection_type = EnumProperty(
        items=projection_names, name='Projection Plugin')

    use_physical_camera = BoolProperty(
        name="Use Physical Camera", default=False)

    fstop = FloatProperty(
        name="F-Stop",
        description="Aperture size for depth of field.  Decreasing this value increases the blur on out of focus areas",
        default=4.0)

    dof_aspect = FloatProperty(
        name="DOF Aspect", default=1, max=2, min=0,
        description="The ratio of blur in the 'x' and 'y' directions. Changing this value from the default will simulate anamorphic lens bokeh effects.  Values less than 1 elongate the blur on the 'y' axis.  Values greater than 1 elongate the blur on the 'x' axis")

    aperture_sides = IntProperty(
        name="Aperture Blades", default=0, min=0,
        description="The number of sides of the aperture.  If this value is less than 3 the aperture will appear circular")

    aperture_angle = FloatProperty(
        name="Aperture Angle", default=0.0, max=180.0, min=-180.0,
        description="The aperture polygon's orientation, in degrees from some arbitrary reference direction. (A value of 0 aligns a vertex horizontally with the center of the aperture.)")

    aperture_roundness = FloatProperty(
        name="Aperture Roundness", default=0.0, max=1.0, min=-1.0,
        description="A shape parameter, from -1 to 1.  When 0, the aperture is a regular polygon with straight sides.  Values between 0 and 1 give polygons with curved edges bowed out and values between 0 and -1 make the edges bow in")

    aperture_density = FloatProperty(
        name="Aperture Density", default=0.0, max=1.0, min=-1.0,
        description="The slope, between -1 and 1, of the (linearly varying) aperture density.  A value of zero gives uniform density.  Negative values make the aperture brighter near the center.  Positive values make it brighter near the rim")


# Blender data
# --------------------------

class RendermanPath(bpy.types.PropertyGroup):
    name = StringProperty(
        name="", subtype='DIR_PATH')


class RendermanInlineRIB(bpy.types.PropertyGroup):
    name = StringProperty(name="Text Block")


class RendermanGroup(bpy.types.PropertyGroup):
    name = StringProperty(name="Group Name")
    members = CollectionProperty(type=bpy.types.PropertyGroup,
                                 name='Group Members')
    members_index = IntProperty(min=-1, default=-1)


class LightLinking(bpy.types.PropertyGroup):

    def update_link(self, context):
        if engine.is_ipr_running():
            engine.ipr.update_light_link(context, self)

    illuminate = EnumProperty(
        name="Illuminate",
        update=update_link,
        items=[('DEFAULT', 'Default', ''),
               ('ON', 'On', ''),
               ('OFF', 'Off', '')])


class RendermanAOV(bpy.types.PropertyGroup):

    def aov_list(self, context):
        items = [
            # (LPE, ID, Extra ID, no entry, sorting order)
            # Basic lpe
            ("", "Basic LPE's", "Basic LPE's", "", 0),
            ("color rgba", "rgba", "Combined (beauty)", "", 1),
            ("color lpe:C[<.D%G><.S%G>][DS]*[<L.%LG>O]",
             "All Lighting", "All Lighting", "", 2),
            ("color lpe:C<.D%G><L.%LG>", "Diffuse", "Diffuse", "", 3),
            ("color lpe:(C<RD%G>[DS]+<L.%LG>)|(C<RD%G>[DS]*O)",
             "IndirectDiffuse", "IndirectDiffuse", "", 4),
            ("color lpe:C<.S%G><L.%LG>", "Specular", "Specular", "", 5),
            ("color lpe:(C<RS%G>[DS]+<L.%LG>)|(C<RS%G>[DS]*O)",
             "IndirectSpecular", "IndirectSpecular", "", 6),
            ("color lpe:(C<TD%G>[DS]+<L.%LG>)|(C<TD%G>[DS]*O)",
             "Subsurface", "Subsurface", "", 7),
            ("color lpe:C<RS%G>([DS]+<L.%LG>)|([DS]*O)",
             "Reflection", "Reflection", "", 8),
            ("color lpe:(C<T[S]%G>[DS]+<L.%LG>)|(C<T[S]%G>[DS]*O)",
             "Refraction", "Refraction", "", 9),
            ("color lpe:emission", "Emission", "Emission", "", 10),
            ("color lpe:shadows;C[<.D%G><.S%G>]<L.%LG>",
             "Shadows", "Shadows", "", 11),
            ("color lpe:nothruput;noinfinitecheck;noclamp;unoccluded;overwrite;C(U2L)|O",
             "Albedo", "Albedo", "", 12),
            ("color lpe:C<.D%G>[S]+<L.%LG>", "Caustics", "Caustics", "", 13),
            # Matte ID
            ("", "Matte ID's", "Matte ID's", "", 0),
            ("color MatteID0", "MatteID0", "MatteID0", "", 14),
            ("color MatteID1", "MatteID1", "MatteID1", "", 15),
            ("color MatteID2", "MatteID2", "MatteID2", "", 16),
            ("color MatteID3", "MatteID3", "MatteID3", "", 17),
            ("color MatteID4", "MatteID4", "MatteID4", "", 18),
            ("color MatteID5", "MatteID5", "MatteID5", "", 19),
            ("color MatteID6", "MatteID6", "MatteID6", "", 20),
            ("color MatteID7", "MatteID7", "MatteID7", "", 21),
            # PxrSurface lpe
            ("", "PxrSurface lobe LPE's", "PxrSurface lobe LPE's", "", 0),
            ("color lpe:C<.D2%G>[<L.%LG>O]",
             "directDiffuseLobe", "", "", 22),
            ("color lpe:C<.D2%G>[DS]+[<L.%LG>O]",
             "indirectDiffuseLobe", "", "", 23),
            ("color lpe:C<.D3%G>[DS]*[<L.%LG>O]",
             "subsurfaceLobe", "", "", 24),
            ("color lpe:C<.S2%G>[<L.%LG>O]",
             "directSpecularPrimaryLobe", "", "", 25),
            ("color lpe:C<.S2%G>[DS]+[<L.%LG>O]",
             "indirectSpecularPrimaryLobe", "", "", 26),
            ("color lpe:C<.S3%G>[<L.%LG>O]",
             "directSpecularRoughLobe", "", "", 27),
            ("color lpe:C<.S3%G>[DS]+[<L.%LG>O]",
             "indirectSpecularRoughLobe", "", "", 28),
            ("color lpe:C<.S4%G>[<L.%LG>O]",
             "directSpecularClearcoatLobe", "", "", 29),
            ("color lpe:C<.S4%G>[DS]+[<L.%LG>O]",
             "indirectSpecularClearcoatLobe", "", "", 30),
            ("color lpe:C<.S5%G>[<L.%LG>O]",
             "directSpecularIridescenceLobe", "", "", 31),
            ("color lpe:C<.S5%G>[DS]+[<L.%LG>O]",
             "indirectSpecularIridescenceLobe", "", "", 32),
            ("color lpe:C<.S6%G>[<L.%LG>O]",
             "directSpecularFuzzLobe", "", "", 33),
            ("color lpe:C<.S6%G>[DS]+[<L.%LG>O]",
             "indirectSpecularFuzzLobe", "", "", 34),
            ("color lpe:C<.S7%G>[DS]*[<L.%LG>O]",
             "transmissiveSingleScatterLobe", "", "", 35),
            ("color lpe:C<RS8%G>[<L.%LG>O]",
             "directSpecularGlassLobe", "", "", 36),
            ("color lpe:C<RS8%G>[DS]+[<L.%LG>O]",
             "indirectSpecularGlassLobe", "", "", 37),
            ("color lpe:C<TS8%G>[DS]*[<L.%LG>O]",
             "transmissiveGlassLobe", "", "", 38),
            # Data AOV's
            ("", "Data AOV's", "Data AOV's", "", 0),
            ("float a", "alpha", "", "", 39),
            ("float id", "id", "Returns the integer assigned via the 'identifier' attribute as the pixel value", "", 40),
            ("float z", "z_depth", "Depth from the camera in world space", "", 41),
            ("float zback", "z_back",
             "Depth at the back of volumetric objects in world space", "", 42),
            ("point P", "P", "Position of the point hit by the incident ray", "", 43),
            ("float PRadius", "PRadius",
             "Cross-sectional size of the ray at the hit point", "", 44),
            ("float cpuTime", "cpuTime",
             "The time taken to render a pixel", "", 45),
            ("float sampleCount", "sampleCount",
             "The number of samples taken for the resulting pixel", "", 46),
            ("normal Nn", "Nn", "Normalized shading normal", "", 47),
            ("normal Ngn", "Ngn", "Normalized geometric normal", "", 48),
            ("vector Tn", "Tn", "Normalized shading tangent", "", 49),
            ("vector Vn", "Vn",
             "Normalized view vector (reverse of ray direction)", "", 50),
            ("float VLen", "VLen", "Distance to hit point along the ray", "", 51),
            ("float curvature", "curvature", "Local surface curvature", "", 52),
            ("float incidentRaySpread", "incidentRaySpread",
             "Rate of spread of incident ray", "", 53),
            ("float mpSize", "mpSize",
             "Size of the micropolygon that the ray hit", "", 54),
            ("float u", "u", "The parametric coordinates on the primitive", "", 55),
            ("float v", "v", "The parametric coordinates on the primitive", "", 56),
            ("float w", "w", "The parametric coordinates on the primitive", "", 57),
            ("float du", "du",
             "Derivatives of u, v, and w to adjacent micropolygons", "", 58),
            ("float dv", "dv",
             "Derivatives of u, v, and w to adjacent micropolygons", "", 59),
            ("float dw", "dw",
             "Derivatives of u, v, and w to adjacent micropolygons", "", 60),
            ("vector dPdu", "dPdu",
             "Direction of maximal change in u, v, and w", "", 61),
            ("vector dPdv", "dPdv",
             "Direction of maximal change in u, v, and w", "", 62),
            ("vector dPdw", "dPdw",
             "Direction of maximal change in u, v, and w", "", 63),
            ("float dufp", "dufp",
             "Multiplier to dPdu, dPdv, dPdw for ray differentials", "", 64),
            ("float dvfp", "dvfp",
             "Multiplier to dPdu, dPdv, dPdw for ray differentials", "", 65),
            ("float dwfp", "dwfp",
             "Multiplier to dPdu, dPdv, dPdw for ray differentials", "", 66),
            ("float time", "time", "Time sample of the ray", "", 67),
            ("vector dPdtime", "dPdtime", "Motion vector", "", 68),
            ("float id", "id", "Returns the integer assigned via the identifier attribute as the pixel value", "", 69),
            ("float outsideIOR", "outsideIOR",
             "Index of refraction outside this surface", "", 70),
            ("point __Pworld", "Pworld", "P in world-space", "", 71),
            ("normal __Nworld", "Nworld", "Nn in world-space", "", 72),
            ("float __depth", "depth", "Multi-purpose AOV\nr : depth from camera in world-space\ng : height in world-space\nb : geometric facing ratio : abs(Nn.V)", "", 73),
            ("float[2] __st", "st", "Texture coords", "", 74),
            ("point __Pref", "Pref",
             "Reference Position primvar (if available)", "", 75),
            ("normal __Nref", "Nref",
             "Reference Normal primvar (if available)", "", 76),
            ("point __WPref", "WPref",
             "Reference World Position primvar (if available)", "", 77),
            ("normal __WNref", "WNref",
             "Reference World Normal primvar (if available)", "", 78),
            # Custom lpe
            ("", "Custom", "Custom", "", 0),
            ("color custom_lpe", "Custom LPE", "Custom LPE", "", 79)
        ]
        return items

    def update_type(self, context):
        types = self.aov_list(context)
        for item in types:
            if self.aov_name == item[0]:
                self.name = item[1]
                self.channel_name = item[1]

    show_advanced = BoolProperty(name='Advanced Options', default=False)

    name = StringProperty(name='Channel Name')

    channel_name = StringProperty()

    aov_name = EnumProperty(name="AOV Type",
                            description="",
                            items=aov_list, update=update_type)

    custom_lpe_string = StringProperty(
        name="lpe String",
        description="This is where you enter the custom lpe string")

    stats_type = EnumProperty(
        name="Statistics",
        description="this is the name of the statistics to display in this AOV (if any)",
        items=[
            ('none', 'None', ''),
            ('variance', 'Variance',
             'estimates the variance of the samples in each pixel'),
            ('mse', 'MSE', 'the estimate of the variance divided by the actual number of samples per pixel'),
            ('even', 'Even', 'this image is created from half the total camera samples'),
            ('odd', 'Odd', 'this image is created from the other half of the camera samples')],
        default='none')

    exposure_gain = FloatProperty(
        name="Gain",
        description="The gain of the exposure.  This is the overall brightness of the image",
        default=1.0)

    exposure_gamma = FloatProperty(
        name="Gamma",
        description="The gamma of the exposure.  This determines how flat the brightness curve is.  Raising gamma leads to lighter shadows",
        default=1.0)

    remap_a = FloatProperty(
        name="a",
        description="A value for remap",
        default=0.0)

    remap_b = FloatProperty(
        name="b",
        description="B value for remap",
        default=0.0)

    remap_c = FloatProperty(
        name="c",
        description="C value for remap",
        default=0.0)

    quantize_zero = IntProperty(
        name="Zero",
        description="Zero value for quantization",
        default=0)

    quantize_one = IntProperty(
        name="One",
        description="One value for quantization",
        default=0)

    quantize_min = IntProperty(
        name="Min",
        description="Minimum value for quantization",
        default=0)

    quantize_max = IntProperty(
        name="Max",
        description="Max value for quantization",
        default=0)

    aov_pixelfilter = EnumProperty(
        name="Pixel Filter",
        description="Filter to use to combine pixel samples.  If 'default' is selected the aov will use the filter set in the render panel",
        items=[('default', 'Default', ''),
               ('box', 'Box', ''),
               ('sinc', 'Sinc', ''),
               ('gaussian', 'Gaussian', ''),
               ('triangle', 'Triangle', ''),
               ('catmull-rom', 'Catmull-Rom', '')],
        default='default')
    aov_pixelfilter_x = IntProperty(
        name="Filter Size X",
        description="Size of the pixel filter in X dimension",
        min=0, max=16, default=2)
    aov_pixelfilter_y = IntProperty(
        name="Filter Size Y",
        description="Size of the pixel filter in Y dimension",
        min=0, max=16, default=2)


class RendermanRenderLayerSettings(bpy.types.PropertyGroup):
    render_layer = StringProperty()
    custom_aovs = CollectionProperty(type=RendermanAOV,
                                     name='Custom AOVs')
    custom_aov_index = IntProperty(min=-1, default=-1)
    camera = StringProperty()
    object_group = StringProperty(name='Object Group')
    light_group = StringProperty(name='Light Group')

    export_multilayer = BoolProperty(
        name="Export Multilayer",
        description="Enabling this will combine passes and output as a multilayer file",
        default=False)

    exr_format_options = EnumProperty(
        name="EXR Bit Depth",
        description="Sets the bit depth of the .exr file.  Leaving at 'default' will use the RenderMan defaults",
        items=[
            ('default', 'Default', ''),
            ('half', 'Half (16 bit)', ''),
            ('float', 'Float (32 bit)', '')],
        default='default')

    use_deep = BoolProperty(
        name="Use Deep Data",
        description="The output file will contain extra 'deep' information that can aid with compositing.  This can increase file sizes dramatically.  Z channels will automatically be generated so they do not need to be added to the AOV panel",
        default=False)

    denoise_aov = BoolProperty(
        name="Denoise AOVs",
        default=False)

    exr_compression = EnumProperty(
        name="EXR Compression",
        description="Determined the compression used on the EXR file.  Leaving at 'default' will use the RenderMan defaults",
        items=[
            ('default', 'Default', ''),
            ('none', 'None', ''),
            ('rle', 'rle', ''),
            ('zip', 'zip', ''),
            ('zips', 'zips', ''),
            ('pixar', 'pixar', ''),
            ('b44', 'b44', ''),
            ('piz', 'piz', '')],
        default='default')

    exr_storage = EnumProperty(
        name="EXR Storage Mode",
        description="This determines how the EXR file is formatted.  Tile-based may reduce the amount of memory used by the display buffer",
        items=[
            ('scanline', 'Scanline Storage', ''),
            ('tiled', 'Tiled Storage', '')],
        default='scanline')


displayfilter_names = []


class RendermanDisplayFilterSettings(bpy.types.PropertyGroup):

    def get_filter_name(self):
        return self.filter_type.replace('_settings', '')

    def get_filter_node(self):
        return getattr(self, self.filter_type + '_settings')

    filter_type = EnumProperty(items=displayfilter_names, name='Filter')


samplefilter_names = []


class RendermanSampleFilterSettings(bpy.types.PropertyGroup):

    def get_filter_name(self):
        return self.filter_type.replace('_settings', '')

    def get_filter_node(self):
        return getattr(self, self.filter_type + '_settings')

    filter_type = EnumProperty(items=samplefilter_names, name='Filter')


class RendermanSceneSettings(bpy.types.PropertyGroup):
    display_filters = CollectionProperty(
        type=RendermanDisplayFilterSettings, name='Display Filters')
    display_filters_index = IntProperty(min=-1, default=-1)
    sample_filters = CollectionProperty(
        type=RendermanSampleFilterSettings, name='Sample Filters')
    sample_filters_index = IntProperty(min=-1, default=-1)

    light_groups = CollectionProperty(type=RendermanGroup,
                                      name='Light Groups')
    light_groups_index = IntProperty(min=-1, default=-1)

    ll = CollectionProperty(type=LightLinking,
                            name='Light Links')

    # we need these in case object/light selector changes
    def reset_ll_light_index(self, context):
        self.ll_light_index = -1

    def reset_ll_object_index(self, context):
        self.ll_object_index = -1

    ll_light_index = IntProperty(min=-1, default=-1)
    ll_object_index = IntProperty(min=-1, default=-1)
    ll_light_type = EnumProperty(
        name="Select by",
        description="Select by",
        items=[('light', 'Lights', ''),
               ('group', 'Light Groups', '')],
        default='group', update=reset_ll_light_index)

    ll_object_type = EnumProperty(
        name="Select by",
        description="Select by",
        items=[('object', 'Objects', ''),
               ('group', 'Object Groups', '')],
        default='group', update=reset_ll_object_index)

    render_layers = CollectionProperty(type=RendermanRenderLayerSettings,
                                       name='Custom AOVs')

    solo_light = BoolProperty(name="Solo Light", default=False)

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
               ('gaussian', 'Gaussian', ''),
               ('triangle', 'Triangle', ''),
               ('catmull-rom', 'Catmull-Rom', '')],
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
        description="If a pixel changes by less than this amount when updated, it will not receive further samples in adaptive mode.  Lower values lead to increased render times and higher quality images",
        min=0, max=1, default=.01)

    dark_falloff = FloatProperty(
        name="Dark Falloff",
        description="Deprioritizes adaptive sampling in dark areas. Raising this can potentially reduce render times but may increase noise in dark areas",
        min=0, max=1, default=.025)

    min_samples = IntProperty(
        name="Min Samples",
        description="The minimum number of camera samples per pixel.  If this is set to '0' then the min samples will be the square root of the max_samples",
        min=0, default=4)
    max_samples = IntProperty(
        name="Max Samples",
        description="The maximum number of camera samples per pixel.  This should be set in 'power of two' numbers (1, 2, 4, 8, 16, etc)",
        min=0, default=128)

    bucket_shape = EnumProperty(
        name="Bucket Order",
        description="The order buckets are rendered in",
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

    bucket_sprial_x = IntProperty(
        name="X",
        description="X coordinate of bucket spiral start",
        min=-1, default=-1)

    bucket_sprial_y = IntProperty(
        name="Y",
        description="Y coordinate of bucket spiral start",
        min=-1, default=-1)

    render_selected_objects_only = BoolProperty(
        name="Only Render Selected",
        description="Render only the selected object(s)",
        default=False)

    shadingrate = FloatProperty(
        name="Micropolygon Length",
        description="Default maximum distance between displacement samples.  This can be left at 1 unless you need more detail on displaced objects",
        default=1.0)

    dicing_strategy = EnumProperty(
        name="Dicing Strategy",
        description="Sets the method that RenderMan uses to tessellate objects.  Spherical may help with volume rendering",
        items=[
            ("planarprojection", "Planar Projection",
             "Tessellates using the screen space coordinates of a primitive projected onto a plane"),
            ("sphericalprojection", "Spherical Projection",
             "Tessellates using the coordinates of a primitive projected onto a sphere"),
            ("worlddistance", "World Distance", "Tessellation is determined using distances measured in world space units compared to the current micropolygon length")],
        default="sphericalprojection")

    worlddistancelength = FloatProperty(
        name="World Distance Length",
        description="If this is a value above 0, it sets the length of a micropolygon after tessellation",
        default=-1.0)

    instanceworlddistancelength = FloatProperty(
        name="Instance World Distance Length",
        description="Set the length of a micropolygon for tessellated instanced meshes",
        default=1e30)

    motion_blur = BoolProperty(
        name="Motion Blur",
        description="Enable motion blur",
        default=False)
    sample_motion_blur = BoolProperty(
        name="Sample Motion Blur",
        description="Determines if motion blur is rendered in the final image.  If this is disabled the motion vectors are still calculated and can be exported with the dPdTime AOV.  This allows motion blur to be added as a post process effect",
        default=True)
    motion_segments = IntProperty(
        name="Motion Samples",
        description="Number of motion samples to take for motion blur.  Set this higher if you notice segment artifacts in blurs",
        min=2, max=16, default=2)
    shutter_timing = EnumProperty(
        name="Shutter Timing",
        description="Controls when the shutter opens for a given frame",
        items=[('CENTER', 'Center on frame', 'Motion is centered on frame #.'),
               ('PRE', 'Pre frame', 'Motion ends on frame #'),
               ('POST', 'Post frame', 'Motion starts on frame #')],
        default='CENTER')

    shutter_angle = FloatProperty(
        name="Shutter Angle",
        description="Fraction of time that the shutter is open (360 is one full second).  180 is typical for North America 24fps cameras, 172.8 is typical in Europe",
        default=180.0, min=0.0, max=360.0)

    shutter_efficiency_open = FloatProperty(
        name="Shutter open speed",
        description="Shutter open efficiency - controls the speed of the shutter opening.  0 means instantaneous, > 0 is a gradual opening",
        default=0.0)
    shutter_efficiency_close = FloatProperty(
        name="Shutter close speed",
        description="Shutter close efficiency - controls the speed of the shutter closing.  1 means instantaneous, < 1 is a gradual closing",
        default=1.0)

    depth_of_field = BoolProperty(
        name="Depth of Field",
        description="Enable depth of field blur",
        default=False)

    threads = IntProperty(
        name="Rendering Threads",
        description="Number of processor threads to use.  Note, 0 uses all cores, -1 uses all cores but one",
        min=-32, max=32, default=-1)

    override_threads = BoolProperty(
        name="Override Threads",
        description="Overrides thread count for spooled render",
        default=False)

    external_threads = IntProperty(
        name="Spool Rendering Threads",
        description="Number of processor threads to use.  Note, 0 uses all cores, -1 uses all cores but one",
        default=0, min=-32, max=32)

    max_trace_depth = IntProperty(
        name="Max Trace Depth",
        description="Maximum number of times a ray can bounce before the path is ended.  Lower settings will render faster but may change lighting",
        min=0, max=32, default=10)
    max_specular_depth = IntProperty(
        name="Max Specular Depth",
        description="Maximum number of specular ray bounces",
        min=0, max=32, default=4)
    max_diffuse_depth = IntProperty(
        name="Max Diffuse Depth",
        description="Maximum number of diffuse ray bounces",
        min=0, max=32, default=1)
    use_statistics = BoolProperty(
        name="Statistics",
        description="Print statistics to stats.xml after render",
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
        default=os.path.join('$OUT', '{scene}.####.rib'))

    path_object_archive_static = StringProperty(
        name="Object archive RIB Output Path",
        description="Path to generated rib file for a non-deforming objects' geometry",
        subtype='FILE_PATH',
        default=os.path.join('$ARC', 'static', '{object}.rib'))

    path_object_archive_animated = StringProperty(
        name="Object archive RIB Output Path",
        description="Path to generated rib file for an animated objects geometry",
        subtype='FILE_PATH',
        default=os.path.join('$ARC', '####', '{object}.rib'))

    path_texture_output = StringProperty(
        name="Teture Output Path",
        description="Path to generated .tex files",
        subtype='FILE_PATH',
        default=os.path.join('$OUT', 'textures'))

    out_dir = StringProperty(
        name="Shader Output Path",
        description="Path to compiled .oso files",
        subtype='FILE_PATH',
        default="./shaders")

    rib_format = EnumProperty(
        name="RIB Format",
        items=[
            ("ascii", "ASCII", ""),
            ("binary", "Binary", "")],
        default="binary")

    rib_compression = EnumProperty(
        name="RIB Compression",
        items=[
            ("none", "None", ""),
            ("gzip", "GZip", "")],
        default="none")

    texture_cache_size = IntProperty(
        name="Texture Cache Size (MB)",
        description="Maximum number of megabytes to devote to texture caching",
        default=2048
    )

    geo_cache_size = IntProperty(
        name="Tesselation Cache Size (MB)",
        description="Maximum number of megabytes to devote to tesselation cache for tracing geometry",
        default=2048
    )

    opacity_cache_size = IntProperty(
        name="Opacity Cache Size (MB)",
        description="Maximum number of megabytes to devote to caching opacity and presence values.  0 turns this off",
        default=1000
    )

    output_action = EnumProperty(
        name="Action",
        description="Action to take when rendering",
        items=[('EXPORT_RENDER', 'Export RIB and Render', 'Generate RIB file and render it with the renderer'),
               ('EXPORT', 'Export RIB Only', 'Generate RIB file only')],
        default='EXPORT_RENDER')

    lazy_rib_gen = BoolProperty(
        name="Cache Rib Generation",
        description="On unchanged objects, don't re-emit rib.  Will result in faster spooling of renders",
        default=True)

    always_generate_textures = BoolProperty(
        name="Always Recompile Textures",
        description="Recompile used textures at export time to the current rib folder. Leave this unchecked to speed up re-render times",
        default=False)
    # preview settings
    preview_pixel_variance = FloatProperty(
        name="Preview Pixel Variance",
        description="If a pixel changes by less than this amount when updated, it will not receive further samples in adaptive mode",
        min=0, max=1, default=.05)

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
        description="The minimum number of camera samples per pixel.  Setting this to '0' causes the min_samples to be set to the square root of max_samples",
        min=0, default=0)
    preview_max_samples = IntProperty(
        name="Preview Max Samples",
        description="The maximum number of camera samples per pixel.  This should be set lower than the final render setting to imporove speed",
        min=0, default=64)

    preview_max_specular_depth = IntProperty(
        name="Max Preview Specular Depth",
        description="Maximum number of specular ray bounces",
        min=0, max=32, default=2)
    preview_max_diffuse_depth = IntProperty(
        name="Max Preview Diffuse Depth",
        description="Maximum number of diffuse ray bounces",
        min=0, max=32, default=1)

    enable_external_rendering = BoolProperty(
        name="Enable External Rendering",
        description="This will allow extended rendering modes, which allow batch rendering to RenderMan outside of Blender",
        default=False)

    display_driver = EnumProperty(
        name="Display Driver",
        description="File Type for output pixels, 'it' will send to an external framebuffer",
        items=[
            ('openexr', 'OpenEXR',
             'Render to a OpenEXR file, to be read back into Blender\'s Render Result'),
            ('tiff', 'Tiff',
             'Render to a TIFF file, to be read back into Blender\'s Render Result'),
            ('it', 'it', 'External framebuffer display (must have RMS installed)')
        ], default='it')

    exr_format_options = EnumProperty(
        name="Bit Depth",
        description="Sets the bit depth of the main EXR file.  Leaving at 'default' will use the RenderMan defaults",
        items=[
            ('default', 'Default', ''),
            ('half', 'Half (16 bit)', ''),
            ('float', 'Float (32 bit)', '')],
        default='default')

    exr_compression = EnumProperty(
        name="Compression",
        description="Determined the compression used on the main EXR file.  Leaving at 'default' will use the RenderMan defaults",
        items=[
            ('default', 'Default', ''),
            ('none', 'None', ''),
            ('rle', 'rle', ''),
            ('zip', 'zip', ''),
            ('zips', 'zips', ''),
            ('pixar', 'pixar', ''),
            ('b44', 'b44', ''),
            ('piz', 'piz', '')],
        default='default')

    render_into = EnumProperty(
        name="Render to",
        description="Render to blender or external framebuffer",
        items=[('blender', 'Blender', 'Render to the Image Editor'),
               ('it', 'it', 'External framebuffer display (must have RMS installed)')],
        default='blender')

    export_options = BoolProperty(
        name="Export Options",
        default=False)

    generate_rib = BoolProperty(
        name="Generate RIBs",
        description="Generates RIB files for the scene information",
        default=True)

    generate_object_rib = BoolProperty(
        name="Generate object RIBs",
        description="Generates RIB files for each object",
        default=True)

    generate_alf = BoolProperty(
        name="Generate ALF files",
        description="Generates an ALF file.  This file contains a sequential list of commmands used for rendering",
        default=True)

    convert_textures = BoolProperty(
        name="Convert Textures",
        description="Add commands to the ALF file to convert textures to .tex files",
        default=True)

    generate_render = BoolProperty(
        name="Generate render commands",
        description="Add render commands to the ALF file",
        default=True)

    do_render = BoolProperty(
        name="Initiate Renderer",
        description="Spool RIB files to RenderMan",
        default=True)

    alf_options = BoolProperty(
        name="ALF Options",
        default=False)

    custom_alfname = StringProperty(
        name="Custom Spool Name",
        description="Allows a custom name for the spool .alf file.  This would allow you to export multiple spool files for the same scene",
        default='spool')

    queuing_system = EnumProperty(
        name="Spool to",
        description="System to spool to",
        items=[('lq', 'LocalQueue', 'LocalQueue, must have RMS installed'),
               ('tractor', 'tractor', 'Tractor, must have tractor setup')],
        default='lq')

    recover = BoolProperty(
        name="Enable Recovery",
        description="Attempt to resume render from a previous checkpoint (if possible)",
        default=False)

    custom_cmd = StringProperty(
        name="Custom Render Commands",
        description="Inserts a string of custom command arguments into the render process",
        default='')

    denoise_cmd = StringProperty(
        name="Custom Denoise Commands",
        description="Inserts a string of custom commands arguments into the denoising process, if selected",
        default='')

    spool_denoise_aov = BoolProperty(
        name="Process denoisable AOV's",
        description="Denoises tagged AOV's",
        default=False)

    denoise_gpu = BoolProperty(
        name="Use GPU for denoising",
        description="The denoiser will attempt to use the GPU (if available)",
        default=True)

    external_animation = BoolProperty(
        name="Render Animation",
        description="Spool Animation",
        default=False)

    enable_checkpoint = BoolProperty(
        name="Enable Checkpointing",
        description="Allows partial images to be output at specific intervals while the renderer continued to run.  The user may also set a point at which the render will terminate",
        default=False)

    checkpoint_type = EnumProperty(
        name="Checkpoint Method",
        description="Sets the method that the checkpointing will use",
        items=[('i', 'Iterations', 'Number of samples per pixel'),
               ('s', 'Seconds', ''),
               ('m', 'Minutes', ''),
               ('h', 'Hours', ''),
               ('d', 'Days', '')],
        default='s')

    checkpoint_interval = IntProperty(
        name="Interval",
        description="The interval between checkpoint images",
        default=60)

    render_limit = IntProperty(
        name="Limit",
        description="The maximum interval that will be reached before the render terminates.  0 will disable this option",
        default=0)

    asfinal = BoolProperty(
        name="Final Image as Checkpoint",
        description="Saves the final image as a checkpoint.  This allows you to resume it after raising the sample count",
        default=False)

    header_rib_boxes = StringProperty(
        name="External RIB File",
        description="Injects an external RIB into the header of the output file",
        subtype='FILE_PATH',
        default="")

    do_denoise = BoolProperty(
        name="Denoise Post-Process",
        description="Use RenderMan's image denoiser to post process your render.  This allows you to use a higher pixel variance (and therefore faster render) while still producing a high quality image",
        default=False)

    external_denoise = BoolProperty(
        name="Denoise Post-Process",
        description="Use RenderMan's image denoiser to post process your render.  This allows you to use a higher pixel variance (and therefore faster render) while still producing a high quality image",
        default=False)

    crossframe_denoise = BoolProperty(
        name="Crossframe Denoise",
        description="Only available when denoising an external render.\n  This is more efficient especially with motion blur",
        default=False)

    update_frequency = IntProperty(
        name="Update frequency",
        description="Number of seconds between display update when rendering to Blender",
        min=0, default=10)

    import_images = BoolProperty(
        name="Import AOV's into Blender",
        description="Imports all AOV's from the render session into Blender's image editor",
        default=True)

    incremental = BoolProperty(
        name="Incremental Render",
        description="When enabled every pixel is sampled once per render pass.  This allows the user to quickly see the entire image during rendering, and as each pass completes the image will become clearer.  NOTE-This mode is automatically enabled with some render integrators (PxrVCM)",
        default=True)

    raytrace_progressive = BoolProperty(
        name="Progressive Rendering",
        description="Enables progressive rendering (the entire image is refined at once).\nThis is only visible with some display drivers (such as it)",
        default=False)

    integrator = EnumProperty(
        name="Integrator",
        description="Integrator for rendering",
        items=integrator_names,
        default='PxrPathTracer')

    show_integrator_settings = BoolProperty(
        name="Integration Settings",
        description="Show Integrator Settings",
        default=False
    )

    # Rib Box Properties
    frame_rib_box = StringProperty(
        name="Frame RIB box",
        description="Injects RIB into the 'frame' block",
        default="")

    # Trace Sets (grouping membership)
    object_groups = CollectionProperty(
        type=RendermanGroup, name="Trace Sets")
    object_groups_index = IntProperty(min=-1, default=-1)

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


class RendermanMaterialSettings(bpy.types.PropertyGroup):
    instance_num = IntProperty(name='Instance number for IPR', default=0)

    displacementbound = FloatProperty(
        name="Displacement Bound",
        description="Maximum distance the displacement shader can displace vertices.  This should be increased if you notice raised details being sharply cut off",
        precision=4,
        default=0.5)

    preview_render_type = EnumProperty(
        name="Preview Render Type",
        description="Object to display in material preview",
        items=[('SPHERE', 'Sphere', ''),
               ('CUBE', 'Cube', '')],
        default='SPHERE')


class RendermanAnimSequenceSettings(bpy.types.PropertyGroup):
    animated_sequence = BoolProperty(
        name="Animated Sequence",
        description="Interpret this archive as an animated sequence (converts #### in file path to frame number)",
        default=False)
    sequence_in = IntProperty(
        name="Sequence In Point",
        description="The first numbered file to use",
        default=1)
    sequence_out = IntProperty(
        name="Sequence Out Point",
        description="The last numbered file to use",
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


class RendermanLightFilter(bpy.types.PropertyGroup):

    def get_filters(self, context):
        obs = context.scene.objects
        items = [('None', 'Not Set', 'Not Set')]
        for o in obs:
            if o.type == 'LAMP' and o.data.renderman.renderman_type == 'FILTER':
                items.append((o.name, o.name, o.name))
        return items

    def update_name(self, context):
        self.name = self.filter_name
        from . import engine
        if engine.is_ipr_running():
            engine.ipr.reset_filter_names()
            engine.ipr.issue_shader_edits()

    name = StringProperty(default='SET FILTER')
    filter_name = EnumProperty(
        name="Linked Filter:", items=get_filters, update=update_name)


class RendermanLightSettings(bpy.types.PropertyGroup):

    def get_light_node(self):
        if self.renderman_type == 'SPOT':
            light_shader = 'PxrRectLight' if self.id_data.use_square else 'PxrDiskLight'
            return getattr(self, light_shader + "_settings", None)
        return getattr(self, self.light_node, None)

    def get_light_node_name(self):
        if self.renderman_type == 'SPOT':
            return 'PxrRectLight' if self.id_data.use_square else 'PxrDiskLight'
        if self.renderman_type == 'PORTAL':
            return 'PxrPortalLight'
        else:
            return self.light_node.replace('_settings', '')

    light_node = StringProperty(
        name="Light Node",
        default='')

    # thes are used for light filters
    color_ramp_node = StringProperty(default='')
    float_ramp_node = StringProperty(default='')

    # do this to keep the nice viewport update
    def update_light_type(self, context):
        lamp = self.id_data
        light_type = lamp.renderman.renderman_type

        if light_type in ['SKY', 'ENV']:
            lamp.type = 'HEMI'
        elif light_type == 'DIST':
            lamp.type = 'SUN'
        elif light_type == 'PORTAL':
            lamp.type = 'AREA'
        elif light_type == 'FILTER':
            lamp.type = 'AREA'
        else:
            lamp.type = light_type

        # use pxr area light for everything but env, sky
        light_shader = 'PxrRectLight'
        if light_type == 'ENV':
            light_shader = 'PxrDomeLight'
        elif light_type == 'SKY':
            light_shader = 'PxrEnvDayLight'
        elif light_type == 'PORTAL':
            light_shader = 'PxrPortalLight'
        elif light_type == 'POINT':
            light_shader = 'PxrSphereLight'
        elif light_type == 'DIST':
            light_shader = 'PxrDistantLight'
        elif light_type == 'FILTER':
            light_shader = 'PxrBlockerLightFilter'
        elif light_type == 'SPOT':
            light_shader = 'PxrRectLight' if lamp.use_square else 'PxrDiskLight'
        elif light_type == 'AREA':
            try:
                lamp.shape = 'RECTANGLE'
                lamp.size = 1.0
                lamp.size_y = 1.0
            except:
                pass

        self.light_node = light_shader + "_settings"
        if light_type == 'FILTER':
            self.update_filter_type(context)

        # setattr(node, 'renderman_portal', light_type == 'PORTAL')

    def update_area_shape(self, context):
        lamp = self.id_data
        area_shape = self.area_shape
        # use pxr area light for everything but env, sky
        light_shader = 'PxrRectLight'

        if area_shape == 'disk':
            lamp.shape = 'SQUARE'
            light_shader = 'PxrDiskLight'
        elif area_shape == 'sphere':
            lamp.shape = 'SQUARE'
            light_shader = 'PxrSphereLight'
        else:
            lamp.shape = 'RECTANGLE'

        self.light_node = light_shader + "_settings"

        from . import engine
        if engine.is_ipr_running():
            engine.ipr.issue_shader_edits()

    def update_vis(self, context):
        lamp = self.id_data

        from . import engine
        if engine.is_ipr_running():
            engine.ipr.update_light_visibility(lamp)

    # remove any filter control geo that might be on the lamp
    def remove_filter_geo(self):
        lamp_ob = bpy.context.scene.objects.active
        for ob in lamp_ob.children:
            if 'rman_filter_shape' in ob.name:
                data = ob.data

                for sc in ob.users_scene:
                    sc.objects.unlink(ob)

                try:
                    bpy.data.objects.remove(ob)
                except:
                    pass

                if data.users == 0:
                    try:
                        data.user_clear()
                        bpy.data.meshes.remove(data)
                    except:
                        pass

    def add_filter_geo(self, name):
        lamp_ob = bpy.context.scene.objects.active
        # here we add some geo
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        filter_file = os.path.join(plugin_dir, 'filters',
                                   name + ".blend")
        directory = '/Object/'
        obj_name = name
        bpy.ops.wm.append(filepath=filter_file + directory + obj_name,
                          filename=obj_name,
                          directory=filter_file + directory)
        filter_geo_obj = bpy.context.selected_objects[0]
        filter_geo_obj.select = False
        filter_geo_obj.name = 'rman_filter_shape_' + name
        filter_geo_obj.parent = lamp_ob
        filter_geo_obj.hide_select = True
        filter_geo_obj.lock_rotation = [True, True, True]
        filter_geo_obj.lock_location = [True, True, True]
        filter_geo_obj.lock_scale = [True, True, True]
        bpy.context.scene.objects.active = lamp_ob
        return filter_geo_obj

    def get_filter_geo(self, name):
        lamp_ob = bpy.context.scene.objects.active
        for ob in lamp_ob.children:
            if 'rman_filter_shape' in ob.name:
                if name in ob.name:
                    return ob
                else:
                    self.remove_filter_geo()
                    return self.add_filter_geo(name)
        return self.add_filter_geo(name)

    def update_filter_type(self, context):
        self.remove_filter_geo()

        filter_name = 'IntMult' if self.filter_type == 'intmult' else self.filter_type.capitalize()
        # set the lamp type

        self.light_node = 'Pxr%sLightFilter_settings' % filter_name
        if self.filter_type in ['gobo', 'cookie']:
            self.id_data.id_data.type = 'AREA'
            self.id_data.shape = 'RECTANGLE'
        else:
            self.id_data.id_data.type = 'POINT'
            if self.filter_type != 'intmult':
                self.update_filter_shape()
        if self.filter_type in ['blocker', 'ramp', 'rod']:
            lamp = context.lamp
            if not lamp.use_nodes:
                lamp.use_nodes = True
            nt = lamp.node_tree
            if self.color_ramp_node not in nt.nodes.keys():
                # make a new color ramp node to use
                self.color_ramp_node = nt.nodes.new('ShaderNodeValToRGB').name
            if self.float_ramp_node not in nt.nodes.keys():
                self.float_ramp_node = nt.nodes.new(
                    'ShaderNodeVectorCurve').name

    # updates the filter shape when a node params change
    def update_filter_shape(self):
        node = self.get_light_node()

        if self.filter_type in ['gobo', 'cookie']:
            self.id_data.size = node.width
            self.id_data.size_y = node.height
        else:
            shape = 'rect'
            if self.filter_type in ['blocker', 'rod']:
                shape = 'cube'
            if self.filter_type == 'ramp':
                if node.rampType in ['0', '2']:
                    shape = 'sphere'
                elif node.rampType == '1':
                    shape = 'rect'
                else:
                    shape = 'circle'

            ob = self.get_filter_geo(shape)
            if not ob:
                return
            else:
                if self.filter_type == 'barn':
                    width = node.width * node.scaleWidth
                    height = node.height * node.scaleHeight
                    mesh = ob.data
                    mesh.vertices[0].co = Vector((0 - width - node.left,
                                                  0 - height - node.bottom, 0.0))
                    mesh.vertices[1].co = Vector((width + node.right,
                                                  0 - height - node.bottom, 0.0))
                    mesh.vertices[2].co = Vector((-width - node.left,
                                                  height + node.top, 0.0))
                    mesh.vertices[3].co = Vector((width + node.right,
                                                  height + node.top, 0.0))
                    left_edge = node.edge * node.leftEdge
                    right_edge = node.edge * node.rightEdge
                    top_edge = node.edge * node.topEdge
                    bottom_edge = node.edge * node.bottomEdge

                    mesh.vertices[4].co = Vector((0 - width - node.left - left_edge,
                                                  0 - height - node.bottom - bottom_edge, 0.0))
                    mesh.vertices[5].co = Vector((width + node.right + right_edge,
                                                  0 - height - node.bottom - bottom_edge, 0.0))
                    mesh.vertices[6].co = Vector((-width - node.left - left_edge,
                                                  height + node.top + top_edge, 0.0))
                    mesh.vertices[7].co = Vector((width + node.right + right_edge,
                                                  height + node.top + top_edge, 0.0))
                    ob.modifiers['bevel'].width = node.radius

                if self.filter_type == 'blocker':
                    width = node.width
                    height = node.height
                    depth = node.depth

                    mesh = ob.data
                    edge = node.edge
                    # xy inner
                    mesh.vertices[0].co = Vector((-width, -height, 0.0))
                    mesh.vertices[1].co = Vector((width, -height, 0.0))
                    mesh.vertices[2].co = Vector((-width, height, 0.0))
                    mesh.vertices[3].co = Vector((width, height, 0.0))

                    # xy outer
                    mesh.vertices[4].co = Vector((-width - edge,
                                                  -height - edge, 0.0))
                    mesh.vertices[5].co = Vector((width + edge,
                                                  -height - edge, 0.0))
                    mesh.vertices[6].co = Vector((-width - edge,
                                                  height + edge, 0.0))
                    mesh.vertices[7].co = Vector((width + edge,
                                                  height + edge, 0.0))

                    # yz inner
                    mesh.vertices[8].co = Vector((0.0, -height, depth))
                    mesh.vertices[9].co = Vector((0.0, -height, -depth))
                    mesh.vertices[10].co = Vector((0.0, height, depth))
                    mesh.vertices[11].co = Vector((0.0, height, -depth))

                    # yz outer
                    mesh.vertices[12].co = Vector(
                        (0.0, -height - edge, depth + edge))
                    mesh.vertices[13].co = Vector(
                        (0.0, -height - edge, -depth - edge))
                    mesh.vertices[14].co = Vector(
                        (0.0, height + edge, depth + edge))
                    mesh.vertices[15].co = Vector(
                        (0.0, height + edge, -depth - edge))

                    # xz inner
                    mesh.vertices[16].co = Vector((width, 0.0, depth))
                    mesh.vertices[17].co = Vector((width, 0.0, -depth))
                    mesh.vertices[18].co = Vector((-width, 0.0, depth))
                    mesh.vertices[19].co = Vector((-width, 0.0, -depth))

                    # xz outer
                    mesh.vertices[20].co = Vector(
                        (width + edge, 0.0, depth + edge))
                    mesh.vertices[21].co = Vector(
                        (width + edge, 0.0, -depth - edge))
                    mesh.vertices[22].co = Vector(
                        (-width - edge, 0.0, depth + edge))
                    mesh.vertices[23].co = Vector(
                        (-width - edge, 0.0, -depth - edge))
                    ob.modifiers['bevel'].width = node.radius

                if self.filter_type == 'rod':
                    width = node.width * node.scaleWidth
                    height = node.height * node.scaleHeight
                    depth = node.depth * node.scaleDepth
                    left_edge = node.edge * node.leftEdge
                    right_edge = node.edge * node.rightEdge
                    top_edge = node.edge * node.topEdge
                    bottom_edge = node.edge * node.bottomEdge
                    front_edge = node.edge * node.frontEdge
                    back_edge = node.edge * node.backEdge

                    mesh = ob.data

                    # xy inner
                    mesh.vertices[0].co = Vector((-width - node.left,
                                                  -height - node.bottom, 0.0))
                    mesh.vertices[1].co = Vector((width + node.right,
                                                  -height - node.bottom, 0.0))
                    mesh.vertices[2].co = Vector((-width - node.left,
                                                  height + node.top, 0.0))
                    mesh.vertices[3].co = Vector((width + node.right,
                                                  height + node.top, 0.0))

                    # xy outer
                    mesh.vertices[4].co = Vector((-width - node.left - left_edge,
                                                  -height - node.bottom - bottom_edge, 0.0))
                    mesh.vertices[5].co = Vector((width + node.right + right_edge,
                                                  -height - node.bottom - bottom_edge, 0.0))
                    mesh.vertices[6].co = Vector((-width - node.left - left_edge,
                                                  height + node.top + top_edge, 0.0))
                    mesh.vertices[7].co = Vector((width + node.right + right_edge,
                                                  height + node.top + top_edge, 0.0))

                    # yz inner
                    mesh.vertices[8].co = Vector((0.0, -height - node.bottom,
                                                  depth + node.front))
                    mesh.vertices[9].co = Vector((0.0, -height - node.bottom,
                                                  -depth - node.back))
                    mesh.vertices[10].co = Vector((0.0, height + node.top,
                                                   depth + node.front))
                    mesh.vertices[11].co = Vector((0.0, height + node.top,
                                                   -depth - node.back))

                    # yz outer
                    mesh.vertices[12].co = Vector((0.0,
                                                   -height - node.bottom - bottom_edge,
                                                   depth + node.front + front_edge))
                    mesh.vertices[13].co = Vector((0.0,
                                                   -height - node.bottom - bottom_edge,
                                                   -depth - node.back - back_edge))
                    mesh.vertices[14].co = Vector((0.0,
                                                   height + node.top + top_edge,
                                                   depth + node.front + front_edge))
                    mesh.vertices[15].co = Vector((0.0,
                                                   height + node.top + top_edge,
                                                   -depth - node.back - back_edge))

                    # xz inner
                    mesh.vertices[16].co = Vector((width + node.right, 0.0,
                                                   depth + node.front))
                    mesh.vertices[17].co = Vector((width + node.right, 0.0,
                                                   -depth - node.back))
                    mesh.vertices[18].co = Vector((-width - node.left, 0.0,
                                                   depth + node.front))
                    mesh.vertices[19].co = Vector((-width - node.left, 0.0,
                                                   -depth - node.back))

                    # xz outer
                    mesh.vertices[20].co = Vector((width + node.right + right_edge,
                                                   0.0, depth + node.front + front_edge))
                    mesh.vertices[21].co = Vector((width + node.right + right_edge,
                                                   0.0, -depth - node.back - back_edge))
                    mesh.vertices[22].co = Vector((-width - node.left - left_edge,
                                                   0.0, depth + node.front + front_edge))
                    mesh.vertices[23].co = Vector((-width - node.left - left_edge,
                                                   0.0, -depth - node.back - back_edge))

                    ob.modifiers['bevel'].width = node.radius

                if self.filter_type == 'ramp':
                    if node.rampType in ['0', '2']:
                        # set sphere radii
                        mesh = ob.data
                        len_outer = mesh.vertices[0].co.length
                        len_inner = mesh.vertices[58].co.length
                        # if len is 0 we can't scale stuff
                        if len_inner == 0.0 or len_outer == 0.0:
                            self.remove_filter_geo()
                            mesh = self.add_filter_geo(shape).data
                            len_outer = mesh.vertices[0].co.length
                            len_inner = mesh.vertices[58].co.length

                        for v in mesh.vertices[0:58]:
                            v.co = v.co * node.endDist * (1.0 / len_outer)

                        for v in mesh.vertices[58:]:
                            v.co = v.co * node.beginDist * (1.0 / len_inner)

                    elif node.rampType == '1':
                        # one rect close, other far
                        nearz = node.beginDist
                        farz = node.endDist
                        mesh = ob.data
                        mesh.vertices[0].co = Vector((-.5, -.5, nearz))
                        mesh.vertices[1].co = Vector((.5, -.5, nearz))
                        mesh.vertices[2].co = Vector((-.5, .5, nearz))
                        mesh.vertices[3].co = Vector((.5, .5, nearz))

                        mesh.vertices[4].co = Vector((-.5, -.5, farz))
                        mesh.vertices[5].co = Vector((.5, -.5, farz))
                        mesh.vertices[6].co = Vector((-.5, .5, farz))
                        mesh.vertices[7].co = Vector((.5, .5, farz))
                    else:
                        # set circle radii
                        mesh = ob.data
                        len_outer = mesh.vertices[0].co.length
                        len_inner = mesh.vertices[58].co.length
                        # if len is 0 we can't scale stuff
                        if len_inner == 0.0 or len_outer == 0.0:
                            self.remove_filter_geo()
                            mesh = self.add_filter_geo(shape).data
                            len_outer = mesh.vertices[0].co.length
                            len_inner = mesh.vertices[58].co.length

                        for v in mesh.vertices[0:32]:
                            v.co = v.co * node.endDist * (1.0 / len_outer)

                        for v in mesh.vertices[32:]:
                            v.co = v.co * node.beginDist * (1.0 / len_inner)

    use_renderman_node = BoolProperty(
        name="Use RenderMans Light Node",
        description="Will enable RenderMan light Nodes, opening more options",
        default=False, update=update_light_type)

    renderman_type = EnumProperty(
        name="Light Type",
        update=update_light_type,
        items=[('AREA', 'Area', 'Area Light'),
               ('ENV', 'Environment', 'Environment Light'),
               ('SKY', 'Sky', 'Simulated Sky'),
               ('DIST', 'Distant', 'Distant Light'),
               ('SPOT', 'Spot', 'Spot Light'),
               ('POINT', 'Point', 'Point Light'),
               ('PORTAL', 'Portal', 'Portal Light'),
               ('FILTER', 'Filter', 'Light Filter')],
        default='AREA'
    )

    area_shape = EnumProperty(
        name="Area Shape",
        update=update_area_shape,
        items=[('rect', 'Rectangle', 'Rectangle'),
               ('disk', 'Disk', 'Disk'),
               ('sphere', 'Sphere', 'Sphere'), ],
        default='rect'
    )

    filter_type = EnumProperty(
        name="Area Shape",
        update=update_filter_type,
        items=[('barn', 'Barn', 'Barn'),
               ('blocker', 'Blocker', 'Blocker'),
               #('combiner', 'Combiner', 'Combiner'),
               ('cookie', 'Cookie', 'Cookie'),
               ('gobo', 'Gobo', 'Gobo'),
               ('intmult', 'Multiply', 'Multiply'),
               ('ramp', 'Ramp', 'Ramp'),
               ('rod', 'Rod', 'Rod')
               ],
        default='blocker'
    )

    light_filters = CollectionProperty(
        type=RendermanLightFilter
    )
    light_filters_index = IntProperty(min=-1, default=-1)

    shadingrate = FloatProperty(
        name="Light Shading Rate",
        description="Shading Rate for lights.  Keep this high unless banding or pixellation occurs on detailed light maps",
        default=100.0)

    # illuminate
    illuminates_by_default = BoolProperty(
        name="Illuminates by default",
        description="The light illuminates objects by default",
        default=True)

    light_primary_visibility = BoolProperty(
        name="Light Primary Visibility",
        description="Camera visibility for this light",
        update=update_vis,
        default=True)

    def update_mute(self, context):
        if engine.is_ipr_running():
            engine.ipr.mute_light()

    mute = BoolProperty(
        name="Mute",
        update=update_mute,
        description="Turn off this light",
        default=False)

    def update_solo(self, context):
        lamp = self.id_data
        scene = context.scene

        # if the scene solo is on already find the old one and turn off
        if self.solo:
            if scene.renderman.solo_light:
                for ob in scene.objects:
                    if ob.type == 'LAMP' and ob.data.renderman != self and ob.data.renderman.solo:
                        ob.data.renderman.solo = False
                        break

            if engine.is_ipr_running():
                engine.ipr.solo_light()
        elif engine.is_ipr_running():
            engine.ipr.un_solo_light()

        scene.renderman.solo_light = self.solo

    solo = BoolProperty(
        name="Solo",
        update=update_solo,
        description="Turn on only this light",
        default=False)


class RendermanWorldSettings(bpy.types.PropertyGroup):

    def get_light_node(self):
        return getattr(self, self.light_node) if self.light_node else None

    def get_light_node_name(self):
        return self.light_node.replace('_settings', '')

    # do this to keep the nice viewport update
    def update_light_type(self, context):
        world = context.scene.world
        world_type = world.renderman.renderman_type
        if world_type == 'NONE':
            return
        # use pxr area light for everything but env, sky
        light_shader = 'PxrDomeLight'
        if world_type == 'SKY':
            light_shader = 'PxrEnvDayLight'

        self.light_node = light_shader + "_settings"

    def update_vis(self, context):
        lamp = context.scene.world

        from . import engine
        if engine.is_ipr_running():
            engine.ipr.update_light_visibility(lamp)

    renderman_type = EnumProperty(
        name="World Type",
        update=update_light_type,
        items=[
            ('NONE', 'None', 'No World'),
            ('ENV', 'Environment', 'Environment Light'),
            ('SKY', 'Sky', 'Simulated Sky'),
        ],
        default='NONE'
    )

    use_renderman_node = BoolProperty(
        name="Use RenderMans World Node",
        description="Will enable RenderMan World Nodes, opening more options",
        default=False, update=update_light_type)

    light_node = StringProperty(
        name="Light Node",
        default='')

    light_primary_visibility = BoolProperty(
        name="Light Primary Visibility",
        description="Camera visibility for this light",
        update=update_vis,
        default=True)

    shadingrate = FloatProperty(
        name="Light Shading Rate",
        description="Shading Rate for lights.  Keep this high unless banding or pixellation occurs on detailed light maps",
        default=100.0)

    world_rib_box = StringProperty(
        name="World RIB box",
        description="Injects RIB into the 'world' block",
        default="")

    # illuminate
    illuminates_by_default = BoolProperty(
        name="Illuminates by default",
        description="Illuminates objects by default",
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
               ('LIFE_TIME', 'Lifetime', ''),
               ('ID', 'ID', '')
               ]   # XXX: Would be nice to have particle ID, needs adding in RNA
    )


class RendermanParticleSettings(bpy.types.PropertyGroup):

    particle_type_items = [('particle', 'Particle', 'Point primitive'),
                           ('blobby', 'Blobby',
                            'Implicit Surface (metaballs)'),
                           ('sphere', 'Sphere', 'Two-sided sphere primitive'),
                           ('disk', 'Disk', 'One-sided disk primitive'),
                           ('OBJECT', 'Object',
                            'Instanced objects at each point')
                           ]

    use_object_material = BoolProperty(
        name="Use Master Object's Material",
        description="Use the master object's material for instancing",
        default=False
    )

    particle_type = EnumProperty(
        name="Point Type",
        description="Geometric primitive for points to be rendered as",
        items=particle_type_items,
        default='particle')
    particle_instance_object = StringProperty(
        name="Instance Object",
        description="Object to instance on every particle",
        default="")

    round_hair = BoolProperty(
        name="Round Hair",
        description="Render curves as round cylinders or ribbons.  Round is faster and recommended for hair",
        default=True)

    constant_width = BoolProperty(
        name="Constant Width",
        description="Override particle sizes with constant width value",
        default=False)

    width = FloatProperty(
        name="Width",
        description="With used for constant width across all particles",
        precision=4,
        default=0.01)

    export_default_size = BoolProperty(
        name="Export Default size",
        description="Export the particle size as the default 'width' primitive variable",
        default=True)

    export_scalp_st = BoolProperty(
        name="Export Emitter UV",
        description="On hair, export the u/v from the emitter where the hair originates.  Use the variables 'scalpS' and 'scalpT' in your manifold node",
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
    interp_boundary = IntProperty(
        name="Subdivision Edge Interpolation Mode",
        description="Defines how a subdivided mesh interpolates its boundary edges",
        default=1,
        min=0, max=2)
    face_boundary = IntProperty(
        name="Subdivision UV Interpolation Mode",
        description="Defines how a subdivided mesh interpolates its UV coordinates",
        default=3,
        min=0, max=3)

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


class OpenVDBChannel(bpy.types.PropertyGroup):
    name = StringProperty(name="Channel Name")
    type = EnumProperty(name="Channel Type",
                        items=[
                            ('float', 'Float', ''),
                            ('vector', 'Vector', ''),
                            ('color', 'Color', ''),
                        ])


class RendermanObjectSettings(bpy.types.PropertyGroup):

    # for some odd reason blender truncates this as a float
    update_timestamp = IntProperty(
        name="Update Timestamp", default=int(time.time()),
        description="Used for telling if an objects rib archive is dirty", subtype='UNSIGNED'
    )

    pre_object_rib_box = StringProperty(
        name="Pre Object RIB text",
        description="Injects an RIB before this object's geometry",
        default="")

    post_object_rib_box = StringProperty(
        name="Post Object RIB text",
        description="Injects an RIB after this object's geometry",
        default="")

    geometry_source = EnumProperty(
        name="Geometry Source",
        description="Where to get the geometry data for this object",
        items=[('BLENDER_SCENE_DATA', 'Blender Scene Data', 'Exports and renders blender scene data directly from memory'),
               ('ARCHIVE', 'Archive',
                'Renders a prevously exported RIB archive'),
               ('OPENVDB', 'OpenVDB File',
                'Renders a prevously exported OpenVDB file'),
               ('DELAYED_LOAD_ARCHIVE', 'Delayed Load Archive',
                'Loads and renders geometry from an archive only when its bounding box is visible'),
               ('PROCEDURAL_RUN_PROGRAM', 'Procedural Run Program',
                'Generates procedural geometry at render time from an external program'),
               ('DYNAMIC_LOAD_DSO', 'Dynamic Load DSO',
                'Generates procedural geometry at render time from a dynamic shared object library')
               ],
        default='BLENDER_SCENE_DATA')

    openvdb_channels = CollectionProperty(
        type=OpenVDBChannel, name="OpenVDB Channels")
    openvdb_channel_index = IntProperty(min=-1, default=-1)

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
               ('RI_VOLUME', 'Volume', 'Volume primitive'),
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
        name="Archive Export Path",
        description="Path to automatically save this object as a RIB archive",
        subtype='FILE_PATH',
        default="")

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
        description="Override the default shading rate for this object",
        default=False)
    shadingrate = FloatProperty(
        name="Micropolygon Length",
        description="Maximum distance between displacement samples (lower = more detailed shading)",
        default=1.0)
    watertight = BoolProperty(
        name="Watertight Dicing",
        description="Enables watertight dicing, which can solve cases where displacement causes visible seams in objects",
        default=False)
    geometric_approx_motion = FloatProperty(
        name="Motion Approximation",
        description="Shading Rate is scaled up by motionfactor/16 times the number of pixels of motion",
        default=1.0)
    geometric_approx_focus = FloatProperty(
        name="Focus Approximation",
        description="Shading Rate is scaled proportionally to the radius of DoF circle of confusion, multiplied by this value",
        default=-1.0)

    motion_segments_override = BoolProperty(
        name="Override Motion Samples",
        description="Override the global number of motion samples for this object",
        default=False)
    motion_segments = IntProperty(
        name="Motion Samples",
        description="Number of motion samples to take for multi-segment motion blur.  This should be raised if you notice segment artifacts in blurs",
        min=2, max=16, default=2)

    shadinginterpolation = EnumProperty(
        name="Shading Interpolation",
        description="Method of interpolating shade samples across micropolygons",
        items=[('constant', 'Constant', 'Flat shaded micropolygons'),
               ('smooth', 'Smooth', 'Smooth Gourard shaded micropolygons')],
        default='smooth')

    matte = BoolProperty(
        name="Matte Object",
        description="Render the object as a matte cutout (alpha 0.0 in final frame)",
        default=False)

    holdout = BoolProperty(
        name="Holdout",
        description="Render the object as a holdout",
        default=False)

    visibility_camera = BoolProperty(
        name="Visible to Camera Rays",
        description="Object visibility to Camera Rays",
        default=True)
    visibility_trace_indirect = BoolProperty(
        name="All Indirect Rays",
        description="Sets all the indirect transport modes at once (specular & diffuse)",
        default=True)
    visibility_trace_transmission = BoolProperty(
        name="Visible to Transmission Rays",
        description="Object visibility to Transmission Rays (eg. shadow() and transmission())",
        default=True)

    raytrace_override = BoolProperty(
        name="Ray Trace Override",
        description="Override default RenderMan ray tracing behavior. Recommended for advanced users only",
        default=False)
    raytrace_pixel_variance = FloatProperty(
        name="Relative Pixel Variance",
        description="Allows this object to render to a different quality level than the main scene.  Actual pixel variance will be this number multiplied by the main pixel variance",
        default=1.0)
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
    raytrace_ior = FloatProperty(
        name="Index of Refraction",
        description="When using nested dielectrics (overlapping materials), this should be set to the same value as the ior of your material",
        default=1.0)

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

    MatteID0 = FloatVectorProperty(
        name="Matte ID 0",
        description="Matte ID 0 Color, you also need to add the PxrMatteID node to your bxdf",
        size=3,
        subtype='COLOR',
        default=[0.0, 0.0, 0.0], soft_min=0.0, soft_max=1.0)

    MatteID1 = FloatVectorProperty(
        name="Matte ID 1",
        description="Matte ID 1 Color, you also need to add the PxrMatteID node to your bxdf",
        size=3,
        subtype='COLOR',
        default=[0.0, 0.0, 0.0], soft_min=0.0, soft_max=1.0)

    MatteID2 = FloatVectorProperty(
        name="Matte ID 2",
        description="Matte ID 2 Color, you also need to add the PxrMatteID node to your bxdf",
        size=3,
        subtype='COLOR',
        default=[0.0, 0.0, 0.0], soft_min=0.0, soft_max=1.0)

    MatteID3 = FloatVectorProperty(
        name="Matte ID 3",
        description="Matte ID 3 Color, you also need to add the PxrMatteID node to your bxdf",
        size=3,
        subtype='COLOR',
        default=[0.0, 0.0, 0.0], soft_min=0.0, soft_max=1.0)

    MatteID4 = FloatVectorProperty(
        name="Matte ID 4",
        description="Matte ID 4 Color, you also need to add the PxrMatteID node to your bxdf",
        size=3,
        subtype='COLOR',
        default=[0.0, 0.0, 0.0], soft_min=0.0, soft_max=1.0)

    MatteID5 = FloatVectorProperty(
        name="Matte ID 5",
        description="Matte ID 5 Color, you also need to add the PxrMatteID node to your bxdf",
        size=3,
        subtype='COLOR',
        default=[0.0, 0.0, 0.0], soft_min=0.0, soft_max=1.0)

    MatteID6 = FloatVectorProperty(
        name="Matte ID 6",
        description="Matte ID 6 Color, you also need to add the PxrMatteID node to your bxdf",
        size=3,
        subtype='COLOR',
        default=[0.0, 0.0, 0.0], soft_min=0.0, soft_max=1.0)

    MatteID7 = FloatVectorProperty(
        name="Matte ID 7",
        description="Matte ID 7 Color, you also need to add the PxrMatteID node to your bxdf",
        size=3,
        subtype='COLOR',
        default=[0.0, 0.0, 0.0], soft_min=0.0, soft_max=1.0)


class Tab_CollectionGroup(bpy.types.PropertyGroup):

    #################
    #       Tab     #
    #################

    bpy.types.Scene.rm_ipr = BoolProperty(
        name="IPR settings",
        description="Show some useful setting for the Interactive Rendering",
        default=False)

    bpy.types.Scene.rm_render = BoolProperty(
        name="Render settings",
        description="Show some useful setting for the Rendering",
        default=False)

    bpy.types.Scene.rm_render_external = BoolProperty(
        name="Render settings",
        description="Show some useful setting for external rendering",
        default=False)

    bpy.types.Scene.rm_help = BoolProperty(
        name="Help",
        description="Show some links about RenderMan and the documentation",
        default=False)

    bpy.types.Scene.rm_env = BoolProperty(
        name="Envlight",
        description="Show some settings about the selected Env light",
        default=False)

    bpy.types.Scene.rm_area = BoolProperty(
        name="AreaLight",
        description="Show some settings about the selected Area Light",
        default=False)

    bpy.types.Scene.rm_daylight = BoolProperty(
        name="DayLight",
        description="Show some settings about the selected Day Light",
        default=False)

    bpy.types.Scene.prm_cam = BoolProperty(
        name="Renderman Camera",
        description="Show some settings about the camera",
        default=False)


initial_aov_channels = [("a", "alpha", ""),
                        ("id", "id", "Returns the integer assigned via the 'identifier' attribute as the pixel value"),
                        ("z", "z_depth", "Depth from the camera in world space"),
                        ("zback", "z_back",
                         "Depth at the back of volumetric objects in world space"),
                        ("P", "P", "Position of the point hit by the incident ray"),
                        ("PRadius", "PRadius",
                         "Cross-sectional size of the ray at the hit point"),
                        ("cpuTime", "cpuTime", "The time taken to render a pixel"),
                        ("sampleCount", "sampleCount",
                         "The number of samples taken for the resulting pixel"),
                        ("Nn", "Nn", "Normalized shading normal"),
                        ("Ngn", "Ngn", "Normalized geometric normal"),
                        ("Tn", "Tn", "Normalized shading tangent"),
                        ("Vn", "Vn", "Normalized view vector (reverse of ray direction)"),
                        ("VLen", "VLen", "Distance to hit point along the ray"),
                        ("curvature", "curvature", "Local surface curvature"),
                        ("incidentRaySpread", "incidentRaySpread",
                         "Rate of spread of incident ray"),
                        ("mpSize", "mpSize",
                         "Size of the micropolygon that the ray hit"),
                        ("u", "u", "The parametric coordinates on the primitive"),
                        ("v", "v", "The parametric coordinates on the primitive"),
                        ("w", "w", "The parametric coordinates on the primitive"),
                        ("du", "du", "Derivatives of u, v, and w to adjacent micropolygons"),
                        ("dv", "dv", "Derivatives of u, v, and w to adjacent micropolygons"),
                        ("dw", "dw", "Derivatives of u, v, and w to adjacent micropolygons"),
                        ("dPdu", "dPdu", "Direction of maximal change in u, v, and w"),
                        ("dPdv", "dPdv", "Direction of maximal change in u, v, and w"),
                        ("dPdw", "dPdw", "Direction of maximal change in u, v, and w"),
                        ("dufp", "dufp",
                         "Multiplier to dPdu, dPdv, dPdw for ray differentials"),
                        ("dvfp", "dvfp",
                         "Multiplier to dPdu, dPdv, dPdw for ray differentials"),
                        ("dwfp", "dwfp",
                         "Multiplier to dPdu, dPdv, dPdw for ray differentials"),
                        ("time", "time", "Time sample of the ray"),
                        ("dPdtime", "dPdtime", "Motion vector"),
                        ("id", "id", "Returns the integer assigned via the identifier attribute as the pixel value"),
                        ("outsideIOR", "outsideIOR",
                         "Index of refraction outside this surface"),
                        ("__Pworld", "Pworld", "P in world-space"),
                        ("__Nworld", "Nworld", "Nn in world-space"),
                        ("__depth", "depth", "Multi-purpose AOV\nr : depth from camera in world-space\ng : height in world-space\nb : geometric facing ratio : abs(Nn.V)"),
                        ("__st", "st", "Texture coords"),
                        ("__Pref", "Pref", "Reference Position primvar (if available)"),
                        ("__Nref", "Nref", "Reference Normal primvar (if available)"),
                        ("__WPref", "WPref",
                         "Reference World Position primvar (if available)"),
                        ("__WNref", "WNref", "Reference World Normal primvar (if available)")]


class RendermanPluginSettings(bpy.types.PropertyGroup):
    pass


def prune_perspective_camera(args_xml, name):
    for page in args_xml.findall('page'):
        page_name = page.get('name')
        if page_name == 'Standard Perspective':
            args_xml.remove(page)

    pretty_name = name.replace('Pxr', '')
    projection_names.append((name, pretty_name, ''))
    return args_xml


# get the names of args files in rmantree/lib/ris/integrator/args
def get_integrator_names(args_xml, name):
    integrator_names.append((name, name[3:], ''))
    return args_xml


def get_samplefilter_names(args_xml, name):
    if 'Combiner' in name:
        return None
    else:
        samplefilter_names.append((name, name[3:], ''))
        return args_xml


def get_displayfilter_names(args_xml, name):
    if 'Combiner' in name:
        return None
    else:
        displayfilter_names.append((name, name[3:], ''))
        return args_xml


plugin_mapping = {
    'integrator': (get_integrator_names, RendermanSceneSettings),
    'projection': (prune_perspective_camera, RendermanCameraSettings),
    'light': (None, RendermanLightSettings),
    'lightfilter': (None, RendermanLightSettings),
    'displayfilter': (get_displayfilter_names, RendermanDisplayFilterSettings),
    'samplefilter': (get_samplefilter_names, RendermanSampleFilterSettings),
}


def register_plugin_to_parent(ntype, name, args_xml, plugin_type, parent):
    # do some parsing and get props
    inputs = [p for p in args_xml.findall('./param')] + \
        [p for p in args_xml.findall('./page')]
    class_generate_properties(ntype, name, inputs)
    setattr(ntype, 'renderman_node_type', plugin_type)

    # register and add to scene_settings
    bpy.utils.register_class(ntype)
    setattr(parent, "%s_settings" % name,
            PointerProperty(type=ntype, name="%s Settings" % name)
            )

    # special case for world lights
    if plugin_type == 'light' and name in ['PxrDomeLight', 'PxrEnvDayLight']:
        setattr(RendermanWorldSettings, "%s_settings" % name,
                PointerProperty(type=ntype, name="%s Settings" % name)
                )


def register_plugin_types():
    rmantree = guess_rmantree()
    args_path = os.path.join(rmantree, 'lib', 'plugins', 'Args')
    items = []
    for f in os.listdir(args_path):
        args_xml = ET.parse(os.path.join(args_path, f)).getroot()
        plugin_type = args_xml.find("shaderType/tag").attrib['value']
        if plugin_type not in plugin_mapping:
            continue
        prune_method, parent = plugin_mapping[plugin_type]
        name = f.split('.')[0]
        typename = name + plugin_type.capitalize() + 'Settings'
        ntype = type(typename, (RendermanPluginSettings,), {})
        ntype.bl_label = name
        ntype.typename = typename
        ntype.bl_idname = typename
        ntype.plugin_name = name

        if prune_method:
            args_xml = prune_method(args_xml, name)
        if not args_xml:
            continue

        register_plugin_to_parent(ntype, name, args_xml, plugin_type, parent)


@persistent
def initial_groups(scene):
    scene = bpy.context.scene
    if 'collector' not in scene.renderman.object_groups.keys():
        default_group = scene.renderman.object_groups.add()
        default_group.name = 'collector'
    if 'All' not in scene.renderman.light_groups.keys():
        default_group = scene.renderman.light_groups.add()
        default_group.name = 'All'


# collection of property group classes that need to be registered on
# module startup
classes = [RendermanPath,
           RendermanInlineRIB,
           RendermanGroup,
           LightLinking,
           RendermanMeshPrimVar,
           RendermanParticlePrimVar,
           RendermanMaterialSettings,
           RendermanAnimSequenceSettings,
           RendermanTextureSettings,
           RendermanLightFilter,
           RendermanLightSettings,
           RendermanParticleSettings,
           RendermanPluginSettings,
           RendermanWorldSettings,
           RendermanAOV,
           RendermanRenderLayerSettings,
           RendermanCameraSettings,
           RendermanDisplayFilterSettings,
           RendermanSampleFilterSettings,
           RendermanSceneSettings,
           RendermanMeshGeometrySettings,
           RendermanCurveGeometrySettings,
           OpenVDBChannel,
           RendermanObjectSettings,
           Tab_CollectionGroup
           ]


def register():

    register_plugin_types()
    # dynamically find integrators from args
    # register_integrator_settings(RendermanSceneSettings)
    # dynamically find camera from args
    # register_camera_settings()

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.renderman = PointerProperty(
        type=RendermanSceneSettings, name="Renderman Scene Settings")
    bpy.types.World.renderman = PointerProperty(
        type=RendermanWorldSettings, name="Renderman World Settings")
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
