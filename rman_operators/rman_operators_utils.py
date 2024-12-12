from ..rfb_logger import rfb_log
from ..rfb_utils import shadergraph_utils
from ..rfb_utils import string_utils
from ..rfb_utils import texture_utils
from ..rfb_utils import filepath_utils
from ..rfb_utils import object_utils
from ..rfb_utils import upgrade_utils
from ..rfb_utils import scene_utils
from ..rfb_utils.envconfig_utils import envconfig
from .. import rman_constants
from bpy.types import Operator
from bpy.props import StringProperty, FloatProperty, BoolProperty
import os
import zipfile
import bpy
import shutil
import time

class PRMAN_OT_Renderman_Upgrade_Scene(Operator):
    """An operator to upgrade the scene to the current version of RenderMan."""

    bl_idname = "renderman.upgrade_scene"
    bl_label = "Upgrade Scene"
    bl_description = "Upgrade your scene to the current version"
    bl_options = {'INTERNAL'}
  
    @classmethod
    def poll(cls, context):
        if context.engine != "PRMAN_RENDER":
            return False

        scene = context.scene
        version = scene.renderman.renderman_version
        if version == '':
            return True
        
        if version < rman_constants.RMAN_SUPPORTED_VERSION_STRING:
            return True
            
        return False

    def execute(self, context):
        upgrade_utils.upgrade_scene(None)
        return {'FINISHED'}

