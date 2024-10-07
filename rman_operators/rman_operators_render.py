from ..rfb_utils import filepath_utils
from ..rman_render import RmanRender
from ..rfb_logger import rfb_log
import bpy
import os
import time
import shutil
import webbrowser

class PRMAN_OT_Renderman_Use_Renderman(bpy.types.Operator):
    bl_idname = "renderman.use_renderman"
    bl_label = "Use RenderMan"
    bl_description = "Switch render engine to RenderMan"
            
    def execute(self, context):
        rd = context.scene.render
        if rd.engine != 'PRMAN_RENDER':
            rd.engine = 'PRMAN_RENDER'

        return {'FINISHED'}

class PRMAN_OT_RendermanBake(bpy.types.Operator):
    bl_idname = "renderman.bake"
    bl_label = "Baking"
    bl_description = "Bake pattern nodes and/or illumination to 2D and 3D formats."
    bl_options = {'INTERNAL'}    
            
    def execute(self, context):

        scene = context.scene
        rm = scene.renderman
        if not rm.is_rman_interactive_running:
            scene.renderman.hider_type = 'BAKE'
            try:
                bpy.ops.render.render(layer=context.view_layer.name)
            except:
                pass
            scene.renderman.hider_type = 'RAYTRACE'
        else:
            self.report({"ERROR"}, "Viewport rendering is on.")        
        return {'FINISHED'}

class PRMAN_OT_RendermanBakeSelectedBrickmap(bpy.types.Operator):
    bl_idname = "renderman.bake_selected_brickmap"
    bl_label = "Bake to Brickmap"
    bl_description = "Bake to Brickmap"
    bl_options = {'INTERNAL'}    

    filepath: bpy.props.StringProperty(
        subtype="FILE_PATH")

    filename: bpy.props.StringProperty(
        subtype="FILE_NAME",
        default="")

    filter_glob: bpy.props.StringProperty(
        default="*.ptc",
        options={'HIDDEN'},
        )        


    @classmethod
    def poll(cls, context):
        return context.object is not None
            
    def execute(self, context):

        scene = context.scene
        rm = scene.renderman
        if not rm.is_rman_interactive_running:
            ob = context.object
            fp = filepath_utils.get_real_path(self.properties.filepath)
            fp = os.path.splitext(fp)[0]

            org_bake_filename_attr = ob.renderman.bake_filename_attr
            org_bake_illum_mode = scene.renderman.rman_bake_illum_mode
            org_bake_mode = scene.renderman.rman_bake_mode
            org_bake_illum_filename = scene.renderman.rman_bake_illum_filename
            scene.renderman.hider_type = 'BAKE_BRICKMAP_SELECTED'
            scene.renderman.rman_bake_mode = 'integrator'
            ob.renderman.bake_filename_attr = fp
            try:
                bpy.ops.render.render(layer=context.view_layer.name)
            except:
                pass
            scene.renderman.hider_type = 'RAYTRACE'
            scene.renderman.rman_bake_mode = org_bake_mode
        else:
            self.report({"ERROR"}, "Viewport rendering is on.")        
        return {'FINISHED'}        

    def invoke(self, context, event=None):
        ob = context.object
        self.properties.filename = '%s.<F4>.ptc' % ob.name
        context.window_manager.fileselect_add(self)
        return{'RUNNING_MODAL'}         

class PRMAN_OT_BatchRendermanBake(bpy.types.Operator):
    bl_idname = "renderman.batch_bake_render"
    bl_label = "Batch Baking"
    bl_description = "Spool a batch bake render."
    bl_options = {'INTERNAL'}    
            
    def execute(self, context):

        scene = context.scene
        rm = scene.renderman        
        if not rm.is_rman_interactive_running:
            scene.renderman.hider_type = 'BAKE'
            scene.renderman.enable_external_rendering = True
            try:
                for view_layer in scene.view_layers:
                    if view_layer.use:
                        bpy.ops.render.render(layer=view_layer.name)
            except:
                pass
            scene.renderman.hider_type = 'RAYTRACE'
            scene.renderman.enable_external_rendering = False
        else:
            self.report({"ERROR"}, "Viewport rendering is on.")        
        return {'FINISHED'}


