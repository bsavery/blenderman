from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty,  CollectionProperty, PointerProperty
from ..rfb_utils import string_utils
from ..rfb_logger import rfb_log
from ..rfb_utils import shadergraph_utils
from ..rfb_utils import scenegraph_utils
from ..rfb_utils import object_utils
from ..rfb_utils.rman_socket_utils import node_add_input

import bpy

def return_empty_list(label=''):
    items = []
    items.append(('0', label, '', '', 0))
    return items  

class COLLECTION_OT_add_remove(bpy.types.Operator):
    bl_label = "Add or Remove Paths"
    bl_idname = "collection.add_remove"

    action: EnumProperty(
        name="Action",
        description="Either add or remove properties",
        items=[('ADD', 'Add', ''),
               ('REMOVE', 'Remove', '')],
        default='ADD')
    context: StringProperty(
        name="Context",
        description="Name of context member to find renderman pointer in",
        default="")
    collection: StringProperty(
        name="Collection",
        description="The collection to manipulate",
        default="")
    collection_index: StringProperty(
        name="Index Property",
        description="The property used as a collection index",
        default="")
    defaultname: StringProperty(
        name="Default Name",
        description="Default name to give this collection item",
        default="")

    def invoke(self, context, event):
        scene = context.scene
        id = string_utils.getattr_recursive(context, self.properties.context)
        rm = id.renderman if hasattr(id, 'renderman') else id

        prop_coll = self.properties.collection
        coll_idx = self.properties.collection_index

        collection = getattr(rm, prop_coll)
        index = getattr(rm, coll_idx)

        if self.properties.action == 'ADD':
            dflt_name = self.properties.defaultname          
            collection.add()
            index = len(collection)-1
            setattr(rm, coll_idx, index)
            if dflt_name != '':
                for coll in collection:
                    if coll.name == dflt_name:
                        dflt_name = '%s_NEW' % dflt_name                  

                collection[-1].name = dflt_name

        elif self.properties.action == 'REMOVE':
            collection.remove(index)
            setattr(rm, coll_idx, index - 1)

        if context.object:
            context.object.update_tag(refresh={'DATA'})

        return {'FINISHED'}
    
class COLLECTION_OT_add_remove_light_filter(bpy.types.Operator):
    bl_label = "Add or Remove Light Filters"
    bl_idname = "renderman.add_remove_lightfilter"

    action: EnumProperty(
        name="Action",
        description="Either add or remove properties",
        items=[('ADD', 'Add', ''),
               ('REMOVE', 'Remove', '')],
        default='ADD')
    context: StringProperty(
        name="Context",
        description="Name of context member to find renderman pointer in",
        default="")
    collection: StringProperty(
        name="Collection",
        description="The collection to manipulate",
        default="")
    collection_index: StringProperty(
        name="Index Property",
        description="The property used as a collection index",
        default="")
    defaultname: StringProperty(
        name="Default Name",
        description="Default name to give this collection item",
        default="")

    def invoke(self, context, event):
        scene = context.scene
        id = string_utils.getattr_recursive(context, self.properties.context)
        rm = id.renderman if hasattr(id, 'renderman') else id

        prop_coll = self.properties.collection
        coll_idx = self.properties.collection_index

        collection = getattr(rm, prop_coll)
        index = getattr(rm, coll_idx)

        if self.properties.action == 'ADD':
            dflt_name = self.properties.defaultname          
            collection.add()
            index = len(collection)-1
            setattr(rm, coll_idx, index)
            if dflt_name != '':
                for coll in collection:
                    if coll.name == dflt_name:
                        dflt_name = '%s_NEW' % dflt_name                  

                collection[-1].name = dflt_name

        elif self.properties.action == 'REMOVE':
            collection.remove(index)
            setattr(rm, coll_idx, index - 1)
            id.node_tree.update_tag()

        return {'FINISHED'}


