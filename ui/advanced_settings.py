import bpy
from .base_classes import PRManPanel
from ..resources.icons.icons import load_icons

# Panel for advanced render settings


class RENDER_PT_renderman_advanced_settings(PRManPanel):
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

        # layout.separator()
        # col = layout.column()
        # col.prop(rm, "dark_falloff")

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
