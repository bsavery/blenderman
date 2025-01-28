import bpy
from bpy.props import StringProperty, IntProperty, CollectionProperty, EnumProperty, BoolProperty, FloatProperty
from bpy.types import PropertyGroup, UIList, Operator, Panel
from bpy_extras.io_utils import ImportHelper
from .rman_ui_base import _RManPanelHeader
from ..rfb_utils import texture_utils
from ..rfb_utils import shadergraph_utils
from ..rfb_utils import scene_utils
from ..rfb_utils import object_utils
from ..rfb_utils.prefs_utils import get_pref, using_qt
from ..rfb_logger import rfb_log
from ..rman_config import __RFB_CONFIG_DICT__ as rfb_config
from ..rman_constants import RFB_HELP_URL
from .. import rman_render
from rman_utils.txmanager import txparams
from rman_utils import txmanager as txmngr
from .. import rfb_icons
import sys
import hashlib
import os
import uuid

__TXMANAGER_WINDOW__ = None 

if not bpy.app.background:
    try:
        from ..rman_ui import rfb_qt
    except:
        rfb_qt = None

    if rfb_qt:
        class TxManagerQtAppTimed(rfb_qt.RfbBaseQtAppTimed):
            bl_idname = "wm.txm_qt_app_timed"
            bl_label = "Texture Manager"

            def __init__(self):
                super(TxManagerQtAppTimed, self).__init__()

            def execute(self, context):
                self._window = create_widget()
                return super(TxManagerQtAppTimed, self).execute(context)

        def parse_scene():
            from ..rfb_utils import texture_utils
            bl_scene = bpy.context.scene
            mgr = texture_utils.get_txmanager().txmanager
            mgr.reset()
            texture_utils.parse_for_textures(bl_scene)

        def _append_to_tx_list(file_path_list):
            """Called by the txmanager when extra files are added to the scene list.
            """
            from ..rfb_utils import texture_utils
            bl_scene = bpy.context.scene
            txmgr = texture_utils.get_txmanager().txmanager
            texture_utils.parse_for_textures(bl_scene)    
            for fpath in file_path_list:
                # Pass None as the nodeID and a hash will be generated.
                texid = hashlib.sha1(fpath.encode('utf-8')).hexdigest()
                txmgr.add_texture(texid, fpath)
            txmgr.update_ui_list()
            # make sure to restart the queue.
            txmgr.txmake_all(start_queue=True, blocking=False)   

        def help_func(url):
            bpy.ops.wm.url_open(url = RFB_HELP_URL)

        def create_widget():
            global __TXMANAGER_WINDOW__
            if not __TXMANAGER_WINDOW__:
                import rman_utils.txmanager.ui as rui    
                from ..rfb_utils import texture_utils    
                mgr = texture_utils.get_txmanager().txmanager
                __TXMANAGER_WINDOW__ = rui.TxManagerUI(None, txmanager=mgr, 
                                                        parse_scene_func=parse_scene,
                                                        append_tx_func=_append_to_tx_list,
                                                        help_func=help_func)
                mgr.ui = __TXMANAGER_WINDOW__
            return __TXMANAGER_WINDOW__
    
