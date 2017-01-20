import os.path
from .base_classes import RendermanBasePropertyGroup
import bpy
from bpy.props import *
from .rib_helpers import *
from ..util.util import path_list_convert, args_files_in_path
from bpy.props import PointerProperty, StringProperty, BoolProperty, \
    EnumProperty, IntProperty, FloatProperty, FloatVectorProperty, \
    CollectionProperty, BoolVectorProperty


def export_searchpaths(ri, paths):
    ''' converts the paths dictionary to a rib specific format and exports them '''
    ri.Option("ribparse", {"string varsubst": ["$"]})
    ri.Option("searchpath", {"string shader": ["%s" % ':'.join(path_list_convert(paths['shader'],
                                                                                 to_unix=True))]})
    rel_tex_paths = [os.path.relpath(path, paths['export_dir'])
                     for path in paths['texture']]
    ri.Option("searchpath", {"string texture": ["%s" % ':'.join(path_list_convert(rel_tex_paths +
                                                                                  ["@"], to_unix=True))]})
    ri.Option("searchpath", {"string archive": os.path.relpath(paths['archive'],
                                                               paths['export_dir'])})

''' Scene Properties '''


class RendermanSceneSettings(RendermanBasePropertyGroup):
    ''' Holds the main property endpoint for converting a scene to Renderman 
        as well as the methods for caching any data under it'''
    ### scene properties ###

    # sampling
    pixel_variance = FloatProperty(
        name="Pixel Variance",
        description="If a pixel changes by less than this amount when updated, it will not receive further samples in adaptive mode.  Lower values lead to increased render times and higher quality images.",
        min=0, max=1, default=.01)

    dark_falloff = FloatProperty(
        name="Dark Falloff",
        description="Deprioritizes adaptive sampling in dark areas. Raising this can potentially reduce render times but may increase noise in dark areas.",
        min=0, max=1, default=.025)

    min_samples = IntProperty(
        name="Min Samples",
        description="The minimum number of camera samples per pixel.  If this is set to '0' then the min samples will be the square root of the max_samples.",
        min=0, default=4)

    max_samples = IntProperty(
        name="Max Samples",
        description="The maximum number of camera samples per pixel.  This should be set in 'power of two' numbers (1, 2, 4, 8, 16, etc).",
        min=0, default=128)

    incremental = BoolProperty(
        name="Incremental Render",
        description="When enabled every pixel is sampled once per render pass.  This allows the user to quickly see the entire image during rendering, and as each pass completes the image will become clearer.  NOTE-This mode is automatically enabled with some render integrators (PxrVCM)",
        default=True)

    show_integrator_settings = BoolProperty(
        name="Integration Settings",
        description="Show Integrator Settings",
        default=False)

    # motion blur
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

    advanced_timing = BoolProperty(
        name="Advanced Shutter Timing",
        description="Enables advanced settings for shutter timing",
        default=False)

    c1 = FloatProperty(
        name="C1",
        default=0.0)

    c2 = FloatProperty(
        name="C2",
        default=0.0)

    d1 = FloatProperty(
        name="D1",
        default=0.0)

    d2 = FloatProperty(
        name="D2",
        default=0.0)

    e1 = FloatProperty(
        name="E1",
        default=0.0)

    e2 = FloatProperty(
        name="E2",
        default=0.0)

    f1 = FloatProperty(
        name="F1",
        default=0.0)

    f2 = FloatProperty(
        name="F2",
        default=0.0)

    # advanced properties
    pixelfilter = EnumProperty(
        name="Pixel Filter",
        description="Filter to use to combine pixel samples",
        items=[('box', 'Box', ''),
               ('sinc', 'Sinc', ''),
               ('gaussian', 'Gaussian', ''),
               ('triangle',  'Triangle',  ''),
               ('catmull-rom',  'Catmull-Rom', '')],
        default='gaussian')

    pixelfilter_x = IntProperty(
        name="Filter Size X",
        description="Size of the pixel filter in X dimension",
        min=0, max=16, default=2)

    pixelfilter_y = IntProperty(
        name="Filter Size Y",
        description="Size of the pixel filter in Y dimension",
        min=0, max=16, default=2)

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

    micropoly_length = FloatProperty(
        name="Micropolygon Length",
        description="Default maximum distance between displacement samples.  This can be left at 1 unless you need more detail on displaced objects.",
        default=1.0)

    dicing_strategy = EnumProperty(
        name="Dicing Strategy",
        description="Sets the method that PRMan uses to tessellate objects.  Spherical may help with volume rendering",
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

    threads = IntProperty(
        name="Rendering Threads",
        description="Number of processor threads to use.  Note, 0 uses all cores, -1 uses all cores but one.",
        min=-32, max=32, default=-1)

    use_statistics = BoolProperty(
        name="Statistics",
        description="Print statistics to stats.xml after render",
        default=False)

    texture_cache_size = IntProperty(
        name="Texture Cache Size (MB)",
        description="Maximum number of megabytes to devote to texture caching.",
        default=2048)

    geo_cache_size = IntProperty(
        name="Tesselation Cache Size (MB)",
        description="Maximum number of megabytes to devote to tesselation cache for tracing geometry.",
        default=2048)

    opacity_cache_size = IntProperty(
        name="Opacity Cache Size (MB)",
        description="Maximum number of megabytes to devote to caching opacity and presence values.  0 turns this off.",
        default=1000)

    lazy_rib_gen = BoolProperty(
        name="Cache Rib Generation",
        description="On unchanged objects, don't re-emit rib.  Will result in faster spooling of renders.",
        default=True)

    always_generate_textures = BoolProperty(
        name="Always Recompile Textures",
        description="Recompile used textures at export time to the current rib folder. Leave this unchecked to speed up re-render times",
        default=False)

    ### overrides of base class methods ###

    def to_rib(self, ri, **kwargs):
        ''' Pretty simply generates the RIB for the scene and injects all the objects '''
        scene = self.id_data
        scene_rm = scene.renderman

        # self.export_options(ri)
        # self.export_displayfilters(ri)
        # self.export_samplefilters(ri)
        # self.export_hider(ri)
        # self.export_integrator(ri)

        ri.FrameBegin(scene.frame_current)

        # self.export_render_settings(ri)
        #export_default_bxdf(ri, "default")
        #export_materials_archive(ri, rpass, scene)

        # each render layer gets it's own display and world rib
        for render_layer in scene.render.layers:
            self.render_layer_to_rib(ri, render_layer, **kwargs)

        ri.FrameEnd()

    def cache_motion(self, ri, mgr=None):
        ''' Since objects can override the motion segments for the scene, we need to 
            collect all the objects in motion and group them by number of segments.  
            Only then can we update the frame number in the scene and cache the motion. 
            Finally, check that the objects/datas are actually in motion before writing their 
            caches '''
        if not self.motion_blur:
            return

        scene = self.id_data
        motion_items = {}

        # add item with mb to dictionary
        def add_mb_item(item):
            if item.has_motion():
                if item.motion_segments not in motion_items:
                    motion_items[item.motion_segments] = []
                motion_items[item.motion_segments].append(item)

        # first we sort the items in motion by motion segments
        for ob in scene.objects:
            ob_rm = ob.renderman

            add_mb_item(ob_rm)

            for data in ob_rm.get_data_items():
                add_mb_item(data.renderman)

        # trying to do the minimal scene recalcs to get the motion data
        origframe = scene.frame_current
        for num_segs, items in motion_items.items():
            # prepare list of frames/sub-frames in advance,
            # ordered from future to present,
            # to prevent too many scene updates
            # (since loop ends on current frame/subframe)
            subframes = self.get_subframes(num_segs)
            actual_subframes = [origframe + subframe for subframe in subframes]
            for seg in subframes:
                if seg < 0.0:
                    scene.frame_set(origframe - 1, 1.0 + seg)
                else:
                    scene.frame_set(origframe, seg)

                for item in items:
                    item.cache_motion(scene, seg)

        scene.frame_set(origframe, 0)

        # check for items that might not be actually in motion
        for segs, items in motion_items.items():
            for item in items:
                item.check_motion()

    ### scene specific methods ###

    def clear_motion(self):
        ''' remove all the motion data on objects and datas '''
        scene = self.id_data
        for ob in scene.objects:
            ob.renderman.clear_motion()

            for data in ob.renderman.get_data_items():
                data.renderman.clear_motion()

    def get_subframes(self, segs):
        ''' get the range of subframs for a scene based on mb settings '''
        if segs == 0:
            return []
        min = -1.0
        shutter_interval = self.shutter_angle / 360.0
        if self.shutter_timing == 'CENTER':
            min = 0 - .5 * shutter_interval
        elif self.shutter_timing == 'PRE':
            min = 0 - shutter_interval
        elif self.shutter_timing == 'POST':
            min = 0

        return [min + i * shutter_interval / (segs - 1) for i in range(segs)]

    def export_displayfilters(self, ri):
        ''' calls each display filter's to_rib and exports a combiner if n > 1 '''
        display_filter_names = []
        for df in self.display_filters:
            df.to_rib(ri)
            display_filter_names.append(df.name)

        if len(display_filter_names) > 1:
            params = {'reference displayfilter[%d] filter' % len(
                display_filter_names): display_filter_names}
            ri.DisplayFilter('PxrDisplayFilterCombiner', 'combiner', params)

    def export_samplefilters(self, ri):
        ''' calls each sample filter's to_rib and exports a combiner if n > 1 '''
        filter_names = []
        for sf in self.sample_filters:
            sf.to_rib(ri)
            filter_names.append(sf.name)

        if len(filter_names) > 1:
            params = {'reference samplefilter[%d] filter' % len(
                filter_names): filter_names}
            ri.SampleFilter('PxrSampleFilterCombiner', 'combiner', params)

    def render_layer_to_rib(self, ri, render_layer, **kwargs):
        ''' Each Render Layer gets it own world begin, world end 
            pass the visible layers to the objects so that only visibile 
            objects get exported '''
        scene = self.id_data
        ri.WorldBegin()
        # if scene.world:
        #    scene.world.renderman.to_rib(ri, **kwargs)

        self.export_displays_for_layer(ri, render_layer, **kwargs)
        kwargs['render_layer'] = render_layer
        for ob in scene.objects:
            if not ob.parent:
                ob.renderman.to_rib(ri, **kwargs)

        ri.WorldEnd()

    def export_displays_for_layer(self, ri, render_layer, **kwargs):
        ''' export all the displays for this render layer 
            as well as the bucket order '''
        is_interactive = kwargs.get('is_interactive', False)
        scene = self.id_data
        render_settings = scene.render

        # bucket order
        # bucket_order = 'spiral' if is_interactive else self.bucket_shape.lower()
        # bucket_params = {'string order': [bucket_order]}
        # if bucket_order == 'spiral':
        #     x = self.bucket_spiral_x
        #     y = self.bucket_spiral_y
        #     if x > render_settings.resolution_x or x == -1:
        #         x = settings.resolution_x / 2
        #     if y > render_settings.resolution_y or y == -1:
        #         y = settings.resolution_y / 2
        #     bucket_params['orderorigin'] = [x,y]
        # ri.Option("bucket", {"string order": [rm.bucket_shape.lower()]})

        display_driver = kwargs.get('display_driver', 'openexr')
        paths = kwargs.get('paths', {})
        output_files = paths.get('output_files', [])
        aovs_to_denoise = paths.get('aovs_to_denoise', [])

        if 'main_image' in paths:
            # just going to always output rgba
            ri.Display(paths['main_image'], display_driver, "rgba", {})
            output_files.append(paths['main_image'])
        else:
            ri.Display('null', 'null', "rgba", {})

        # rm_rl = self.render_layers.get(render_layer.name, None)

        # # there's no render layer settins
        # if not rm_rl:
        #     RenderLayer.simple_to_rib(ri, render_layer)

        # # else we have custom rman render layer settings
        # else:
        #     rm_rl.to_rib(ri)

        # external_render = kwargs.get('external_render', False)
        # if (self.do_denoise and not external_render or \
        #     self.external_denoise and external_render) and not is_interactive:
        #     # add display channels for denoising
        #     denoise_aovs = [
        #         # (name, declare type/name, source, statistics, filter)
        #         ("Ci", 'color', None, None, None),
        #         ("a", 'float', None, None, None),
        #         ("mse", 'color', 'color Ci', 'mse', None),
        #         ("albedo", 'color',
        #          'color lpe:nothruput;noinfinitecheck;noclamp;unoccluded;overwrite;C(U2L)|O',
        #          None, None),
        #         ("albedo_var", 'color', 'color lpe:nothruput;noinfinitecheck;noclamp;unoccluded;overwrite;C(U2L)|O',
        #          "variance", None),
        #         ("diffuse", 'color', 'color lpe:C(D[DS]*[LO])|O', None, None),
        #         ("diffuse_mse", 'color', 'color lpe:C(D[DS]*[LO])|O', 'mse', None),
        #         ("specular", 'color', 'color lpe:CS[DS]*[LO]', None, None),
        #         ("specular_mse", 'color', 'color lpe:CS[DS]*[LO]', 'mse', None),
        #         ("z", 'float', 'float z', None, True),
        #         ("z_var", 'float', 'float z', "variance", True),
        #         ("normal", 'normal', 'normal Nn', None, None),
        #         ("normal_var", 'normal', 'normal Nn', "variance", None),
        #         ("forward", 'vector', 'vector motionFore', None, None),
        #         ("backward", 'vector', 'vector motionBack', None, None)
        #     ]

        #     for aov, declare_type, source, statistics, do_filter in denoise_aovs:
        #         params = {}
        #         if source:
        #             params['string source'] = source
        #         if statistics:
        #             params['string statistics'] = statistics
        #         if do_filter:
        #             params['string filter'] = rm.pixelfilter
        #         ri.DisplayChannel('%s %s' % (declare_type, aov), params)

        #     # output denoise_data.exr
        #     image_base, ext = main_display.rsplit('.', 1)
        #     ri.Display('+' + image_base + '.variance.exr', 'openexr',
        #                "Ci,a,mse,albedo,albedo_var,diffuse,diffuse_mse,specular,specular_mse,z,z_var,normal,normal_var,forward,backward",
        #                {"string storage": "tiled"})