class COLLECTION_OT_add_remove_dspymeta(bpy.types.Operator):
    bl_label = ""
    bl_idname = "renderman.add_remove_dspymeta"

    action: EnumProperty(
        name="Action",
        description="Either add or remove properties",
        items=[('ADD', 'Add', ''),
               ('REMOVE', 'Remove', '')],
        default='ADD')
    collection: StringProperty(
        name="Collection",
        description="The collection to manipulate",
        default="")
    collection_index: StringProperty(
        name="Index Property",
        description="The property used as a collection index",
        default="")
    defaultname: StringProperty(
        name="Default Name",
        description="Default name to give this collection item",
        default="")

    def invoke(self, context, event):
        scene = context.scene
        rm = context.node

        prop_coll = self.properties.collection
        coll_idx = self.properties.collection_index

        collection = getattr(rm, prop_coll)
        index = getattr(rm, coll_idx)

        if self.properties.action == 'ADD':
            dflt_name = self.properties.defaultname          
            collection.add()
            index = len(collection)-1
            setattr(rm, coll_idx, index)
            i = 0
            if dflt_name != '':
                for coll in collection:
                    if coll.name == dflt_name:
                        i += 1
                        dflt_name = '%s_%d' % (self.properties.defaultname, i)

                collection[-1].name = dflt_name

        elif self.properties.action == 'REMOVE':
            collection.remove(index)
            setattr(rm, coll_idx, index - 1)

        if context.object:
            context.object.update_tag(refresh={'DATA'})

        return {'FINISHED'}   

class COLLECTION_OT_add_remove_user_attributes(bpy.types.Operator):
    bl_label = ""
    bl_idname = "renderman.add_remove_user_attributes"

    action: EnumProperty(
        name="Action",
        description="Either add or remove properties",
        items=[('ADD', 'Add', ''),
               ('REMOVE', 'Remove', '')],
        default='ADD')
    collection: StringProperty(
        name="Collection",
        description="The collection to manipulate",
        default="")
    collection_index: StringProperty(
        name="Index Property",
        description="The property used as a collection index",
        default="")
    defaultname: StringProperty(
        name="Default Name",
        description="Default name to give this collection item",
        default="")

    def invoke(self, context, event):
        object = context.object
        rm = object.renderman

        prop_coll = self.properties.collection
        coll_idx = self.properties.collection_index

        collection = getattr(rm, prop_coll)
        index = getattr(rm, coll_idx)

        if self.properties.action == 'ADD':
            dflt_name = self.properties.defaultname          
            collection.add()
            index = len(collection)-1
            setattr(rm, coll_idx, index)
            i = 0
            if dflt_name != '':
                for coll in collection:
                    if coll.name == dflt_name:
                        i += 1
                        dflt_name = '%s_%d' % (self.properties.defaultname, i)

                collection[-1].name = dflt_name

        elif self.properties.action == 'REMOVE':
            collection.remove(index)
            setattr(rm, coll_idx, index - 1)

        if context.object:
            context.object.update_tag(refresh={'DATA'})

        return {'FINISHED'}                 

class COLLECTION_OT_meshlight_lightfilter_add_remove(bpy.types.Operator):
    bl_label = "Add Light Filter to Mesh Light"
    bl_idname = "renderman.add_meshlight_lightfilter"

    action: EnumProperty(
        name="Action",
        description="Either add or remove properties",
        items=[('ADD', 'Add', ''),
               ('REMOVE', 'Remove', '')],
        default='ADD')
    context: StringProperty(
        name="Context",
        description="Name of context member to find renderman pointer in",
        default="")
    collection: StringProperty(
        name="Collection",
        description="The collection to manipulate",
        default="")
    collection_index: StringProperty(
        name="Index Property",
        description="The property used as a collection index",
        default="")
    defaultname: StringProperty(
        name="Default Name",
        description="Default name to give this collection item",
        default="")    

    def invoke(self, context, event):
        scene = context.scene
        mat = context.material
        rm = mat.renderman_light

        prop_coll = self.properties.collection
        coll_idx = self.properties.collection_index

        collection = getattr(rm, prop_coll)
        index = getattr(rm, coll_idx)

        if self.properties.action == 'ADD':
            dflt_name = self.properties.defaultname
            for coll in collection:
                if coll.name == dflt_name:
                    dflt_name = '%s_NEW' % dflt_name
            collection.add()
            index = len(collection)-1
            setattr(rm, coll_idx, index)
            try:
                collection[-1].name = dflt_name
            except:
                pass

        elif self.properties.action == 'REMOVE':
            collection.remove(index)
            setattr(rm, coll_idx, index - 1)

        return {'FINISHED'}               