class TxFileItem(PropertyGroup):
    """UIList item representing a TxFile"""

    name: StringProperty(
           name="Name",
           description="Image name",
           default="")

    tooltip: StringProperty(
           name="tooltip",
           description="Tool Tip",
           default="")

    nodeID: StringProperty(
            name="nodeID",
            description="Node ID (hidden)",
            default="")

    state: IntProperty(
            name="state",
            description="",
            default=0
            )

    enable: BoolProperty(
            name="enable",
            description="Enable or disable this TxFileItem",
            default=True
            )

    def colorspace_names(self, context):
        items = []
        items.append(('0', '', ''))
        try:
            mdict = texture_utils.get_txmanager().txmanager.color_manager.colorspace_names()
            for nm in mdict:
                items.append((nm, nm, ""))
        except AttributeError:
            pass
        return items

    ocioconvert: EnumProperty(
            name="Color Space",
            description="colorspace",
            items=colorspace_names
            )

    txsettings = ['texture_type', 
                  's_mode', 
                  't_mode', 
                  'texture_format',
                  'data_type',
                  'resize',
                  'ocioconvert']

    items = []
    for item in txparams.TX_TYPES:
        items.append((item, item, ''))        

    texture_type: EnumProperty(
           name="Texture Type",
           items=items,
           description="Texture Type",
           default=txparams.TX_TYPE_REGULAR)           

    items = []
    for item in txparams.TX_WRAP_MODES:
        items.append((item, item, ''))           

    s_mode: EnumProperty(
        name="S Wrap",
        items=items,
        default=txparams.TX_WRAP_MODE_PERIODIC)

    t_mode: EnumProperty(
        name="T Wrap",
        items=items,
        default=txparams.TX_WRAP_MODE_PERIODIC)       

    items = []
    for item in txparams.TX_FORMATS:
        items.append((item, item, ''))

    texture_format: EnumProperty(
              name="Format", 
              default=txparams.TX_FORMAT_PIXAR,
              items=items,
              description="Texture format")

    items = []
    items.append(('default', 'default', ''))
    for item in txparams.TX_DATATYPES:
        items.append((item, item, ''))

    data_type: EnumProperty(
            name="Data Type",
            default=txparams.TX_DATATYPE_FLOAT,
            items=items,
            description="The data storage txmake uses")

    items = []
    for item in txparams.TX_RESIZES:
        items.append((item, item, ''))

    resize: EnumProperty(
            name="Resize",
            default=txparams.TX_RESIZE_UP_DASH,
            items=items,
            description="The type of resizing flag to pass to txmake")

    bumpRough: EnumProperty(
            name="Bump Rough",
            default="-1",
            items=(
                ("-1", "Off", ""),
                ("0", "Bump Map", ""),
                ("1", "Normal Map", "")
            )
    )
    bumpRough_factor: FloatProperty(
            name="Scale",
            default=2.0
    )

    bumpRough_invert: BoolProperty(
            name="Invert",
            default=False
    )

    bumpRough_invertU: BoolProperty(
            name="InvertU",
            default=False
    )    
    bumpRough_invertV: BoolProperty(
            name="InvertV",
            default=False
    )    
    bumpRough_refit: BoolProperty(
            name="Refit",
            default=False
    )    

class PRMAN_UL_Renderman_txmanager_list(UIList):
    """RenderMan TxManager UIList."""

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):

        icons_map = {txmngr.STATE_MISSING: 'ERROR',
                    txmngr.STATE_EXISTS: 'CHECKBOX_HLT',
                    txmngr.STATE_IS_TEX: 'TEXTURE',
                    txmngr.STATE_IN_QUEUE: 'PLUS',
                    txmngr.STATE_PROCESSING: 'TIME',
                    txmngr.STATE_ERROR: 'CANCEL',
                    txmngr.STATE_REPROCESS: 'TIME',
                    txmngr.STATE_UNKNOWN: 'CANCEL',
                    txmngr.STATE_INPUT_MISSING: 'ERROR'}
        

        txfile = None
        if item.nodeID != "":
            txfile = texture_utils.get_txmanager().txmanager.get_txfile_from_id(item.nodeID)

        if txfile:
            custom_icon = icons_map[txfile.state]
        else:
            custom_icon = 'CANCEL'

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=item.name, icon = custom_icon)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon = custom_icon)


class PRMAN_OT_Renderman_txmanager_parse_scene(Operator):
    """Parse scene for textures to add to to the txmanager"""

    bl_idname = "rman_txmgr_list.parse_scene"
    bl_label = "Parse Scene"
    bl_description = "Parse the scene and look for textures that need converting."

    def execute(self, context):
        rman_txmgr_list = context.scene.rman_txmgr_list
        texture_utils.parse_for_textures(context.scene)
        texture_utils.get_txmanager().txmake_all(blocking=False)
        bpy.ops.rman_txmgr_list.refresh('EXEC_DEFAULT')
        return{'FINISHED'}

class PRMAN_OT_Renderman_txmanager_reset_state(Operator):
    """Reset State"""

    bl_idname = "rman_txmgr_list.reset_state"
    bl_label = "Reset State"
    bl_description = "All texture settings will be erased and the scene will be re-parsed. All manual edits will be lost."

    def execute(self, context):
        rman_txmgr_list = context.scene.rman_txmgr_list
        rman_txmgr_list.clear()
        texture_utils.get_txmanager().txmanager.reset()
        texture_utils.parse_for_textures(context.scene)
        texture_utils.get_txmanager().txmake_all(blocking=False)
        texture_utils.get_txmanager().txmanager.reset_state()
        return{'FINISHED'}

