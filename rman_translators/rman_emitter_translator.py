from .rman_translator import RmanTranslator
from ..rman_sg_nodes.rman_sg_emitter import RmanSgEmitter
from ..rfb_utils import object_utils
from ..rfb_utils import transform_utils
from ..rfb_utils import scenegraph_utils
from ..rfb_utils import particles_utils

import bpy
import math

class RmanEmitterTranslator(RmanTranslator):

    def __init__(self, rman_scene):
        super().__init__(rman_scene)
        self.bl_type = 'EMITTER' 

    def export(self, ob, psys, db_name):

        sg_node = self.rman_scene.sg_scene.CreatePoints('%s-POINTS' % db_name)
        rman_sg_emitter = RmanSgEmitter(self.rman_scene, sg_node, db_name)

        return rman_sg_emitter

    def export_deform_sample(self, rman_sg_emitter, ob, psys, time_sample):
        return  

    def clear_children(self, ob, psys, rman_sg_emitter):
        if rman_sg_emitter.sg_node:        
            for c in [ rman_sg_emitter.sg_node.GetChild(i) for i in range(0, rman_sg_emitter.sg_node.GetNumChildren())]:
                rman_sg_emitter.sg_node.RemoveChild(c)
                self.rman_scene.sg_scene.DeleteDagNode(c)                

    def add_object_instance(self, rman_sg_emitter, rman_sg_group):
        rman_sg_emitter.sg_node.AddChild(rman_sg_group.sg_node)
        rman_sg_emitter.instances[rman_sg_group.db_name] = rman_sg_group
        rman_sg_group.rman_sg_group_parent = rman_sg_emitter

    def update(self, ob, psys, rman_sg_emitter):

        sg_emitter_node = rman_sg_emitter.sg_node

        rm = psys.settings.renderman
        inv_mtx = ob.matrix_world.inverted_safe()
        cur_frame = self.rman_scene.bl_scene.frame_current
        do_motion = do_motion = self.rman_scene.do_motion_blur
        P, next_P, width = particles_utils.get_particles(ob, psys, inv_mtx, cur_frame, get_next_P=do_motion)

        if not P:
            return

        rman_sg_emitter.npoints = len(P)
        sg_emitter_node.Define(rman_sg_emitter.npoints)          

        primvar = sg_emitter_node.GetPrimVars()
        primvar.Clear()
            
        if rman_sg_emitter.motion_steps and rm.do_velocity_blur:
            super().set_primvar_times(rman_sg_emitter.motion_steps, primvar)
        else:
            primvar.SetTimes([])            
    
        
        particles_utils.get_primvars_particle(primvar, cur_frame, psys, [cur_frame], 0)      
        
        if self.rman_scene.do_motion_blur and rm.do_velocity_blur:
            primvar.SetPointDetail(self.rman_scene.rman.Tokens.Rix.k_P, P, "vertex", 0) 
            primvar.SetPointDetail(self.rman_scene.rman.Tokens.Rix.k_P, next_P, "vertex", 1)  
        else:
            primvar.SetPointDetail(self.rman_scene.rman.Tokens.Rix.k_P, P, "vertex")                   
        if rm.constant_width:
            width = rm.width
            primvar.SetFloatDetail(self.rman_scene.rman.Tokens.Rix.k_width, width, "constant")
        else:
            primvar.SetFloatDetail(self.rman_scene.rman.Tokens.Rix.k_width, width, "vertex")                     

        super().export_object_primvars(ob, primvar)
        sg_emitter_node.SetPrimVars(primvar)

        # Attach material
        mat_idx = psys.settings.material - 1
        if mat_idx < len(ob.material_slots):
            mat = ob.material_slots[mat_idx].material
            material_sg_node = None
            if mat:
                rman_sg_material = self.rman_scene.rman_materials.get(mat.original, None)
                if rman_sg_material:
                    material_sg_node = rman_sg_material.sg_node
            scenegraph_utils.set_material(sg_emitter_node, material_sg_node, rman_sg_material, mat=mat, ob=ob)