class COLLECTION_OT_object_groups_add_remove(bpy.types.Operator):
    bl_label = "Add or Remove Object Groups"
    bl_idname = "renderman.add_remove_object_groups"

    action: EnumProperty(
        name="Action",
        description="Either add or remove properties",
        items=[('ADD', 'Add', ''),
               ('REMOVE', 'Remove', '')],
        default='ADD')
    context: StringProperty(
        name="Context",
        description="Name of context member to find renderman pointer in",
        default="")
    collection: StringProperty(
        name="Collection",
        description="The collection to manipulate",
        default="")
    collection_index: StringProperty(
        name="Index Property",
        description="The property used as a collection index",
        default="")
    defaultname: StringProperty(
        name="Default Name",
        description="Default name to give this collection item",
        default="")

    def invoke(self, context, event):
        scene = context.scene
        id = string_utils.getattr_recursive(context, self.properties.context)
        rm = id.renderman if hasattr(id, 'renderman') else id

        prop_coll = self.properties.collection
        coll_idx = self.properties.collection_index

        collection = getattr(rm, prop_coll)
        index = getattr(rm, coll_idx)

        if self.properties.action == 'ADD':
            dflt_name = self.properties.defaultname
            for coll in collection:
                if coll.name == dflt_name:
                    dflt_name = '%s_NEW' % dflt_name
            collection.add()
            index = len(collection)-1
            setattr(rm, coll_idx, index)
            collection[-1].name = dflt_name

        elif self.properties.action == 'REMOVE':
            group = collection[index]            
            # get a list of all objects in this group
            ob_list = [member.ob_pointer for member in group.members]
            collection.remove(index)
            setattr(rm, coll_idx, index - 1)

            # now tell each object to update
            for ob in ob_list:
                ob.update_tag(refresh={'OBJECT'})

        return {'FINISHED'}               

class PRMAN_OT_convert_mixer_group_to_light_group(bpy.types.Operator):
    bl_idname = 'renderman.convert_mixer_group_to_light_group'
    bl_label = 'Convert to Light Mixer Group' 
    bl_description = 'Convert the currently selected light mixer group to a light group. If the lights in this mixer group were already in a light group, this will override.'

    group_index: IntProperty(name="group_index", default=-1)

    def execute(self, context):
        if self.properties.group_index < 0:
            return {'FINISHED'}

        scene = context.scene
        mixer_group_index = self.properties.group_index

        mixer_groups = scene.renderman.light_mixer_groups
        mixer_group = mixer_groups[mixer_group_index]

        for member in mixer_group.members:
            light_ob = member.light_ob
            light_shader = shadergraph_utils.get_light_node(light_ob, include_light_filters=False)
            light_shader.lightGroup = mixer_group.name
            light_ob.update_tag(refresh={'DATA'})

        return {'FINISHED'}       


