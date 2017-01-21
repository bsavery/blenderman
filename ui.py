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
import math
import blf
from bpy.types import Panel
from .nodes import NODE_LAYOUT_SPLIT, is_renderman_nodetree, panel_node_draw

from . import engine
# global dictionaries
from bl_ui.properties_particle import ParticleButtonsPanel

# helper functions for parameters
from .nodes import draw_nodes_properties_ui, draw_node_properties_recursive

# Use some of the existing buttons.
import bl_ui.properties_render as properties_render
# properties_render.RENDER_PT_render.COMPAT_ENGINES.add('PRMAN_RENDER')
properties_render.RENDER_PT_dimensions.COMPAT_ENGINES.add('PRMAN_RENDER')
properties_render.RENDER_PT_output.COMPAT_ENGINES.add('PRMAN_RENDER')
properties_render.RENDER_PT_post_processing.COMPAT_ENGINES.add('PRMAN_RENDER')
del properties_render

import bl_ui.properties_material as properties_material
properties_material.MATERIAL_PT_context_material.COMPAT_ENGINES.add(
    'PRMAN_RENDER')
# properties_material.MATERIAL_PT_preview.COMPAT_ENGINES.add('PRMAN_RENDER')
properties_material.MATERIAL_PT_custom_props.COMPAT_ENGINES.add('PRMAN_RENDER')
del properties_material

import bl_ui.properties_scene as properties_scene
properties_scene.SCENE_PT_scene.COMPAT_ENGINES.add('PRMAN_RENDER')
properties_scene.SCENE_PT_unit.COMPAT_ENGINES.add('PRMAN_RENDER')
properties_scene.SCENE_PT_physics.COMPAT_ENGINES.add('PRMAN_RENDER')
properties_scene.SCENE_PT_rigid_body_world.COMPAT_ENGINES.add('PRMAN_RENDER')
properties_scene.SCENE_PT_color_management.COMPAT_ENGINES.add('PRMAN_RENDER')
del properties_scene

import bl_ui.properties_data_lamp as properties_data_lamp
properties_data_lamp.DATA_PT_context_lamp.COMPAT_ENGINES.add('PRMAN_RENDER')
properties_data_lamp.DATA_PT_spot.COMPAT_ENGINES.add('PRMAN_RENDER')
del properties_data_lamp

# enable all existing panels for these contexts
import bl_ui.properties_data_mesh as properties_data_mesh
for member in dir(properties_data_mesh):
    subclass = getattr(properties_data_mesh, member)
    try:
        subclass.COMPAT_ENGINES.add('PRMAN_RENDER')
    except:
        pass
del properties_data_mesh

import bl_ui.properties_object as properties_object
for member in dir(properties_object):
    subclass = getattr(properties_object, member)
    try:
        subclass.COMPAT_ENGINES.add('PRMAN_RENDER')
    except:
        pass
del properties_object

import bl_ui.properties_data_mesh as properties_data_mesh
for member in dir(properties_data_mesh):
    subclass = getattr(properties_data_mesh, member)
    try:
        subclass.COMPAT_ENGINES.add('PRMAN_RENDER')
    except:
        pass
del properties_data_mesh

import bl_ui.properties_data_camera as properties_data_camera
for member in dir(properties_data_camera):
    subclass = getattr(properties_data_camera, member)
    try:
        if subclass != properties_data_camera.DATA_PT_camera_dof:
            subclass.COMPAT_ENGINES.add('PRMAN_RENDER')
        pass
    except:
        pass
del properties_data_camera

import bl_ui.properties_particle as properties_particle
for member in dir(properties_particle):
    subclass = getattr(properties_particle, member)
    try:
        subclass.COMPAT_ENGINES.add('PRMAN_RENDER')
    except:
        pass
del properties_particle

import bl_ui.properties_physics_fluid as properties_fluid
for member in dir(properties_fluid):
    subclass = getattr(properties_fluid, member)
    try:
        subclass.COMPAT_ENGINES.add('PRMAN_RENDER')
    except:
        pass
del properties_fluid

# this is here for 2.78
try:
    import bl_ui
    bl_ui.properties_physics_common.PHYSICS_PT_add.COMPAT_ENGINES.add(
        'PRMAN_RENDER')
    import bl_ui.properties_physics_smoke as properties_smoke
    for member in dir(properties_smoke):
        subclass = getattr(properties_smoke, member)
        try:
            subclass.COMPAT_ENGINES.add('PRMAN_RENDER')
        except:
            pass
    del properties_smoke
except:
    pass


# icons
import os
from . icons.icons import load_icons


from bpy.props import PointerProperty, StringProperty, BoolProperty, \
    EnumProperty, IntProperty, FloatProperty, FloatVectorProperty, \
    CollectionProperty

# ------- Subclassed Panel Types -------


class CollectionPanel():
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return rd.engine == 'PRMAN_RENDER'

    def _draw_collection(self, context, layout, ptr, name, operator,
                         opcontext, prop_coll, collection_index, default_name=''):
        layout.label(name)
        row = layout.row()
        row.template_list("UI_UL_list", "PRMAN", ptr, prop_coll, ptr,
                          collection_index, rows=1)
        col = row.column(align=True)

        op = col.operator(operator, icon="ZOOMIN", text="")
        op.context = opcontext
        op.collection = prop_coll
        op.collection_index = collection_index
        op.defaultname = default_name
        op.action = 'ADD'

        op = col.operator(operator, icon="ZOOMOUT", text="")
        op.context = opcontext
        op.collection = prop_coll
        op.collection_index = collection_index
        op.action = 'REMOVE'

        if hasattr(ptr, prop_coll) and len(getattr(ptr, prop_coll)) > 0 and \
                getattr(ptr, collection_index) >= 0:
            item = getattr(ptr, prop_coll)[getattr(ptr, collection_index)]
            self.draw_item(layout, context, item)


# ------- UI panel definitions -------
narrowui = 180


class PRManButtonsPanel():
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return rd.engine == 'PRMAN_RENDER'


class RENDER_PT_renderman_render(PRManButtonsPanel, Panel):
    bl_label = "Render"

    def draw(self, context):
        if context.scene.render.engine != "PRMAN_RENDER":
            return

        icons = load_icons()
        layout = self.layout
        rd = context.scene.render
        rm = context.scene.renderman

        # Render
        row = layout.row(align=True)
        rman_render = icons.get("render")
        row.operator("render.render", text="Render",
                     icon_value=rman_render.icon_id)

        # IPR
        if engine.ipr:
            # Stop IPR
            rman_batch_cancel = icons.get("stop_ipr")
            row.operator('lighting.start_interactive',
                         text="Stop IPR", icon_value=rman_batch_cancel.icon_id)
        else:
            # Start IPR
            rman_rerender_controls = icons.get("start_ipr")
            row.operator('lighting.start_interactive', text="Start IPR",
                         icon_value=rman_rerender_controls.icon_id)

        # Batch Render
        rman_batch = icons.get("batch_render")
        row.operator("render.render", text="Render Animation",
                     icon_value=rman_batch.icon_id).animation = True

        layout.separator()

        split = layout.split(percentage=0.33)

        split.label(text="Display:")
        row = split.row(align=True)
        row.prop(rd, "display_mode", text="")
        row.prop(rd, "use_lock_interface", icon_only=True)
        col = layout.column()
        row = col.row()
        row.prop(rm, "render_into", text="Render To")

        layout.separator()
        col = layout.column()
        col.prop(context.scene.renderman, "render_selected_objects_only")
        col.prop(rm, "do_denoise")


class RENDER_PT_renderman_spooling(PRManButtonsPanel, Panel):
    bl_label = "External Rendering"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rm = scene.renderman

        # note
        row = layout.row()
        row.label(
            'Note:  External Rendering will render outside of Blender, images will not show up in the Image Editor.')

        row = layout.row()
        row.prop(rm, 'enable_external_rendering')
        if not rm.enable_external_rendering:
            return

        # button
        icons = load_icons()
        row = layout.row()
        rman_batch = icons.get("batch_render")
        row.operator("renderman.external_render",
                     text="External Render", icon_value=rman_batch.icon_id)

        layout.separator()

#        row = layout.row()
#        split = row.split(percentage=0.33)
#        col = split.column()
#        col.prop(rm, "external_denoise")
#        sub_row = col.row()
#        sub_row.enabled = rm.external_denoise
#        sub_row.prop(rm, "crossframe_denoise")
#
#        # display driver
#        split = split.split()
#        col = split.column()
        col = layout.column()
        col.prop(rm, "display_driver", text='Render To')

