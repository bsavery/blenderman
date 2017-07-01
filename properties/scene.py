import os.path
from .base_classes import RendermanBasePropertyGroup
import bpy
from bpy.props import *
from .rib_helpers import *
from ..util.util import path_list_convert, args_files_in_path
from bpy.props import PointerProperty, StringProperty, BoolProperty, \
    EnumProperty, IntProperty, FloatProperty, FloatVectorProperty, \
    CollectionProperty, BoolVectorProperty
from .render_layer import RendermanRenderLayerSettings
from ..ui.base_classes import PRManPanel
from bpy.types import Panel
from ..resources.icons.icons import load_icons


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

    # display settings
    render_into = EnumProperty(
        name="Render to",
        description="Render to blender or external framebuffer",
        items=[('socket', 'Blender', 'Render to the Image Editor'),
               ('it', 'it', 'External framebuffer display (must have RMS installed)')],
        default='socket')

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

    # render layers (since we can't save them on the layer themselves)
    render_layers = CollectionProperty(type=RendermanRenderLayerSettings,
                                       name='Custom AOVs')

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
        ri.Integrator("PxrDefault", 'inter', {})
        ri.Hider("raytrace", {'int minsamples': 128,
                              'int maxsamples': 128, 'int incremental': 1})
        ri.Format(960, 540, 1)

        # self.export_render_settings(ri)
        self.export_camera(ri, **kwargs)
        # export_default_bxdf(ri, "default")
        # export_materials_archive(ri, rpass, scene)

        # each render layer gets it's own display and world rib
        for render_layer in scene.render.layers:
            self.export_displays_for_layer(ri, render_layer, **kwargs)
            # self.export_render_layer_camera(ri, render_layer, **kwargs)
            ri.WorldBegin()
            # if scene.world:
            #    scene.world.renderman.to_rib(ri, **kwargs)

            kwargs['render_layer'] = render_layer
            for ob in scene.objects:
                if not ob.parent:
                    ob.renderman.to_rib(ri, **kwargs)

            ri.WorldEnd()

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

    def export_camera(self, ri, **kwargs):
        ''' exports the camera for the scene '''
        scene = self.id_data
        camera_name = kwargs.get('camera', None)
        camera = scene.objects[camera_name] if camera_name else scene.camera

        camera.renderman.export_camera_matrix(ri)
        ri.Camera(camera.name, {})

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

    def export_displays_for_layer(self, ri, render_layer, **kwargs):
        rm_rl = self.render_layers.get(render_layer.name, None)
        is_interactive = kwargs.get('is_interactive', False)
        scene = self.id_data
        # there's no render layer settins
        if not rm_rl or is_interactive or is_preview:
            RendermanRenderLayerSettings.simple_to_rib(
                ri, render_layer, **kwargs)

        # else we have custom rman render layer settings
        else:
            rm_rl.to_rib(ri)


class RENDER_PT_renderman_render(PRManPanel, Panel):
    '''This panel covers the settings for Renderman's motion blur'''
    bl_context = "render"
    bl_label = "Render"

    def draw(self, context):
        # icons = load_icons()
        layout = self.layout
        rd = context.scene.render
        rm = context.scene.renderman

        # # Render
        # row = layout.row(align=True)
        # rman_render = icons.get("render")
        # row.operator("render.render", text="Render",
        #              icon_value=rman_render.icon_id)

        # # IPR
        # if engine.ipr:
        #     # Stop IPR
        #     rman_batch_cancel = icons.get("stop_ipr")
        #     row.operator('lighting.start_interactive',
        #                  text="Stop IPR", icon_value=rman_batch_cancel.icon_id)
        # else:
        #     # Start IPR
        #     rman_rerender_controls = icons.get("start_ipr")
        #     row.operator('lighting.start_interactive', text="Start IPR",
        #                  icon_value=rman_rerender_controls.icon_id)

        # # Batch Render
        # rman_batch = icons.get("batch_render")
        # row.operator("render.render", text="Render Animation",
        #              icon_value=rman_batch.icon_id).animation = True

        # layout.separator()

        split = layout.split(percentage=0.33)

        split.label(text="Display:")
        row = split.row(align=True)
        row.prop(rd, "display_mode", text="")
        row.prop(rd, "use_lock_interface", icon_only=True)
        col = layout.column()
        row = col.row()
        row.prop(rm, "render_into", text="Render To")

        # layout.separator()
        # col = layout.column()
        # col.prop(context.scene.renderman, "render_selected_objects_only")
        # col.prop(rm, "do_denoise")