class PRMAN_OT_add_light_to_light_mixer_group(bpy.types.Operator):
    bl_idname = 'renderman.add_light_to_light_mixer_group'
    bl_label = 'Add Selected Light to Light Mixer Group' 

    group_index: IntProperty(default=0)
    do_scene_selected: BoolProperty(name="do_scene_selected", default=False)  
    open_editor: BoolProperty(default=False)  

    def add_selected(self, context):
        scene = context.scene
        group_index = scene.renderman.light_mixer_groups_index
        object_groups = scene.renderman.light_mixer_groups
        object_group = object_groups[group_index]        
        ob = getattr(context, "selected_light", None)
        if not ob:
            return {'FINISHED'}

        do_add = True

        for member in object_group.members:
            if ob == member.light_ob:
                do_add = False
                break                

        if do_add:
            ob_in_group = object_group.members.add()
            ob_in_group.name = ob.name
            ob_in_group.light_ob = ob       

            op = getattr(context, 'op_ptr')
            if op:
                op.selected_light_name = '0'              
            
    def add_scene_selected(self, context):
        scene = context.scene
        group_index = self.group_index
        if not hasattr(context, 'selected_objects'):
            return {'FINISHED'}        
        
        object_groups = scene.renderman.light_mixer_groups
        object_group = object_groups[group_index]
        for ob in context.selected_objects:
            if not shadergraph_utils.is_rman_light(ob):
                continue
            do_add = True
            for member in object_group.members:
                if ob == member.light_ob:
                    do_add = False
                    break                

            if do_add:
                ob_in_group = object_group.members.add()
                ob_in_group.name = ob.name
                ob_in_group.light_ob = ob          

    def execute(self, context):
        if self.properties.do_scene_selected:
            self.add_scene_selected(context)
        else:
            self.add_selected(context)

        if self.properties.open_editor:
            bpy.ops.scene.rman_open_light_mixer_editor('INVOKE_DEFAULT')
        return {'FINISHED'}   

class PRMAN_OT_remove_light_from_light_mixer_group(bpy.types.Operator):
    bl_idname = 'renderman.remove_light_from_light_mixer_group'
    bl_label = 'Remove Selected from Light Mixer Group'

    group_index: IntProperty(default=0)

    def execute(self, context):
        scene = context.scene
        group_index = self.properties.group_index

        object_group = scene.renderman.light_mixer_groups
        object_group = object_group[group_index].members
        members = [member.light_ob for member in object_group]
        ob = getattr(context, "selected_light", None)
        if not ob:
            return {'FINISHED'}   

        for i, member in enumerate(object_group):
            if member.light_ob == ob:
                object_group.remove(i)
                break

        return {'FINISHED'}            

class PRMAN_OT_add_to_group(bpy.types.Operator):
    bl_idname = 'renderman.add_to_group'
    bl_label = 'Add Selected to Object Group'

    group_index: IntProperty(default=-1)
    do_scene_selected: BoolProperty(name="do_scene_selected", default=False)
    open_editor: BoolProperty(default=False)

    def add_selected(self, context):
        scene = context.scene
        rm = scene.renderman
        group_index = rm.object_groups_index
        ob = getattr(context, "selected_obj", None)
        if not ob:
            return {'FINISHED'}       

        object_groups = scene.renderman.object_groups
        object_group = object_groups[group_index]
        do_add = True
        for member in object_group.members:            
            if ob == member.ob_pointer:
                do_add = False
                break
        if do_add:
            ob_in_group = object_group.members.add()
            ob_in_group.name = ob.name
            ob_in_group.ob_pointer = ob    
            op = getattr(context, 'op_ptr')
            if op:
                op.selected_obj_name = '0'             
            ob.update_tag(refresh={'DATA'})    

    def add_scene_selected(self, context):
        scene = context.scene
        rm = scene.renderman
        if not hasattr(context, 'selected_objects'):
            return {'FINISHED'}

        group_index = self.properties.group_index
        object_groups = scene.renderman.object_groups
        object_group = object_groups[group_index]
        for ob in context.selected_objects:
            do_add = True
            for member in object_group.members:            
                if ob == member.ob_pointer:
                    do_add = False
                    break
            if do_add:
                ob_in_group = object_group.members.add()
                ob_in_group.name = ob.name
                ob_in_group.ob_pointer = ob      
                ob.update_tag(refresh={'DATA'})          

    def execute(self, context):
        if self.properties.do_scene_selected:
            self.add_scene_selected(context)
        else:
            self.add_selected(context)

        if self.properties.open_editor:
            bpy.ops.scene.rman_open_groups_editor('INVOKE_DEFAULT')            
        
        return {'FINISHED'}