class PRMAN_OT_BatchRender(bpy.types.Operator):

    ''''''
    bl_idname = "renderman.batch_render"
    bl_label = "Batch Render"
    bl_description = "Launch a spooled batch render."
    bl_options = {'INTERNAL'}    

    def blender_batch_render(self, context):
        rm = context.scene.renderman
        if rm.queuing_system != 'none':
            from .. import rman_spool
            
            depsgraph = context.evaluated_depsgraph_get()

            # FIXME: we should move all of this into
            # rman_render.py
            rr = RmanRender.get_rman_render()
            rr.rman_scene.bl_scene = depsgraph.scene_eval
            rr.rman_scene.bl_view_layer = depsgraph.view_layer
            rr.rman_scene.bl_frame_current = rr.rman_scene.bl_scene.frame_current
            rr.rman_scene._find_renderman_layer()
            rr.rman_scene.external_render = True
            spooler = rman_spool.RmanSpool(rr, rr.rman_scene, depsgraph)

            bl_scene_file = bpy.data.filepath
            pid = os.getpid()
            timestamp = int(time.time())
            _id = 'pid%s_%d' % (str(pid), timestamp)
            bl_filepath = os.path.dirname(bl_scene_file)
            bl_filename = os.path.splitext(os.path.basename(bl_scene_file))[0]
            bl_cache_dir = os.path.join(bl_filepath, 'blendcache_%s' % bl_filename)

            # cache out any dynamics
            bpy.ops.ptcache.bake_all(bake=True)
            
            # create a temporary .blend file
               

            # set blend_token to the real filename
            rm.blend_token = bl_filename
            bl_stash_name = '_%s%s_' % (bl_filename, _id)
            bl_stash_scene_file = os.path.join(bl_filepath, '%s.blend' % (bl_stash_name))

            # copy the blend cache to the stash scene name
            bl_stash_blend_cache = ""
            if os.path.exists(bl_cache_dir):
                bl_stash_blend_cache = os.path.join(bl_filepath, 'blendcache_%s' % bl_stash_name)
                shutil.copytree(bl_cache_dir, bl_stash_blend_cache)

            bpy.ops.wm.save_as_mainfile(filepath=bl_stash_scene_file, copy=True)
            spooler.blender_batch_render(bl_stash_scene_file, bl_stash_blend_cache=bl_stash_blend_cache)
            # now reset the token back
            rm.blend_token = ''
        else:
            self.report({'ERROR'}, 'Queuing system set to none')       

    def rib_batch_render(self, context):
        scene = context.scene
        rm = scene.renderman
        if not rm.is_rman_interactive_running:
            # cache out any dynamics
            bpy.ops.ptcache.bake_all(bake=True)
            
            scene.renderman.enable_external_rendering = True        
            try:
                for view_layer in scene.view_layers:
                    if view_layer.use:
                        bpy.ops.render.render(layer=view_layer.name)
            except:
                pass
            scene.renderman.enable_external_rendering = False
        else:
            self.report({"ERROR"}, "Viewport rendering is on.")           

    def execute(self, context):
        scene = context.scene
        rm = scene.renderman
        if not rm.is_rman_interactive_running:
            if scene.renderman.spool_style == 'rib':
                self.rib_batch_render(context)       
            else:
                self.blender_batch_render(context)
        else:
            self.report({"ERROR"}, "Viewport rendering is on.")              
        return {'FINISHED'}        

class PRMAN_OT_StartInteractive(bpy.types.Operator):

    ''''''
    bl_idname = "renderman.start_ipr"
    bl_label = "Start Interactive Rendering"
    bl_description = "Start IPR and render to the viewport"
    bl_options = {'INTERNAL'}    

    render_to_it: bpy.props.BoolProperty(default=False)

    @classmethod
    def description(cls, context, properties): 
        if properties.render_to_it:
            return "Start IPR and render to 'it'"
        return cls.bl_description

    def invoke(self, context, event=None):
        scene = context.scene
        if self.render_to_it:
            rr = RmanRender.get_rman_render()
            rr.rman_scene.ipr_render_into = 'it'            
            depsgraph = context.evaluated_depsgraph_get()
            rr.start_interactive_render(context, depsgraph)
        else:
            view = context.space_data
            if view and view.shading.type != 'RENDERED':        
                rr = RmanRender.get_rman_render()
                rr.rman_scene.ipr_render_into = 'blender'
                view.shading.type = 'RENDERED'

        return {'FINISHED'}

