import bpy
from .base_classes import PRManPanel
from ..resources.icons.icons import load_icons

# Panel for motion blur settings


class RENDER_PT_renderman_motion_blur(PRManPanel):
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
