from .rman_translator import RmanTranslator
from ..rfb_utils import transform_utils
from ..rfb_utils import scenegraph_utils
from ..rfb_logger import rfb_log
from ..rman_sg_nodes.rman_sg_hair import RmanSgHair
from mathutils import Vector
import math
import bpy    
import numpy as np

class BlHair:

    def __init__(self):        
        self.points = []
        self.next_points = []
        self.vertsArray = []
        self.scalpST = []
        self.mcols = []
        self.nverts = 0
        self.hair_width = []

    @property
    def constant_width(self):
        return (len(self.hair_width) < 2)
class RmanHairTranslator(RmanTranslator):

    def __init__(self, rman_scene):
        super().__init__(rman_scene)
        self.bl_type = 'HAIR'  

    def export(self, ob, psys, db_name):

        sg_node = self.rman_scene.sg_scene.CreateGroup(db_name)
        rman_sg_hair = RmanSgHair(self.rman_scene, sg_node, db_name)

        return rman_sg_hair

    def clear_children(self, ob, psys, rman_sg_hair):
        if rman_sg_hair.sg_node:
            for c in [ rman_sg_hair.sg_node.GetChild(i) for i in range(0, rman_sg_hair.sg_node.GetNumChildren())]:
                rman_sg_hair.sg_node.RemoveChild(c)
                self.rman_scene.sg_scene.DeleteDagNode(c)     
                rman_sg_hair.sg_curves_list.clear()   

    def export_deform_sample(self, rman_sg_hair, ob, psys, time_sample):
        return

        '''
        # Keep this code below, in case we want to give users the option
        # to do non-velocity based motion blur

        curves = self._get_strands_(ob, psys)
        for i, bl_curve in enumerate(curves):
            curves_sg = rman_sg_hair.sg_curves_list[i]
            if not curves_sg:
                continue
            primvar = curves_sg.GetPrimVars()

            primvar.SetPointDetail(self.rman_scene.rman.Tokens.Rix.k_P, bl_curve.points, "vertex", time_sample)  
            curves_sg.SetPrimVars(primvar)
        '''

    def update(self, ob, psys, rman_sg_hair):
        if rman_sg_hair.sg_node:
            if rman_sg_hair.sg_node.GetNumChildren() > 0:
                self.clear_children(ob, psys, rman_sg_hair)

        curves = self._get_strands_(ob, psys)
        if not curves:
            return

        ob_inv_mtx = transform_utils.convert_matrix(ob.matrix_world.inverted_safe())
        for i, bl_curve in enumerate(curves):
            curves_sg = self.rman_scene.sg_scene.CreateCurves("%s-%d" % (rman_sg_hair.db_name, i))
            curves_sg.SetTransform(ob_inv_mtx) # puts points in object space
            curves_sg.Define(self.rman_scene.rman.Tokens.Rix.k_cubic, "nonperiodic", "catmull-rom", len(bl_curve.vertsArray), len(bl_curve.points))
            primvar = curves_sg.GetPrimVars()            
            if rman_sg_hair.motion_steps and psys.settings.renderman.do_velocity_blur:
                super().set_primvar_times(rman_sg_hair.motion_steps, primvar)            
            else:
                print("SET TIMES")
                primvar.SetTimes([])

            if self.rman_scene.do_motion_blur and psys.settings.renderman.do_velocity_blur:
                primvar.SetPointDetail(self.rman_scene.rman.Tokens.Rix.k_P, bl_curve.points, "vertex", 0)
                primvar.SetPointDetail(self.rman_scene.rman.Tokens.Rix.k_P, bl_curve.next_points, "vertex", 1)
            else:
                primvar.SetPointDetail(self.rman_scene.rman.Tokens.Rix.k_P, bl_curve.points, "vertex")

            primvar.SetIntegerDetail(self.rman_scene.rman.Tokens.Rix.k_Ri_nvertices, bl_curve.vertsArray, "uniform")
            index_nm = psys.settings.renderman.hair_index_name
            if index_nm == '':
                index_nm = 'index'
            primvar.SetIntegerDetail(index_nm, range(len(bl_curve.vertsArray)), "uniform")

            width_detail = "vertex"
            if bl_curve.constant_width:
                width_detail = "constant" 
            primvar.SetFloatDetail(self.rman_scene.rman.Tokens.Rix.k_width, bl_curve.hair_width, width_detail)
            
            if len(bl_curve.scalpST):
                primvar.SetFloatArrayDetail("scalpST", bl_curve.scalpST, 2, "uniform")

            if len(bl_curve.mcols):
                primvar.SetColorDetail("Cs", bl_curve.mcols, "uniform")
                    
            curves_sg.SetPrimVars(primvar)
            rman_sg_hair.sg_node.AddChild(curves_sg)  
            rman_sg_hair.sg_curves_list.append(curves_sg)

        # Attach material
        mat_idx = psys.settings.material - 1
        if mat_idx < len(ob.material_slots):
            mat = ob.material_slots[mat_idx].material
            material_sg_node = None
            if mat:
                rman_sg_material = self.rman_scene.rman_materials.get(mat.original, None)
                if rman_sg_material:
                    material_sg_node = rman_sg_material.sg_node
            scenegraph_utils.set_material(rman_sg_hair.sg_node, material_sg_node, rman_sg_material, mat=mat, ob=ob)
        
    def add_object_instance(self, rman_sg_hair, rman_sg_group):
        rman_sg_hair.sg_node.AddChild(rman_sg_group.sg_node)                
        rman_sg_hair.instances[rman_sg_group.db_name] = rman_sg_group
        rman_sg_group.rman_sg_group_parent = rman_sg_hair

    def _get_strands_(self, ob, psys):

        psys_modifier = None
        for mod in ob.modifiers:
            if hasattr(mod, 'particle_system') and mod.particle_system == psys:
                psys_modifier = mod
                break

        if self.rman_scene.is_interactive:
            if psys_modifier and not psys_modifier.show_viewport:
                return None
        else:
            if psys_modifier and not psys_modifier.show_render:
                return None             

        tip_width = psys.settings.tip_radius * psys.settings.radius_scale
        base_width = psys.settings.root_radius * psys.settings.radius_scale
        conwidth = (tip_width == base_width)                 

        if self.rman_scene.is_interactive:
            steps = (2 ** psys.settings.display_step)+1
        else:
            steps = (2 ** psys.settings.render_step)+1
        
        num_parents = len(psys.particles)
        num_children = len(psys.child_particles)
        rm = psys.settings.renderman
        if self.rman_scene.is_interactive:
            num_children = int(num_children * psys.settings.display_percentage / 100.0)
        total_hair_count = num_parents + num_children
        uv_set = 0
        export_st = rm.export_scalp_st and psys_modifier and len(
            ob.data.uv_layers) > 0
        if export_st and rm.uv_name != '':
            for i, uv in enumerate(ob.data.uv_layers):
                if uv.name == rm.uv_name:
                    uv_set = i
                    break
        mcol_set = 0
        export_mcol = rm.export_mcol and psys_modifier and len(
            ob.data.vertex_colors) > 0
        if export_mcol and rm.mcol_name != '':
            for i, mcol in enumerate(ob.data.vertex_colors):
                if mcol.name == rm.mcol_name:
                    mcol_set = i
                    break            

        curve_sets = []
        bl_curve = BlHair()
        if conwidth:
            bl_curve.hair_width.append(base_width)
        
        start_idx = 0
        if psys.settings.child_type != 'NONE' and num_children > 0:
            start_idx = num_parents
        
        for pindex in range(start_idx, total_hair_count):
            particle = psys.particles[
                (pindex - num_parents) % num_parents]           
            strand_points = []
            next_strand_points = []
            # walk through each strand
            for step in range(0, steps):           
                pt = psys.co_hair(ob, particle_no=pindex, step=step)

                if pt.length_squared == 0:
                    # this strand ends prematurely                    
                    break                

                strand_points.append(pt)

            if len(strand_points) < 2:
                # not enought points
                continue

            # double the first and last
            strand_points = strand_points[:1] + \
                strand_points + strand_points[-1:]
                
            vertsInStrand = len(strand_points)

            # catmull-rom requires at least 4 vertices
            if vertsInStrand < 4:
                continue

            if self.rman_scene.do_motion_blur:
                # calculate the points for the next frame using velocity
                vel = Vector(particle.velocity / particle.lifetime )
                next_strand_points = [p + vel for p in strand_points]

            # for varying width make the width array
            if not conwidth:
                decr = (base_width - tip_width) / (vertsInStrand - 2)
                bl_curve.hair_width.extend([base_width] + [(base_width - decr * i)
                                                for i in range(vertsInStrand - 2)] +
                                [tip_width])

            bl_curve.points.extend(strand_points)
            bl_curve.next_points.extend(next_strand_points)
            bl_curve.vertsArray.append(vertsInStrand)
            bl_curve.nverts += vertsInStrand
               
            # get the scalp ST
            if export_st:
                st = psys.uv_on_emitter(psys_modifier, particle=particle, particle_no=pindex, uv_no=uv_set)
                bl_curve.scalpST.append(st)

            # get mcol
            if export_mcol:                 
                mcol = psys.mcol_on_emitter(psys_modifier, particle=particle, particle_no=pindex, vcol_no=mcol_set)
                bl_curve.mcols.append(mcol)

            # if we get more than 100000 vertices, start a new BlHair.  This
            # is to avoid a maxint on the array length
            if bl_curve.nverts > 100000:
                curve_sets.append(bl_curve)
                bl_curve = BlHair()
                if conwidth:
                    bl_curve.hair_width.append(base_width)                

        if bl_curve.nverts > 0:       
            curve_sets.append(bl_curve)

        return curve_sets              
            