class PRMAN_OT_Renderman_Package(Operator):
    """An operator to create a zip archive of the current scene."""

    bl_idname = "renderman.scene_package"
    bl_label = "Package Scene"
    bl_description = "Package your scene including textures into a zip file. The directory you choose should be empty."
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
    
    use_tex: BoolProperty(
        name="Use RenderMan Textures",
        default=False,
        description="Substitute all textures with the .tex version in the paths before packaging"
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
        
        # check if the directory is not empty
        with os.scandir(self.directory) as f:
            if any(f):
                self.report({"ERROR"}, "The selected directory is not empty")
                return {'FINISHED'}            

        z = zipfile.ZipFile(self.filepath, mode='w')

        bl_scene_file = bpy.data.filepath

        remove_files = list()
        remove_dirs = list()

        bl_original_filepath = os.path.dirname(bl_scene_file)
        bl_filename = os.path.basename(bl_scene_file)
        bl_filepath = os.path.join(self.directory, bl_filename)        

        # deal with libraries
        # bpy.ops.file.pack_libraries() # comment out for now. May need it later on.
        for lib in bpy.data.libraries:
            real_path = filepath_utils.get_real_path(lib.filepath)
            if not lib.filepath.startswith('//'):
                self.report({'ERROR'}, "We currently only support library files that are relative to the main Blend scene.")
                z.close()
                try:
                    os.remove(self.filepath)
                except:
                    rfb_log().debug("Cannot remove: %s" % self.filepath)
                    pass
                return {'FINISHED'}
            subdir = os.path.dirname(lib.filepath).replace('//', '', 1)
            dst_path = os.path.join(self.directory, subdir)
            shutil.copytree(os.path.dirname(real_path), dst_path)

        # get all directories and files that were copied from the libraries
        for root, dirnames, files in os.walk(self.directory):
            for d in dirnames:
                dst_path = os.path.join(root, d)
                if dst_path == self.directory:
                    continue
                if dst_path not in remove_dirs:
                    remove_dirs.append(dst_path)        
            for f in files:
                fpath = os.path.relpath(os.path.join(root, f), self.directory)
                diskpath = os.path.join(root, f)
                if diskpath == self.filepath:
                    continue                
                if diskpath not in remove_files:
                    z.write(diskpath, arcname=fpath)
                    remove_files.append(diskpath)

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

        # check for OCIO
        OCIO = envconfig().getenv('OCIO', default=None)
        if OCIO and envconfig().rmantree not in OCIO:
            ocio_config_file = os.environ['OCIO']
            ocio_config_path = os.path.dirname(ocio_config_file)
            ocio_assets_dir = os.path.join(assets_dir, 'ocio', os.path.basename(ocio_config_path))
            shutil.copytree(ocio_config_path, ocio_assets_dir)
            for root, dirnames, files in os.walk(ocio_assets_dir):
                for d in dirnames:
                    dst_path = os.path.join(root, d)
                    if dst_path not in remove_dirs:
                        remove_dirs.append(dst_path)        
                for f in files:
                    fpath = os.path.relpath(os.path.join(root, f), self.directory)
                    diskpath = os.path.join(root, f)             
                    if diskpath not in remove_files:
                        z.write(diskpath, arcname=fpath)
                        remove_files.append(diskpath)            

        # re-parse the scene and make sure all textures have been txmake'd
        texture_utils.get_txmanager().txmanager.flush_queue()
        texture_utils.parse_scene_for_textures(bl_scene=context.scene)
        texture_utils.get_txmanager().txmake_all(blocking=True)
        # for some reason, blocking doesn't seem to work? Just loop for now until we're done
        while not texture_utils.get_txmanager().txmanager.all_textures_available():
            time.sleep(0.1)

        for item in context.scene.rman_txmgr_list:
            txfile = texture_utils.get_txmanager().txmanager.get_txfile_from_id(item.nodeID)
            if not txfile:
                continue
            for fpath, txitem in txfile.tex_dict.items():
                bfile = os.path.basename(fpath)
                diskpath = os.path.join(texture_dir, bfile)
                if not os.path.exists(diskpath):
                    shutil.copy2(fpath, diskpath)
                    z.write(diskpath, arcname=os.path.join('textures', bfile))
                    remove_files.append(diskpath)
                # Check if .tex already copied - agentyRANCH
                # - when .tex directly specified in texture
                if fpath == txitem.outfile:
                    continue
                bfile = os.path.basename(txitem.outfile)
                diskpath = os.path.join(texture_dir, bfile)
                if not os.path.exists(diskpath):
                    shutil.copy2(txitem.outfile, diskpath)
                    z.write(diskpath, arcname=os.path.join('textures', bfile))
                    remove_files.append(diskpath)
                  
        token_dict = {'blender': bl_filename, 'blend_dir': self.directory}
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
                        colorspace_nm = '%s_colorspace' % prop_name
                        colorspace = getattr(node, colorspace_nm, None)                        
                        if self.use_tex:
                            ob = scene_utils.find_node_owner(node, context)
                            txfile = texture_utils.get_txmanager().get_txfile(node, prop_name, ob=ob)  
                            if txfile:
                                if colorspace and not txfile.source_is_tex():
                                    # check the colorspace
                                    params = txfile.params.as_dict()   
                                    texture_utils.update_txfile_colorspace(txfile, colorspace, blocking=True)                           
                                texpath = txfile.get_output_texture()
                                texpath = string_utils.expand_string(texpath, asFilePath=None) 
                                texfile = os.path.basename(texpath)
                                node[prop_name] = os.path.join('<blend_dir>', 'textures', texfile)
                                
                                # double check the tex file has been copied. 
                                diskpath = os.path.join(texture_dir, texfile)
                                if not os.path.exists(diskpath):
                                    shutil.copy2(texpath, diskpath)
                                    z.write(diskpath, arcname=os.path.join('textures', texfile))
                                    remove_files.append(diskpath)                                

                                continue

                        node[prop_name] = os.path.join('<blend_dir>', 'textures', prop)
                        if colorspace:
                            # we need to set the colorspace again, since we've changed the path to the texture
                            setattr(node, colorspace_nm, colorspace)                        
                else:
                    prop = getattr(node, prop_name)
                    val = string_utils.expand_string(prop)
                    if os.path.exists(val):
                        bfile = os.path.basename(val)
                        diskpath = os.path.join(assets_dir, bfile)
                        setattr(node, prop_name, os.path.join('<blend_dir>', 'assets', bfile))
                        # Check if file already copied - agentyRANCH
                        #(avoid z.write creating multiple instances of same file) 
                        if os.path.exists(diskpath):
                            continue
                        shutil.copyfile(val, diskpath)
                        z.write(diskpath, arcname=os.path.join('assets', bfile))
                        remove_files.append(diskpath)

        # volumes
        for db in bpy.data.volumes:
            openvdb_file = filepath_utils.get_real_path(db.filepath)
            bfile = os.path.basename(openvdb_file)
            diskpath = os.path.join(assets_dir, bfile)
            shutil.copyfile(openvdb_file, diskpath)      
            #setattr(db, 'filepath', '//./assets/%s' % bfile)  - agentyRANCH
            setattr(db, 'filepath', '//assets/%s' % bfile)            
            z.write(diskpath, arcname=os.path.join('assets', bfile))               
            remove_files.append(diskpath)
            
        # Caches #  - agentyRANCH
        # https://docs.blender.org/manual/fr/dev/animation/constraints/transform/transform_cache.html
        for cache in bpy.data.cache_files:
            # Change get_real_path with filesystem_path  - agentyRANCH
            # (resolve blender relative path for shutil)
            cache_file = filepath_utils.filesystem_path(cache.filepath)
            bfile = os.path.basename(cache_file)
            diskpath = os.path.join(assets_dir, bfile)
            shutil.copyfile(cache_file, diskpath)      
            setattr(cache, 'filepath', '//assets/%s' % bfile)            
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

        # Set all output paths to default.
        scene_utils.reset_workspace(context.scene) 
                                                                      
        # Add  relative_remap=False  to avoid //..\ - agentyRANCH
        bpy.ops.wm.save_as_mainfile(filepath=bl_filepath, copy=True, compress=False, relative_remap=False)
        remove_files.append(bl_filepath)

        z.write(bl_filepath, arcname=bl_filename)
        z.close()

        # Try to remove the temporary files and directories - agentyRANCH
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
    
class PRMAN_OT_Renderman_Zip_Addon(Operator):
    """An operator to create a zip archive of the current version of the addon."""

    bl_idname = "renderman.rfb_zip_addon"
    bl_label = "Zip Addon"
    bl_description = "Create a zip archive of the addon. This might be useful if you made changes the code and want to share."   
    bl_options = {'INTERNAL'}

    directory: StringProperty(subtype='FILE_PATH')
    filter_folder: BoolProperty(
        default=True,
        options={"HIDDEN"}
        )   

    @classmethod
    def poll(cls, context):
        return context.engine == "PRMAN_RENDER"

    def execute(self, context):

        if not os.access(self.directory, os.W_OK):
            self.report({"ERROR"}, "Directory is not writable")
            return {'FINISHED'}     

        rfb_addon = rman_constants.RFB_ADDON_PATH
        rfb_zip = os.path.join(self.properties.directory, 'RenderManForBlender.zip')
        if os.path.exists(rfb_zip):
            os.remove(rfb_zip)

        z = zipfile.ZipFile(rfb_zip, mode='w')

        # get all directories and files in the addon path
        for root, dirnames, files in os.walk(rfb_addon): 
            if '.git' in root:
                continue  
            for f in files:
                if f in ['.DS_Store']:
                    continue
                if os.path.splitext(f)[-1] in ['.pyc']:
                    continue
                fpath = os.path.relpath(os.path.join(root, f), rfb_addon)
                diskpath = os.path.join(root, f)             
                z.write(diskpath, arcname=os.path.join('RenderManForBlender', fpath))                  

        z.close()

        return {'FINISHED'}

    def invoke(self, context, event=None):
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
    
class PRMAN_OT_Renderman_Run_Unit_Tests(bpy.types.Operator):
    bl_idname = "renderman.run_unit_tests"
    bl_label = "Run Unit Tests"
    bl_description = "Run unit tests"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return (context.engine == "PRMAN_RENDER")

    def execute(self, context):
        from .. import rfb_unittests
        msg = rfb_unittests.run_rfb_unittests()
        if msg is None:
            self.report({'INFO'}, 'All tests passed')
        else:
            self.report({'ERROR'}, msg)

        return {"FINISHED"}        

classes = [
   PRMAN_OT_Renderman_Upgrade_Scene,
   PRMAN_OT_Renderman_Package,
   PRMAN_OT_Renderman_Start_Debug_Server,
   PRMAN_OT_Renderman_Run_Unit_Tests,
   PRMAN_OT_Renderman_Zip_Addon
]

def register():
    from ..rfb_utils import register_utils

    register_utils.rman_register_classes(classes)

def unregister():
    from ..rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes)