class PRMAN_OT_Renderman_txmanager_clear_unused(Operator):
    """Clear Unused"""

    bl_idname = "rman_txmgr_list.clear_unused"
    bl_label = "Clear Unused"
    bl_description = "Clear unused textures"

    def execute(self, context):
        rman_txmgr_list = context.scene.rman_txmgr_list
        nodeIDs = list()
        for item in rman_txmgr_list:
            nodeID = item.nodeID
            if item.nodeID != "":
                txfile = texture_utils.get_txmanager().txmanager.get_txfile_from_id(item.nodeID)
            if not txfile:
                nodeIDs.append(nodeID)
                continue

            tokens = nodeID.split('|')
            if len(tokens) < 3:
                return

            ob_name = tokens[0]
            node_name = tokens[1]
            param = tokens[2]
            library = tokens[3] 
            node, ob = scene_utils.find_node_by_name(node_name, ob_name, library=library)

            if not node:
                nodeIDs.append(nodeID)
                continue
            if getattr(node, param) != item.name:
                nodeIDs.append(nodeID)

        for nodeID in nodeIDs:
            bpy.ops.rman_txmgr_list.remove_texture('EXEC_DEFAULT', nodeID=nodeID)

        return{'FINISHED'}

class PRMAN_OT_Renderman_txmanager_pick_images(Operator, ImportHelper):
    """Pick images from a directory."""

    bl_idname = "rman_txmgr_list.pick_images"
    bl_label = "Pick Images"
    bl_description = "Manually choose images on disk to convert."

    filename: StringProperty(maxlen=1024)
    directory: StringProperty(maxlen=1024)
    files: CollectionProperty(type=bpy.types.PropertyGroup)

    def execute(self, context):

        rman_txmgr_list = context.scene.rman_txmgr_list

        if len(self.files) > 0:
            for f in self.files:
                img = os.path.join(self.directory, f.name)  
                nodeID = str(uuid.uuid1())
                texture_utils.get_txmanager().txmanager.add_texture(nodeID, img) 
                bpy.ops.rman_txmgr_list.add_texture('EXEC_DEFAULT', filepath=img, nodeID=nodeID)
            texture_utils.get_txmanager().txmake_all(blocking=False)
            texture_utils.get_txmanager().txmanager.save_state()

        PRMAN_PT_Renderman_txmanager_list.refresh_panel(context)                

        return{'FINISHED'}


class PRMAN_OT_Renderman_txmanager_clear_all_cache(Operator):
    """Clear RenderMan Texture cache"""

    bl_idname = "rman_txmgr_list.clear_all_cache"
    bl_label = "Flush Texture Cache"
    bl_description = "Tell the core RenderMan to flush its texture cache."

    def execute(self, context):
        rr = rman_render.RmanRender.get_rman_render() 
        if rr.rman_interactive_running and rr.sg_scene:
            texture_list = list()
            for item in context.scene.rman_txmgr_list:
                if item.nodeID != "":
                    output_texture = texture_utils.get_txmanager().get_output_tex_from_id(item.nodeID)
                    texture_list.append(output_texture)
            if texture_list:
                rr.rman_scene_sync.flush_texture_cache(texture_list)
                    
        return{'FINISHED'}

class PRMAN_OT_Renderman_txmanager_reconvert_all(Operator):
    """Clear all .tex files and re-convert."""

    bl_idname = "rman_txmgr_list.reconvert_all"
    bl_label = "RE-Convert All"
    bl_description = "Clear all .tex files for all input images and re-convert."

    def execute(self, context):
        texture_utils.get_txmanager().txmanager.delete_texture_files()
        texture_utils.get_txmanager().txmake_all(blocking=False)

        return{'FINISHED'}        