class PRMAN_OT_remove_from_group(bpy.types.Operator):
    bl_idname = 'renderman.remove_from_group'
    bl_label = 'Remove Selected from Object Group'

    def execute(self, context):
        scene = context.scene
        rm = scene.renderman        
        group_index = rm.object_groups_index
        ob = getattr(context, "selected_obj", None)
        if not ob:
            return {'FINISHED'}        

        object_groups = scene.renderman.object_groups
        object_group = object_groups[group_index]
        for i, member in enumerate(object_group.members):
            if member.ob_pointer == ob:
                object_group.members.remove(i)
                ob.update_tag(refresh={'DATA'})
                break

        return {'FINISHED'}

class PRMAN_OT_add_light_link_object(bpy.types.Operator):
    bl_idname = 'renderman.add_light_link_object'
    bl_label = 'Add Selected Object to Light Link'

    def obj_list_items(self, context):
        scene = context.scene
        rm = scene.renderman
        group = rm.light_links[rm.light_links_index]
        objs_in_group = []
        for member in group.members:
            objs_in_group.append(member.ob_pointer.name)

        items = []
        for ob_name in [ob.name for ob in context.scene.objects if ob.type not in ['LIGHT', 'CAMERA']]:
            if ob_name not in objs_in_group:
                items.append((ob_name, ob_name, ''))
        return items       

    group_index: IntProperty(default=-1)
    do_scene_selected: BoolProperty(name="do_scene_selected", default=False)    

    def execute(self, context):
        scene = context.scene
        rm = scene.renderman

        ll = None
        if self.group_index == -1:
            light_links_index = rm.light_links_index
            ll = scene.renderman.light_links[light_links_index]
        else:
            ll = scene.renderman.light_links.get[self.group_index]

        if not ll:
            return {'FINISHED'}              
    
        ob = getattr(context, "selected_obj", None)
        if not ob:
            return {'FINISHED'}                  

        do_add = True
        for member in ll.members:            
            if ob == member.ob_pointer:
                do_add = False
                break
        if do_add:
            ob_in_group = ll.members.add()
            ob_in_group.name = ob.name
            ob_in_group.ob_pointer = ob   
            ob.update_tag(refresh={'OBJECT'})

            op = getattr(context, 'op_ptr')
            if op:
                op.selected_obj_name = '0'                    

        return {'FINISHED'}

class PRMAN_OT_remove_light_link_object(bpy.types.Operator):
    bl_idname = 'renderman.remove_light_link_object'
    bl_label = 'Remove Selected Object from Light Link'

    group_index: IntProperty(default=-1)

    def execute(self, context):
        scene = context.scene
        rm = scene.renderman

        ll = None
        if self.group_index == -1:
            light_links_index = rm.light_links_index
            ll = scene.renderman.light_links[light_links_index]
        else:
            ll = scene.renderman.light_links.get[self.group_index]

        if not ll:
            return {'FINISHED'}              
    
        ob = getattr(context, "selected_obj", None)
        if not ob:
            return {'FINISHED'}       

        for i, member in enumerate(ll.members):
            if member.ob_pointer == ob:
                ll.members.remove(i)
                ll.members_index -= 1
                if not rm.invert_light_linking:
                    grp = ob.renderman.rman_lighting_excludesubset
                    light_props = shadergraph_utils.get_rman_light_properties_group(ll.light_ob)
                    if light_props.renderman_light_role == 'RMAN_LIGHTFILTER':
                        grp = ob.renderman.rman_lightfilter_subset
                    for j, subset in enumerate(grp):
                        if subset.light_ob == ll.light_ob:
                            grp.remove(j)
                            ob.update_tag(refresh={'OBJECT'})
                            break
                else:
                    ob.update_tag(refresh={'OBJECT'})
                break                            

        return {'FINISHED'}


