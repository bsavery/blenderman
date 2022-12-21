from ..rfb_logger import rfb_log
from ..rfb_utils import shadergraph_utils
from ..rfb_utils import string_utils
from ..rfb_utils import texture_utils
from ..rfb_utils import filepath_utils
from ..rfb_utils import object_utils
from bpy.types import Operator
from bpy.props import StringProperty, FloatProperty
import os
import zipfile
import bpy
import shutil

class PRMAN_OT_Renderman_Package(Operator):
    """An operator to create a zip archive of the current scene."""

    bl_idname = "renderman.scene_package"
    bl_label = "Package Scene"
    bl_description = "Package your scene including textures into a zip file."
    bl_options = {'INTERNAL'}

    directory: StringProperty(subtype='FILE_PATH')
    filepath: StringProperty(
        subtype="FILE_PATH")

    filename: StringProperty(
        subtype="FILE_NAME",
        default="")

    filter_glob: StringProperty(
        default="*.zip",
        options={'HIDDEN'},
        )           

    @classmethod
    def poll(cls, context):
        return context.engine == "PRMAN_RENDER"

    def execute(self, context):

        if not os.access(self.directory, os.W_OK):
            self.report({"ERROR"}, "Directory is not writable")
            return {'FINISHED'}

        if not bpy.data.is_saved:            
            self.report({"ERROR"}, "Scene not saved yet.")
            return {'FINISHED'}

        z = zipfile.ZipFile(self.filepath, mode='w')

        bl_scene_file = bpy.data.filepath

        remove_files = list()
        remove_dirs = list()

        # textures
        texture_dir = os.path.join(self.directory, 'textures')
        os.mkdir(os.path.join(texture_dir))
        remove_dirs.append(texture_dir)

        # assets
        assets_dir = os.path.join(self.directory, 'assets')
        os.mkdir(os.path.join(assets_dir))
        remove_dirs.append(assets_dir)

        # osl shaders
        shaders_dir = os.path.join(self.directory, 'shaders')
        os.mkdir(os.path.join(shaders_dir))
        remove_dirs.append(shaders_dir)

        for item in context.scene.rman_txmgr_list:
            txfile = texture_utils.get_txmanager().txmanager.get_txfile_from_id(item.nodeID)
            if not txfile:
                continue
            for fpath, txitem in txfile.tex_dict.items():
                bfile = os.path.basename(fpath)
                diskpath = os.path.join(texture_dir, bfile)
                shutil.copyfile(fpath, diskpath)
                z.write(diskpath, arcname=os.path.join('textures', bfile))
                remove_files.append(diskpath)
                # Check if texture already copied
                if fpath == txitem.outfile:
                    pass
                else:
                    bfile = os.path.basename(txitem.outfile)
                    diskpath = os.path.join(texture_dir, bfile)
                    shutil.copyfile(txitem.outfile, diskpath)
                    z.write(diskpath, arcname=os.path.join('textures', bfile))
                    remove_files.append(diskpath)

        for node in shadergraph_utils.get_all_shading_nodes():
            if node.bl_label == 'PxrOSL' and getattr(node, "codetypeswitch") == "EXT":
                osl_path = string_utils.expand_string(getattr(node, 'shadercode'))
                osl_path = filepath_utils.get_real_path(osl_path)
                FileName = os.path.basename(osl_path)
                FileNameNoEXT = os.path.splitext(FileName)[0] 

                diskpath = os.path.join(shaders_dir, FileName)
                shutil.copyfile(osl_path, diskpath)
                setattr(node, 'shadercode', os.path.join('<blend_dir>', 'shaders', FileName))
                z.write(diskpath, arcname=os.path.join('shaders', FileName))
                remove_files.append(diskpath)                

            for prop_name, meta in node.prop_meta.items():
                param_type = meta['renderman_type']
                if param_type != 'string':
                    continue
                if shadergraph_utils.is_texture_property(prop_name, meta):
                    prop = getattr(node, prop_name)
                    if prop != '':
                        prop = os.path.basename(prop)
                        setattr(node, prop_name, os.path.join('<blend_dir>', 'textures', prop))
                        
                else:
                    prop = getattr(node, prop_name)
                    val = string_utils.expand_string(prop)
                    if os.path.exists(val):
                        bfile = os.path.basename(val)
                        diskpath = os.path.join(assets_dir, bfile)
                        shutil.copyfile(val, diskpath)
                        setattr(node, prop_name, os.path.join('<blend_dir>', 'assets', bfile))
                        z.write(diskpath, arcname=os.path.join('assets', bfile))
                        remove_files.append(diskpath)

        # volumes
        for db in bpy.data.volumes:
            openvdb_file = filepath_utils.get_real_path(db.filepath)
            bfile = os.path.basename(openvdb_file)
            diskpath = os.path.join(assets_dir, bfile)
            shutil.copyfile(openvdb_file, diskpath)      
            setattr(db, 'filepath', '//./assets/%s' % bfile)   
            z.write(diskpath, arcname=os.path.join('assets', bfile))               
            remove_files.append(diskpath)

        # archives etc.
        for ob in bpy.data.objects:
            rman_type = object_utils._detect_primitive_(ob)
            if rman_type == 'DELAYED_LOAD_ARCHIVE':
                rm = ob.renderman
                rib_path = string_utils.expand_string(rm.path_archive)
                bfile = os.path.basename(rib_path)
                diskpath = os.path.join(assets_dir, bfile)
                shutil.copyfile(rib_path, diskpath)  
                setattr(rm, 'path_archive', os.path.join('<blend_dir>', 'assets', bfile))
                z.write(diskpath, arcname=os.path.join('assets', bfile))
                remove_files.append(diskpath)    
            elif rman_type == 'ALEMBIC':
                rm = ob.renderman
                abc_filepath = string_utils.expand_string(rm.abc_filepath)
                bfile = os.path.basename(abc_filepath)
                diskpath = os.path.join(assets_dir, bfile)
                shutil.copyfile(abc_filepath, diskpath)  
                setattr(rm, 'abc_filepath', os.path.join('<blend_dir>', 'assets', bfile))
                z.write(diskpath, arcname=os.path.join('assets', bfile))
                remove_files.append(diskpath)   
            elif rman_type == 'BRICKMAP':  
                rm = ob.renderman
                bkm_filepath = string_utils.expand_string(rm.bkm_filepath)
                bfile = os.path.basename(bkm_filepath)
                diskpath = os.path.join(assets_dir, bfile)
                shutil.copyfile(bkm_filepath, diskpath)  
                setattr(rm, 'bkm_filepath', os.path.join('<blend_dir>', 'assets', bfile))
                z.write(diskpath, arcname=os.path.join('assets', bfile))
                remove_files.append(diskpath)                                
                                          
                            
        bl_filepath = os.path.dirname(bl_scene_file)
        bl_filename = os.path.basename(bl_scene_file)
        bl_filepath = os.path.join(self.directory, bl_filename)
        bpy.ops.wm.save_as_mainfile(filepath=bl_filepath, copy=True)
        remove_files.append(bl_filepath)       

        z.write(bl_filepath, arcname=bl_filename)
        z.close()
		
		# Try to remove the temporary files and directories
        for f in remove_files:
            try:
                os.remove(f)
            except:
                continue

        for d in remove_dirs:
            try:
                os.removedirs(d)
            except:
                continue            

        bpy.ops.wm.revert_mainfile()

        return {'FINISHED'}

    def invoke(self, context, event=None):
        bl_scene_file = bpy.data.filepath
        bl_filename = os.path.splitext(os.path.basename(bl_scene_file))[0]
        self.properties.filename = '%s.zip' % bl_filename
        context.window_manager.fileselect_add(self)
        return{'RUNNING_MODAL'} 