class PRMAN_OT_Renderman_txmanager_reconvert_selected(Operator):
    """Clear all .tex files and re-convert selected."""

    bl_idname = "rman_txmgr_list.reconvert_selected"
    bl_label = "RE-Convert Selected"
    bl_description = "Clear all .tex files for selected image and re-convert"

    def execute(self, context):
        idx = context.scene.rman_txmgr_list_index
        item = context.scene.rman_txmgr_list[idx]

        txfile = None
        txfile = texture_utils.get_txmanager().txmanager.get_txfile_from_id(item.nodeID)

        if txfile:
            rr = rman_render.RmanRender.get_rman_render()
            txfile.delete_texture_files()
            txfile.build_texture_dict()
            if item.nodeID:
                rr.rman_scene_sync.texture_updated(item.nodeID)
            texture_utils.get_txmanager().txmake_all(blocking=False)

        return{'FINISHED'}               

class PRMAN_OT_Renderman_txmanager_apply_preset(Operator):
    """Apply current settings to the selected texture."""

    bl_idname = "rman_txmgr_list.apply_preset"
    bl_label = "Apply preset"
    bl_description = "Apply the current settings for this input image and re-convert."

    def execute(self, context):
        idx = context.scene.rman_txmgr_list_index
        item = context.scene.rman_txmgr_list[idx]
        
        txsettings = dict()
        for attr in item.txsettings:
            val = getattr(item, attr)
            if attr == 'data_type' and val == 'default':
                val = None
            txsettings[attr] = val

        # b2r
        bumprough = dict()
        if item.bumpRough != "-1":
            bumprough['normalmap'] = int(item.bumpRough)
            bumprough['factor'] = item.bumpRough_factor
            bumprough['invert'] = int(item.bumpRough_invert)
            bumprough['invertU'] = int(item.bumpRough_invertU)
            bumprough['invertV'] = int(item.bumpRough_invertV)
            bumprough['refit'] = int(item.bumpRough_refit)
        else:
            bumprough = list()        
        txsettings['bumprough'] = bumprough

        if txsettings:
            txfile = None
            txfile = texture_utils.get_txmanager().txmanager.get_txfile_from_id(item.nodeID)

            if txfile:
                txfile.params.from_dict(txsettings)
                txfile.delete_texture_files()
                txfile.build_texture_dict()
                texture_utils.get_txmanager().txmake_all(blocking=False)

        texture_utils.get_txmanager().txmanager.save_state()

        # update any nodes with colorspace in it
        tokens = item.nodeID.split('|')
        if len(tokens) < 3:
            return {'FINISHED'}

        ob_name = tokens[0]
        node_name = tokens[1]
        param = tokens[2]
        library = tokens[3]                             
        prop_colorspace_name = '%s_colorspace' % param

        try:
            mdict = texture_utils.get_txmanager().txmanager.color_manager.colorspace_names()
            val = 0
            for i, nm in enumerate(mdict):
                if nm == item.ocioconvert:
                    val = i+1
                    break        

            node, ob = scene_utils.find_node_by_name(node_name, ob_name, library=library)
            if node:
                node[prop_colorspace_name] = val    
        except AttributeError:
            pass        

        return {'FINISHED'}

class PRMAN_OT_Renderman_txmanager_add_texture(Operator):
    """Add texture."""

    bl_idname = "rman_txmgr_list.add_texture"
    bl_label = "add_texture"

    filepath: StringProperty()
    nodeID: StringProperty()

    def execute(self, context):
        if self.nodeID == "":
            return {'FINISHED'}

        txfile = texture_utils.get_txmanager().txmanager.get_txfile_from_id(self.nodeID)
        if not txfile:
            return{'FINISHED'}

        item = None
        # check if nodeID already exists in the list
        nodeIDs = list()
        rman_txmgr_list = context.scene.rman_txmgr_list
        for idx, i in enumerate(rman_txmgr_list):
            if i.nodeID == self.nodeID:
                item = i
                break
            txfile_item = texture_utils.get_txmanager().txmanager.get_txfile_from_id(i.nodeID)
            if txfile_item is None:
                nodeIDs.append(i.nodeID)
                continue
            
            if txfile_item == txfile and i.nodeID != self.nodeID:
                nodeIDs.append(i.nodeID)

        for nodeID in nodeIDs:
            bpy.ops.rman_txmgr_list.remove_texture('EXEC_DEFAULT', nodeID=nodeID)                
                
        if not item:
            item = rman_txmgr_list.add()
            item.nodeID = self.nodeID
        item.name = txfile.input_image
        params = txfile.params
        item.texture_type = params.texture_type
        item.s_mode = params.s_mode
        item.t_mode = params.t_mode
        item.texture_format = params.texture_format
        if params.data_type is not None:
            item.data_type = params.data_type
        item.resize = params.resize 
        item.state = txfile.state   
        if txfile.state == txmngr.STATE_IS_TEX:
            item.enable = False  
        else:
            item.enable = True
        if params.ocioconvert:
            item.ocioconvert = params.ocioconvert

        if params.bumprough:
            bumprough = params.bumprough_as_dict()
            item.bumpRough = str(bumprough['normalmap'])
            item.bumpRough_factor = float(bumprough['factor'])
            item.bumpRough_invert = bool(bumprough['invert'])
            item.bumpRough_invertU = bool(bumprough['invertU'])
            item.bumpRough_invertV = bool(bumprough['invertV'])
            item.bumpRough_refit = bool(bumprough['refit'])
        else:
            params.bumpRough = "-1"

        item.tooltip = '\nNode ID: ' + item.nodeID + "\n" + str(txfile)
        # FIXME: should also add the nodes that this texture is referenced in     

        return{'FINISHED'}        

