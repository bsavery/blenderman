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
from .nodes import NODE_LAYOUT_SPLIT

from . import engine
# global dictionaries
from .shader_parameters import exclude_lamp_params
from bl_ui.properties_particle import ParticleButtonsPanel

# helper functions for parameters
from .shader_parameters import tex_optimised_path
from .shader_parameters import tex_source_path
from .nodes import draw_nodes_properties_ui, draw_node_properties_recursive

# Use some of the existing buttons.
import bl_ui.properties_render as properties_render
properties_render.RENDER_PT_render.COMPAT_ENGINES.add('PRMAN_RENDER')
properties_render.RENDER_PT_dimensions.COMPAT_ENGINES.add('PRMAN_RENDER')
# properties_render.RENDER_PT_output.COMPAT_ENGINES.add('PRMAN_RENDER')
properties_render.RENDER_PT_post_processing.COMPAT_ENGINES.add('PRMAN_RENDER')
del properties_render

import bl_ui.properties_material as properties_material
properties_material.MATERIAL_PT_context_material.COMPAT_ENGINES.add(
    'PRMAN_RENDER')
# properties_material.MATERIAL_PT_preview.COMPAT_ENGINES.add('PRMAN_RENDER')
properties_material.MATERIAL_PT_custom_props.COMPAT_ENGINES.add('PRMAN_RENDER')
del properties_material

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
        subclass.COMPAT_ENGINES.add('PRMAN_RENDER')
    except:
        pass
del properties_data_camera

import bl_ui.properties_particle as properties_particle
for member in dir(properties_particle):
    if member == 'PARTICLE_PT_render':
        continue

    subclass = getattr(properties_particle, member)
    try:
        subclass.COMPAT_ENGINES.add('PRMAN_RENDER')
    except:
        pass
del properties_particle

# ------- Subclassed Panel Types -------


class CollectionPanel():
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return rd.engine == 'PRMAN_RENDER'

    def _draw_collection(self, context, layout, ptr, name, operator,
                         opcontext, prop_coll, collection_index):
        layout.label(name)
        row = layout.row()
        row.template_list("UI_UL_list", "PRMAN", ptr, prop_coll, ptr,
                          collection_index, rows=1)
        col = row.column(align=True)

        op = col.operator(operator, icon="ZOOMIN", text="")
        op.context = opcontext
        op.collection = prop_coll
        op.collection_index = collection_index
        op.defaultname = ''
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