class PRMAN_OT_add_light_link(bpy.types.Operator):
    bl_idname = 'renderman.add_light_link'
    bl_label = 'Add New Light Link'
  
    group_index: IntProperty(default=-1)
    do_scene_selected: BoolProperty(name="do_scene_selected", default=False)

    def add_selected(self, context):
        scene = context.scene
        rm = scene.renderman

        light_ob = getattr(context, 'selected_light', None)
        if not light_ob:
            return {'FINISHED'}      

        do_add = True
        for light_link in rm.light_links:
            if light_ob == light_link.light_ob:
                do_add = False
                break            

        if do_add:
            ll = scene.renderman.light_links.add()
            ll.name = light_ob.name
            ll.light_ob = light_ob     
            
            op = getattr(context, 'op_ptr')
            if op:
                op.selected_light_name = '0'

            if not object_utils.is_light_filter(light_ob):
                light_ob.update_tag(refresh={'DATA'})
            
    def add_scene_selected(self, context):
        scene = context.scene
        rm = scene.renderman
        obs_list = []
        op = getattr(context, 'op_ptr')
        if op:
            for nm in op.light_search_results.split('|'):
                ob = scene.objects[nm]
                if ob:
                    obs_list.append(ob)
            op.light_search_results = ''
            op.light_search_filter = ''   
            op.do_light_filter = False            
        else:
            if not hasattr(context, 'selected_objects'):
                return {'FINISHED'}

            obs_list = context.selected_objects                
            
        group_index = self.properties.group_index
        object_groups = scene.renderman.object_groups
        object_group = object_groups[group_index]
        for light_ob in obs_list:
            do_add = True
            for light_link in rm.light_links:
                if light_ob == light_link.light_ob:
                    do_add = False
                    break            

            if do_add:
                ll = scene.renderman.light_links.add()
                ll.name = light_ob.name
                ll.light_ob = light_ob.data   
                if not object_utils.is_light_filter(light_ob):
                    light_ob.update_tag(refresh={'DATA'})  

    def execute(self, context):
        if self.properties.do_scene_selected:
            self.add_scene_selected(context)
        else:
            self.add_selected(context)   
        if context.scene.renderman.invert_light_linking:
            scenegraph_utils.update_root_lightlinks(context)                        

        return {'FINISHED'}

class PRMAN_OT_remove_light_link(bpy.types.Operator):
    bl_idname = 'renderman.remove_light_link'
    bl_label = 'Remove Light Link'

    group_index: IntProperty(name="idx", default=-1)

    def execute(self, context):
        scene = context.scene
        rm = scene.renderman
        group_index = self.group_index
        if group_index == -1:
            group_index = rm.light_links_index
        if group_index != -1:
            light_link = rm.light_links[group_index]
            for i, member in enumerate(light_link.members):
                ob = member.ob_pointer
                grp = ob.renderman.rman_lighting_excludesubset
                light_props = shadergraph_utils.get_rman_light_properties_group(light_link.light_ob)
                if light_props.renderman_light_role == 'RMAN_LIGHTFILTER':
                    grp = ob.renderman.rman_lightfilter_subset
                for j, subset in enumerate(grp):
                    if subset.light_ob == light_link.light_ob:
                        grp.remove(j)
                        break
                ob.update_tag(refresh={'OBJECT'})   

            light_link.light_ob.update_tag(refresh={'DATA'})
            rm.light_links.remove(group_index)
            rm.light_links_index -= 1
            
        if rm.invert_light_linking:
            scenegraph_utils.update_root_lightlinks(context)              

        return {'FINISHED'}

