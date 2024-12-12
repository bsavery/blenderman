# Translators
from .rman_translators.rman_camera_translator import RmanCameraTranslator
from .rman_translators.rman_light_translator import RmanLightTranslator
from .rman_translators.rman_lightfilter_translator import RmanLightFilterTranslator
from .rman_translators.rman_mesh_translator import RmanMeshTranslator
from .rman_translators.rman_material_translator import RmanMaterialTranslator
from .rman_translators.rman_hair_translator import RmanHairTranslator
from .rman_translators.rman_group_translator import RmanGroupTranslator
from .rman_translators.rman_points_translator import RmanPointsTranslator
from .rman_translators.rman_quadric_translator import RmanQuadricTranslator
from .rman_translators.rman_blobby_translator import RmanBlobbyTranslator
from .rman_translators.rman_particles_translator import RmanParticlesTranslator
from .rman_translators.rman_procedural_translator import RmanProceduralTranslator
from .rman_translators.rman_dra_translator import RmanDraTranslator
from .rman_translators.rman_runprogram_translator import RmanRunProgramTranslator
from .rman_translators.rman_openvdb_translator import RmanOpenVDBTranslator
from .rman_translators.rman_gpencil_translator import RmanGPencilTranslator
from .rman_translators.rman_fluid_translator import RmanFluidTranslator
from .rman_translators.rman_curve_translator import RmanCurveTranslator
from .rman_translators.rman_nurbs_translator import RmanNurbsTranslator
from .rman_translators.rman_volume_translator import RmanVolumeTranslator
from .rman_translators.rman_brickmap_translator import RmanBrickmapTranslator
from .rman_translators.rman_emitter_translator import RmanEmitterTranslator
from .rman_translators.rman_empty_translator import RmanEmptyTranslator
from .rman_translators.rman_alembic_translator import RmanAlembicTranslator
from .rman_translators.rman_hair_curves_translator import RmanHairCurvesTranslator
from .rman_translators.rman_pointcloud_translator import RmanPointCloudTranslator

# utils
from .rfb_utils import object_utils
from .rfb_utils import transform_utils
from .rfb_utils import property_utils
from .rfb_utils import display_utils
from .rfb_utils import string_utils
from .rfb_utils import texture_utils
from .rfb_utils import filepath_utils
from .rfb_utils.envconfig_utils import envconfig
from .rfb_utils import scene_utils
from .rfb_utils.prefs_utils import get_pref
from .rfb_utils import shadergraph_utils
from .rfb_utils import color_manager_blender
from .rfb_utils import scenegraph_utils

# config
from .rman_config import __RFB_CONFIG_DICT__ as rfb_config
from . import rman_constants

from .rfb_logger import rfb_log
from .rman_sg_nodes.rman_sg_node import RmanSgNode

import bpy
import os
import sys

