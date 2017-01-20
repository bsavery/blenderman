import bpy
from .base_classes import PRManPanel
from ..resources.icons.icons import load_icons

'''This file defines the panels that appear in the Render ui tab'''


class RENDER_PT_renderman_motion_blur(PRManPanel):
    '''This panel covers the settings for Renderman's motion blur'''
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


class RENDER_PT_renderman_advanced_settings(PRManPanel):
    '''This panel covers additional render settings

    # shading and tessellation
    # geometry caches
    # pixel filter
    # render tiled order
    # additional options (statistics, rib and texture generation caching,
    thread settings)'''
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
        row.operator('rman.open_stats')
        col.operator('rman.open_rib')
        row = col.row()
        col.prop(rm, "always_generate_textures")
        col.prop(rm, "lazy_rib_gen")
        col.prop(rm, "threads")