class PRMAN_OT_Renderman_txmanager_refresh(Operator):
    """Refresh Texture Manager"""

    bl_idname = "rman_txmgr_list.refresh"
    bl_label = "refresh"

    filepath: StringProperty()
    nodeID: StringProperty()

    def execute(self, context):

        for item in context.scene.rman_txmgr_list:
            txfile = texture_utils.get_txmanager().txmanager.get_txfile_from_id(item.nodeID)
            if not txfile:
                continue
            item.name = txfile.input_image
            params = txfile.params
            item.texture_type = params.texture_type
            item.s_mode = params.s_mode
            item.t_mode = params.t_mode
            item.texture_type = params.texture_type
            if params.data_type is not None:
                item.data_type = params.data_type
            item.resize = params.resize 
            item.state = txfile.state    
            if txfile.state == txmngr.STATE_IS_TEX:
                item.enable = False  
            else:
                item.enable = True
            if params.ocioconvert:
                item.ocioconvert = params.ocioconvert

            if params.bumprough:
                bumprough = params.bumprough_as_dict()
                item.bumpRough = str(bumprough['normalmap'])
                item.bumpRough_factor = float(bumprough['factor'])
                item.bumpRough_invert = bool(int(bumprough['invert']))
                item.bumpRough_invertU = bool(int(bumprough['invertU']))
                item.bumpRough_invertV = bool(int(bumprough['invertV']))
                item.bumpRough_refit = bool(int(bumprough['refit']))
            else:
                params.bumpRough = "-1"                
    
            try:
                item.tooltip = '\n' + item.nodeID + "\n" + str(txfile)
            except:
                rfb_log().debug("Could not set tooltip for: %s" % item.name)
                pass
       
        PRMAN_PT_Renderman_txmanager_list.refresh_panel(context)

        return {'FINISHED'}    

class PRMAN_OT_Renderman_txmanager_remove_texture(Operator):

    bl_idname = "rman_txmgr_list.remove_texture"
    bl_label = "remove texture"

    nodeID: StringProperty()

    def execute(self, context):

        for i, item in enumerate(context.scene.rman_txmgr_list):
            if item.nodeID == self.properties.nodeID:
                context.scene.rman_txmgr_list.remove(i)
                break              

        return{'FINISHED'}                    