class PRMAN_OT_Renderman_Start_Debug_Server(bpy.types.Operator):
    bl_idname = "renderman.start_debug_server"
    bl_label = "Start Debug Server"
    bl_description = "Start the debug server. This requires the debugpy module."
    bl_options = {'INTERNAL'}

    max_timeout: FloatProperty(default=120.0)
    num_seconds: FloatProperty(default=0.0)
    debugpy = None

    @classmethod
    def poll(cls, context):
        if context.engine != "PRMAN_RENDER":
            return False
        
        if cls.debugpy and cls.debugpy.is_client_connected():
            return False
            
        return True

    # call check_done
    def modal(self, context, event):
        if event.type == "TIMER":
            if not self.__class__.debugpy.is_client_connected():
                if self.properties.num_seconds >= self.properties.max_timeout:
                    self.report({'INFO'}, 'Max timeout reached. Aborting...')
                    return {'FINISHED'}
                self.report({'INFO'}, 'Still waiting...')
                self.properties.num_seconds += 0.1
                return {'RUNNING_MODAL'}
            else:
                self.report({'INFO'}, 'Debugger attached.')
                return {'FINISHED'}
        
        return {'RUNNING_MODAL'}

    def execute(self, context):
        self.report({'INFO'}, 'Debugger attached.')
        return {"FINISHED"}       

    def invoke(self, context, event):
        cls = self.__class__
        if not cls.debugpy:
            try:
                import debugpy

            except ModuleNotFoundError:
                self.report({'ERROR'}, 'Cannot import debugpy module.')
                return {'FINISHED'}

            try:
                debugpy.listen(("localhost", 5678))
                cls.debugpy = debugpy
                self.report({'INFO'}, 'debugpy started!')
            except:
                self.report({'ERROR'}, 'debugpy already running!')
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)        
        context.window_manager.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}

class PRMAN_OT_Renderman_Open_Addon_Preferences(bpy.types.Operator):
    bl_idname = "renderman.open_addon_preferences"
    bl_label = "Addon Preferences"
    bl_description = "Open the RenderMan for Blender addon prferences"
    bl_options = {'INTERNAL'}


    @classmethod
    def poll(cls, context):
        return context.engine == "PRMAN_RENDER"

    def execute(self, context):
        context.preferences.active_section = 'ADDONS'
        context.window_manager.addon_search = 'RenderMan For Blender'
        bpy.ops.screen.userpref_show()
        return {"FINISHED"}       

classes = [
   PRMAN_OT_Renderman_Package,
   PRMAN_OT_Renderman_Start_Debug_Server,
   PRMAN_OT_Renderman_Open_Addon_Preferences
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():

    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            rfb_log().debug('Could not unregister class: %s' % str(cls))
            pass