class InlineRibPanel(CollectionPanel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_label = "Inline RIB"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_item(self, layout, context, item):
        layout.prop_search(item, "name", bpy.data, "texts")


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


class RENDER_PT_renderman_output(PRManButtonsPanel, Panel):
    bl_label = "Output"
    # bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rm = scene.renderman

        layout.prop(rm, "display_driver")
        layout.prop(rm, "path_display_driver_image")
        # if rm.display_driver in ['tiff', 'openexr']:
        #    layout.prop(rm, "combine_aovs")
        layout.prop(rm, "do_denoise")


class RENDER_PT_renderman_sampling(PRManButtonsPanel, Panel):
    bl_label = "Sampling"
    # bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):

        layout = self.layout
        scene = context.scene
        rm = scene.renderman

        # layout.prop(rm, "display_driver")
        col = layout.column()
        col.prop(rm, "pixel_variance")
        row = col.row(align=True)
        row.prop(rm, "min_samples", text="Min Samples")
        row.prop(rm, "max_samples", text="Max Samples")
        row = col.row(align=True)
        row.prop(rm, "max_specular_depth", text="Specular Depth")
        row.prop(rm, "max_diffuse_depth", text="Diffuse Depth")
        row = col.row(align=True)
        layout.separator()
        col.prop(rm, "integrator")
        # find args for integrators here!
        integrator_settings = getattr(rm, "%s_settings" % rm.integrator)

        # for each property add it to ui
        def draw_props(prop_names, layout):
            for prop_name in prop_names:
                prop_meta = integrator_settings.prop_meta[prop_name]
                prop = getattr(integrator_settings, prop_name)
                row = layout.row()

                if prop_meta['renderman_type'] == 'page':
                    ui_prop = prop_name + "_ui_open"
                    ui_open = getattr(integrator_settings, ui_prop)
                    icon = 'TRIA_DOWN' if ui_open \
                        else 'TRIA_RIGHT'

                    split = layout.split(NODE_LAYOUT_SPLIT)
                    row = split.row()
                    row.prop(integrator_settings, ui_prop, icon=icon, text=text,
                             icon_only=True, emboss=True)
                    row.label(prop_name + ':')

                    if ui_open:
                        draw_props(prop, layout)

                else:
                    row.label('', icon='BLANK1')
                    # indented_label(row, socket.name+':')
                    row.prop(integrator_settings, prop_name)

        icon = 'TRIA_DOWN' if rm.show_integrator_settings \
            else 'TRIA_RIGHT'
        text = rm.integrator + " Settings:"

        row = col.row()
        row.prop(rm, "show_integrator_settings", icon=icon, text=text,
                 icon_only=True, emboss=False)
        if rm.show_integrator_settings:
            draw_props(integrator_settings.prop_names, col)


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
        row.prop(rm, "shutter_open")
        row.prop(rm, "shutter_close")

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

        row = layout.row()
        row.prop(rm, "shadingrate")

        layout.separator()
        
        row = layout.row()
        row.label("Pixel Filter:")
        row.prop(rm, "pixelfilter", text="")
        row = layout.row()
        row.prop(rm, "pixelfilter_x", text="Size X")
        row.prop(rm, "pixelfilter_y", text="Size Y")

        layout.separator()
        row = layout.row()
        row.prop(rm, 'light_localization')

        layout.separator()
        row = layout.row()
        row.prop(rm, "bucket_shape")
        if rm.bucket_shape == 'SPIRAL':
            row = layout.row(align=True)
            row.prop(rm, "bucket_sprial_x", text="X")
            row.prop(rm, "bucket_sprial_y", text="Y")

        layout.separator()
        layout.prop(rm, "output_action")
        layout.prop(rm, "path_rib_output")
        row = layout.row()
        row.prop(rm, "use_statistics", text="Output stats")
        row.operator('rman.open_stats')

        layout.separator()
        row = layout.row()
        row.operator('rman.open_rib')
        row.prop(rm, "editor_override")
        
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
        layout.prop(rm, "export_smooth_normals")


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
            if mat.renderman.nodetree != '':
                layout.prop_search(
                    mat.renderman, "nodetree", bpy.data, "node_groups")


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
            if context.material and context.material.renderman.nodetree != '':
                return True
        if cls.bl_context == 'data':
            if not context.lamp:
                return False
            if context.lamp.renderman.nodetree != '':
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
        if context.material.renderman and context.material.renderman.nodetree:
            nt = bpy.data.node_groups[context.material.renderman.nodetree]
            draw_nodes_properties_ui(
                self.layout, context, nt, input_name=self.shader_type)
        else:
            # if no nodetree we use pxrdisney
            layout = self.layout
            mat = context.material
            rm = mat.renderman

            row = layout.row()
            row.prop(mat, "diffuse_color")

            layout.separator()
        if mat and mat.renderman.nodetree == '':
            layout.operator(
                'shading.add_renderman_nodetree').idtype = "material"
        # self._draw_shader_menu_params(layout, context, rm)


class MATERIAL_PT_renderman_shader_light(ShaderPanel, Panel):
    bl_context = "material"
    bl_label = "Light Emission"
    shader_type = 'Light'

    def draw(self, context):
        if context.material.renderman.nodetree:
            nt = bpy.data.node_groups[context.material.renderman.nodetree]
            draw_nodes_properties_ui(
                self.layout, context, nt, input_name=self.shader_type)


class MATERIAL_PT_renderman_shader_displacement(ShaderPanel, Panel):
    bl_context = "material"
    bl_label = "Displacement"
    shader_type = 'Displacement'

    def draw(self, context):
        if context.material.renderman.nodetree != "":
            nt = bpy.data.node_groups[context.material.renderman.nodetree]
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
        col.prop(rl, "layers_exclude", text="Exclude")

        col = split.column()
        col.prop(rl, "layers", text="Layer")
        col.prop(rl, "layers_zmask", text="Mask Layer")

        split = layout.split()

        col = split.column()
        col.label(text="Material:")
        col.prop(rl, "material_override", text="")
        col.separator()
        col.prop(rl, "samples")

        col = split.column()


class RENDER_PT_layer_passes(PRManButtonsPanel, Panel):
    bl_label = "Passes"
    bl_context = "render_layer"
    # bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        rd = scene.render
        rl = rd.layers.active

        split = layout.split()

        col = split.column()
        col.prop(rl, "use_pass_combined")
        col.prop(rl, "use_pass_z")
        col.prop(rl, "use_pass_normal")
        col.prop(rl, "use_pass_vector")
        col.prop(rl, "use_pass_uv")
        col.prop(rl, "use_pass_object_index")
        # col.prop(rl, "use_pass_shadow")
        # col.prop(rl, "use_pass_reflection")

        col = split.column()
        col.label(text="Diffuse:")
        row = col.row(align=True)
        row.prop(rl, "use_pass_diffuse_direct", text="Direct", toggle=True)
        row.prop(rl, "use_pass_diffuse_indirect", text="Indirect", toggle=True)
        row.prop(rl, "use_pass_diffuse_color", text="Albedo", toggle=True)
        col.label(text="Specular:")
        row = col.row(align=True)
        row.prop(rl, "use_pass_glossy_direct", text="Direct", toggle=True)
        row.prop(rl, "use_pass_glossy_indirect", text="Indirect", toggle=True)

        col.prop(rl, "use_pass_subsurface_indirect", text="Subsurface")
        col.prop(rl, "use_pass_refraction", text="Refraction")
        col.prop(rl, "use_pass_emit", text="Emission")

        # layout.separator()
        #row = layout.row()
        # row.label('Holdouts')
        #rm = scene.renderman.holdout_settings
        #layout.prop(rm, 'do_collector_shadow')
        #layout.prop(rm, 'do_collector_reflection')
        #layout.prop(rm, 'do_collector_refraction')
        #layout.prop(rm, 'do_collector_indirectdiffuse')
        #layout.prop(rm, 'do_collector_subsurface')

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
        row = layout.row()
        row.prop(scene.renderman, "depth_of_field")
        sub = row.row()
        sub.enabled = scene.renderman.depth_of_field
        sub.prop(scene.renderman, "fstop")

        row = layout.row()
        row.label("Aperture Controls:")
        row.prop(cam.renderman, "aperture_sides")
        row.prop(cam.renderman, "aperture_angle")
        row.prop(cam.renderman, "aperture_roundness")
        row.prop(cam.renderman, "aperture_density")

        layout.prop(cam.renderman, "use_physical_camera")
        if cam.renderman.use_physical_camera:
            pxrcamera = getattr(cam.renderman, "PxrCamera_settings")

            # for each property add it to ui
            def draw_props(prop_names, layout):
                for prop_name in prop_names:
                    prop_meta = pxrcamera.prop_meta[prop_name]
                    prop = getattr(pxrcamera, prop_name)
                    row = layout.row()

                    if prop_meta['renderman_type'] == 'page':
                        ui_prop = prop_name + "_ui_open"
                        ui_open = getattr(pxrcamera, ui_prop)
                        icon = 'TRIA_DOWN' if ui_open \
                            else 'TRIA_RIGHT'

                        split = layout.split(NODE_LAYOUT_SPLIT)
                        row = split.row()
                        row.prop(pxrcamera, ui_prop, icon=icon, text='',
                                 icon_only=True, emboss=False)
                        row.label(prop_name + ':')

                        if ui_open:
                            draw_props(prop, layout)

                    else:
                        row.label('', icon='BLANK1')
                        # indented_label(row, socket.name+':')
                        row.prop(pxrcamera, prop_name)

            draw_props(pxrcamera.prop_names, layout)


class DATA_PT_renderman_lamp(ShaderPanel, Panel):
    bl_context = "data"
    bl_label = "Lamp"
    shader_type = 'light'
    param_exclude = exclude_lamp_params

    def draw(self, context):
        layout = self.layout

        lamp = context.lamp
        if lamp.renderman.nodetree == '':
            layout.prop(lamp, "type", expand=True)
            layout.operator('shading.add_renderman_nodetree').idtype = 'lamp'
            return
        else:
            layout.prop(lamp.renderman, "renderman_type", expand=True)
            if lamp.renderman.renderman_type == "AREA":
                layout.prop(lamp.renderman, "area_shape", expand=True)
                row = layout.row()
                if lamp.renderman.area_shape == "rect":
                    row.prop(lamp, 'size', text="Size X")
                    row.prop(lamp, 'size_y')
                else:
                    row.prop(lamp, 'size', text="Radius")
                    if lamp.renderman.area_shape == "cylinder":
                        row.prop(lamp, 'size_y', text="Length")
            layout.prop(lamp.renderman, "shadingrate")

        layout.prop_search(lamp.renderman, "nodetree", bpy.data, "node_groups")
        layout.prop(lamp.renderman, 'illuminates_by_default')


class DATA_PT_renderman_node_shader_lamp(ShaderNodePanel, Panel):
    bl_label = "Light Shader"
    bl_context = 'data'

    def draw(self, context):
        layout = self.layout
        lamp = context.lamp

        nt = bpy.data.node_groups[lamp.renderman.nodetree]
        output_node = next(
            (n for n in nt.nodes if n.renderman_node_type == 'output'), None)
        lamp_node = output_node.inputs['Light'].links[0].from_node
        if lamp_node:
            layout.prop(lamp_node, 'light_primary_visibility')
            layout.prop(lamp_node, 'light_shading_rate')
            draw_node_properties_recursive(self.layout, context, nt, lamp_node)


class OBJECT_PT_renderman_object_geometry(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Renderman Geometry"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return (context.object and rd.engine in {'PRMAN_RENDER'})

    def draw(self, context):
        layout = self.layout
        ob = context.object
        rm = ob.renderman
        anim = rm.archive_anim_settings

        col = layout.column()

        col.prop(rm, "geometry_source")

        if rm.geometry_source in ('ARCHIVE', 'DELAYED_LOAD_ARCHIVE'):
            col.prop(rm, "path_archive")
            col.prop(rm,"material_in_archive")
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

            
        
        col = layout.column()
        col.operator("export.export_rib_archive", icon="EXPORT", text="Export Object as RIB Archive.")
        
        
        
        #col = layout.column()
        # col.prop(rm, "export_coordsys")

        #row = col.row()
        #row.prop(rm, "motion_segments_override", text="")
        #sub = row.row()
        #sub.active = rm.motion_segments_override
        #sub.prop(rm, "motion_segments")


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

        row = col.row()
        row.prop(rm, 'do_holdout')
        sub = col.row()
        sub.enabled = rm.do_holdout
        sub.prop(rm, 'lpe_group')

        col.separator()

        row = col.row()
        row.prop(rm, 'shading_override')

        colgroup = layout.column()
        colgroup.enabled = rm.shading_override
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

        self._draw_collection(context, layout, rm, "Trace sets:", "collection.add_remove",
                              "object", "trace_set", "trace_set_index")

        layout.prop(
            rm, "raytrace_override", text="Override Default Ray Tracing")

        col = layout.column()
        col.active = rm.raytrace_override
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
        row = col.row()
        row.prop(
            rm, "raytrace_intersectpriority", text="Intersection Priority")


class OBJECT_PT_renderman_object_lightlinking(CollectionPanel, Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Light Linking"

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
        col.prop_search(item, "light", bpy.data, "lamps")
        col.prop(item, "illuminate")

    def draw(self, context):
        layout = self.layout
        ob = context.object
        rm = ob.renderman
        scene = context.scene

        self._draw_collection(context, layout, rm, "Light Link:",
                              "collection.add_remove", "object",
                              "light_linking", "light_linking_index")


class RENDER_PT_layer_custom_aovs(CollectionPanel, Panel):
    bl_label = "RenderMan AOVs"
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
        row = layout.row()
        #row.prop(item, "layers")
        col = layout.column()
        col.prop(item, "name")
        col.prop(item, "channel_type")
        if item.channel_type == "custom":
            col.prop(item, 'custom_lpe')
        
        col = layout.column()
        col.label("Exposure Settings")
        col.prop(item, "exposure_gain")
        col.prop(item, "exposure_gamma")
        
        col = layout.column()
        col.label("Remap Settings")
        row = col.row(align=True)
        row.prop(item, "remap_a", text="A")
        row.prop(item, "remap_b", text="B")
        row.prop(item, "remap_c", text="C")

        col.prop(item, "show_advanced")
        col = col.column()
        col.enabled = item.show_advanced
        col.prop(item, 'lpe_group')
        col.prop(item, 'lpe_light_group')

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rm = scene.renderman
        aov_list = None
        active_layer = scene.render.layers.active
        for l in rm.aov_lists:
            if l.render_layer == active_layer.name:
                aov_list = l
                break
        if aov_list is None:
            layout.operator('renderman.add_aov_list')
        else:
            layout.context_pointer_set("aov_list", aov_list)
            self._draw_collection(context, layout, aov_list, "AOVs",
                                  "collection.add_remove", "aov_list",
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
            col.row().prop(rm, "width")

        else:
            col.prop(psys.settings, "material_slot")

        # XXX: if rm.type in ('sphere', 'disc', 'patch'):
        # implement patchaspectratio and patchrotation

        split = layout.split()
        col = split.column()

        if psys.settings.type == 'HAIR':
            col.prop(rm, "constant_width")
            subcol = col.column()
            subcol.active = rm.constant_width
            subcol.prop(rm, "width")
            subcol2 = col.column()
            subcol2.active = not rm.constant_width
            subcol2.prop(rm, "base_width")
            subcol2.prop(rm, "tip_width")
            col.prop(rm, 'export_scalp_st')


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

        row = layout.row(align=True)
        row.operator("render.render", text="Render", icon='RENDER_STILL')

        if engine.ipr:
            row.operator('lighting.start_interactive',
                         text="Stop Interactive Rendering", icon='CANCEL')
        else:
            row.operator('lighting.start_interactive',
                         text="Start Interactive Rendering", icon='PLAY')


class DrawRenderHeaderImage(bpy.types.Header):
    bl_space_type = "IMAGE_EDITOR"

    def draw(self, context):
        if context.scene.render.engine != "PRMAN_RENDER":
            return
        layout = self.layout

        row = layout.row(align=True)
        row.operator("render.render", text="Render", icon='RENDER_STILL')

        if engine.ipr:
            row.operator('lighting.start_interactive',
                         text="Stop Interactive Rendering", icon='CANCEL')
        else:
            row.operator('lighting.start_interactive',
                         text="Start Interactive Rendering", icon='PLAY')


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


def register():
    bpy.types.INFO_MT_render.append(PRMan_menu_func)


def unregister():
    pass