class RmanScene(object):
    '''
    The RmanScene handles translating the Blender scene.

    Attributes:
        rman_render (RmanRender) - pointer back to the current RmanRender object
        rman () - rman python module
        sg_scene (RixSGSCene) - the RenderMan scene graph object
        context (bpy.types.Context) - the current Blender context object
        depsgraph (bpy.types.Depsgraph) - the Blender dependency graph
        bl_scene (bpy.types.Scene) - the current Blender scene object
        bl_frame_current (int) - the current Blender frame
        bl_view_layer (bpy.types.ViewLayer) - the current Blender view layer
        rm_rl (RendermanRenderLayerSettings) - the current rman layer
        do_motion_blur (bool) - user requested for motion blur
        rman_bake (bool) - user requested a bake render
        is_interactive (bool) - whether we are in interactive mode
        external_render (bool) - whether we are exporting for external (RIB) renders
        is_viewport_render (bool) - whether we are rendering into Blender's viewport
        scene_solo_light (bool) - user has solo'd a light (all other lights are muted)
        rman_materials (dict) - dictionary of scene's materials
        rman_translators (dict) - dictionary of all RmanTranslator(s)
        rman_particles (dict) - dictionary of all particle systems used
        rman_cameras (dict) - dictionary of all cameras in the scene
        obj_hash (dict) - dictionary of hashes to objects ( for object picking )
        moving_objects (dict) - dictionary of objects that are moving/deforming in the scene
        motion_steps (set) - the full set of motion steps for the scene, including
                            overrides from individual objects
        main_camera (RmanSgCamera) - pointer to the main scene camera
        rman_root_sg_node (RixSGGroup) - the main root RixSceneGraph node
        render_default_light (bool) - whether to add a "headlight" light when there are no lights in the scene
        world_df_node (RixSGShader) - a display filter shader that represents the world color
        default_light (RixSGAnalyticLight) - the default "headlight" light
        viewport_render_res_mult (float) - the current render resolution multiplier (for IPR)
        num_object_instances (int) - the current number of object instances. This is used during IPR to
                                    track the number of instances between edits. We try to use this to determine
                                    when an object is added or deleted.
        num_objects_in_viewlayer (int) - the current number of objects in the current view layer. We're using this
                                       to keep track if an object was removed from a collection
        objects_in_viewlayer (list) - the list of objects (bpy.types.Object) in this view layer.
    '''

    def __init__(self, rman_render=None):
        self.rman_render = rman_render
        self.rman = rman_render.rman
        self.sg_scene = None
        self.context = None
        self.depsgraph = None
        self.bl_scene = None
        self.bl_frame_current = None
        self.bl_view_layer = None
        self.rm_rl = None

        self.do_motion_blur = False
        self.rman_bake = False
        self.is_interactive = False
        self.external_render = False
        self.is_viewport_render = False
        self.is_swatch_render = False
        self.scene_solo_light = False
        self.scene_any_lights = False
        self.is_xpu = False

        self.rman_materials = dict()
        self.rman_translators = dict()
        self.rman_particles = dict()
        self.rman_cameras = dict()
        self.obj_hash = dict()
        self.moving_objects = dict()
        self.rman_prototypes = dict()

        self.motion_steps = set()
        self.main_camera = None
        self.rman_root_sg_node = None

        self.render_default_light = False
        self.world_df_node = None
        self.default_light = None

        self.viewport_render_res_mult = 1.0
        self.num_object_instances = 0
        self.num_objects_in_viewlayer = 0
        self.objects_in_viewlayer = list()

        self.ipr_render_into = 'blender'

        self.create_translators()


    def create_translators(self):
        # Create our dictionary of translators. The object type is determined
        # by the "_detect_primitive_" function in rfb_utils/object_utils.py

        self.rman_translators['CAMERA'] = RmanCameraTranslator(rman_scene=self)
        self.rman_translators['LIGHT'] = RmanLightTranslator(rman_scene=self)
        self.rman_translators['LIGHTFILTER'] = RmanLightFilterTranslator(rman_scene=self)
        self.rman_translators['MATERIAL'] = RmanMaterialTranslator(rman_scene=self)
        self.rman_translators['HAIR'] = RmanHairTranslator(rman_scene=self)
        self.rman_translators['GROUP'] = RmanGroupTranslator(rman_scene=self)
        self.rman_translators['EMPTY'] = RmanEmptyTranslator(rman_scene=self)
        self.rman_translators['ARMATURE'] = self.rman_translators['EMPTY']
        self.rman_translators['LATTICE'] = RmanEmptyTranslator(rman_scene=self)
        self.rman_translators['EMPTY_INSTANCER'] = self.rman_translators['EMPTY']
        self.rman_translators['POINTS'] = RmanPointsTranslator(rman_scene=self)
        self.rman_translators['META'] = RmanBlobbyTranslator(rman_scene=self)
        self.rman_translators['PARTICLES'] = RmanParticlesTranslator(rman_scene=self)
        self.rman_translators['EMITTER'] = RmanEmitterTranslator(rman_scene=self)
        self.rman_translators['DYNAMIC_LOAD_DSO'] = RmanProceduralTranslator(rman_scene=self)
        self.rman_translators['DELAYED_LOAD_ARCHIVE'] = RmanDraTranslator(rman_scene=self)
        self.rman_translators['PROCEDURAL_RUN_PROGRAM'] = RmanRunProgramTranslator(rman_scene=self)
        self.rman_translators['OPENVDB'] = RmanOpenVDBTranslator(rman_scene=self)
        self.rman_translators['GPENCIL'] = RmanGPencilTranslator(rman_scene=self)
        self.rman_translators['MESH'] = RmanMeshTranslator(rman_scene=self)
        self.rman_translators['QUADRIC'] = RmanQuadricTranslator(rman_scene=self)
        self.rman_translators['FLUID'] = RmanFluidTranslator(rman_scene=self)
        self.rman_translators['CURVE'] = RmanCurveTranslator(rman_scene=self)
        self.rman_translators['NURBS'] = RmanNurbsTranslator(rman_scene=self)
        self.rman_translators['RI_VOLUME'] = RmanVolumeTranslator(rman_scene=self)
        self.rman_translators['BRICKMAP'] = RmanBrickmapTranslator(rman_scene=self)
        self.rman_translators['ALEMBIC'] = RmanAlembicTranslator(rman_scene=self)
        self.rman_translators['CURVES'] = RmanHairCurvesTranslator(rman_scene=self)
        self.rman_translators['POINTCLOUD'] = RmanPointCloudTranslator(rman_scene=self)

    def _find_renderman_layer(self):
        self.rm_rl = None
        if self.bl_view_layer.renderman.use_renderman:
            self.rm_rl = self.bl_view_layer.renderman

    def reset(self):
        # clear out dictionaries etc.
        self.rman_materials.clear()
        self.rman_particles.clear()
        self.rman_cameras.clear()
        self.obj_hash.clear()
        self.motion_steps = set()
        self.moving_objects.clear()
        self.rman_prototypes.clear()

        self.main_camera = None
        self.render_default_light = False
        self.world_df_node = None
        self.default_light = None
        self.is_xpu = False
        self.num_object_instances = 0
        self.num_objects_in_viewlayer = 0
        self.objects_in_viewlayer.clear()

        try:
            if self.is_viewport_render:
                self.viewport_render_res_mult = float(self.context.scene.renderman.viewport_render_res_mult)
            else:
                self.viewport_render_res_mult = 1.0
        except AttributeError as err:
            rfb_log().debug("Cannot set viewport_render_res_mult: %s" % str(err))


    def export_for_final_render(self, depsgraph, sg_scene, bl_view_layer, is_external=False):
        self.sg_scene = sg_scene
        self.context = bpy.context
        self.bl_scene = depsgraph.scene_eval
        self.bl_view_layer = bl_view_layer
        self._find_renderman_layer()
        self.depsgraph = depsgraph
        self.external_render = is_external
        self.is_interactive = False
        self.is_viewport_render = False
        self.do_motion_blur = self.bl_scene.renderman.motion_blur
        self.export()

    def export_for_bake_render(self, depsgraph, sg_scene, bl_view_layer, is_external=False):
        self.sg_scene = sg_scene
        self.context = bpy.context
        self.bl_scene = depsgraph.scene_eval
        self.bl_view_layer = bl_view_layer
        self._find_renderman_layer()
        self.depsgraph = depsgraph
        self.external_render = is_external
        self.is_interactive = False
        self.is_viewport_render = False
        self.do_motion_blur = self.bl_scene.renderman.motion_blur
        self.rman_bake = True

        if self.bl_scene.renderman.hider_type == 'BAKE_BRICKMAP_SELECTED':
            self.export_bake_brickmap_selected()
        else:
            self.export_bake_render_scene()

    def export_for_interactive_render(self, context, depsgraph, sg_scene):
        self.sg_scene = sg_scene
        self.context = context
        self.bl_view_layer = depsgraph.view_layer_eval
        self.bl_scene = depsgraph.scene_eval
        self._find_renderman_layer()
        self.depsgraph = depsgraph
        self.external_render = False
        self.is_interactive = True
        self.is_viewport_render = False
        self.rman_bake = False

        if self.ipr_render_into == 'blender':
            self.is_viewport_render = True

        self.do_motion_blur = False

        self.export()

    def export_for_rib_selection(self, context, sg_scene):
        self.reset()
        self.bl_scene = context.scene
        self.bl_frame_current = self.bl_scene.frame_current
        self.sg_scene = sg_scene
        self.context = context
        self.depsgraph = context.evaluated_depsgraph_get()
        self.bl_view_layer = self.depsgraph.view_layer_eval
        self._find_renderman_layer()
        self.rman_bake = False
        self.external_render = False
        self.is_interactive = False
        self.is_viewport_render = False

        self.export_root_sg_node()
        self.export_materials([m for m in self.depsgraph.ids if isinstance(m, bpy.types.Material)])
        self.export_data_blocks(selected_objects=True)

    def export_for_swatch_render(self, depsgraph, sg_scene):
        self.sg_scene = sg_scene
        self.context = bpy.context #None
        self.bl_scene = depsgraph.scene_eval
        self.depsgraph = depsgraph
        self.external_render = False
        self.is_interactive = False
        self.is_viewport_render = False
        self.do_motion_blur = False
        self.rman_bake = False
        self.is_swatch_render = True
        self.export_swatch_render_scene()

    def export(self):

        self.reset()

        self.render_default_light = self.bl_scene.renderman.render_default_light
        if sys.platform != "darwin":
            self.is_xpu = (self.bl_scene.renderman.renderVariant != 'prman')

        # update variables
        string_utils.set_var('scene', self.bl_scene.name.replace(' ', '_'))
        string_utils.set_var('layer', self.bl_view_layer.name.replace(' ', '_'))

        self.bl_frame_current = self.bl_scene.frame_current
        string_utils.update_frame_token(self.bl_frame_current)

        rfb_log().debug("Creating root scene graph node")
        self.export_root_sg_node()

        rfb_log().debug("Calling export_materials()")
        #self.export_materials(bpy.data.materials)
        self.export_materials([m for m in self.depsgraph.ids if isinstance(m, bpy.types.Material)])

        # tell the texture manager to start converting any unconverted textures
        # normally textures are converted as they are added to the scene
        rfb_log().debug("Calling txmake_all()")
        texture_utils.get_txmanager().rman_scene = self
        texture_utils.get_txmanager().txmake_all(blocking=True)

        self.scene_any_lights = self._scene_has_lights()

        rfb_log().debug("Calling export_data_blocks()")
        self.export_data_blocks()

        self.export_searchpaths()
        self.export_global_options()
        self.export_hider()
        self.export_integrator()

        self.export_cameras([c for c in self.depsgraph.objects if isinstance(c.data, bpy.types.Camera)])

        # export default light
        self.export_defaultlight()
        self.main_camera.sg_node.AddChild(self.default_light)

        self.export_displays()
        self.export_samplefilters()
        self.export_displayfilters()

        if self.do_motion_blur:
            rfb_log().debug("Calling export_instances_motion()")
            self.export_instances_motion()

        self.rman_render.stats_mgr.set_export_stats("Finished Export", 1.0)
        self.num_object_instances = len(self.depsgraph.object_instances)
        visible_objects = getattr(self.context, 'visible_objects', list())
        self.num_objects_in_viewlayer = len(visible_objects)
        self.objects_in_viewlayer = [o for o in visible_objects]

        if self.is_interactive:
            self.export_viewport_stats()
        else:
            self.export_stats()

    def export_bake_render_scene(self):
        self.reset()

        # update tokens
        string_utils.set_var('scene', self.bl_scene.name.replace(' ', '_'))
        string_utils.set_var('layer', self.bl_view_layer.name.replace(' ', '_'))

        self.bl_frame_current = self.bl_scene.frame_current
        rfb_log().debug("Creating root scene graph node")
        self.export_root_sg_node()

        rfb_log().debug("Calling export_materials()")
        self.export_materials([m for m in self.depsgraph.ids if isinstance(m, bpy.types.Material)])

        rfb_log().debug("Calling txmake_all()")
        texture_utils.get_txmanager().rman_scene = self
        texture_utils.get_txmanager().txmake_all(blocking=True)

        self.scene_any_lights = self._scene_has_lights()

        rm = self.bl_scene.renderman
        rman_root_sg_node = self.get_root_sg_node()
        attrs = rman_root_sg_node.GetAttributes()
        attrs.SetFloat("dice:worlddistancelength", rm.rman_bake_illlum_density)
        rman_root_sg_node.SetAttributes(attrs)

        rfb_log().debug("Calling export_data_blocks()")
        self.export_data_blocks()

        self.export_searchpaths()
        self.export_global_options()
        self.export_hider()
        self.export_integrator()
        self.export_cameras([c for c in self.depsgraph.objects if isinstance(c.data, bpy.types.Camera)])

        # export default light
        self.export_defaultlight()
        self.main_camera.sg_node.AddChild(self.default_light)

        self.export_bake_displays()
        self.export_samplefilters()
        self.export_displayfilters()

        if self.do_motion_blur:
            rfb_log().debug("Calling export_instances_motion()")
            self.export_instances_motion()

        options = self.sg_scene.GetOptions()
        bake_resolution = int(rm.rman_bake_illlum_res)
        options.SetIntegerArray(self.rman.Tokens.Rix.k_Ri_FormatResolution, (bake_resolution, bake_resolution), 2)
        self.sg_scene.SetOptions(options)

    def export_bake_brickmap_selected(self):
        self.reset()

        # update variables
        string_utils.set_var('scene', self.bl_scene.name.replace(' ', '_'))
        string_utils.set_var('layer', self.bl_view_layer.name.replace(' ', '_'))

        self.bl_frame_current = self.bl_scene.frame_current
        rfb_log().debug("Creating root scene graph node")
        self.export_root_sg_node()

        rfb_log().debug("Calling export_materials()")
        self.export_materials([m for m in self.depsgraph.ids if isinstance(m, bpy.types.Material)])
        rfb_log().debug("Calling txmake_all()")
        texture_utils.get_txmanager().rman_scene = self
        texture_utils.get_txmanager().txmake_all(blocking=True)

        self.scene_any_lights = self._scene_has_lights()

        rm = self.bl_scene.renderman
        rman_root_sg_node = self.get_root_sg_node()
        attrs = rman_root_sg_node.GetAttributes()
        attrs.SetFloat("dice:worlddistancelength", rm.rman_bake_illlum_density)
        rman_root_sg_node.SetAttributes(attrs)

        self.export_searchpaths()
        self.export_global_options()
        self.export_hider()
        self.export_integrator()
        self.export_cameras([c for c in self.depsgraph.objects if isinstance(c.data, bpy.types.Camera)])

        # export default light
        self.export_defaultlight()
        self.main_camera.sg_node.AddChild(self.default_light)

        ob = self.context.active_object
        self.export_materials([m for m in self.depsgraph.ids if isinstance(m, bpy.types.Material)])
        objects_needed = [x.original for x in self.bl_scene.objects if object_utils._detect_primitive_(x) == 'LIGHT']
        objects_needed.append(ob.original)
        self.export_data_blocks(objects_list=objects_needed)

        self.export_samplefilters()
        self.export_displayfilters()

        options = self.sg_scene.GetOptions()
        bake_resolution = int(rm.rman_bake_illlum_res)
        options.SetIntegerArray(self.rman.Tokens.Rix.k_Ri_FormatResolution, (bake_resolution, bake_resolution), 2)
        self.sg_scene.SetOptions(options)

        # Display
        display_driver = 'pointcloud'
        dspy_chan_Ci = self.rman.SGManager.RixSGDisplayChannel('color', 'Ci')

        self.sg_scene.SetDisplayChannel([dspy_chan_Ci])
        render_output = '%s.ptc' % ob.renderman.bake_filename_attr
        render_output = string_utils.expand_string(render_output)
        display = self.rman.SGManager.RixSGShader("Display", display_driver, render_output)
        display.params.SetString("mode", 'Ci')
        self.main_camera.sg_camera_node.SetDisplay(display)

    def export_swatch_render_scene(self):
        self.reset()

        # options
        options = self.sg_scene.GetOptions()
        options.SetInteger(self.rman.Tokens.Rix.k_hider_minsamples, get_pref('rman_preview_renders_minSamples', default=0))
        options.SetInteger(self.rman.Tokens.Rix.k_hider_maxsamples, get_pref('rman_preview_renders_minSamples', default=1))
        options.SetInteger(self.rman.Tokens.Rix.k_hider_incremental, 1)
        options.SetString("adaptivemetric", "variance")
        scale = 100.0 / self.bl_scene.render.resolution_percentage
        w = int(self.bl_scene.render.resolution_x * scale)
        h = int(self.bl_scene.render.resolution_y * scale)
        options.SetIntegerArray(self.rman.Tokens.Rix.k_Ri_FormatResolution, (w, h), 2)
        options.SetFloat(self.rman.Tokens.Rix.k_Ri_PixelVariance, get_pref('rman_preview_renders_pixelVariance', default=0.15))
        options.SetInteger(self.rman.Tokens.Rix.k_limits_threads, -2)
        options.SetString(self.rman.Tokens.Rix.k_bucket_order, 'horizontal')
        self.sg_scene.SetOptions(options)

        # searchpaths
        self.export_searchpaths()

        # integrator
        integrator_sg = self.rman.SGManager.RixSGShader("Integrator", "PxrPathTracer", "integrator")
        self.sg_scene.SetIntegrator(integrator_sg)

        # camera
        self.export_cameras([c for c in self.depsgraph.objects if isinstance(c.data, bpy.types.Camera)])

        # Display
        display_driver = 'blender'
        dspy_chan_Ci = self.rman.SGManager.RixSGDisplayChannel('color', 'Ci')
        dspy_chan_a = self.rman.SGManager.RixSGDisplayChannel('float', 'a')

        self.sg_scene.SetDisplayChannel([dspy_chan_Ci, dspy_chan_a])
        display = self.rman.SGManager.RixSGShader("Display", display_driver, 'blender_preview')
        display.params.SetString("mode", 'Ci,a')
        self.main_camera.sg_camera_node.SetDisplay(display)

        rfb_log().debug("Calling materials()")
        self.export_materials([m for m in self.depsgraph.ids if isinstance(m, bpy.types.Material)])
        rfb_log().debug("Calling export_data_blocks()")

        self.export_data_blocks()

    def set_root_lightlinks(self, rixattrs=None):
        rm = self.bl_scene.renderman
        root_sg = self.get_root_sg_node()
        attrs = rixattrs
        if rixattrs is None:
            attrs = root_sg.GetAttributes()    
        all_lightfilters = [string_utils.sanitize_node_name(l.name) for l in scene_utils.get_all_lightfilters(self.bl_scene)]            

        if rm.invert_light_linking:
            all_lights = [string_utils.sanitize_node_name(l.name) for l in scene_utils.get_all_lights(self.bl_scene, include_light_filters=False)]
            for ll in rm.light_links:
                light_ob = ll.light_ob
                light_nm = string_utils.sanitize_node_name(light_ob.name)
                light_props = shadergraph_utils.get_rman_light_properties_group(light_ob)
                if light_props.renderman_light_role == 'RMAN_LIGHT':
                    if light_nm in all_lights:
                        all_lights.remove(light_nm)
                elif light_nm in all_lightfilters:
                    all_lightfilters.remove(light_nm)

            if all_lights:
                attrs.SetString(self.rman.Tokens.Rix.k_lighting_subset, ' '. join(all_lights) )
            else:
                attrs.SetString(self.rman.Tokens.Rix.k_lighting_subset, '*')

            if all_lightfilters:
                attrs.SetString(self.rman.Tokens.Rix.k_lightfilter_subset, ' '. join(all_lightfilters) )
            else:
                attrs.SetString(self.rman.Tokens.Rix.k_lightfilter_subset, '*')
        else:
            attrs.SetString(self.rman.Tokens.Rix.k_lightfilter_subset, ','. join(all_lightfilters) )

        if rixattrs is None:
            root_sg.SetAttributes(attrs)           

    def export_root_sg_node(self):

        rm = self.bl_scene.renderman
        root_sg = self.get_root_sg_node()
        attrs = root_sg.GetAttributes()

        # set any properties marked riattr in the config file
        for prop_name, meta in rm.prop_meta.items():
            property_utils.set_riattr_bl_prop(attrs, prop_name, meta, rm, check_inherit=False, remove=False)

        self.set_root_lightlinks(rixattrs=attrs)
        root_sg.SetAttributes(attrs)

    def get_root_sg_node(self):
        return self.sg_scene.Root()

    def export_materials(self, materials):
        for mat in materials:
            db_name = object_utils.get_db_name(mat)
            rman_sg_material = self.rman_translators['MATERIAL'].export(mat.original, db_name)
            if rman_sg_material:
                self.rman_materials[mat.original] = rman_sg_material

    def check_visibility(self, instance, ob_eval=None):
        if not self.is_interactive:
            return True
        viewport = self.context.space_data
        if viewport is None or viewport.type != 'VIEW_3D':
            return True

        if instance.is_instance:
            ob_eval = instance.instance_object
            ob_eval_visible = ob_eval.visible_in_viewport_get(viewport)
            parent_visible = instance.parent.visible_in_viewport_get(viewport)
            return (ob_eval_visible or parent_visible)

        if ob_eval is None:
            ob_eval = instance.object.evaluated_get(self.depsgraph)
        visible = ob_eval.visible_in_viewport_get(viewport)
        return visible

    def is_instance_selected(self, instance):
        ob = instance.object
        parent = None
        if instance.is_instance:
            parent = instance.parent

        if not ob.original.select_get():
            if parent:
                if not parent.original.select_get():
                    return False
            else:
                return False
        if parent and not parent.original.select_get():
            return False

        return True

    def get_rman_sg_instance(self, ob_inst, rman_sg_node, instance_parent, psys, create=True):  
        group_db_name = object_utils.get_group_db_name(ob_inst) 
        rman_parent_node = None
        if psys and instance_parent:
            rman_parent_node = self.get_rman_prototype(object_utils.prototype_key(instance_parent), ob=instance_parent, create=True)
            if rman_parent_node:
                if group_db_name in rman_parent_node.instances:
                    return rman_parent_node.instances[group_db_name]
        else:
            if group_db_name in rman_sg_node.instances:
                return rman_sg_node.instances[group_db_name]

        rman_sg_group = None
        if create:
            rman_group_translator = self.rman_translators['GROUP']
            rman_sg_group = rman_group_translator.export(None, group_db_name)
            rman_sg_group.sg_node.AddChild(rman_sg_node.sg_node)       

            if rman_parent_node:
                # this is an instance that comes from a particle system
                # add this instance to the rman_sg_node that owns the particle system        
                rman_parent_node.instances[group_db_name] = rman_sg_group
            else:       
                rman_sg_node.instances[group_db_name] = rman_sg_group                   

        return rman_sg_group       

    def update_instance_attributes(self, translator, rman_sg_node, ob_eval, ob_inst, remove=False): 
        # we want to export attributes for the instance
        # as we still want the instance to be able override attributes        
        attrs = rman_sg_node.sg_node.GetAttributes()
        translator.export_object_attributes_attrs(ob_eval, attrs, remove=remove)
        rman_sg_node.sg_node.SetAttributes(attrs)            
        # export instance attributes
        translator.export_instance_attributes(ob_eval, rman_sg_node, ob_inst)         

    def export_instance(self, ob_eval, ob_inst, rman_sg_node, rman_type, instance_parent, psys):
        rman_group_translator = self.rman_translators['GROUP']
        rman_sg_group = self.get_rman_sg_instance(ob_inst, rman_sg_node, instance_parent, psys, create=True)
        is_empty_instancer = False
        if instance_parent: 
            is_empty_instancer = object_utils.is_empty_instancer(instance_parent)
           
        # Object attrs
        translator =  self.rman_translators.get(rman_type, None)
        if translator:
            self.update_instance_attributes(translator, rman_sg_group, ob_eval, ob_inst)

        # Add any particles necessary
        if rman_sg_node.rman_sg_particle_group_node:
            if (len(ob_eval.particle_systems) > 0) and ob_inst.show_particles:
                rman_sg_group.sg_node.AddChild(rman_sg_node.rman_sg_particle_group_node.sg_node)

        # Attach any material overrides
        if is_empty_instancer:
            if instance_parent.renderman.rman_material_override:
                rman_sg_group.sg_node.SetMaterial(None)
            else:
                # if there is not a material override, we want
                # the material of the object
                self.attach_material(ob_eval, rman_sg_group)        
        elif psys:
            self.attach_particle_material(psys.settings, instance_parent, ob_eval, rman_sg_group)
            rman_sg_group.bl_psys_settings = psys.settings.original     
        elif ob_eval.renderman.rman_material_override:
            self.attach_material(ob_eval, rman_sg_group) 
        else:
            rman_sg_group.sg_node.SetMaterial(None)                   

        if is_empty_instancer:
            # if this is an empty instancer, add as a child to the empty instancer
            parent_proto_key = object_utils.prototype_key(instance_parent)
            rman_parent_node = self.get_rman_prototype(parent_proto_key, ob=instance_parent, create=True)             
            rman_parent_node.sg_attributes.AddChild(rman_sg_group.sg_node)
        else:
            rman_sg_node.sg_attributes.AddChild(rman_sg_group.sg_node)

        # check if instance has transform motion
        if self.do_motion_blur and object_utils.is_transforming(ob_eval):
            mb_segs = self.bl_scene.renderman.motion_segments
            if ob_eval.renderman.motion_segments_override:
                mb_segs = ob_eval.renderman.motion_segments
            if mb_segs > 1:
                subframes = scene_utils._get_subframes_(mb_segs, self.bl_scene)
                rman_sg_group.motion_steps = subframes
                rman_sg_group.is_transforming = True
                self.motion_steps.update(subframes)            
                self.moving_objects[ob_inst.object.name_full] = ob_inst.object
            
        if rman_type == "META":
            # meta/blobbies are already in world space. Their instances don't need to
            # set a transform.
            return rman_sg_group           
        rman_sg_group.sg_node.SetInheritTransform(False) # we don't want to inherit the transform                
        rman_group_translator.update_transform(ob_inst, rman_sg_group)
        return rman_sg_group


    def export_data_blocks(self, selected_objects=False, objects_list=False):
        total = len(self.depsgraph.object_instances)
        for i, ob_inst in enumerate(self.depsgraph.object_instances):
            ob = ob_inst.object
            rfb_log().debug("   Exported %d/%d instances... (%s)" % (i, total, ob.name))
            self.rman_render.stats_mgr.set_export_stats("Exporting instances",i/total)
            if ob.type in ('CAMERA'):
                continue

            if selected_objects and not self.is_instance_selected(ob_inst):
                continue

            # only export these objects
            if objects_list and ob.original not in objects_list:
                continue

            if not self.check_visibility(ob_inst):
                rfb_log().debug("       Object (%s) not visible" % (ob.name))
                continue

            ob_eval = ob.evaluated_get(self.depsgraph)
            psys = None
            instance_parent = None
            proto_key = object_utils.prototype_key(ob_inst)
            if ob_inst.is_instance:
                psys = ob_inst.particle_system
                instance_parent = ob_inst.parent

            rman_type = object_utils._detect_primitive_(ob_eval)
            rman_sg_node = self.get_rman_prototype(proto_key, ob=ob_eval, create=True)
            if not rman_sg_node:
                continue

            if rman_type == 'LIGHT':
                self.check_solo_light(rman_sg_node, ob_eval)

            if rman_type in object_utils._RMAN_NO_INSTANCES_:
                continue

            self.export_instance(ob_eval, ob_inst, rman_sg_node, rman_type, instance_parent, psys)

    def export_data_block(self, proto_key, ob):
        rman_type = object_utils._detect_primitive_(ob)

        if rman_type == "META":
            if rman_constants.META_AS_MESH:
                return None
            # only add the meta instance that matches the family name
            if ob.name_full != object_utils.get_meta_family(ob):
                return None

        if proto_key in self.rman_prototypes:
            return self.rman_prototypes[proto_key]

        translator =  self.rman_translators.get(rman_type, None)
        if not translator:
            return None

        rman_sg_node = None
        db_name = object_utils.get_db_name(ob)
        rman_sg_node = translator.export(ob, db_name)
        if not rman_sg_node:
            return None
        rman_sg_node.create_sg_attributes(ob)
        rman_sg_node.rman_type = rman_type
        self.rman_prototypes[proto_key] = rman_sg_node

        # motion blur
        # we set motion steps for this object, even if it's not moving
        # it could be moving as part of a particle system
        #
        # FIXME: remove the checking of transform motion here, this should
        # and is already being done in export_instance.
        mb_segs = -1
        mb_deform_segs = -1
        if self.do_motion_blur:
            mb_segs = self.bl_scene.renderman.motion_segments
            mb_deform_segs = self.bl_scene.renderman.deform_motion_segments
            if ob.renderman.motion_segments_override:
                mb_segs = ob.renderman.motion_segments
            if mb_segs > 1:
                subframes = scene_utils._get_subframes_(mb_segs, self.bl_scene)
                rman_sg_node.motion_steps = subframes
                self.motion_steps.update(subframes)

            if ob.renderman.motion_segments_override:
                mb_deform_segs = ob.renderman.deform_motion_segments

            if mb_deform_segs > 1:
                subframes = scene_utils._get_subframes_(mb_deform_segs, self.bl_scene)
                rman_sg_node.deform_motion_steps = subframes
                self.motion_steps.update(subframes)

        if rman_sg_node.is_transforming or rman_sg_node.is_deforming:
            if mb_segs > 1 or mb_deform_segs > 1:
                self.moving_objects[ob.name_full] = ob

            if mb_segs < 1:
                rman_sg_node.is_transforming = False
            if mb_deform_segs < 1:
                rman_sg_node.is_deforming = False

        translator.update(ob, rman_sg_node)
        
        # set object attributes
        attrs = rman_sg_node.sg_attributes.GetAttributes()
        translator.export_object_attributes_attrs(ob, attrs, remove=False)
        rman_sg_node.sg_attributes.SetAttributes(attrs)

        # set material
        self.attach_material(ob, rman_sg_node, sg_node=rman_sg_node.sg_attributes)

        if len(ob.particle_systems) > 0:
            # Deal with any particles now.
            subframes = []
            if self.do_motion_blur:
                subframes = scene_utils._get_subframes_(2, self.bl_scene)
                self.motion_steps.update(subframes)

            particles_group_db = ''
            rman_sg_node.rman_sg_particle_group_node = self.rman_translators['GROUP'].export(None, particles_group_db)

            psys_translator = self.rman_translators['PARTICLES']
            for psys in ob.particle_systems:
                psys_db_name = '%s' % psys.name
                rman_sg_particles = psys_translator.export(ob, psys, psys_db_name)
                if not rman_sg_particles:
                    continue

                psys_translator.set_motion_steps(rman_sg_particles, subframes)
                psys_translator.update(ob, psys, rman_sg_particles)

                ob_psys = self.rman_particles.get(proto_key, dict())
                ob_psys[psys.settings.original] = rman_sg_particles
                self.rman_particles[proto_key] = ob_psys
                rman_sg_node.rman_sg_particle_group_node.sg_node.AddChild(rman_sg_particles.sg_node)

        if rman_type == 'EMPTY':
            self._export_hidden_instance(ob, rman_sg_node)

        if ob.original.parent:
            ob_parent_eval = object_utils.find_parent(ob.original)
            if ob_parent_eval:
                ob_parent_eval = ob_parent_eval.evaluated_get(self.depsgraph)
                parent_proto_key = object_utils.prototype_key(ob.original.parent)
                rman_parent_node = self.get_rman_prototype(parent_proto_key, ob=ob_parent_eval, create=True)
                rman_parent_node.sg_attributes.AddChild(rman_sg_node.sg_attributes)
            else:
                # doesn't have a parent, add to root
                self.get_root_sg_node().AddChild(rman_sg_node.sg_attributes)
        else:
            self.get_root_sg_node().AddChild(rman_sg_node.sg_attributes)

        return rman_sg_node

    def export_instances_motion(self, selected_objects=False):
        origframe = self.bl_scene.frame_current

        mb_segs = self.bl_scene.renderman.motion_segments
        origframe = self.bl_scene.frame_current

        motion_steps = sorted(list(self.motion_steps))

        first_sample = False
        delta = 0.0
        if len(motion_steps) > 0:
            delta = -motion_steps[0]
        psys_translator = self.rman_translators['PARTICLES']
        rman_group_translator = self.rman_translators['GROUP']
        for samp, seg in enumerate(motion_steps):
            first_sample = (samp == 0)
            if seg < 0.0:
                self.rman_render.bl_engine.frame_set(origframe - 1, subframe=1.0 + seg)
            else:
                self.rman_render.bl_engine.frame_set(origframe, subframe=seg)

            self.depsgraph.update()
            time_samp = seg + delta # get the normlized version of the segment
            total = len(self.depsgraph.object_instances)
            objFound = False

            # update camera
            if not first_sample and self.main_camera.is_transforming and seg in self.main_camera.motion_steps:
                cam_translator =  self.rman_translators['CAMERA']
                idx = 0
                for i, s in enumerate(self.main_camera.motion_steps):
                    if s == seg:
                        idx = i
                        break
                cam_translator.update_transform(self.depsgraph.scene_eval.camera, self.main_camera, idx, time_samp)

            rfb_log().debug(" Export Sample: %i" % samp)
            for i, ob_inst in enumerate(self.depsgraph.object_instances):
                if selected_objects and not self.is_instance_selected(ob_inst):
                    continue

                if not self.check_visibility(ob_inst):
                    continue

                psys = None
                ob = ob_inst.object.evaluated_get(self.depsgraph)
                proto_key = object_utils.prototype_key(ob_inst)
                rfb_log().debug("   Exported %d/%d motion instances... (%s)" % (i, total, ob.name))
                self.rman_render.stats_mgr.set_export_stats("Exporting motion instances (%d) " % samp ,i/total)
                instance_parent = None
                if ob_inst.is_instance:
                    psys = ob_inst.particle_system
                    instance_parent = ob_inst.parent

                rman_type = object_utils._detect_primitive_(ob)
                if rman_type in object_utils._RMAN_NO_INSTANCES_:
                    continue

                # check particles for motion
                '''
                for psys in ob.particle_systems:
                    ob_psys = self.rman_particles.get(proto_key, None)
                    if not ob_psys:
                        continue
                    rman_sg_particles = ob_psys.get(psys.settings.original, None)
                    if not rman_sg_particles:
                        continue
                    if not seg in rman_sg_particles.motion_steps:
                        continue
                    idx = 0
                    for i, s in enumerate(rman_sg_particles.motion_steps):
                        if s == seg:
                            idx = i
                            break
                    psys_translator.export_deform_sample(rman_sg_particles, ob, psys, idx)
                '''

                # object is not moving and not part of a particle system
                if ob.name_full not in self.moving_objects and not psys:
                    continue

                rman_sg_node = self.get_rman_prototype(proto_key, ob=ob)
                if not rman_sg_node:
                    continue

                rman_sg_group = self.get_rman_sg_instance(ob_inst, rman_sg_node, instance_parent, psys)
                if not rman_sg_group:
                    continue

                # transformation blur
                if seg in rman_sg_group.motion_steps:
                    idx = 0
                    for i, s in enumerate(rman_sg_group.motion_steps):
                        if s == seg:
                            idx = i
                            break

                    if rman_sg_group.is_transforming or psys:
                        if first_sample:
                            rman_group_translator.update_transform_num_samples(rman_sg_group, rman_sg_group.motion_steps ) 
                        rman_group_translator.update_transform_sample( ob_inst, rman_sg_group, idx, time_samp)

                # deformation blur
                if rman_sg_node.is_deforming and seg in rman_sg_node.deform_motion_steps:
                    rman_type = rman_sg_node.rman_type
                    if rman_type in ['MESH', 'FLUID', 'CURVES']:
                        translator = self.rman_translators.get(rman_type, None)
                        if translator:
                            deform_idx = 0
                            for i, s in enumerate(rman_sg_node.deform_motion_steps):
                                if s == seg:
                                    deform_idx = i
                                    break
                            translator.export_deform_sample(rman_sg_node, ob, deform_idx)

        self.rman_render.bl_engine.frame_set(origframe, subframe=0)
        rfb_log().debug("   Finished exporting motion instances")
        self.rman_render.stats_mgr.set_export_stats("Finished exporting motion instances", 100)

    def export_defaultlight(self):
        # Export a headlight light if needed
        if not self.default_light:
            self.default_light = self.sg_scene.CreateAnalyticLight('__defaultlight')
            sg_node = self.rman.SGManager.RixSGShader("Light", 'PxrDistantLight' , "light")
            self.default_light.SetLight(sg_node)
            s_orientPxrLight = [-1.0, 0.0, -0.0, 0.0,
                    -0.0, -1.0, -0.0, 0.0,
                    0.0, 0.0, -1.0, 0.0,
                    0.0, 0.0, 0.0, 1.0]
            self.default_light.SetOrientTransform(s_orientPxrLight)

        if self.render_default_light and not self.scene_any_lights:
            self.default_light.SetHidden(0)
        else:
            self.default_light.SetHidden(1)

    def _scene_has_lights(self):
        # Determine if there are any lights in the scene
        num_lights = len(scene_utils.get_all_lights(self.bl_scene, include_light_filters=False))
        return num_lights > 0

    def get_rman_prototype(self, proto_key, ob=None, create=False):
        if proto_key in self.rman_prototypes:
            return self.rman_prototypes[proto_key]

        if not create:
            return None

        if not ob:
            return None

        rman_sg_node = self.export_data_block(proto_key, ob)
        return rman_sg_node

    def get_rman_particles(self, proto_key, psys, ob, create=True):
        psys_translator = self.rman_translators['PARTICLES']
        group_translator = self.rman_translators['GROUP']
        ob_psys = self.rman_particles.get(proto_key, dict())
        rman_sg_particles = ob_psys.get(psys.settings.original, None)
        if not rman_sg_particles and create:
            psys_db_name = '%s' % psys.name
            rman_sg_particles = psys_translator.export(ob, psys, psys_db_name)
            ob_psys[psys.settings.original] = rman_sg_particles
            self.rman_particles[proto_key] = ob_psys
            rman_sg_node = self.get_rman_prototype(proto_key)
            if rman_sg_node:
                if not rman_sg_node.rman_sg_particle_group_node:
                    particles_group_db = ''
                    rman_sg_node.rman_sg_particle_group_node = group_translator.export(None, particles_group_db)
                rman_sg_node.rman_sg_particle_group_node.sg_node.AddChild(rman_sg_particles.sg_node)
        return rman_sg_particles

    def _export_hidden_instance(self, ob, rman_sg_node):
        translator = self.rman_translators.get('EMPTY')
        translator.export_transform(ob, rman_sg_node.sg_node)
        if ob.renderman.export_as_coordsys:
            self.get_root_sg_node().AddChild(rman_sg_node.sg_node)
            self.get_root_sg_node().AddCoordinateSystem(rman_sg_node.sg_node)

    def attach_material(self, ob, rman_sg_node, sg_node=None):
        mat = object_utils.get_active_material(ob)
        if mat:
            rman_sg_material = self.rman_materials.get(mat.original, None)
            if rman_sg_material and rman_sg_material.sg_node:
                if sg_node is None:
                    sg_node = rman_sg_node.sg_node
                scenegraph_utils.set_material(sg_node, rman_sg_material.sg_node, rman_sg_material, mat=mat, ob=ob)
                rman_sg_node.is_meshlight = rman_sg_material.has_meshlight

    def attach_particle_material(self, psys_settings, parent, ob, group):
        # This function should only be used by particle instancing.
        # For emitters and hair, the material attachment is done in either
        # the emitter translator or hair translator directly

        if not object_utils.is_particle_instancer(psys=None, particle_settings=psys_settings):
            return

        if psys_settings.renderman.override_instance_material:
            mat_idx = psys_settings.material - 1
            if mat_idx < len(parent.material_slots):
                mat = parent.material_slots[mat_idx].material
                rman_sg_material = self.rman_materials.get(mat.original, None)
                if rman_sg_material:
                    scenegraph_utils.set_material(group.sg_node, rman_sg_material.sg_node, rman_sg_material, mat=mat, ob=ob)
        else:
            mat = object_utils.get_active_material(ob)
            if mat:
                rman_sg_material = self.rman_materials.get(mat.original, None)
                if rman_sg_material and rman_sg_material.sg_node:
                    scenegraph_utils.set_material(group.sg_node, rman_sg_material.sg_node, rman_sg_material, mat=mat, ob=ob)
                    group.is_meshlight = rman_sg_material.has_meshlight

    def check_light_local_view(self, ob, rman_sg_node):
        if self.is_interactive and self.context.space_data:
            if not ob.visible_in_viewport_get(self.context.space_data):
                rman_sg_node.sg_node.SetHidden(1)
                return True

        return False


    def check_solo_light(self, rman_sg_node, ob):
        if not self.scene_solo_light:
            rman_sg_node.sg_node.SetHidden(ob.renderman.mute)
        else:
            rm = ob.renderman
            if not rm:
                return
            if rm.solo:
                rman_sg_node.sg_node.SetHidden(0)
            else:
                rman_sg_node.sg_node.SetHidden(1)

    def export_searchpaths(self):
        # TODO
        # RMAN_ARCHIVEPATH,
        # RMAN_DISPLAYPATH, RMAN_PROCEDURALPATH, and RMAN_DSOPATH (combines procedurals and displays)

        # get cycles shader directory
        cycles_shader_dir = filepath_utils.get_cycles_shader_path()

        RMAN_SHADERPATH = envconfig().getenv('RMAN_SHADERPATH', '')
        RMAN_TEXTUREPATH = envconfig().getenv('RMAN_TEXTUREPATH', '')
        RMAN_RIXPLUGINPATH = envconfig().getenv('RMAN_RIXPLUGINPATH', '')
        if sys.platform == ("win32"):
            # substitute ; for : in paths
            RMAN_SHADERPATH = RMAN_SHADERPATH.replace(';', ':')
            RMAN_TEXTUREPATH = RMAN_TEXTUREPATH.replace(';', ':')
            RMAN_RIXPLUGINPATH = RMAN_RIXPLUGINPATH.replace(';', ':')

        options = self.sg_scene.GetOptions()
        options.SetString(self.rman.Tokens.Rix.k_searchpath_shader, '.:%s:%s:@' % (cycles_shader_dir, RMAN_SHADERPATH))
        options.SetString(self.rman.Tokens.Rix.k_searchpath_texture, '.:%s:@' % RMAN_TEXTUREPATH)
        options.SetString(self.rman.Tokens.Rix.k_searchpath_rixplugin, '.:%s:@' % RMAN_RIXPLUGINPATH)
        options.SetString(self.rman.Tokens.Rix.k_searchpath_display, '.:@')

        self.sg_scene.SetOptions(options)

    def export_hider(self):
        options = self.sg_scene.GetOptions()
        rm = self.bl_scene.renderman
        if self.rman_bake:
            options.SetString(self.rman.Tokens.Rix.k_hider_type, self.rman.Tokens.Rix.k_bake)
            bakemode = rm.rman_bake_mode.lower()
            primvar_s = rm.rman_bake_illum_primvarS
            if primvar_s == '':
                primvar_s = 's'
            primvar_t = rm.rman_bake_illum_primvarT
            if primvar_t == '':
                primvar_t = 't'
            invert_t = rm.rman_bake_illum_invertT
            udim_stride = rm.rman_bake_illum_bakeudimstride
            udim_offset = rm.rman_bake_illum_bakeudimoffset
            bbox_min = rm.rman_bake_illum_bakebboxmin
            bbox_max = rm.rman_bake_illum_bakebboxmax
            
            options.SetString(self.rman.Tokens.Rix.k_hider_bakemode, bakemode)
            options.SetStringArray(self.rman.Tokens.Rix.k_hider_primvar, (primvar_s, primvar_t), 2) 
            options.SetInteger(self.rman.Tokens.Rix.k_hider_invert, invert_t)
            options.SetInteger(self.rman.Tokens.Rix.k_hider_bakeudimstride, udim_stride)
            options.SetInteger(self.rman.Tokens.Rix.k_hider_bakeudimoffset, udim_offset)
            options.SetPoint(self.rman.Tokens.Rix.k_hider_bakebboxmin, bbox_min)
            options.SetPoint(self.rman.Tokens.Rix.k_hider_bakebboxmax, bbox_max)
        else:
            pv = rm.ri_pixelVariance

            options.SetInteger(self.rman.Tokens.Rix.k_hider_minsamples, rm.hider_minSamples)
            options.SetInteger(self.rman.Tokens.Rix.k_hider_maxsamples, rm.hider_maxSamples)
            options.SetInteger(self.rman.Tokens.Rix.k_hider_incremental, rm.hider_incremental)

            if self.is_interactive:
                options.SetInteger(self.rman.Tokens.Rix.k_hider_decidither, rm.hider_decidither)
                options.SetInteger(self.rman.Tokens.Rix.k_hider_minsamples, rm.ipr_hider_minSamples)
                options.SetInteger(self.rman.Tokens.Rix.k_hider_maxsamples, rm.ipr_hider_maxSamples)
                pv = rm.ipr_ri_pixelVariance

            # force incremental when checkpointing
            if rm.enable_checkpoint:
                options.SetInteger(self.rman.Tokens.Rix.k_hider_incremental, 1)

            if not rm.sample_motion_blur:
                options.SetInteger(self.rman.Tokens.Rix.k_hider_samplemotion, 0)

            options.SetFloat(self.rman.Tokens.Rix.k_Ri_PixelVariance, pv)

            dspys_dict = display_utils.get_dspy_dict(self)
            anyDenoise = False
            for dspy,params in dspys_dict['displays'].items():
                if params['denoise']:
                    anyDenoise = True
                    break

        self.sg_scene.SetOptions(options)

    def export_global_options(self):
        rm = self.bl_scene.renderman
        options = self.sg_scene.GetOptions()

        # set any properties marked riopt in the config file
        for prop_name, meta in rm.prop_meta.items():
            property_utils.set_rioption_bl_prop(options, prop_name, meta, rm)

        # threads
        if not self.external_render:
            options.SetInteger(self.rman.Tokens.Rix.k_limits_threads, rm.threads)

        # pixelfilter
        # options.SetString(self.rman.Tokens.Rix.k_Ri_PixelFilterName, rm.ri_displayFilter)
        # options.SetFloatArray(self.rman.Tokens.Rix.k_Ri_PixelFilterWidth, (rm.ri_displayFilterSize[0], rm.ri_displayFilterSize[1]), 2)

        # checkpointing
        if not self.is_interactive and rm.enable_checkpoint:
            if rm.checkpoint_interval != '':
                interval_tokens = rm.checkpoint_interval.split()
                if len(interval_tokens) > 0:
                    options.SetStringArray(self.rman.Tokens.Rix.k_checkpoint_interval, interval_tokens, len(interval_tokens) )
            if rm.checkpoint_exitat != '':
                options.SetString(self.rman.Tokens.Rix.k_checkpoint_exitat, rm.checkpoint_exitat)

            options.SetInteger(self.rman.Tokens.Rix.k_checkpoint_asfinal, int(rm.checkpoint_asfinal))

        # Set frame number
        options.SetInteger(self.rman.Tokens.Rix.k_Ri_Frame, self.bl_scene.frame_current)

        # Always turn off xml stats when in interactive
        if self.is_interactive:
            options.SetInteger(self.rman.Tokens.Rix.k_statistics_level, 0)

        # Set bucket shape
        bucket_order = rm.opt_bucket_order.lower()
        bucket_orderorigin = []
        if rm.enable_checkpoint and not self.is_interactive:
            bucket_order = 'horizontal'

        elif rm.opt_bucket_order == 'spiral':
            settings = self.bl_scene.render

            if rm.opt_bucket_sprial_x <= settings.resolution_x and rm.opt_bucket_sprial_y <= settings.resolution_y:
                if rm.opt_bucket_sprial_x == -1:
                    halfX = settings.resolution_x / 2
                    bucket_orderorigin = [int(halfX), rm.opt_bucket_sprial_y]

                elif rm.opt_bucket_sprial_y == -1:
                    halfY = settings.resolution_y / 2
                    bucket_orderorigin = [rm.opt_bucket_sprial_y, int(halfY)]
                else:
                    bucket_orderorigin = [rm.opt_bucket_sprial_x, rm.opt_bucket_sprial_y]

        options.SetString(self.rman.Tokens.Rix.k_bucket_order, bucket_order)
        if bucket_orderorigin:
            options.SetFloatArray(self.rman.Tokens.Rix.k_bucket_orderorigin, bucket_orderorigin, 2)

        # Shutter
        if rm.motion_blur:
            shutter_interval = rm.shutter_angle / 360.0
            '''
            if rm.shutter_timing == 'FRAME_CENTER':
                shutter_open, shutter_close = 0 - .5 * \
                    shutter_interval, 0 + .5 * shutter_interval
            elif rm.shutter_timing == 'FRAME_CLOSE':
                shutter_open, shutter_close = 0 - shutter_interval, 0
            elif rm.shutter_timing == 'FRAME_OPEN':
                shutter_open, shutter_close = 0, shutter_interval
            '''
            shutter_open, shutter_close = 0, shutter_interval
            options.SetFloatArray(self.rman.Tokens.Rix.k_Ri_Shutter, (shutter_open, shutter_close), 2)

        # dirmaps
        dirmaps = ''
        prefs_dirmaps = get_pref('rman_tractor_dirmaps', [])
        for dirmap in prefs_dirmaps:
            d = "[ \"%s\" \"%s\" \"%s\"]" % (dirmap.zone, dirmap.from_path, dirmap.to_path)
            dirmaps += d

        for k in rfb_config['dirmaps']:
            dirmap = rfb_config['dirmaps'][k]
            d = "[ \"%s\" \"%s\" \"%s\"]" % (dirmap['zone'], dirmap['from'], dirmap['to'])
            dirmaps += d
        if dirmaps:
            options.SetString('searchpath:dirmap', dirmaps)

        # colorspace
        ocioconfig = color_manager_blender.get_config_path()
        ociocolorspacename = color_manager_blender.get_colorspace_name()
        options.SetString('user:ocioconfigpath', ocioconfig)
        options.SetString('user:ociocolorspacename', ociocolorspacename)
        options.SetInteger('user:ocioenabled', 1 if ocioconfig else 0)

        self.sg_scene.SetOptions(options)

    def export_integrator(self):
        world = self.bl_scene.world
        rm = world.renderman

        bl_integrator_node = shadergraph_utils.find_integrator_node(world)
        if bl_integrator_node:
            integrator_sg = self.rman.SGManager.RixSGShader("Integrator", bl_integrator_node.bl_label, "integrator")
            rman_sg_node = RmanSgNode(self, integrator_sg, "")
            property_utils.property_group_to_rixparams(bl_integrator_node, rman_sg_node, integrator_sg, ob=world)
        else:
            integrator_sg = self.rman.SGManager.RixSGShader("Integrator", "PxrPathTracer", "integrator")

        self.sg_scene.SetIntegrator(integrator_sg)


    def export_cameras(self, bl_cameras):

        main_cam = self.depsgraph.scene_eval.camera
        cam_translator =  self.rman_translators['CAMERA']

        if self.is_viewport_render:
            db_name = 'main_camera'
            self.main_camera = cam_translator.export(None, db_name)
            self.main_camera.sg_camera_node.SetRenderable(1)
            self.sg_scene.Root().AddChild(self.main_camera.sg_node)

            # add camera so we don't mistake it for a new obj
            if main_cam:
                self.rman_cameras[main_cam.original] = self.main_camera
        else:
            if self.is_interactive:
                main_cam = self.context.space_data.camera
            db_name = object_utils.get_db_name(main_cam)
            rman_sg_camera = cam_translator.export(main_cam, db_name)
            self.main_camera = rman_sg_camera
            if main_cam:
                self.rman_cameras[main_cam.original] = rman_sg_camera

                # resolution
                cam_translator._update_render_resolution(main_cam, self.main_camera)

            self.sg_scene.Root().AddChild(rman_sg_camera.sg_node)

        # export all other scene cameras
        for cam in bl_cameras:
            ob = cam.original
            if cam.original in self.rman_cameras:
                continue
            if cam == main_cam:
                if self.main_camera.is_transforming:
                    self.motion_steps.update(self.main_camera.motion_steps)
                continue

            db_name = object_utils.get_db_name(ob)
            rman_sg_camera = cam_translator._export_render_cam(ob, db_name)

            self.rman_cameras[cam.original] = rman_sg_camera

            self.sg_scene.Root().AddChild(rman_sg_camera.sg_node)
            self.sg_scene.Root().AddCoordinateSystem(rman_sg_camera.sg_node)

        # For now, make the main camera the 'primary' dicing camera
        self.main_camera.sg_camera_node.SetRenderable(1)
        self.sg_scene.Root().AddCoordinateSystem(self.main_camera.sg_node)

    def export_displayfilters(self):
        rm = self.bl_scene.renderman
        display_filter_names = []
        displayfilters_list = []

        world = self.bl_scene.world

        output = shadergraph_utils.find_node(world, 'RendermanDisplayfiltersOutputNode')
        if not output:
            # put in a default background color, using world color, then bail
            if not self.world_df_node:
                self.world_df_node = self.rman.SGManager.RixSGShader("DisplayFilter", "PxrBackgroundDisplayFilter", "__rman_world_df")
            params = self.world_df_node.params
            params.SetColor("backgroundColor", self.bl_scene.world.color[:3])
            self.sg_scene.SetDisplayFilter([self.world_df_node])
            return

        for bl_df_node in shadergraph_utils.find_displayfilter_nodes(world):
            if not bl_df_node.is_active:
                continue

            # don't emit stylized filters, if render_rman_stylized is false
            if bl_df_node.bl_label in rman_constants.RMAN_STYLIZED_FILTERS and not rm.render_rman_stylized:
                continue

            df_name = bl_df_node.name.replace('.', '_')

            rman_df_node = self.rman.SGManager.RixSGShader("DisplayFilter", bl_df_node.bl_label, df_name)
            rman_sg_node = RmanSgNode(self, rman_df_node, "")
            property_utils.property_group_to_rixparams(bl_df_node, rman_sg_node, rman_df_node, ob=world)
            display_filter_names.append(df_name)
            displayfilters_list.append(rman_df_node)

        if len(display_filter_names) > 1:
            df_name = "rman_displayfilter_combiner"
            df_node = self.rman.SGManager.RixSGShader("DisplayFilter", "PxrDisplayFilterCombiner", df_name)
            params = df_node.params
            params.SetDisplayFilterReferenceArray("filter", display_filter_names, len(display_filter_names))
            displayfilters_list.append(df_node)

        self.sg_scene.SetDisplayFilter(displayfilters_list)

    def export_samplefilters(self, sel_chan_name=None):
        rm = self.bl_scene.renderman
        sample_filter_names = []
        samplefilters_list = list()

        if rm.do_holdout_matte != "OFF":
            sf_node = self.rman.SGManager.RixSGShader("SampleFilter", "PxrShadowFilter", "rm_PxrShadowFilter_shadows")
            params = sf_node.params
            params.SetString("occludedAov", "occluded")
            params.SetString("unoccludedAov", "holdoutMatte")
            if rm.do_holdout_matte == "ALPHA":
                params.SetString("shadowAov", "a")
            else:
                params.SetString("shadowAov", "holdoutMatte")

            sample_filter_names.append("rm_PxrShadowFilter_shadows")
            samplefilters_list.append(sf_node)

        world = self.bl_scene.world

        for bl_sf_node in shadergraph_utils.find_samplefilter_nodes(world):
            if not bl_sf_node.is_active:
                continue
            sf_name = bl_sf_node.name.replace('.', '_')

            rman_sf_node = self.rman.SGManager.RixSGShader("SampleFilter", bl_sf_node.bl_label, sf_name)
            rman_sg_node = RmanSgNode(self, rman_sf_node, "")
            property_utils.property_group_to_rixparams(bl_sf_node, rman_sg_node, rman_sf_node, ob=world)
            sample_filter_names.append(sf_name)
            samplefilters_list.append(rman_sf_node)

        if sel_chan_name:
            sf_name = '__RMAN_VIEWPORT_CHANNEL_SELECT__'
            rman_sel_chan_node = self.rman.SGManager.RixSGShader("SampleFilter", "PxrCopyAOVSampleFilter", sf_name)
            params = rman_sel_chan_node.params
            params.SetString("readAov", sel_chan_name)
            sample_filter_names.append(sf_name)
            samplefilters_list.append(rman_sel_chan_node)


        if len(sample_filter_names) > 1:
            sf_name = "rman_samplefilter_combiner"
            sf_node = self.rman.SGManager.RixSGShader("SampleFilter", "PxrSampleFilterCombiner", sf_name)
            params = sf_node.params
            params.SetSampleFilterReferenceArray("filter", sample_filter_names, len(sample_filter_names))

            samplefilters_list.append(sf_node)

        self.sg_scene.SetSampleFilter(samplefilters_list)

    def export_bake_displays(self):
        rm = self.bl_scene.renderman
        sg_displays = []
        displaychannels = []
        display_driver = None
        cams_to_dspys = dict()

        dspys_dict = display_utils.get_dspy_dict(self)

        for chan_name, chan_params in dspys_dict['channels'].items():
            chan_type = chan_params['channelType']['value']
            chan_source = chan_params['channelSource']['value']
            chan_remap_a = chan_params['remap_a']['value']
            chan_remap_b = chan_params['remap_b']['value']
            chan_remap_c = chan_params['remap_c']['value']
            chan_exposure = chan_params['exposure']['value']
            chan_filter = chan_params['filter']['value']
            chan_statistics = chan_params['statistics']['value']
            displaychannel = self.rman.SGManager.RixSGDisplayChannel(chan_type, chan_name)
            if chan_source:
                if "lpe" in chan_source:
                    displaychannel.params.SetString(self.rman.Tokens.Rix.k_source, '%s %s' % (chan_type, chan_source))
                else:
                    displaychannel.params.SetString(self.rman.Tokens.Rix.k_source, chan_source)

            displaychannel.params.SetFloatArray("exposure", chan_exposure, 2)
            displaychannel.params.SetFloatArray("remap", [chan_remap_a, chan_remap_b, chan_remap_c], 3)

            if chan_filter != 'default':
                displaychannel.params.SetString("filter", chan_filter)
            else:
                # Use the global filter.
                # This is temporary until RixSceneGraph/riley gets fixed
                displaychannel.params.SetString("filter", rm.ri_displayFilter)
                displaychannel.params.SetFloatArray("filterwidth", rm.ri_displayFilterSize, 2)                

            if chan_statistics and chan_statistics != 'none':
                displaychannel.params.SetString("statistics", chan_statistics)
            displaychannels.append(displaychannel)

        # baking requires we only do one channel per display. So, we create a new display
        # for each channel
        for dspy,dspy_params in dspys_dict['displays'].items():
            if not dspy_params['bake_mode']:
                continue
            display_driver = dspy_params['driverNode']
            channels = (dspy_params['params']['displayChannels'])

            if not dspy_params['bake_mode']:
                # if bake is off for this aov, just render to the null display driver
                dspy_file_name = dspy_params['filePath']
                display = self.rman.SGManager.RixSGShader("Display", "null", dspy_file_name)
                channels = ','.join(channels)
                display.params.SetString("mode", channels)
                cam_dspys = cams_to_dspys.get(self.main_camera, list())
                cam_dspys.append(display)
                cams_to_dspys[self.main_camera] = cam_dspys

            else:
                for chan in channels:
                    chan_type = dspys_dict['channels'][chan]['channelType']['value']
                    if chan_type != 'color':
                        # we can only bake color channels
                        continue

                    dspy_file_name = dspy_params['filePath']
                    if rm.rman_bake_illum_filename == 'BAKEFILEATTR':
                        tokens = os.path.splitext(dspy_file_name)
                        if tokens[1] == '':
                            token_dict = {'aov': dspy}
                            dspy_file_name = string_utils.expand_string('%s.<ext>' % dspy_file_name,
                                                                        display=display_driver,
                                                                        token_dict=token_dict
                                                                        )
                    else:
                        tokens = os.path.splitext(dspy_file_name)
                        dspy_file_name = '%s.%s%s' % (tokens[0], chan, tokens[1])
                    display = self.rman.SGManager.RixSGShader("Display", display_driver, dspy_file_name)

                    dspydriver_params = dspy_params['dspyDriverParams']
                    if dspydriver_params:
                        display.params.Inherit(dspydriver_params)
                    display.params.SetString("mode", chan)

                    if display_driver in ['deepexr', 'openexr']:
                        if rm.use_metadata:
                            display_utils.export_metadata(self.bl_scene, display.params)

                    camera = dspy_params['camera']
                    if camera is None:
                        cam_dspys = cams_to_dspys.get(self.main_camera, list())
                        cam_dspys.append(display)
                        cams_to_dspys[self.main_camera] = cam_dspys
                    else:
                        #db_name = object_utils.get_db_name(camera)
                        if camera not in self.rman_cameras:
                            cam_dspys = cams_to_dspys.get(self.main_camera, list())
                            cam_dspys.append(display)
                            cams_to_dspys[self.main_camera] = cam_dspys
                        else:
                            cam_sg_node = self.rman_cameras.get(camera)
                            cam_dspys = cams_to_dspys.get(cam_sg_node, list())
                            cam_dspys.append(display)
                            cams_to_dspys[cam_sg_node] = cam_dspys

        for cam_sg_node,cam_dspys in cams_to_dspys.items():
            #cam = self.rman_cameras.get(db_name, None)
            if not cam_sg_node:
                continue
            if cam_sg_node != self.main_camera:
                cam_sg_node.sg_camera_node.SetRenderable(2)
            cam_sg_node.sg_camera_node.SetDisplay(cam_dspys)

        self.sg_scene.SetDisplayChannel(displaychannels)

    def export_displays(self):
        rm = self.bl_scene.renderman
        sg_displays = []
        displaychannels = []
        display_driver = None
        cams_to_dspys = dict()

        dspys_dict = display_utils.get_dspy_dict(self)
        for chan_name, chan_params in dspys_dict['channels'].items():
            chan_type = chan_params['channelType']['value']
            chan_source = chan_params['channelSource']['value']
            chan_remap_a = chan_params['remap_a']['value']
            chan_remap_b = chan_params['remap_b']['value']
            chan_remap_c = chan_params['remap_c']['value']
            chan_exposure = chan_params['exposure']['value']
            chan_filter = chan_params['filter']['value']
            chan_statistics = chan_params['statistics']['value']
            chan_shadowthreshold = chan_params['shadowthreshold']['value']
            if chan_type == 'float[2]':
                chan_type = self.rman.Tokens.Rix.k_float2
            displaychannel = self.rman.SGManager.RixSGDisplayChannel(chan_type, chan_name)
            if chan_source and chan_source != '':
                if "lpe" in chan_source:
                    displaychannel.params.SetString(self.rman.Tokens.Rix.k_source, '%s %s' % (chan_type, chan_source))
                else:
                    displaychannel.params.SetString(self.rman.Tokens.Rix.k_source, '%s' % (chan_source))

            displaychannel.params.SetFloatArray("exposure", chan_exposure, 2)
            displaychannel.params.SetFloatArray("remap", [chan_remap_a, chan_remap_b, chan_remap_c], 3)
            displaychannel.params.SetFloat("shadowthreshold", chan_shadowthreshold)

            if chan_filter != 'default':
                displaychannel.params.SetString("filter", chan_filter)
            else:
                # Use the global filter.
                # This is temporary until RixSceneGraph/riley gets fixed
                displaychannel.params.SetString("filter", rm.ri_displayFilter)
                displaychannel.params.SetFloatArray("filterwidth", rm.ri_displayFilterSize, 2)

            if chan_statistics and chan_statistics != 'none':
                displaychannel.params.SetString("statistics", chan_statistics)
            displaychannels.append(displaychannel)

        for dspy,dspy_params in dspys_dict['displays'].items():
            display_driver = dspy_params['driverNode']
            dspy_file_name = dspy_params['filePath']
            display = self.rman.SGManager.RixSGShader("Display", display_driver, dspy_file_name)
            channels = ','.join(dspy_params['params']['displayChannels'])
            dspydriver_params = dspy_params['dspyDriverParams']
            if dspydriver_params:
                display.params.Inherit(dspydriver_params)
            display.params.SetString("mode", channels)
            if display_driver == "it":
                dspy_info = display_utils.make_dspy_info(self.bl_scene, self.is_interactive)
                port = self.rman_render.it_port
                dspy_callback = "dspyRender"
                if self.is_interactive:
                    dspy_callback = "dspyIPR"
                display.params.SetString("dspyParams",
                                        "%s -port %d -crop 1 0 1 0 -notes %s" % (dspy_callback, port, dspy_info))

            cam_sg_node = self.main_camera
            camera = dspy_params['camera']
            if camera and camera in self.rman_cameras:
                cam_sg_node = self.rman_cameras.get(camera)

            if display_driver in ['deepexr', 'openexr']:
                is_variance = dspy_params.get('is_variance', False)
                if rm.use_metadata:
                    display_utils.export_metadata(self.bl_scene, display.params, camera_name=cam_sg_node.db_name)
                if is_variance and dspy_params['denoise'] and display.params.HasParam("asrgba"):
                    display.params.SetInteger("asrgba", 0)

            cam_dspys = cams_to_dspys.get(cam_sg_node, list())
            cam_dspys.append(display)
            cams_to_dspys[cam_sg_node] = cam_dspys

        for cam_sg_node,cam_dspys in cams_to_dspys.items():
            #cam = self.rman_cameras.get(db_name, None)
            if not cam_sg_node:
                continue
            if cam_sg_node != self.main_camera:
                cam_sg_node.sg_camera_node.SetRenderable(2)
            cam_sg_node.sg_camera_node.SetDisplay(cam_dspys)

        self.sg_scene.SetDisplayChannel(displaychannels)

    def export_stats(self):

        stats_mgr = self.rman_render.stats_mgr
        rm = self.bl_scene.renderman

        integrator = 'PxrPathTracer'
        world = self.bl_scene.world

        bl_integrator_node = shadergraph_utils.find_integrator_node(world)
        if bl_integrator_node:
            integrator = bl_integrator_node.bl_label
        stats_mgr._integrator = integrator
        #stats_mgr._minSamples = rm.hider_minSamples
        stats_mgr._maxSamples = rm.hider_maxSamples

    def export_viewport_stats(self, integrator=''):

        stats_mgr = self.rman_render.stats_mgr
        rm = self.bl_scene.renderman
        if integrator == '':
            integrator = 'PxrPathTracer'
            world = self.bl_scene.world

            bl_integrator_node = shadergraph_utils.find_integrator_node(world)
            if bl_integrator_node:
                integrator = bl_integrator_node.bl_label
        stats_mgr._integrator = integrator
        #stats_mgr._minSamples = rm.ipr_hider_minSamples
        stats_mgr._maxSamples = rm.ipr_hider_maxSamples
        stats_mgr._decidither = rm.hider_decidither
        stats_mgr._res_mult = int(self.viewport_render_res_mult*100)