class PRMAN_PT_Renderman_txmanager_list(_RManPanelHeader, Panel):
    """RenderMan Texture Manager Panel."""

    bl_label = "RenderMan Texture Manager"
    bl_idname = "PRMAN_PT_Renderman_txmanager_list"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    nodeID: StringProperty()    

    @classmethod
    def refresh_panel(cls, context):
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                for space in area.spaces:
                    if space.type == 'PROPERTIES':
                        for region in area.regions:
                            if region.type == 'WINDOW':
                                region.tag_redraw()

    @classmethod
    def draw_txmanager_layout(cls, context, layout):
        scene = context.scene
        row = layout.row()
        txmanager = texture_utils.get_txmanager().txmanager
        row.operator('rman_txmgr_list.parse_scene', text='Parse Scene')
        row.operator("rman_txmgr_list.clear_unused")
        row.operator('rman_txmgr_list.reset_state', text='Reset', icon='FILE_REFRESH')         
        row.operator('rman_txmgr_list.pick_images', text='Pick Images', icon='FILE_FOLDER')        
        row.operator('rman_txmgr_list.reconvert_all', text='Reconvert All')         

        if scene.rman_txmgr_list_index >= 0 and scene.rman_txmgr_list:
            row = layout.row()
            row.template_list("PRMAN_UL_Renderman_txmanager_list", "The_List", scene,
                            "rman_txmgr_list", scene, "rman_txmgr_list_index", item_dyntip_propname="tooltip")

            if scene.rman_txmgr_list_index < len(scene.rman_txmgr_list):

                item = scene.rman_txmgr_list[scene.rman_txmgr_list_index]

                row = layout.row()
                row.label(text='Texture Settings')
                row = layout.row()
                row.enabled = item.enable
                row.prop(item, "texture_type")
                row = layout.row()
                row.enabled = item.enable
                row.prop(item, "s_mode")
                row.prop(item, "t_mode")
                row = layout.row()
                row.enabled = item.enable
                row.prop(item, "texture_format")
                row = layout.row()
                row.enabled = item.enable
                row.prop(item, "data_type")
                row = layout.row()
                row.enabled = item.enable
                row.prop(item, "resize")   
                if item.ocioconvert != '0':
                    row = layout.row()
                    row.enabled = item.enable
                    row.prop(item, "ocioconvert")   
                    dst = txmanager.color_manager.scene_colorspace_name
                    row.label(text='%s' % dst if dst else txmngr.NO_COLORSPACE)        

                # b2r
                row = layout.row()   
                row.enabled = item.enable 
                row.prop(item, "bumpRough")
                if item.bumpRough != "-1":
                    row = layout.row()
                    row.enabled = item.enable 
                    row.alignment = "RIGHT"
                    row.label(text="")
                    row.prop(item, "bumpRough_factor")
                    row.prop(item, "bumpRough_invert")
                    row.prop(item, "bumpRough_invertU")
                    row.prop(item, "bumpRough_invertV")
                    row.prop(item, "bumpRough_refit")

                row = layout.row()   
                row.enabled = item.enable
                row.alignment = 'RIGHT'          
                row.operator('rman_txmgr_list.reconvert_selected', text='Reconvert')
                row.operator('rman_txmgr_list.apply_preset', text='Apply')
                
                row = layout.row()
                row.alignment='CENTER'
                in_list = len(context.scene.rman_txmgr_list)
                progress = 'All Converted'
                qsize = txmanager.work_queue.qsize()
                if qsize != 0:
                    progress = 'Converting... %d left to convert' % (qsize)
                else:
                    t_size = txmanager.file_size()
                    # t_size in bytes
                    t_size /= 1024.0 * 1024.0
                    unit = 'MB'
                    if t_size > 1024:
                        t_size /= 1024.0
                        unit = 'GB'
                    progress = 'All Converted (Texture Disk Space: %.2f %s)' % (t_size, unit)
                row.label(text=progress)         


    def draw(self, context):
        layout = self.layout
        if get_pref('rman_ui_framework') == 'QT':
            rman_icon = rfb_icons.get_icon('rman_txmanager')  
            layout.operator("rman_txmgr_list.open_txmanager", icon_value=rman_icon.icon_id) 
        else:
            PRMAN_PT_Renderman_txmanager_list.draw_txmanager_layout(context, layout)