#        sub_row = col.row()
#        if rm.display_driver == 'openexr':
#            sub_row = col.row()
#            sub_row.prop(rm,  "exr_format_options")
#            sub_row = col.row()
#            sub_row.prop(rm,  "exr_compression")

        layout.separator()

        layout.separator()
        split = layout.split(percentage=0.33)
        # do animation
        split.prop(rm, "external_animation")

        sub_row = split.row()
        sub_row.enabled = rm.external_animation
        sub_row.prop(scene, "frame_start", text="Start")
        sub_row.prop(scene, "frame_end", text="End")

        # queue Renders
        layout.separator()
        split = layout.split(percentage=0.33)
        # spool render
        split.prop(rm, "external_action")
        sub_row = split.row()
        sub_row.enabled = rm.external_action == 'spool'
        sub_row.prop(rm, "queuing_system")

        # options
        col = layout.column()
        col.label('Spooling Options:')
        col = layout.column()
        col.prop(rm, 'custom_cmd')
        col.prop(rm, 'custom_alfname')
        col.prop(rm, 'external_denoise')
        row = col.row()
        row.enabled = rm.external_denoise
        row.prop(rm, 'crossframe_denoise')
        row = col.row()
        row.enabled = rm.external_denoise
        row.prop(rm, 'spool_denoise_aov')
        row = col.row()
        row.enabled = rm.external_denoise and not rm.spool_denoise_aov
        row.prop(rm, "denoise_gpu")
        row = col.row()
        row.enabled = rm.external_denoise
        row.prop(rm, 'denoise_cmd')

        # checkpointing
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


def draw_props(node, prop_names, layout):
    for prop_name in prop_names:
        prop_meta = node.prop_meta[prop_name]
        prop = getattr(node, prop_name)
        row = layout.row()

        if prop_meta['renderman_type'] == 'page':
            ui_prop = prop_name + "_ui_open"
            ui_open = getattr(node, ui_prop)
            icon = 'DISCLOSURE_TRI_DOWN' if ui_open \
                else 'DISCLOSURE_TRI_RIGHT'

            split = layout.split(NODE_LAYOUT_SPLIT)
            row = split.row()
            row.prop(node, ui_prop, icon=icon, text='',
                     icon_only=True, emboss=False)
            row.label(prop_name.split('.')[-1] + ':')

            if ui_open:
                draw_props(node, prop, layout)

        else:
            if 'widget' in prop_meta and prop_meta['widget'] == 'null' or \
                    'hidden' in prop_meta and prop_meta['hidden'] or prop_name == 'combineMode':
                continue

            row.label('', icon='BLANK1')
            # indented_label(row, socket.name+':')
            if "Subset" in prop_name and prop_meta['type'] == 'string':
                row.prop_search(node, prop_name, bpy.data.scenes[0].renderman,
                                "object_groups")
            else:
                if 'widget' in prop_meta and prop_meta['widget'] == 'floatRamp':
                    rm = bpy.context.lamp.renderman
                    nt = bpy.context.lamp.node_tree
                    float_node = nt.nodes[rm.float_ramp_node]
                    layout.template_curve_mapping(float_node, 'mapping')
                elif 'widget' in prop_meta and prop_meta['widget'] == 'colorRamp':
                    rm = bpy.context.lamp.renderman
                    nt = bpy.context.lamp.node_tree
                    ramp_node = nt.nodes[rm.color_ramp_node]
                    layout.template_color_ramp(ramp_node, 'color_ramp')
                else:
                    row.prop(node, prop_name)


class RENDER_PT_renderman_sampling(PRManButtonsPanel, Panel):
    bl_label = "Sampling"
    # bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):

        layout = self.layout
        scene = context.scene
        rm = scene.renderman

        # layout.prop(rm, "display_driver")
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


class RENDER_PT_renderman_motion_blur(PRManButtonsPanel, Panel):
    bl_label = "Motion Blur"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        rm = context.scene.renderman

        layout = self.layout
        row = layout.row()
        row.prop(rm, "motion_blur")
        sub = layout.row()
        sub.enabled = rm.motion_blur
        sub.prop(rm, "motion_segments")
        row = layout.row()
        row.enabled = rm.motion_blur
        row.prop(rm, "sample_motion_blur")
        row = layout.row()
        row.enabled = rm.motion_blur
        row.prop(rm, "shutter_timing")
        row = layout.row()
        row.enabled = rm.motion_blur
        row.prop(rm, "shutter_angle")

        row = layout.row()
        row.enabled = rm.motion_blur
        row.prop(rm, "shutter_efficiency_open")
        row.prop(rm, "shutter_efficiency_close")


class RENDER_PT_renderman_sampling_preview(PRManButtonsPanel, Panel):
    bl_label = "Interactive and Preview Sampling"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):

        layout = self.layout
        scene = context.scene
        rm = scene.renderman

        col = layout.column()
        col.prop(rm, "preview_pixel_variance")
        row = col.row(align=True)
        row.prop(rm, "preview_min_samples", text="Min Samples")
        row.prop(rm, "preview_max_samples", text="Max Samples")
        row = col.row(align=True)
        row.prop(rm, "preview_max_specular_depth", text="Specular Depth")
        row.prop(rm, "preview_max_diffuse_depth", text="Diffuse Depth")
        row = col.row(align=True)


class RENDER_PT_renderman_advanced_settings(PRManButtonsPanel, Panel):
    bl_label = "Advanced"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rm = scene.renderman

        layout.separator()

        col = layout.column()
        col.prop(rm, "shadingrate")
        col.prop(rm, "dicing_strategy")
        row = col.row()
        row.enabled = rm.dicing_strategy == "worlddistance"
        row.prop(rm, "worlddistancelength")
        col.prop(rm, "instanceworlddistancelength")

        layout.separator()

        col = layout.column()
        col.prop(rm, "texture_cache_size")
        col.prop(rm, "geo_cache_size")
        col.prop(rm, "opacity_cache_size")

        layout.separator()
        col = layout.column()
        row = col.row()
        row.label("Pixel Filter:")
        row.prop(rm, "pixelfilter", text="")
        row = col.row(align=True)
        row.prop(rm, "pixelfilter_x", text="Size X")
        row.prop(rm, "pixelfilter_y", text="Size Y")

        layout.separator()
        col = layout.column()
        col.prop(rm, "dark_falloff")

        layout.separator()
        col = layout.column()
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
        row = col.row()
        row.operator('rman.open_rib')
        row.prop(rm, "editor_override")
        row = layout.row()
        row.label(text="RIB Format:")
        row.label(text="RIB Compression")
        row = layout.row()
        row.prop(rm, "rib_format", text="")
        row.prop(rm, "rib_compression", text="")

        layout.separator()
        layout.prop(rm, "always_generate_textures")
        layout.prop(rm, "lazy_rib_gen")
        layout.prop(rm, "threads")


class MESH_PT_renderman_prim_vars(CollectionPanel, Panel):
    bl_context = "data"
    bl_label = "Primitive Variables"

    def draw_item(self, layout, context, item):
        ob = context.object
        if context.mesh:
            geo = context.mesh
        layout.prop(item, "name")

        row = layout.row()
        row.prop(item, "data_source", text="Source")
        if item.data_source == 'VERTEX_COLOR':
            row.prop_search(item, "data_name", geo, "vertex_colors", text="")
        elif item.data_source == 'UV_TEXTURE':
            row.prop_search(item, "data_name", geo, "uv_textures", text="")
        elif item.data_source == 'VERTEX_GROUP':
            row.prop_search(item, "data_name", ob, "vertex_groups", text="")

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        if not context.mesh:
            return False
        return rd.engine == 'PRMAN_RENDER'

    def draw(self, context):
        layout = self.layout
        mesh = context.mesh
        rm = mesh.renderman

        self._draw_collection(context, layout, rm, "Primitive Variables:",
                              "collection.add_remove", "mesh", "prim_vars",
                              "prim_vars_index")

        layout.prop(rm, "export_default_uv")
        layout.prop(rm, "export_default_vcol")
        layout.prop(rm, "interp_boundary")
        layout.prop(rm, "face_boundary")