class PRMAN_OT_light_link_update_illuminate(bpy.types.Operator):
    bl_idname = 'renderman.update_light_link_illuminate'
    bl_label = 'Update Illuminate'

    illuminate: EnumProperty(
        name="Illuminate",
        items=[
              ('DEFAULT', 'Default', ''),
               ('ON', 'On', ''),
               ('OFF', 'Off', '')])

    @classmethod
    def description(cls, context, properties):
        active_light = context.active_object
        info = 'Inherit the illumination'    
        if properties.illuminate == 'ON':
            info = 'Turn on illumination for all objects linked to %s' % active_light.name
        elif properties.illuminate == 'OFF':
            info = 'Turn off illumination for all objects linked to %s' % active_light.name
        return info               

    def execute(self, context):
        active_light = getattr(context, 'light_ob', None)
        if not active_light:
            return {'FINISHED'}
        light_props = shadergraph_utils.get_rman_light_properties_group(active_light)
        if light_props.renderman_light_role not in {'RMAN_LIGHTFILTER', 'RMAN_LIGHT'}:
            return {'FINISHED'}

        scene = context.scene
        rm = scene.renderman

        light_link = None
        for ll in rm.light_links:
            if ll.light_ob == active_light:
                light_link = ll
                break

        if light_link is None:
            light_link = rm.light_links.add()
            light_link.light_ob = active_light            

        for ob in context.selected_objects:
            if ob.type == 'LIGHT':
                continue
            member = None
            for m in light_link.members:
                if m.ob_pointer == ob:
                    member = m
                    break
            if member is None:
                member = light_link.members.add()
                member.name = ob.name
                member.ob_pointer = ob

            member.illuminate = self.illuminate

        return {'FINISHED'}     

class PRMAN_OT_light_link_update_objects(bpy.types.Operator):
    bl_idname = 'renderman.update_light_link_objects'
    bl_label = 'Update Light Link Objects'

    update_type: EnumProperty(
        name="Illuminate",
        items=[
              ('ADD', 'Add', ''),
               ('REMOVE', 'Remove', '')])

    @classmethod
    def description(cls, context, properties):
        info = 'Link the selected objects to this light'    
        if properties.update_type == 'REMOVE':
            info = 'Unlink the selected objects from this light'
        return info               

    def execute(self, context):
        
        active_light = getattr(context, 'light_ob', None)
        if not active_light:
            return {'FINISHED'}

        scene = context.scene
        rm = scene.renderman

        light_link = None
        for ll in rm.light_links:
            if ll.light_ob == active_light:
                light_link = ll
                break

        if light_link is None:
            light_link = rm.light_links.add()
            light_link.light_ob = active_light

        if self.update_type == 'ADD':
            for ob in context.selected_objects:
                if ob.type == 'LIGHT':
                    continue
                member = None
                for m in light_link.members:
                    if m.ob_pointer == ob:
                        member = m
                        break
                if member is None:
                    m = light_link.members.add()
                    m.name = ob.name
                    m.ob_pointer = ob
                    light_ob = light_link.light_ob
                if rm.invert_light_linking:
                    scenegraph_utils.update_root_lightlinks(context)
                ob.update_tag(refresh={'OBJECT'})

        else:
            for ob in context.selected_objects:
                if ob.type == 'LIGHT':
                    continue
                member = None
                idx = -1
                for j, m in enumerate(light_link.members):
                    if m.ob_pointer == ob:
                        member = m
                        idx = j
                        break
                if member:
                    if not rm.invert_light_linking:
                        light_ob = light_link.light_ob  
                        for j, subset in enumerate(ob.renderman.rman_lighting_excludesubset):
                            if subset.light_ob == light_ob:
                                ob.renderman.rman_lighting_excludesubset.remove(j)
                                break      
                    if rm.invert_light_linking:
                        scenegraph_utils.update_root_lightlinks(context)                            
                    ob.update_tag(refresh={'OBJECT'})  
                    light_link.members.remove(idx)
                    light_link.members_index = idx-1

        return {'FINISHED'}              