class PRMAN_OT_Renderman_open_txmanager(Operator):

    bl_idname = "rman_txmgr_list.open_txmanager"
    bl_label = "Open TxManager"

    nodeID: StringProperty(default='')

    def execute(self, context):
        return{'FINISHED'}         

    def draw(self, context):
        layout = self.layout
        PRMAN_PT_Renderman_txmanager_list.draw_txmanager_layout(context, layout)

    def cancel(self, context):
        if self.event and self.event.type == 'LEFTMOUSE':
            bpy.ops.rman_txmgr_list.open_txmanager('INVOKE_DEFAULT')
            
    def __init__(self):
        self.event = None    

    def invoke(self, context, event):
        if using_qt():
            global __TXMANAGER_WINDOW__
            if __TXMANAGER_WINDOW__ and __TXMANAGER_WINDOW__.isVisible():
                return {'FINISHED'}

            if sys.platform == "darwin":
                rfb_qt.run_with_timer(__TXMANAGER_WINDOW__, create_widget)   
            else:
                bpy.ops.wm.txm_qt_app_timed()
            mgr = texture_utils.get_txmanager().txmanager
            mgr.update_ui_list()
            if self.nodeID:
                txfile = mgr.get_txfile_from_id(self.nodeID)
                mgr.ui.select_txfile(txfile)        
            
            return {'FINISHED'}            


        if self.properties.nodeID != '':
            for i, item in enumerate(context.scene.rman_txmgr_list):
                if item.nodeID == self.properties.nodeID:
                    context.scene.rman_txmgr_list_index = i
                    break

        wm = context.window_manager
        width = rfb_config['editor_preferences']['texture_manager']['width']
        self.event = event
        return wm.invoke_props_dialog(self, width=width)
            
def index_updated(self, context):
    '''
    When the index updates, make sure the texture settings
    are in sync with the txmanager.
    '''
    idx = context.scene.rman_txmgr_list_index
    if idx < 0:
        return
    item = context.scene.rman_txmgr_list[idx]
    txfile = None
    txfile = texture_utils.get_txmanager().txmanager.get_txfile_from_id(item.nodeID)

    if txfile:
        params = txfile.params
        item.texture_type = params.texture_type
        item.s_mode = params.s_mode
        item.t_mode = params.t_mode
        item.texture_format = params.texture_format
        item.texture_type = params.texture_type
        if params.data_type is not None:
            item.data_type = params.data_type
        item.resize = params.resize 
        if txfile.state == txmngr.STATE_IS_TEX:
            item.enable = False
        else:
            item.enable = True
        if params.ocioconvert:
            item.ocioconvert = params.ocioconvert

        if params.bumprough:
            bumprough = params.bumprough_as_dict()
            item.bumpRough = str(bumprough['normalmap'])
            item.bumpRough_factor = float(bumprough['factor'])
            item.bumpRough_invert = bool(int(bumprough['invert']))
            item.bumpRough_invertU = bool(int(bumprough['invertU']))
            item.bumpRough_invertV = bool(int(bumprough['invertV']))
            item.bumpRough_refit = bool(int(bumprough['refit']))
        else:
            params.bumpRough = "-1"  

        item.tooltip = '\nNode ID: ' + item.nodeID + "\n" + str(txfile)                      

classes = [
    TxFileItem,
    PRMAN_UL_Renderman_txmanager_list,
    PRMAN_OT_Renderman_txmanager_parse_scene,
    PRMAN_OT_Renderman_txmanager_reset_state,
    PRMAN_OT_Renderman_txmanager_clear_unused,
    PRMAN_OT_Renderman_txmanager_pick_images,
    PRMAN_OT_Renderman_txmanager_clear_all_cache,
    PRMAN_OT_Renderman_txmanager_reconvert_all,
    PRMAN_OT_Renderman_txmanager_reconvert_selected,
    PRMAN_OT_Renderman_txmanager_apply_preset,
    PRMAN_OT_Renderman_txmanager_add_texture,
    PRMAN_OT_Renderman_txmanager_refresh,
    PRMAN_PT_Renderman_txmanager_list,
    PRMAN_OT_Renderman_txmanager_remove_texture,   
    PRMAN_OT_Renderman_open_txmanager,
]    

if not bpy.app.background and rfb_qt:
    classes.append(TxManagerQtAppTimed)

def register():

    from ..rfb_utils import register_utils       

    register_utils.rman_register_classes(classes)

    bpy.types.Scene.rman_txmgr_list = CollectionProperty(type = TxFileItem)
    bpy.types.Scene.rman_txmgr_list_index = IntProperty(name = "RenderMan Texture Manager",
                                             default = 0, update=index_updated)

def unregister():

    del bpy.types.Scene.rman_txmgr_list
    del bpy.types.Scene.rman_txmgr_list_index

    from ..rfb_utils import register_utils
    
    register_utils.rman_unregister_classes(classes) 