class PRMAN_OT_StopInteractive(bpy.types.Operator):

    ''''''
    bl_idname = "renderman.stop_ipr"
    bl_label = "Stop Interactive Rendering"
    bl_description = "Stop Interactive Rendering"
    bl_options = {'INTERNAL'}    

    def invoke(self, context, event=None):
        scene = context.scene
        rr = RmanRender.get_rman_render()
        if rr.is_ipr_to_it():            
            rr.stop_render(stop_draw_thread=False)
        elif context.space_data.type == 'VIEW_3D':
            context.space_data.shading.type = 'SOLID'
        else:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                if space.shading.type == 'RENDERED':    
                                    space.shading.type = 'SOLID'

        return {'FINISHED'}

class PRMAN_OT_StopRender(bpy.types.Operator):
    ''''''
    bl_idname = "renderman.stop_render"
    bl_label = "Stop Render"
    bl_description = "Stop the current render."
    bl_options = {'INTERNAL'}

    def invoke(self, context, event=None):
        rm = context.scene.renderman      
        if rm.is_rman_running:  
            rr = RmanRender.get_rman_render()   
            rr.del_bl_engine()

        return {'FINISHED'}

class PRMAN_OT_AttachStatsRender(bpy.types.Operator):

    ''''''
    bl_idname = "renderman.attach_stats_render"
    bl_label = "Attach Stats Listener"
    bl_description = "Attach the stats listener to the renderer"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event=None):

        rr = RmanRender.get_rman_render()
        rr.stats_mgr.attach()
        return {'FINISHED'}      

class PRMAN_OT_DisconnectStatsRender(bpy.types.Operator):

    ''''''
    bl_idname = "renderman.disconnect_stats_render"
    bl_label = "Disconnect Stats Listener"
    bl_description = "Disconnect the stats listener from the renderer. This shouldn't need to be done in most circumstances. Disconnecting can cause error-proned behavior."
    bl_options = {'INTERNAL'}

    def invoke(self, context, event=None):

        rr = RmanRender.get_rman_render()
        rr.stats_mgr.disconnect()
        return {'FINISHED'}                 

class PRMAN_OT_UpdateStatsConfig(bpy.types.Operator):

    ''''''
    bl_idname = "renderman.update_stats_config"
    bl_label = "Update Config"
    bl_description = "Update the current stats configuration"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event=None):

        rr = RmanRender.get_rman_render()
        bpy.ops.wm.save_userpref()         
        rr.stats_mgr.update_session_config()
        return {'FINISHED'}            

class PRMAN_OT_Renderman_Launch_Webbrowser(bpy.types.Operator):

    ''''''
    bl_idname = "renderman.launch_webbrowser"
    bl_label = ""
    bl_description = ""
    bl_options = {'INTERNAL'}

    url: bpy.props.StringProperty(name="URL", default='')

    def invoke(self, context, event=None):
        try:
            webbrowser.open(self.url)
        except Exception as e:
            rfb_log().error("Failed to open URL: %s" % str(e))    
        return {'FINISHED'}        

classes = [
    PRMAN_OT_Renderman_Use_Renderman,
    PRMAN_OT_RendermanBake,
    PRMAN_OT_RendermanBakeSelectedBrickmap,
    PRMAN_OT_BatchRendermanBake,
    PRMAN_OT_BatchRender,
    PRMAN_OT_StartInteractive,
    PRMAN_OT_StopInteractive,
    PRMAN_OT_StopRender,
    PRMAN_OT_AttachStatsRender,
    PRMAN_OT_DisconnectStatsRender,
    PRMAN_OT_UpdateStatsConfig,
    PRMAN_OT_Renderman_Launch_Webbrowser
]

def register():
    from ..rfb_utils import register_utils

    register_utils.rman_register_classes(classes)
    
def unregister():
    from ..rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes)       