class RENDER_PT_renderman_sampling(PRManPanel, Panel):
    bl_label = "Sampling"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):

        layout = self.layout
        scene = context.scene
        rm = scene.renderman
        col = layout.column()
        row = col.row(align=True)
        row.menu("presets", text=bpy.types.presets.bl_label)
        row.operator("render.renderman_preset_add", text="", icon='ZOOMIN')
        row.operator("render.renderman_preset_add", text="",
                     icon='ZOOMOUT').remove_active = True
        col.prop(rm, "pixel_variance")
        row = col.row(align=True)
        row.prop(rm, "min_samples", text="Min Samples")
        row.prop(rm, "max_samples", text="Max Samples")
        row = col.row(align=True)
        row.prop(rm, "max_specular_depth", text="Specular Depth")
        row.prop(rm, "max_diffuse_depth", text="Diffuse Depth")
        row = col.row(align=True)
        row.prop(rm, 'incremental')
        row = col.row(align=True)
        layout.separator()
        col.prop(rm, "integrator")
        # find args for integrators here!
        integrator_settings = getattr(rm, "%s_settings" % rm.integrator)

        icon = 'DISCLOSURE_TRI_DOWN' if rm.show_integrator_settings \
            else 'DISCLOSURE_TRI_RIGHT'
        text = rm.integrator + " Settings:"

        row = col.row()
        row.prop(rm, "show_integrator_settings", icon=icon, text=text,
                 emboss=False)
        if rm.show_integrator_settings:
            draw_props(integrator_settings,
                       integrator_settings.prop_names, col)


class RENDER_PT_renderman_spooling(PRManPanel, Panel):

    '''this panel covers the options for spooling a render to an external queue manager'''
    bl_context = "render"
    bl_label = "External Rendering"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rm = scene.renderman

        # if external rendering is disabled, the panel will not appear
        row = layout.row()
        row.label(
            'Note:  External Rendering will render outside of Blender, images will not show up in the Image Editor.')

        row = layout.row()
        row.prop(rm, 'enable_external_rendering')
        if not rm.enable_external_rendering:
            return
        icons = load_icons()
        row = layout.row()
        rman_batch = icons.get("batch_render")
        row.operator("renderman.external_render",
                     text="Export", icon_value=rman_batch.icon_id)

        layout.separator()
        col = layout.column()
        col.prop(rm, "display_driver", text='Render To')

        layout.separator()
        split = layout.split(percentage=0.33)
        # do animation
        split.prop(rm, "external_animation")

        sub_row = split.row()
        sub_row.enabled = rm.external_animation
        sub_row.prop(scene, "frame_start", text="Start")
        sub_row.prop(scene, "frame_end", text="End")
        col = layout.column()
        col.enabled = rm.generate_alf
        col.prop(rm, 'external_denoise')
        row = col.row()
        row.enabled = rm.external_denoise and rm.external_animation
        row.prop(rm, 'crossframe_denoise')

        # render steps
        layout.separator()
        col = layout.column()
        icon_export = 'DISCLOSURE_TRI_DOWN' if rm.export_options else 'DISCLOSURE_TRI_RIGHT'
        col.prop(rm, "export_options", icon=icon_export,
                 text="Export Options:", emboss=False)
        if rm.export_options:
            col.prop(rm, "generate_rib")
            row = col.row()
            row.enabled = rm.generate_rib
            row.prop(rm, "generate_object_rib")
            col.prop(rm, "generate_alf")
            split = col.split(percentage=0.33)
            split.enabled = rm.generate_alf and rm.generate_render
            split.prop(rm, "do_render")
            sub_row = split.row()
            sub_row.enabled = rm.do_render and rm.generate_alf and rm.generate_render
            sub_row.prop(rm, "queuing_system")

        # options
        layout.separator()
        if rm.generate_alf:
            icon_alf = 'DISCLOSURE_TRI_DOWN' if rm.alf_options else 'DISCLOSURE_TRI_RIGHT'
            col = layout.column()
            col.prop(rm, "alf_options", icon=icon_alf, text="ALF Options:",
                     emboss=False)
            if rm.alf_options:
                col.prop(rm, 'custom_alfname')
                col.prop(rm, "convert_textures")
                col.prop(rm, "generate_render")
                row = col.row()
                row.enabled = rm.generate_render
                row.prop(rm, 'custom_cmd')
                split = col.split(percentage=0.33)
                split.enabled = rm.generate_render
                split.prop(rm, "override_threads")
                sub_row = split.row()
                sub_row.enabled = rm.override_threads
                sub_row.prop(rm, "external_threads")

                row = col.row()
                row.enabled = rm.external_denoise
                row.prop(rm, 'denoise_cmd')
                row = col.row()
                row.enabled = rm.external_denoise
                row.prop(rm, 'spool_denoise_aov')
                row = col.row()
                row.enabled = rm.external_denoise and not rm.spool_denoise_aov
                row.prop(rm, "denoise_gpu")

                col = layout.column()
                col.enabled = rm.generate_render
                row = col.row()
                row.prop(rm, 'recover')
                row = col.row()
                row.prop(rm, 'enable_checkpoint')
                row = col.row()
                row.enabled = rm.enable_checkpoint
                row.prop(rm, 'asfinal')
                row = col.row()
                row.enabled = rm.enable_checkpoint
                row.prop(rm, 'checkpoint_type')
                row = col.row(align=True)
                row.enabled = rm.enable_checkpoint
                row.prop(rm, 'checkpoint_interval')
                row.prop(rm, 'render_limit')