class PRMAN_OT_Add_Remove_Array_Element(bpy.types.Operator):
    bl_idname = 'renderman.add_remove_array_elem'
    bl_label = ''

    action: EnumProperty(
        name="",
        items=[
              ('ADD', 'Add', ''),
               ('REMOVE', 'Remove', '')])

    param_name: StringProperty(name="", default="")
    collection: StringProperty(name="", default="")
    collection_index: StringProperty(name="", default="")
    elem_type: StringProperty(name="", default="")    

    @classmethod
    def description(cls, context, properties):
        info = 'Add a new array element to this array'
        if properties.action == 'REMOVE':
            info = 'Remove the selected array element from this array'
        return info               

    def execute(self, context):
        
        node = context.node
        collection = getattr(node, self.collection)
        index = getattr(node, self.collection_index)        
        meta = node.prop_meta[self.param_name]
        connectable = True
        if '__noconnection' in meta and meta['__noconnection']:
            connectable = False
        if self.action == 'ADD':
            elem = collection.add()
            index = len(collection)-1
            setattr(node, self.collection_index, index)
            elem.name = '%s[%d]' % (self.param_name, len(collection)-1)  
            elem.type = self.elem_type
            if connectable:
                param_array_label = '%s[%d]' % (meta.get('label', self.param_name), len(collection)-1)
                node_add_input(node, self.elem_type, elem.name, meta, param_array_label)

        else:
            do_rename = False
            idx = -1
            if connectable:
                # rename sockets
                def update_sockets(socket, name, label):
                    link = None
                    from_socket = None
                    if socket.is_linked:                    
                        link = socket.links[0]
                        from_socket = link.from_socket       
                    node.inputs.remove(socket)                                     
                    new_socket = node_add_input(node, self.elem_type, name, meta, label)
                    if not new_socket:
                        return
                    if link and from_socket:
                        nt = node.id_data
                        nt.links.new(from_socket, new_socket)
                    
                idx = 0 
                elem = collection[index]
                node.inputs.remove(node.inputs[elem.name])
                for elem in collection:
                    nm = elem.name
                    new_name = '%s[%d]' % (self.param_name, idx)
                    new_label = '%s[%d]' % (meta.get('label', self.param_name), idx)
                    socket = node.inputs.get(nm, None)
                    if socket:
                        update_sockets(socket, new_name, new_label)
                        idx += 1                    
                    
            collection.remove(index)                    
            index -= 1
            setattr(node, self.collection_index, 0)
            for i in range(len(collection)):
                elem = collection[i]
                elem.name = '%s[%d]' % (self.param_name, i)

        return {'FINISHED'}   


classes = [
    COLLECTION_OT_add_remove,
    COLLECTION_OT_add_remove_light_filter,
    COLLECTION_OT_add_remove_dspymeta,
    COLLECTION_OT_add_remove_user_attributes,
    COLLECTION_OT_meshlight_lightfilter_add_remove,
    COLLECTION_OT_object_groups_add_remove,
    PRMAN_OT_convert_mixer_group_to_light_group,
    PRMAN_OT_add_to_group,
    PRMAN_OT_add_light_to_light_mixer_group,
    PRMAN_OT_remove_light_from_light_mixer_group,
    PRMAN_OT_remove_from_group,
    PRMAN_OT_add_light_link_object,
    PRMAN_OT_remove_light_link_object,
    PRMAN_OT_add_light_link,
    PRMAN_OT_remove_light_link,
    PRMAN_OT_light_link_update_illuminate,
    PRMAN_OT_light_link_update_objects,
    PRMAN_OT_Add_Remove_Array_Element
]

def register():
    from ..rfb_utils import register_utils

    register_utils.rman_register_classes(classes)

def unregister():
    
    from ..rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes)    