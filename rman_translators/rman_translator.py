from ..rfb_logger import rfb_log
from ..rfb_utils import transform_utils
from ..rfb_utils import property_utils
from ..rfb_utils import string_utils
from ..rfb_utils import object_utils
from ..rfb_utils import prefs_utils
from ..rfb_utils import shadergraph_utils
from ..rfb_utils import scene_utils
import hashlib
import os
import bpy

class RmanTranslator(object):
    '''
    RmanTranslator and subclasses are responsible for taking a Blender object/material and converting
    them to the equivalent RixSceneGraph node. The scene graph nodes are wrapped in a thin layer RmanSgNode
    class corresponding to their type. The flow should be something like:

        db_name = 'FOOBAR' # unique datablock name
        rman_sg_node = translator.export(ob, db_name) # create an RmanSgNode node
        # set primvars on geo
        translator.update(ob, rman_sg_node)        
        .
        .
        # ob is a deforming object, export object at time_sample
        translator.export_deform_sample(rman_sg_node, ob, time_sample)
        .
        .
        # ob has changed
        translator.update(ob, rman_sg_node)

    Attributes:
        rman_scene (RmanScene) - pointer back to RmanScene instance
    '''

    def __init__(self, rman_scene):
        self.rman_scene = rman_scene

    @property
    def rman_scene(self):
        return self.__rman_scene

    @rman_scene.setter
    def rman_scene(self, rman_scene):
        self.__rman_scene = rman_scene        

    def export(self, ob, db_name):
        pass

    def export_deform_sample(self, rman_sg_node, ob, time_sample):
        pass

    def update(self, ob, rman_sg_node):
        pass

    def set_primvar_times(self, motion_steps, primvar):
        # take the motion steps, sort it and 
        # normalize it to lie between 0 and 1
        times = []
        sorted_steps = sorted(list(motion_steps))
        delta = -sorted_steps[0]
        for m in sorted_steps:
            times.append(m + delta)
        primvar.SetTimes(times)

    def export_transform(self, ob, sg_node):
        m = ob.matrix_local if ob.parent and ob.parent_type == "object" and ob.type != 'LIGHT'\
                else ob.matrix_world

        v = transform_utils.convert_matrix(m)

        sg_node.SetTransform( v )       

    def export_object_primvars(self, ob, primvars):
        '''
        This method should be called by subclasses of RmanTranslator
        in their update() methods, if they are setting any primvars. This
        sets things like displacement bound and micropolygon length.

        Args:
            ob (bpy.types.Object) - Blender Object
            primvars (RtPrimVars) - primitive variables
        '''
        rm = ob.renderman
        rm_scene = self.rman_scene.bl_scene.renderman
        property_utils.set_primvar_bl_props(primvars, rm, inherit_node=rm_scene)

    def update_primvar(self, ob, rman_sg_node, prop_name):
        pass        

    def update_object_primvar(self, ob, primvars, prop_name):
        '''
        This method should be called by subclasses of RmanTranslator
        in their update_primvar() methods.

        Args:
            ob (bpy.types.Object) - Blender Object
            primvars (RtPrimVars) - primitive variables
            prop_name (str) - name of the Blender property that was updated
        '''
        rm = ob.renderman
        rm_scene = self.rman_scene.bl_scene.renderman
        meta = rm.prop_meta[prop_name]
        property_utils.set_primvar_bl_prop(primvars, prop_name, meta, rm, inherit_node=rm_scene)        

    def export_instance_attributes(self, ob, rman_sg_node, ob_inst):
        '''
        Export attributes that should vary between each instance
        '''
        if not rman_sg_node.sg_node:
            return        
        name = ob.name_full
        is_instance = ob_inst.is_instance
        if is_instance:
            name = ob_inst.parent.name
        attrs = rman_sg_node.sg_node.GetAttributes()
        rman_type = object_utils._detect_primitive_(ob)

        # Add ID
        if name != "":            
            persistent_id = ob_inst.persistent_id[1]
            if persistent_id == 0:           
                persistent_id = int(hashlib.sha1(name.encode()).hexdigest(), 16) % 10**8
            self.rman_scene.obj_hash[persistent_id] = name
            attrs.SetInteger(self.rman_scene.rman.Tokens.Rix.k_identifier_id, persistent_id)

            if rman_type in [
                    'DELAYED_LOAD_ARCHIVE',
                    'ALEMBIC',
                    'PROCEDURAL_RUN_PROGRAM',
                    'DYNAMIC_LOAD_DSO'
                ]:
                id = int(hashlib.sha1(rman_sg_node.db_name.encode()).hexdigest(), 16) % 10**8
                procprimid = float(id)
                attrs.SetFloat('user:procprimid', procprimid) 

        if is_instance:
            attrs.SetFloat('user:blender_is_instance', 1)
            attrs.SetFloatArray('user:blender_instance_uv', ob_inst.uv, 2)
        else:
            attrs.SetFloat('user:blender_is_instance', 0)

        # Check if this is part of a Blender holdout
        if is_instance:
            holdout = ob_inst.parent.holdout_get(view_layer=self.rman_scene.bl_view_layer)
        else:
            holdout = ob_inst.object.holdout_get(view_layer=self.rman_scene.bl_view_layer)

        if holdout:
            # let Blender's holdout attribute take precedence
            attrs.Remove('trace:holdout')
            attrs.SetInteger('Ri:Matte', 1)

        rman_sg_node.sg_node.SetAttributes(attrs)     

    def export_light_linking_attributes(self, ob, attrs): 
        rm = ob.renderman
        bl_scene = self.rman_scene.bl_scene
        all_lightfilters = [string_utils.sanitize_node_name(l.name) for l in scene_utils.get_all_lightfilters(bl_scene)]

        if self.rman_scene.bl_scene.renderman.invert_light_linking:
            lighting_subset = []
            lightfilter_subset = []
            all_lights = [string_utils.sanitize_node_name(l.name) for l in scene_utils.get_all_lights(bl_scene, include_light_filters=False)]
            for ll in self.rman_scene.bl_scene.renderman.light_links:
                light_ob = ll.light_ob                
                light_props = shadergraph_utils.get_rman_light_properties_group(light_ob)
                found = False
                for member in ll.members:
                    if member.ob_pointer.original == ob.original:
                        found = True
                        break
                    
                if light_props.renderman_light_role == 'RMAN_LIGHT':
                    nm = string_utils.sanitize_node_name(light_ob.name)
                    if found:
                        lighting_subset.append(nm)
                    all_lights.remove(nm)

                elif light_props.renderman_light_role == 'RMAN_LIGHTFILTER':      
                    nm = string_utils.sanitize_node_name(light_ob.name)                  
                    if found:                        
                        lightfilter_subset.append(nm)
                    all_lightfilters.remove(nm)

            if lighting_subset:
                lighting_subset = lighting_subset + all_lights # include all other lights that are not linked
                attrs.SetString(self.rman_scene.rman.Tokens.Rix.k_lighting_subset, ','. join(lighting_subset) )

            if lightfilter_subset:
                lightfilter_subset = lightfilter_subset + all_lightfilters
                attrs.SetString(self.rman_scene.rman.Tokens.Rix.k_lightfilter_subset, ',' . join(lightfilter_subset))

    def export_object_attributes_attrs(self, ob, attrs, remove=True):

        name = ob.name_full
        rm = ob.renderman

        # set any properties marked riattr in the config file
        for prop_name, meta in rm.prop_meta.items():
            property_utils.set_riattr_bl_prop(attrs, prop_name, meta, rm, check_inherit=True, remove=remove)

        obj_groups_str = "World"
        obj_groups_str += "," + name
        lpe_groups_str = "*"
        for obj_group in self.rman_scene.bl_scene.renderman.object_groups:
            for member in obj_group.members:
                if member.ob_pointer.original == ob.original:
                    obj_groups_str += ',' + obj_group.name
                    lpe_groups_str += ',' + obj_group.name
                    break
        attrs.SetString(self.rman_scene.rman.Tokens.Rix.k_grouping_membership, obj_groups_str)

        # add to trace sets
        if lpe_groups_str != '*':                       
            attrs.SetString(self.rman_scene.rman.Tokens.Rix.k_identifier_lpegroup, lpe_groups_str)
      
        self.export_light_linking_attributes(ob, attrs)

        if hasattr(ob, 'color'):
            attrs.SetColor('user:Cs', ob.color[:3])   

        if self.rman_scene.rman_bake and self.rman_scene.bl_scene.renderman.rman_bake_illum_filename == 'BAKEFILEATTR':
            filePath = ob.renderman.bake_filename_attr
            if filePath != '':
                # check for <ext> token, we'll add that later when we're doing displays
                if filePath.endswith('.<ext>'):
                    filePath.replace('.<ext>', '')
                else:
                    tokens = os.path.splitext(filePath)
                    if tokens[1] != '':
                        filePath = tokens[0]
                filePath = string_utils.expand_string(filePath,
                                                asFilePath=True)                
                attrs.SetString('user:bake_filename_attr', filePath)

        # user attributes
        for ua in rm.user_attributes:
            param_type = ua.type
            val = getattr(ua, 'value_%s' % ua.type)
            namespace = ua.namespace
            if namespace == '':
                namespace = 'user'
            ri_name = '%s:%s' % (namespace, ua.name)
            property_utils.set_rix_param(attrs, param_type, ri_name, val, is_reference=False, is_array=False)
   

    def export_object_attributes(self, ob, rman_sg_node, remove=True):
        if not rman_sg_node.sg_node:
            return          

        attrs = rman_sg_node.sg_node.GetAttributes()
        self.export_object_attributes_attrs(ob, attrs, remove=remove)

        rman_sg_node.sg_node.SetAttributes(attrs)  