class MATERIAL_PT_renderman_preview(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_options = {'DEFAULT_CLOSED'}
    bl_context = "material"
    bl_label = "Preview"
    COMPAT_ENGINES = {'PRMAN_RENDER'}

    @classmethod
    def poll(cls, context):
        return (context.scene.render.engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout
        mat = context.material
        row = layout.row()
        if mat:
            row.template_preview(context.material, show_buttons=1)
            # if mat.node_tree:
            #    layout.prop_search(
            #        mat, "node_tree", bpy.data, "node_groups")


class ShaderNodePanel():
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = 'Node Panel'

    bl_context = ""
    COMPAT_ENGINES = {'PRMAN_RENDER'}

    @classmethod
    def poll(cls, context):
        if context.scene.render.engine not in cls.COMPAT_ENGINES:
            return False
        if cls.bl_context == 'material':
            if context.material and context.material.node_tree != '':
                return True
        if cls.bl_context == 'data':
            if not context.lamp:
                return False
            if context.lamp.renderman.use_renderman_node:
                return True
        return False


class ShaderPanel():
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    COMPAT_ENGINES = {'PRMAN_RENDER'}

    shader_type = 'surface'
    param_exclude = {}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render

        if cls.bl_context == 'data' and cls.shader_type == 'light':
            return (hasattr(context, "lamp") and context.lamp is not None
                    and rd.engine in {'PRMAN_RENDER'})
        elif cls.bl_context == 'world':
            return (hasattr(context, "world") and context.world is not None and
                    rd.engine in {'PRMAN_RENDER'})
        elif cls.bl_context == 'material':
            return (hasattr(context, "material") and context.material is not None and
                    rd.engine in {'PRMAN_RENDER'})


class MATERIAL_PT_renderman_shader_surface(ShaderPanel, Panel):
    bl_context = "material"
    bl_label = "Bxdf"
    shader_type = 'Bxdf'

    def draw(self, context):
        mat = context.material
        layout = self.layout
        if context.material.renderman and context.material.node_tree:
            nt = context.material.node_tree

            if is_renderman_nodetree(mat):
                panel_node_draw(layout, context, mat,
                                'RendermanOutputNode', 'Bxdf')
                # draw_nodes_properties_ui(
                #    self.layout, context, nt, input_name=self.shader_type)
            else:
                if not panel_node_draw(layout, context, mat, 'ShaderNodeOutputMaterial', 'Surface'):
                    layout.prop(mat, "diffuse_color")
            layout.separator()

        else:
            # if no nodetree we use pxrdisney
            mat = context.material
            rm = mat.renderman

            row = layout.row()
            row.prop(mat, "diffuse_color")

            layout.separator()
        if mat and not is_renderman_nodetree(mat):
            layout.operator(
                'shading.add_renderman_nodetree').idtype = "material"
            layout.operator('shading.convert_cycles_stuff')
        # self._draw_shader_menu_params(layout, context, rm)


class MATERIAL_PT_renderman_shader_light(ShaderPanel, Panel):
    bl_context = "material"
    bl_label = "Light Emission"
    shader_type = 'Light'

    def draw(self, context):
        if context.material.node_tree:
            nt = context.material.node_tree
            draw_nodes_properties_ui(
                self.layout, context, nt, input_name=self.shader_type)


class MATERIAL_PT_renderman_shader_displacement(ShaderPanel, Panel):
    bl_context = "material"
    bl_label = "Displacement"
    shader_type = 'Displacement'

    def draw(self, context):
        if context.material.node_tree:
            nt = context.material.node_tree
            draw_nodes_properties_ui(
                self.layout, context, nt, input_name=self.shader_type)
            # BBM addition begin
        row = self.layout.row()
        row.prop(context.material.renderman, "displacementbound")
        # BBM addition end
        # self._draw_shader_menu_params(layout, context, rm)


class RENDER_PT_layers(PRManButtonsPanel, Panel):
    bl_label = "Layer List"
    bl_context = "render_layer"
    bl_options = {'HIDE_HEADER'}

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        rd = scene.render
        rl = rd.layers.active

        row = layout.row()
        row.template_list("RENDERLAYER_UL_renderlayers", "",
                          rd, "layers", rd.layers, "active_index", rows=2)

        col = row.column(align=True)
        col.operator("scene.render_layer_add", icon='ZOOMIN', text="")
        col.operator("scene.render_layer_remove", icon='ZOOMOUT', text="")

        row = layout.row()
        if rl:
            row.prop(rl, "name")
        row.prop(rd, "use_single_layer", text="", icon_only=True)


class RENDER_PT_layer_options(PRManButtonsPanel, Panel):
    bl_label = "Layer"
    bl_context = "render_layer"

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        rd = scene.render
        rl = rd.layers.active

        split = layout.split()

        col = split.column()
        col.prop(scene, "layers", text="Scene")

        rm = scene.renderman
        rm_rl = None
        active_layer = scene.render.layers.active
        for l in rm.render_layers:
            if l.render_layer == active_layer.name:
                rm_rl = l
                break
        if rm_rl is None:
            return
            # layout.operator('renderman.add_pass_list')
        else:
            split = layout.split()
            col = split.column()
            # cutting this for now until we can export multiple cameras
            #col.prop_search(rm_rl, 'camera', bpy.data, 'cameras')
            col.prop_search(rm_rl, 'light_group',
                            scene.renderman, 'light_groups')
            col.prop_search(rm_rl, 'object_group',
                            scene.renderman, 'object_groups')

            col.prop(rm_rl, 'export_multilayer')
            if rm_rl.export_multilayer:
                col.prop(rm_rl, 'use_deep')
                col.prop(rm_rl,  "exr_format_options")
                col.prop(rm_rl,  "exr_compression")
                col.prop(rm_rl, "exr_storage")


# class RENDER_PT_layer_passes(PRManButtonsPanel, Panel):
#     bl_label = "Passes"
#     bl_context = "render_layer"
#     # bl_options = {'DEFAULT_CLOSED'}

#     def draw(self, context):
#         layout = self.layout

#         scene = context.scene
#         rd = scene.render
#         rl = rd.layers.active
#         rm = rl.renderman

#         layout.prop(rm, "combine_outputs")
#         split = layout.split()

        # col = split.column()
        # col.prop(rl, "use_pass_combined")
        # col.prop(rl, "use_pass_z")
        # col.prop(rl, "use_pass_normal")
        # col.prop(rl, "use_pass_vector")
        # col.prop(rl, "use_pass_uv")
        # col.prop(rl, "use_pass_object_index")
        # #col.prop(rl, "use_pass_shadow")
        # #col.prop(rl, "use_pass_reflection")

        # col = split.column()
        # col.label(text="Diffuse:")
        # row = col.row(align=True)
        # row.prop(rl, "use_pass_diffuse_direct", text="Direct", toggle=True)
        # row.prop(rl, "use_pass_diffuse_indirect", text="Indirect", toggle=True)
        # row.prop(rl, "use_pass_diffuse_color", text="Albedo", toggle=True)
        # col.label(text="Specular:")
        # row = col.row(align=True)
        # row.prop(rl, "use_pass_glossy_direct", text="Direct", toggle=True)
        # row.prop(rl, "use_pass_glossy_indirect", text="Indirect", toggle=True)

        # col.prop(rl, "use_pass_subsurface_indirect", text="Subsurface")
        # col.prop(rl, "use_pass_refraction", text="Refraction")
        # col.prop(rl, "use_pass_emit", text="Emission")

        # layout.separator()
        # row = layout.row()
        # row.label('Holdouts')
        # rm = scene.renderman.holdout_settings
        # layout.prop(rm, 'do_collector_shadow')
        # layout.prop(rm, 'do_collector_reflection')
        # layout.prop(rm, 'do_collector_refraction')
        # layout.prop(rm, 'do_collector_indirectdiffuse')
        # layout.prop(rm, 'do_collector_subsurface')

        # col.prop(rl, "use_pass_ambient_occlusion")


class DATA_PT_renderman_camera(ShaderPanel, Panel):
    bl_context = "data"
    bl_label = "RenderMan Camera"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        if not context.camera:
            return False
        return rd.engine == 'PRMAN_RENDER'

    def draw(self, context):
        layout = self.layout
        cam = context.camera
        scene = context.scene
        dof_options = cam.gpu_dof

        row = layout.row()
        row.prop(scene.renderman, "depth_of_field")
        sub = row.row()
        sub.enabled = scene.renderman.depth_of_field
        sub.prop(cam.renderman, "fstop")

        split = layout.split()

        col = split.column()

        col.label(text="Focus:")
        col.prop(cam, "dof_object", text="")
        sub = col.column()
        sub.active = (cam.dof_object is None)
        sub.prop(cam, "dof_distance", text="Distance")

        col = split.column()
        sub = col.column(align=True)
        sub.label("Aperture Controls:")
        sub.prop(cam.renderman, "dof_aspect",  text="Aspect")
        sub.prop(cam.renderman, "aperture_sides", text="Sides")
        sub.prop(cam.renderman, "aperture_angle", text="Angle")
        sub.prop(cam.renderman, "aperture_roundness", text="Roundness")
        sub.prop(cam.renderman, "aperture_density", text="Density")

        layout.prop(cam.renderman, "projection_type")
        if cam.renderman.projection_type != 'none':
            projection_node = cam.renderman.get_projection_node()
            draw_props(projection_node, projection_node.prop_names, layout)


class DATA_PT_renderman_world(ShaderPanel, Panel):
    bl_context = "world"
    bl_label = "World"
    shader_type = 'world'

    def draw(self, context):
        layout = self.layout
        world = context.scene.world

        if not world.renderman.use_renderman_node:
            layout.prop(world, "horizon_color")
            layout.operator('shading.add_renderman_nodetree').idtype = 'world'
            return
        else:
            layout.prop(world.renderman, "renderman_type", expand=True)
            if world.renderman.renderman_type == 'NONE':
                return
            layout.prop(world.renderman, 'light_primary_visibility')
            lamp_node = world.renderman.get_light_node()
            if lamp_node:
                draw_props(lamp_node, lamp_node.prop_names, layout)


class DATA_PT_renderman_lamp(ShaderPanel, Panel):
    bl_context = "data"
    bl_label = "Lamp"
    shader_type = 'light'

    def draw(self, context):
        layout = self.layout

        lamp = context.lamp
        ipr_running = engine.ipr != None
        if not lamp.renderman.use_renderman_node:
            layout.prop(lamp, "type", expand=True)
            layout.operator('shading.add_renderman_nodetree').idtype = 'lamp'
            layout.operator('shading.convert_cycles_stuff')
            return
        else:
            if ipr_running:
                layout.label(
                    "Note: Some items cannot be edited while IPR running.")
            row = layout.row()
            row.enabled = not ipr_running
            row.prop(lamp.renderman, "renderman_type", expand=True)
            if lamp.renderman.renderman_type == 'FILTER':
                row = layout.row()
                row.enabled = not ipr_running
                row.prop(lamp.renderman, "filter_type", expand=True)
            if lamp.renderman.renderman_type == "AREA":
                row = layout.row()
                row.enabled = not ipr_running
                row.prop(lamp.renderman, "area_shape", expand=True)
                row = layout.row()
                if lamp.renderman.area_shape == "rect":
                    row.prop(lamp, 'size', text="Size X")
                    row.prop(lamp, 'size_y')
                else:
                    row.prop(lamp, 'size', text="Radius")
            #layout.prop(lamp.renderman, "shadingrate")

        #layout.prop_search(lamp.renderman, "nodetree", bpy.data, "node_groups")
        row = layout.row()
        row.enabled = not ipr_running
        row.prop(lamp.renderman, 'illuminates_by_default')


class DATA_PT_renderman_node_shader_lamp(ShaderNodePanel, Panel):
    bl_label = "Light Shader"
    bl_context = 'data'

    def draw(self, context):
        layout = self.layout
        lamp = context.lamp

        lamp_node = lamp.renderman.get_light_node()
        if lamp_node:
            if lamp.renderman.renderman_type != 'FILTER':
                layout.prop(lamp.renderman, 'light_primary_visibility')
            draw_props(lamp_node, lamp_node.prop_names, layout)


class DATA_PT_renderman_display_filters(CollectionPanel, Panel):
    bl_label = "Display Filters"
    bl_context = 'scene'

    def draw_item(self, layout, context, item):
        layout.prop(item, 'filter_type')
        layout.separator()
        filter_node = item.get_filter_node()
        draw_props(filter_node, filter_node.prop_names, layout)

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return rd.engine == 'PRMAN_RENDER'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rm = scene.renderman

        self._draw_collection(context, layout, rm, "Display Filters:",
                              "collection.add_remove", "scene", "display_filters",
                              "display_filters_index")


class DATA_PT_renderman_Sample_filters(CollectionPanel, Panel):
    bl_label = "Sample Filters"
    bl_context = 'scene'

    def draw_item(self, layout, context, item):
        layout.prop(item, 'filter_type')
        layout.separator()
        filter_node = item.get_filter_node()
        draw_props(filter_node, filter_node.prop_names, layout)

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return rd.engine == 'PRMAN_RENDER'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rm = scene.renderman

        self._draw_collection(context, layout, rm, "Sample Filters:",
                              "collection.add_remove", "scene", "sample_filters",
                              "sample_filters_index")


class DATA_PT_renderman_node_filters_lamp(CollectionPanel, Panel):
    bl_label = "Light Filters"
    bl_context = 'data'

    def draw_item(self, layout, context, item):
        layout.prop(item, 'filter_name')

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return rd.engine == 'PRMAN_RENDER' and hasattr(context, "lamp") \
            and context.lamp is not None and hasattr(context.lamp, 'renderman') \
            and context.lamp.renderman.renderman_type != 'FILTER'

    def draw(self, context):
        layout = self.layout
        lamp = context.lamp

        self._draw_collection(context, layout, lamp.renderman, "",
                              "collection.add_remove", "lamp", "light_filters",
                              "light_filters_index")


class OBJECT_PT_renderman_object_geometry(Panel, CollectionPanel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Renderman Geometry"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw_item(self, layout, context, item):
        col = layout.column()
        col.prop(item, "name")
        col.prop(item, "type")

    def draw(self, context):
        layout = self.layout
        ob = context.object
        rm = ob.renderman
        anim = rm.archive_anim_settings

        col = layout.column()
        col.prop(rm, "geometry_source")

        if rm.geometry_source in ('ARCHIVE', 'DELAYED_LOAD_ARCHIVE'):
            col.prop(rm, "path_archive")

            col.prop(anim, "animated_sequence")
            if anim.animated_sequence:
                col.prop(anim, "blender_start")
                row = col.row()
                row.prop(anim, "sequence_in")
                row.prop(anim, "sequence_out")

        elif rm.geometry_source == 'PROCEDURAL_RUN_PROGRAM':
            col.prop(rm, "path_runprogram")
            col.prop(rm, "path_runprogram_args")
        elif rm.geometry_source == 'DYNAMIC_LOAD_DSO':
            col.prop(rm, "path_dso")
            col.prop(rm, "path_dso_initial_data")
        elif rm.geometry_source == 'OPENVDB':
            col.prop(rm, 'path_archive', text='OpenVDB file')
            self._draw_collection(context, layout, rm, "",
                                  "collection.add_remove", "object.renderman",
                                  "openvdb_channels", "openvdb_channel_index")

        if rm.geometry_source in ('DELAYED_LOAD_ARCHIVE',
                                  'PROCEDURAL_RUN_PROGRAM',
                                  'DYNAMIC_LOAD_DSO'):
            col.prop(rm, "procedural_bounds")

            if rm.procedural_bounds == 'MANUAL':
                colf = layout.column_flow()
                colf.prop(rm, "procedural_bounds_min")
                colf.prop(rm, "procedural_bounds_max")

        if rm.geometry_source == 'BLENDER_SCENE_DATA':
            col.prop(rm, "primitive")

            colf = layout.column_flow()

            if rm.primitive in ('CONE', 'DISK'):
                colf.prop(rm, "primitive_height")
            if rm.primitive in ('SPHERE', 'CYLINDER', 'CONE', 'DISK'):
                colf.prop(rm, "primitive_radius")
            if rm.primitive == 'TORUS':
                colf.prop(rm, "primitive_majorradius")
                colf.prop(rm, "primitive_minorradius")
                colf.prop(rm, "primitive_phimin")
                colf.prop(rm, "primitive_phimax")
            if rm.primitive in ('SPHERE', 'CYLINDER', 'CONE', 'TORUS'):
                colf.prop(rm, "primitive_sweepangle")
            if rm.primitive in ('SPHERE', 'CYLINDER'):
                colf.prop(rm, "primitive_zmin")
                colf.prop(rm, "primitive_zmax")
            if rm.primitive == 'POINTS':
                colf.prop(rm, "primitive_point_type")
                colf.prop(rm, "primitive_point_width")

            # col.prop(rm, "export_archive")
            # if rm.export_archive:
            #    col.prop(rm, "export_archive_path")

        rman_archive = load_icons().get("archive_RIB")
        col = layout.column()
        col.operator("export.export_rib_archive",
                     text="Export Object as RIB Archive.", icon_value=rman_archive.icon_id)

        col = layout.column()
        # col.prop(rm, "export_coordsys")

        row = col.row()
        row.prop(rm, "motion_segments_override", text="")
        sub = row.row()
        sub.active = rm.motion_segments_override
        sub.prop(rm, "motion_segments")


class RendermanRibBoxPanel():
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "RIB Box"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return (rd.engine in {'PRMAN_RENDER'})

    def draw_rib_boxes(self, layout, rib_box_names, item):
        rm = item.renderman
        for rib_box in rib_box_names:
            row = layout.row()
            row.prop_search(rm, rib_box, bpy.data, "texts")
            if getattr(item.renderman, rib_box) != '':
                text_name = getattr(item.renderman, rib_box)
                rib_box_string = bpy.data.texts.get(text_name)
                for line in rib_box_string.lines:
                    row = layout.row()
                    row.label(text=line.body)


class OBJECT_PT_renderman_rib_box(RendermanRibBoxPanel, Panel):
    bl_context = "object"
    bl_label = "Object RIB boxes"

    def draw(self, context):
        self.draw_rib_boxes(self.layout, ['pre_object_rib_box', 'post_object_rib_box'],
                            context.object)


class WORLD_PT_renderman_rib_box(RendermanRibBoxPanel, Panel):
    bl_context = "world"
    bl_label = "World RIB box"

    def draw(self, context):
        self.draw_rib_boxes(self.layout, ['world_rib_box'],
                            context.world)


class SCENE_PT_renderman_rib_box(RendermanRibBoxPanel, Panel):
    bl_context = "scene"
    bl_label = "Scene RIB box"

    def draw(self, context):
        self.draw_rib_boxes(self.layout, ['frame_rib_box'],
                            context.scene)


class OBJECT_PT_renderman_object_render(CollectionPanel, Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Shading and Visibility"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw_item(self, layout, context, item):
        ob = context.object
        rm = bpy.data.objects[ob.name].renderman
        ll = rm.light_linking
        index = rm.light_linking_index

        col = layout.column()
        col.prop(item, "group")
        col.prop(item, "mode")

    def draw(self, context):
        layout = self.layout
        ob = context.object
        rm = ob.renderman

        col = layout.column()
        row = col.row()
        row.prop(rm, "visibility_camera", text="Camera")
        row.prop(rm, "visibility_trace_indirect", text="Indirect")
        row = col.row()
        row.prop(rm, "visibility_trace_transmission", text="Transmission")
        row.prop(rm, "matte")

        col.separator()

        col.separator()

        row = col.row()
        row.prop(rm, 'shading_override')

        colgroup = layout.column()
        colgroup.enabled = rm.shading_override
        row = colgroup.row()
        row.prop(rm, "watertight")
        row = colgroup.row()
        row.prop(rm, "shadingrate")
        row = colgroup.row()
        row.prop(rm, "geometric_approx_motion")
        row = colgroup.row()
        row.prop(rm, "geometric_approx_focus")


class OBJECT_PT_renderman_object_raytracing(CollectionPanel, Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Ray Tracing"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw_item(self, layout, context, item):
        col = layout.column()
        col.prop(item, "group")
        col.prop(item, "mode")

    def draw(self, context):
        layout = self.layout
        ob = context.object
        rm = ob.renderman

        col = layout.column()
        row = col.row(align=True)
        row.prop(
            rm, "raytrace_intersectpriority", text="Intersection Priority")
        row.prop(rm, "raytrace_ior")


        col.prop(
            rm, "raytrace_override", text="Override Default Ray Tracing")

        col = layout.column()
        col.active = rm.raytrace_override
        row = col.row()
        row.prop(rm, "raytrace_pixel_variance")
        row = col.row()
        row.prop(rm, "raytrace_maxdiffusedepth", text="Max Diffuse Depth")
        row = col.row()
        row.prop(rm, "raytrace_maxspeculardepth", text="Max Specular Depth")
        row = col.row()
        row.prop(rm, "raytrace_tracedisplacements", text="Trace Displacements")
        row = col.row()
        row.prop(rm, "raytrace_autobias", text="Ray Origin Auto Bias")
        row = col.row()
        row.prop(rm, "raytrace_bias", text="Ray Origin Bias Amount")
        row.active = not rm.raytrace_autobias
        row = col.row()
        row.prop(rm, "raytrace_samplemotion", text="Sample Motion Blur")
        row = col.row()
        row.prop(rm, "raytrace_decimationrate", text="Decimation Rate")

class OBJECT_PT_renderman_object_matteid(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Matte ID"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw(self, context):
        layout = self.layout
        ob = context.object
        rm = ob.renderman

        row = layout.row()
        row.prop(rm, 'MatteID0')
        row = layout.row()
        row.prop(rm, 'MatteID1')
        row = layout.row()
        row.prop(rm, 'MatteID2')
        row = layout.row()
        row.prop(rm, 'MatteID3')
        row = layout.row()
        row.prop(rm, 'MatteID4')
        row = layout.row()
        row.prop(rm, 'MatteID5')
        row = layout.row()
        row.prop(rm, 'MatteID6')
        row = layout.row()
        row.prop(rm, 'MatteID7')

class RENDER_PT_layer_custom_aovs(CollectionPanel, Panel):
    bl_label = "Passes"
    bl_context = "render_layer"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return rd.engine in {'PRMAN_RENDER'}

    def draw_item(self, layout, context, item):
        scene = context.scene
        rm = scene.renderman
        #ll = rm.light_linking
        #row = layout.row()
        #row.prop(item, "layers")
        col = layout.column()
        col.prop(item, "aov_name")
        if item.aov_name == "color custom_lpe":
            col.prop(item, "name")
            col.prop(item, "custom_lpe_string")

        col = layout.column()
        icon = 'DISCLOSURE_TRI_DOWN' if item.show_advanced \
            else 'DISCLOSURE_TRI_RIGHT'

        row = col.row()
        row.prop(item, "show_advanced", icon=icon, text="Advanced",
                 emboss=False)
        if item.show_advanced:
            col.label("Exposure Settings")
            col.prop(item, "exposure_gain")
            col.prop(item, "exposure_gamma")

            col = layout.column()
            col.label("Remap Settings")
            row = col.row(align=True)
            row.prop(item, "remap_a", text="A")
            row.prop(item, "remap_b", text="B")
            row.prop(item, "remap_c", text="C")
            layout.separator()
            row = col.row()
            row.label(text="Quantize Settings:")
            row = col.row(align=True)
            row.prop(item, "quantize_zero")
            row.prop(item, "quantize_one")
            row.prop(item, "quantize_min")
            row.prop(item, "quantize_max")
            row = col.row()
            row.prop(item, "aov_pixelfilter")
            row = col.row()
            if item.aov_pixelfilter != 'default':
                row.prop(item, "aov_pixelfilter_x", text="Size X")
                row.prop(item, "aov_pixelfilter_y", text="Size Y")
            layout.separator()
            row = col.row()
            row.prop(item,  "stats_type")
            layout.separator()

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rm = scene.renderman
        rm_rl = None
        active_layer = scene.render.layers.active
        for l in rm.render_layers:
            if l.render_layer == active_layer.name:
                rm_rl = l
                break
        if rm_rl is None:
            layout.operator('renderman.add_renderman_aovs')
            split = layout.split()
            col = split.column()
            rl = active_layer
            col.prop(rl, "use_pass_combined")
            col.prop(rl, "use_pass_z")
            col.prop(rl, "use_pass_normal")
            col.prop(rl, "use_pass_vector")
            col.prop(rl, "use_pass_uv")
            col.prop(rl, "use_pass_object_index")
            #col.prop(rl, "use_pass_shadow")
            #col.prop(rl, "use_pass_reflection")

            col = split.column()
            col.label(text="Diffuse:")
            row = col.row(align=True)
            row.prop(rl, "use_pass_diffuse_direct", text="Direct", toggle=True)
            row.prop(rl, "use_pass_diffuse_indirect",
                     text="Indirect", toggle=True)
            row.prop(rl, "use_pass_diffuse_color", text="Albedo", toggle=True)
            col.label(text="Specular:")
            row = col.row(align=True)
            row.prop(rl, "use_pass_glossy_direct", text="Direct", toggle=True)
            row.prop(rl, "use_pass_glossy_indirect",
                     text="Indirect", toggle=True)

            col.prop(rl, "use_pass_subsurface_indirect", text="Subsurface")
            col.prop(rl, "use_pass_refraction", text="Refraction")
            col.prop(rl, "use_pass_emit", text="Emission")

            # layout.separator()
            # row = layout.row()
            # row.label('Holdouts')
            # rm = scene.renderman.holdout_settings
            # layout.prop(rm, 'do_collector_shadow')
            # layout.prop(rm, 'do_collector_reflection')
            # layout.prop(rm, 'do_collector_refraction')
            # layout.prop(rm, 'do_collector_indirectdiffuse')
            # layout.prop(rm, 'do_collector_subsurface')

            col.prop(rl, "use_pass_ambient_occlusion")
        else:
            layout.context_pointer_set("pass_list", rm_rl)
            self._draw_collection(context, layout, rm_rl, "",
                                  "collection.add_remove", "pass_list",
                                  "custom_aovs", "custom_aov_index")


class PARTICLE_PT_renderman_particle(ParticleButtonsPanel, Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "particle"
    bl_label = "Render"
    COMPAT_ENGINES = {'PRMAN_RENDER'}

    def draw(self, context):
        layout = self.layout

        # XXX todo: handle strands properly

        psys = context.particle_system
        rm = psys.settings.renderman

        col = layout.column()

        if psys.settings.type == 'EMITTER':
            col.row().prop(rm, "particle_type", expand=True)
            if rm.particle_type == 'OBJECT':
                col.prop_search(rm, "particle_instance_object", bpy.data,
                                "objects", text="")
                col.prop(rm, 'use_object_material')
            elif rm.particle_type == 'GROUP':
                col.prop_search(rm, "particle_instance_object", bpy.data,
                                "groups", text="")

            if rm.particle_type == 'OBJECT' and rm.use_object_material:
                pass
            else:
                col.prop(psys.settings, "material_slot")
            col.row().prop(rm, "constant_width", text="Override Width")
            col.row().prop(rm, "width")

        else:
            col.prop(psys.settings, "material_slot")

        # XXX: if rm.type in ('sphere', 'disc', 'patch'):
        # implement patchaspectratio and patchrotation

        split = layout.split()
        col = split.column()

        if psys.settings.type == 'HAIR':
            row = col.row()
            row.prop(psys.settings.cycles, "root_width", 'Root Width')
            row.prop(psys.settings.cycles, "tip_width", 'Tip Width')
            row = col.row()
            row.prop(psys.settings.cycles, "radius_scale", 'Width Multiplier')

            col.prop(rm, 'export_scalp_st')
            col.prop(rm, 'round_hair')


class PARTICLE_PT_renderman_prim_vars(CollectionPanel, Panel):
    bl_context = "particle"
    bl_label = "Primitive Variables"

    def draw_item(self, layout, context, item):
        ob = context.object
        layout.prop(item, "name")

        row = layout.row()
        row.prop(item, "data_source", text="Source")

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        if not context.particle_system:
            return False
        return rd.engine == 'PRMAN_RENDER'

    def draw(self, context):
        layout = self.layout
        psys = context.particle_system
        rm = psys.settings.renderman

        self._draw_collection(context, layout, rm, "Primitive Variables:",
                              "collection.add_remove",
                              "particle_system.settings",
                              "prim_vars", "prim_vars_index")

        layout.prop(rm, "export_default_size")

# headers to draw the interactive start/stop buttons


class DrawRenderHeaderInfo(bpy.types.Header):
    bl_space_type = "INFO"

    def draw(self, context):
        if context.scene.render.engine != "PRMAN_RENDER":
            return
        layout = self.layout
        icons = load_icons()

        row = layout.row(align=True)
        rman_render = icons.get("render")
        row.operator("render.render", text="Render",
                     icon_value=rman_render.icon_id)
        rman_batch = icons.get("batch_render")
        if context.scene.renderman.enable_external_rendering:
            row.operator("renderman.external_render",
                         text="External Render", icon_value=rman_batch.icon_id)

        if engine.ipr:

            rman_batch_cancel = icons.get("stop_ipr")
            row.operator('lighting.start_interactive',
                         text="Stop IPR", icon_value=rman_batch_cancel.icon_id)

        else:

            rman_rerender_controls = icons.get("start_ipr")
            row.operator('lighting.start_interactive', text="Start IPR",
                         icon_value=rman_rerender_controls.icon_id)

class DrawRenderHeaderNode(bpy.types.Header):
    bl_space_type = "NODE_EDITOR"

    def draw(self, context):
        if context.scene.render.engine != "PRMAN_RENDER":
            return
        layout = self.layout
        
        row = layout.row(align=True)
        
        if hasattr(context.space_data, 'id') and \
            type(context.space_data.id) == bpy.types.Material and \
            not is_renderman_nodetree(context.space_data.id):
            row.operator(
                'shading.add_renderman_nodetree', text="Convert to RenderMan").idtype = "node_editor"

        row.operator('nodes.new_bxdf')

class DrawRenderHeaderImage(bpy.types.Header):
    bl_space_type = "IMAGE_EDITOR"

    def draw(self, context):
        if context.scene.render.engine != "PRMAN_RENDER":
            return
        layout = self.layout
        icons = load_icons()

        row = layout.row(align=True)
        rman_render = icons.get("render")
        row.operator("render.render", text="Render",
                     icon_value=rman_render.icon_id)

        if engine.ipr:

            rman_batch_cancel = icons.get("stop_ipr")
            row.operator('lighting.start_interactive',
                         text="Stop IPR", icon_value=rman_batch_cancel.icon_id)

        else:

            rman_rerender_controls = icons.get("start_ipr")
            row.operator('lighting.start_interactive', text="Start IPR",
                         icon_value=rman_rerender_controls.icon_id)


def PRMan_menu_func(self, context):
    if context.scene.render.engine != "PRMAN_RENDER":
        return
    self.layout.separator()
    if engine.ipr:
        self.layout.operator('lighting.start_interactive',
                             text="PRMan Stop Interactive Rendering")
    else:
        self.layout.operator('lighting.start_interactive',
                             text="PRMan Start Interactive Rendering")


#################
#       Tab     #
#################
class Renderman_Light_Panel(CollectionPanel, Panel):
    #bl_idname = "renderman_light_panel"
    bl_label = "RenderMan Light Groups"
    bl_context = "scene"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'  # bl_category = "Renderman"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return rd.engine == 'PRMAN_RENDER'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rm = scene.renderman
        # if len(rm.light_groups) == 0:
        #    light_group = rm.object_groups.add()
        #    light_group.name = 'All'
        self._draw_collection(context, layout, rm, "",
                              "collection.add_remove",
                              "scene.renderman",
                              "light_groups", "light_groups_index", default_name=str(len(rm.light_groups)))

    def draw_item(self, layout, context, item):
        scene = context.scene
        rm = scene.renderman
        light_group = rm.light_groups[rm.light_groups_index]
        # row.template_list("RENDERMAN_GROUP_UL_List", "Renderman_light_group_list",
        #                    light_group, "members", light_group, 'members_index',
        #                    rows=9, maxrows=100, type='GRID', columns=9)

        row = layout.row()
        add = row.operator('renderman.add_to_group', 'Add Selected to Group')
        add.item_type = 'light'
        add.group_index = rm.light_groups_index

        #row = layout.row()
        remove = row.operator('renderman.remove_from_group',
                              'Remove Selected from Group')
        remove.item_type = 'light'
        remove.group_index = rm.light_groups_index

        light_names = [member.name for member in light_group.members]
        if light_group.name == 'All':
            light_names = [
                lamp.name for lamp in context.scene.objects if lamp.type == 'LAMP']

        if len(light_names) > 0:
            box = layout.box()
            row = box.row()
            columns = box.column_flow(columns=8)
            columns.label('Name')
            columns.label('Solo')
            columns.label('Mute')
            columns.label('Intensity')
            columns.label('Exposure')
            columns.label('Color')
            columns.label('Temperature')

            for light_name in light_names:
                if light_name not in scene.objects:
                    continue
                lamp = scene.objects[light_name].data
                lamp_rm = lamp.renderman
                if lamp_rm.renderman_type == 'FILTER':
                    continue
                row = box.row()
                columns = box.column_flow(columns=8)
                columns.label(light_name)
                columns.prop(lamp_rm, 'solo', text='')
                columns.prop(lamp_rm, 'mute', text='')
                light_shader = lamp.renderman.get_light_node()
                if light_shader:

                    columns.prop(light_shader, 'intensity', text='')
                    columns.prop(light_shader, 'exposure', text='')
                    if light_shader.bl_label == 'PxrEnvDayLight':
                        #columns.label('sun tint')
                        columns.prop(light_shader, 'skyTint', text='')
                        column.label('')
                    else:
                        columns.prop(light_shader, 'lightColor', text='')
                        row = columns.row()
                        row.prop(light_shader, 'enableTemperature', text='')
                        row.prop(light_shader, 'temperature', text='')
                else:
                    columns.label('')
                    columns.label('')
                    columns.prop(lamp, 'energy', text='')
                    columns.prop(lamp, 'color', text='')
                    columns.label('')


class RENDERMAN_LL_LIGHT_list(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        rm = context.scene.renderman
        icon = 'NONE'
        ll_prefix = "lg_%s>%s" % (rm.ll_light_type, item.name)
        label = item.name
        for ll in rm.ll.keys():
            if ll_prefix in ll:
                icon = 'TRIA_RIGHT'
                break

        layout.alignment = 'CENTER'
        layout.label(label, icon=icon)


class RENDERMAN_LL_OBJECT_list(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        rm = context.scene.renderman
        icon = 'NONE'
        light_type = rm.ll_light_type
        lg = bpy.data.lamps if light_type == "light" else rm.light_groups
        ll_prefix = "lg_%s>%s>obj_%s>%s" % (
            light_type, lg[rm.ll_light_index].name, rm.ll_object_type, item.name)

        label = item.name
        if ll_prefix in rm.ll.keys():
            ll = rm.ll[ll_prefix]
            if ll.illuminate == 'DEFAULT':
                icon = 'TRIA_RIGHT'
            elif ll.illuminate == 'ON':
                icon = 'DISCLOSURE_TRI_RIGHT'
            else:
                icon = 'DISCLOSURE_TRI_DOWN'

        layout.alignment = 'CENTER'
        layout.label(label, icon=icon)


class Renderman_Light_Link_Panel(CollectionPanel, Panel):
    #bl_idname = "renderman_light_panel"
    bl_label = "RenderMan Light Linking"
    bl_context = "scene"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'  # bl_category = "Renderman"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return rd.engine == 'PRMAN_RENDER'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rm = scene.renderman
        row = layout.row()

        flow = row.column_flow(columns=3)
        # first colomn select Light
        flow.prop(rm, 'll_light_type')
        flow.prop(rm, 'll_object_type')
        flow.label('')

        # second row the selectors
        row = layout.row()
        flow = row.column_flow(columns=3)
        if rm.ll_light_type == 'light':
            flow.template_list("RENDERMAN_LL_LIGHT_list", "Renderman_light_link_list",
                               bpy.data, "lamps", rm, 'll_light_index')
        else:
            flow.template_list("RENDERMAN_LL_LIGHT_list", "Renderman_light_link_list",
                               rm, "light_groups", rm, 'll_light_index')

        if rm.ll_object_type == 'object':
            flow.template_list("RENDERMAN_LL_OBJECT_list", "Renderman_light_link_list",
                               bpy.data, "objects", rm, 'll_object_index')
        else:
            flow.template_list("RENDERMAN_LL_OBJECT_list", "Renderman_light_link_list",
                               rm, "object_groups", rm, 'll_object_index')

        if rm.ll_light_index == -1 or rm.ll_object_index == -1:
            flow.label("Select light and object")
        else:
            from_name = bpy.data.lamps[rm.ll_light_index] if rm.ll_light_type == 'light' \
                else rm.light_groups[rm.ll_light_index]
            to_name = bpy.data.objects[rm.ll_object_index] if rm.ll_object_type == 'object' \
                else rm.object_groups[rm.ll_object_index]
            ll_name = "lg_%s>%s>obj_%s>%s" % (rm.ll_light_type, from_name.name,
                                              rm.ll_object_type, to_name.name)

            col = flow.column()
            if ll_name in rm.ll:
                col.prop(rm.ll[ll_name], 'illuminate')
                rem = col.operator(
                    'renderman.add_rem_light_link', 'Remove Light Link')
                rem.ll_name = ll_name
                rem.add_remove = "remove"
            else:
                add = col.operator(
                    'renderman.add_rem_light_link', 'Add Light Link')
                add.ll_name = ll_name
                add.add_remove = 'add'


class RENDERMAN_GROUP_UL_List(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        # We could write some code to decide which icon to use here...
        custom_icon = 'OBJECT_DATAMODE'
        # Make sure your code supports all 3 layout types
        layout.alignment = 'CENTER'
        layout.label(item.name, icon=custom_icon)


class Renderman_Object_Panel(CollectionPanel, Panel):
    bl_idname = "renderman_object_groups_panel"
    bl_label = "RenderMan Object Groups"
    bl_context = "scene"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'  # bl_category = "Renderman"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return rd.engine == 'PRMAN_RENDER'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rm = scene.renderman
        # if len(rm.object_groups) == 0:
        #    collector_group = rm.object_groups.add()
        #    collector_group.name = 'collector'

        self._draw_collection(context, layout, rm, "",
                              "collection.add_remove",
                              "scene.renderman",
                              "object_groups", "object_groups_index",
                              default_name=str(len(rm.object_groups)))

    def draw_item(self, layout, context, item):
        row = layout.row()
        scene = context.scene
        rm = scene.renderman
        group = rm.object_groups[rm.object_groups_index]

        row = layout.row()
        row.operator('renderman.add_to_group',
                     'Add Selected to Group').group_index = rm.object_groups_index
        row.operator('renderman.remove_from_group',
                     'Remove Selected from Group').group_index = rm.object_groups_index

        row = layout.row()
        row.template_list("RENDERMAN_GROUP_UL_List", "Renderman_group_list",
                          group, "members", group, 'members_index',
                          item_dyntip_propname='name',
                          type='GRID', columns=3)


class Renderman_UI_Panel(bpy.types.Panel):
    bl_idname = "renderman_ui_panel"
    bl_label = "Renderman "
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Renderman"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return rd.engine == 'PRMAN_RENDER'

    def draw(self, context):
        icons = load_icons()
        layout = self.layout
        scene = context.scene
        rm = scene.renderman

        # save Scene
        #layout.operator("wm.save_mainfile", text="Save Scene", icon='FILE_TICK')

        # layout.separator()

        if context.scene.render.engine != "PRMAN_RENDER":
            return

        # Render
        row = layout.row(align=True)
        rman_render = icons.get("render")
        row.operator("render.render", text="Render",
                     icon_value=rman_render.icon_id)

        row.prop(context.scene, "rm_render", text="",
                 icon='DISCLOSURE_TRI_DOWN' if context.scene.rm_render else 'DISCLOSURE_TRI_RIGHT')

        if context.scene.rm_render:
            scene = context.scene
            rd = scene.render

            box = layout.box()
            row = box.row(align=True)

            # Display Driver
            row.prop(rm, "render_into")

            # presets
            row = box.row(align=True)
            row.label("Sampling Preset:")
            row.menu("presets", text=bpy.types.presets.bl_label)
            row.operator("render.renderman_preset_add", text="", icon='ZOOMIN')
            row.operator("render.renderman_preset_add", text="",
                         icon='ZOOMOUT').remove_active = True

            # denoise and selected row
            row = box.row(align=True)
            row.prop(rm, "do_denoise", text="Denoise")
            row.prop(rm, "render_selected_objects_only",
                     text="Render Selected")

            # animation
            row = box.row(align=True)
            rman_batch = icons.get("batch_render")
            row.operator("render.render", text="Render Animation",
                         icon_value=rman_batch.icon_id).animation = True
            # row = box.row(align=True)
            # rman_batch = icons.get("batch_render")
            # row.operator("render.render",text="Batch Render",icon_value=rman_batch.icon_id).animation=True

            # #Resolution
            # row = box.row(align=True)
            # sub = row.column(align=True)
            # sub.label(text="Resolution:")
            # sub.prop(rd, "resolution_x", text="X")
            # sub.prop(rd, "resolution_y", text="Y")
            # sub.prop(rd, "resolution_percentage", text="")

            # # layout.prop(rm, "display_driver")
            # #Sampling
            # row = box.row(align=True)
            # row.label(text="Sampling:")
            # row = box.row(align=True)
            # col = row.column()
            # col.prop(rm, "pixel_variance")
            # row = col.row(align=True)
            # row.prop(rm, "min_samples", text="Min Samples")
            # row.prop(rm, "max_samples", text="Max Samples")
            # row = col.row(align=True)
            # row.prop(rm, "max_specular_depth", text="Specular Depth")
            # row.prop(rm, "max_diffuse_depth", text="Diffuse Depth")

        # IPR
        if engine.ipr:
            # Stop IPR
            row = layout.row(align=True)
            rman_batch_cancel = icons.get("stop_ipr")
            row.operator('lighting.start_interactive',
                         text="Stop IPR", icon_value=rman_batch_cancel.icon_id)
            row.prop(context.scene, "rm_ipr", text="",
                     icon='DISCLOSURE_TRI_DOWN' if context.scene.rm_ipr else 'DISCLOSURE_TRI_RIGHT')
            if context.scene.rm_ipr:

                scene = context.scene
                rm = scene.renderman

                box = layout.box()
                row = box.row(align=True)

                col = row.column()
                col.prop(rm, "preview_pixel_variance")
                row = col.row(align=True)
                row.prop(rm, "preview_min_samples", text="Min Samples")
                row.prop(rm, "preview_max_samples", text="Max Samples")
                row = col.row(align=True)
                row.prop(rm, "preview_max_specular_depth",
                         text="Specular Depth")
                row.prop(rm, "preview_max_diffuse_depth", text="Diffuse Depth")
                row = col.row(align=True)

        else:
            # Start IPR
            row = layout.row(align=True)
            rman_rerender_controls = icons.get("start_ipr")
            row.operator('lighting.start_interactive', text="Start IPR",
                         icon_value=rman_rerender_controls.icon_id)

            row.prop(context.scene, "rm_ipr", text="",
                     icon='DISCLOSURE_TRI_DOWN' if context.scene.rm_ipr else 'DISCLOSURE_TRI_RIGHT')

            if context.scene.rm_ipr:

                scene = context.scene
                rm = scene.renderman

                # STart IT
                rman_it = icons.get("start_it")
                layout.operator("rman.start_it", text="Start IT",
                                icon_value=rman_it.icon_id)

                # Interactive and Preview Sampling
                box = layout.box()
                row = box.row(align=True)

                col = row.column()
                col.prop(rm, "preview_pixel_variance")
                row = col.row(align=True)
                row.prop(rm, "preview_min_samples", text="Min Samples")
                row.prop(rm, "preview_max_samples", text="Max Samples")
                row = col.row(align=True)
                row.prop(rm, "preview_max_specular_depth",
                         text="Specular Depth")
                row.prop(rm, "preview_max_diffuse_depth", text="Diffuse Depth")
                row = col.row(align=True)

        row = layout.row(align=True)
        rman_batch = icons.get("batch_render")

        if context.scene.renderman.enable_external_rendering:
            row.operator("renderman.external_render",
                         text="External Render", icon_value=rman_batch.icon_id)

            row.prop(context.scene, "rm_render_external", text="",
                     icon='DISCLOSURE_TRI_DOWN' if context.scene.rm_render_external else 'DISCLOSURE_TRI_RIGHT')
            if context.scene.rm_render_external:
                scene = context.scene
                rd = scene.render

                box = layout.box()
                row = box.row(align=True)

                # Display Driver
                row.prop(rm, "display_driver", text='Render into')

                # animation
                row = box.row(align=True)
                row.prop(rm, "external_animation")

                row = box.row(align=True)
                row.enabled = rm.external_animation
                row.prop(scene, "frame_start", text="Start")
                row.prop(scene, "frame_end", text="End")

                # presets
                row = box.row(align=True)
                row.label("Sampling Preset:")
                row.menu("presets")

                # denoise and selected row
                row = box.row(align=True)
                row.prop(rm, "external_denoise", text="Denoise")
                col = row.column()
                col.enabled = rm.external_denoise and rm.external_animation
                col.prop(rm, "crossframe_denoise", text="Crossframe Denoise")

                row = box.row(align=True)
                row.prop(rm, "render_selected_objects_only",
                         text="Render Selected")

                # spool render
                row = box.row(align=True)
                row.prop(rm, "external_action", text='')
                col = row.column()
                col.enabled = rm.external_action == 'spool'
                col.prop(rm, "queuing_system", text='')

        layout.separator()

        # Create Camera
        row = layout.row(align=True)
        row.operator("object.add_prm_camera",
                     text="Add Camera", icon='CAMERA_DATA')

        row.prop(context.scene, "prm_cam", text="",
                 icon='DISCLOSURE_TRI_DOWN' if context.scene.prm_cam else 'DISCLOSURE_TRI_RIGHT')

        if context.scene.prm_cam:
            ob = bpy.context.object
            box = layout.box()
            row = box.row(align=True)
            row.menu("object.camera_list_menu",
                     text="Camera List", icon='CAMERA_DATA')

            if ob.type == 'CAMERA':

                row = box.row(align=True)
                row.prop(ob, "name", text="", icon='LAMP_HEMI')
                row.prop(ob, "hide", text="")
                row.prop(ob, "hide_render",
                         icon='RESTRICT_RENDER_OFF', text="")
                row.operator("object.delete_cameras",
                             text="", icon='PANEL_CLOSE')

                row = box.row(align=True)
                row.scale_x = 2
                row.operator("view3d.object_as_camera", text="", icon='CURSOR')

                row.scale_x = 2
                row.operator("view3d.viewnumpad", text="",
                             icon='VISIBLE_IPO_ON').type = 'CAMERA'

                if context.space_data.lock_camera == False:
                    row.scale_x = 2
                    row.operator("wm.context_toggle", text="",
                                 icon='UNLOCKED').data_path = "space_data.lock_camera"
                elif context.space_data.lock_camera == True:
                    row.scale_x = 2
                    row.operator("wm.context_toggle", text="",
                                 icon='LOCKED').data_path = "space_data.lock_camera"

                row.scale_x = 2
                row.operator("view3d.camera_to_view",
                             text="", icon='MAN_TRANS')

                row = box.row(align=True)
                row.label("Depth Of Field :")

                row = box.row(align=True)
                row.prop(context.object.data, "dof_object", text="")
                row.prop(context.object.data.cycles, "aperture_type", text="")

                row = box.row(align=True)
                row.prop(context.object.data, "dof_distance", text="Distance")

            else:
                row = layout.row(align=True)
                row.label("No Camera Selected")

        layout.separator()

        # Create Env Light
        row = layout.row(align=True)
        rman_RMSEnvLight = icons.get("envlight")
        row.operator("object.mr_add_hemi", text="Add EnvLight",
                     icon_value=rman_RMSEnvLight.icon_id)

        lamps = [obj for obj in bpy.context.scene.objects if obj.type == "LAMP"]

        lamp_hemi = False
        lamp_area = False
        lamp_point = False
        lamp_spot = False
        lamp_sun = False

        if len(lamps):
            for lamp in lamps:
                if lamp.data.type == 'HEMI':
                    lamp_hemi = True

                if lamp.data.type == 'AREA':
                    lamp_area = True

                if lamp.data.type == 'POINT':
                    lamp_point = True

                if lamp.data.type == 'SPOT':
                    lamp_spot = True

                if lamp.data.type == 'SUN':
                    lamp_sun = True

        if lamp_hemi:

            row.prop(context.scene, "rm_env", text="",
                     icon='DISCLOSURE_TRI_DOWN' if context.scene.rm_env else 'DISCLOSURE_TRI_RIGHT')

            if context.scene.rm_env:
                ob = bpy.context.object
                box = layout.box()
                row = box.row(align=True)
                row.menu("object.hemi_list_menu",
                         text="EnvLight List", icon='LAMP_HEMI')

                if ob.type == 'LAMP' and ob.data.type == 'HEMI':

                    row = box.row(align=True)
                    row.prop(ob, "name", text="", icon='LAMP_HEMI')
                    row.prop(ob, "hide", text="")
                    row.prop(ob, "hide_render",
                             icon='RESTRICT_RENDER_OFF', text="")
                    row.operator("object.delete_lights",
                                 text="", icon='PANEL_CLOSE')
                    row = box.row(align=True)
                    row.prop(ob, "rotation_euler", index=2, text="Rotation")

                else:
                    row = layout.row(align=True)
                    row.label("No EnvLight Selected")

        # Create Area Light

        row = layout.row(align=True)
        rman_RMSAreaLight = icons.get("arealight")
        row.operator("object.mr_add_area", text="Add AreaLight",
                     icon_value=rman_RMSAreaLight.icon_id)

        lamps = [obj for obj in bpy.context.scene.objects if obj.type == "LAMP"]

        lamp_hemi = False
        lamp_area = False
        lamp_point = False
        lamp_spot = False
        lamp_sun = False

        if len(lamps):
            for lamp in lamps:
                if lamp.data.type == 'HEMI':
                    lamp_hemi = True

                if lamp.data.type == 'AREA':
                    lamp_area = True

                if lamp.data.type == 'POINT':
                    lamp_point = True

                if lamp.data.type == 'SPOT':
                    lamp_spot = True

                if lamp.data.type == 'SUN':
                    lamp_sun = True

        if lamp_area:

            row.prop(context.scene, "rm_area", text="",
                     icon='DISCLOSURE_TRI_DOWN' if context.scene.rm_area else 'DISCLOSURE_TRI_RIGHT')

            if context.scene.rm_area:
                ob = bpy.context.object
                box = layout.box()
                row = box.row(align=True)
                row.menu("object.area_list_menu",
                         text="AreaLight List", icon='LAMP_AREA')

                if ob.type == 'LAMP' and ob.data.type == 'AREA':

                    row = box.row(align=True)
                    row.prop(ob, "name", text="", icon='LAMP_AREA')
                    row.prop(ob, "hide", text="")
                    row.prop(ob, "hide_render",
                             icon='RESTRICT_RENDER_OFF', text="")
                    row.operator("object.delete_lights",
                                 text="", icon='PANEL_CLOSE')

                else:
                    row = layout.row(align=True)
                    row.label("No AreaLight Selected")

        # Daylight

        row = layout.row(align=True)
        rman_PxrStdEnvDayLight = icons.get("daylight")
        row.operator("object.mr_add_sky", text="Add Daylight",
                     icon_value=rman_PxrStdEnvDayLight.icon_id)

        lamps = [obj for obj in bpy.context.scene.objects if obj.type == "LAMP"]

        lamp_hemi = False
        lamp_area = False
        lamp_point = False
        lamp_spot = False
        lamp_sun = False

        if len(lamps):
            for lamp in lamps:
                if lamp.data.type == 'SUN':
                    lamp_sun = True

                if lamp.data.type == 'HEMI':
                    lamp_hemi = True

                if lamp.data.type == 'AREA':
                    lamp_area = True

                if lamp.data.type == 'POINT':
                    lamp_point = True

                if lamp.data.type == 'SPOT':
                    lamp_spot = True

        if lamp_sun:

            row.prop(context.scene, "rm_daylight", text="",
                     icon='DISCLOSURE_TRI_DOWN' if context.scene.rm_daylight else 'DISCLOSURE_TRI_RIGHT')

            if context.scene.rm_daylight:
                ob = bpy.context.object
                box = layout.box()
                row = box.row(align=True)
                row.menu("object.daylight_list_menu",
                         text="DayLight List", icon='LAMP_SUN')

                if ob.type == 'LAMP' and ob.data.type == 'SUN':

                    row = box.row(align=True)
                    row.prop(ob, "name", text="", icon='LAMP_SUN')
                    row.prop(ob, "hide", text="")
                    row.prop(ob, "hide_render",
                             icon='RESTRICT_RENDER_OFF', text="")
                    row.operator("object.delete_lights",
                                 text="", icon='PANEL_CLOSE')

                else:
                    row = layout.row(align=True)
                    row.label("No DayLight Selected")

        # Dynamic Binding Editor

        # Create Holdout

        # Open Linking Panel
        #row = layout.row(align=True)
        # row.operator("renderman.lighting_panel")

        selected_objects = []
        if context.selected_objects:
            for obj in context.selected_objects:
                if obj.type not in ['CAMERA', 'LAMP', 'SPEAKER']:
                    selected_objects.append(obj)

        if selected_objects:
            layout.separator()
            layout.label("Seleced Objects:")
            box = layout.box()

            # Create PxrLM Material
            render_PxrDisney = icons.get("pxrdisney")
            box.operator_menu_enum(
                "object.add_bxdf", 'bxdf_name', text="Add New Material", icon='MATERIAL')

            # Make Selected Geo Emissive∂
            rman_RMSGeoAreaLight = icons.get("geoarealight")
            box.operator("object.addgeoarealight", text="Make Emissive",
                         icon_value=rman_RMSGeoAreaLight.icon_id)

            # Add Subdiv Sheme
            rman_subdiv = icons.get("add_subdiv_sheme")
            box.operator("object.add_subdiv_sheme",
                         text="Make Subdiv", icon_value=rman_subdiv.icon_id)

            # Add/Create RIB Box /
            # Create Archive node
            rman_archive = icons.get("archive_RIB")
            box.operator("export.export_rib_archive",
                         icon_value=rman_archive.icon_id)
        # Create Geo LightBlocker

        # Update Archive !! Not needed with current system.

        # Open Last RIB
#        rman_open_last_rib = icons.get("open_last_rib")
#        layout.prop(rm, "path_rib_output",icon_value=rman_open_last_rib.icon_id)

        # Inspect RIB Selection

        # Shared Geometry Attribute

        # Add/Atach Coordsys

        # Open Tmake Window  ?? Run Tmake on everything.

        # Create OpenVDB Visualizer
        layout.separator()
        # Renderman Doc
        rman_help = icons.get("help")
        layout.operator("wm.url_open", text="Renderman Docs",
                        icon_value=rman_help.icon_id).url = "https://github.com/bsavery/PRMan-for-Blender/wiki/Documentation-Home"
        rman_info = icons.get("info")
        layout.operator("wm.url_open", text="About Renderman",
                        icon_value=rman_info.icon_id).url = "http://renderman.pixar.com/view/non-commercial-renderman"

        # Reload the addon
        #rman_reload = icons.get("reload_plugin")
        #layout.operator("renderman.restartaddon", icon_value=rman_reload.icon_id)

        # Enable the menu item to display the examples menu in the Renderman
        # Pannel.
        layout.separator()
        layout.menu("examples", icon_value=rman_help.icon_id)


def register():
    bpy.utils.register_class(RENDERMAN_GROUP_UL_List)
    bpy.utils.register_class(RENDERMAN_LL_LIGHT_list)
    bpy.utils.register_class(RENDERMAN_LL_OBJECT_list)
    # bpy.utils.register_class(RENDERMAN_OUTPUT_list)
    # bpy.utils.register_class(RENDERMAN_CHANNEL_list)
    bpy.types.INFO_MT_render.append(PRMan_menu_func)


def unregister():
    bpy.utils.unregister_class(RENDERMAN_GROUP_UL_List)
    bpy.utils.unregister_class(RENDERMAN_LL_LIGHT_list)
    bpy.utils.unregister_class(RENDERMAN_LL_OBJECT_list)
    # bpy.utils.register_class(RENDERMAN_OUTPUT_list)
    # bpy.utils.register_class(RENDERMAN_CHANNEL_list)
    bpy.types.INFO_MT_render.remove(PRMan_menu_func)