class RENDER_PT_renderman_baking(PRManPanel, Panel):

    '''this panel covers the baking option for exporting pattern networks as textures'''
    bl_context = "render"
    bl_label = "Baking"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        icons = load_icons()
        rman_batch = icons.get("batch_render")
        row.operator("renderman.bake", text="Bake",
                     icon_value=rman_batch.icon_id)


class RENDER_PT_renderman_motion_blur(PRManPanel, Panel):
    '''This panel covers the settings for Renderman's motion blur'''
    bl_context = "render"
    bl_label = "Motion Blur"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        rm = context.scene.renderman

        icon = 'DISCLOSURE_TRI_DOWN' if rm.advanced_timing else 'DISCLOSURE_TRI_RIGHT'

        layout = self.layout
        col = layout.column()
        col.prop(rm, "motion_blur")
        col = layout.column()
        col.enabled = rm.motion_blur
        col.prop(rm, "sample_motion_blur")
        col.prop(rm, "motion_segments")
        col.prop(rm, "shutter_timing")
        col.prop(rm, "shutter_angle")
        row = col.row(align=True)
        row.prop(rm, "shutter_efficiency_open")
        row.prop(rm, "shutter_efficiency_close")
        layout.separator()
        col = layout.column()
        col.prop(item, "show_advanced", icon=icon,
                 text="Advanced Shutter Timing", icon_only=True, emboss=False)
        if rm.advanced_timing:
            row = col.row(align=True)
            row.prop(rm, "c1")
            row.prop(rm, "c2")
            row.prop(rm, "d1")
            row.prop(rm, "d2")
            row = col.row(align=True)
            row.prop(rm, "e1")
            row.prop(rm, "e2")
            row.prop(rm, "f1")
            row.prop(rm, "f2")


class RENDER_PT_renderman_advanced_settings(PRManPanel, Panel):
    '''This panel covers additional render settings

    # shading and tessellation
    # geometry caches
    # pixel filter
    # render tiled order
    # additional options (statistics, rib and texture generation caching,
    thread settings)'''
    bl_context = "render"
    bl_label = "Advanced"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rm = scene.renderman

        layout.separator()

        col = layout.column()
        col.label("Shading and Tessellation:")
        col.prop(rm, "micropoly_length")
        col.prop(rm, "dicing_strategy")
        row = col.row()
        row.enabled = rm.dicing_strategy == "worlddistance"
        row.prop(rm, "worlddistancelength")
        col.prop(rm, "instanceworlddistancelength")

        layout.separator()

        col = layout.column()
        col.label("Cache Settings:")
        col.prop(rm, "texture_cache_size")
        col.prop(rm, "geo_cache_size")
        col.prop(rm, "opacity_cache_size")
        layout.separator()
        col = layout.column()
        col.label("Pixel Filter:")
        col.prop(rm, "pixelfilter")
        row = col.row(align=True)
        row.prop(rm, "pixelfilter_x", text="Size X")
        row.prop(rm, "pixelfilter_y", text="Size Y")
        layout.separator()
        col = layout.column()
        col.label("Bucket Order:")
        col.prop(rm, "bucket_shape")
        if rm.bucket_shape == 'SPIRAL':
            row = col.row(align=True)
            row.prop(rm, "bucket_sprial_x", text="X")
            row.prop(rm, "bucket_sprial_y", text="Y")
        layout.separator()
        col = layout.column()
        row = col.row()
        row.prop(rm, "use_statistics", text="Output stats")
        col.operator('rman.open_rib')
        row = col.row()
        col.prop(rm, "always_generate_textures")
        col.prop(rm, "lazy_rib_gen")
        col.prop(rm, "threads")
