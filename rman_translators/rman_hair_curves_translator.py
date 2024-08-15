from .rman_translator import RmanTranslator
from ..rfb_utils import transform_utils
from ..rfb_utils import scenegraph_utils
from ..rfb_utils.timer_utils import time_this
from ..rfb_utils.scene_utils import BlAttribute
from ..rfb_logger import rfb_log
from ..rman_sg_nodes.rman_sg_haircurves import RmanSgHairCurves
from mathutils import Vector
import math
import bpy    
import numpy as np
from copy import deepcopy

class BlHair:

    def __init__(self):        
        self.points = []
        self.vertsArray = []
        self.nverts = 0
        self.hair_width = []
        self.index = []
        self.bl_hair_attributes = dict()
class RmanHairCurvesTranslator(RmanTranslator):

    def __init__(self, rman_scene):
        super().__init__(rman_scene)
        self.bl_type = 'CURVES'  

    def export(self, ob, db_name):

        sg_node = self.rman_scene.sg_scene.CreateGroup(db_name)
        rman_sg_hair = RmanSgHairCurves(self.rman_scene, sg_node, db_name)

        return rman_sg_hair

    def clear_children(self, ob, rman_sg_hair):
        if rman_sg_hair.sg_node:
            for c in [ rman_sg_hair.sg_node.GetChild(i) for i in range(0, rman_sg_hair.sg_node.GetNumChildren())]:
                rman_sg_hair.sg_node.RemoveChild(c)
                self.rman_scene.sg_scene.DeleteDagNode(c)     
                rman_sg_hair.sg_curves_list.clear()   

    def export_deform_sample(self, rman_sg_hair, ob, time_sample):
        curves = self._get_strands_(ob)
        for i, bl_curve in enumerate(curves):
            curves_sg = rman_sg_hair.sg_curves_list[i]
            if not curves_sg:
                continue
            primvar = curves_sg.GetPrimVars()

            primvar.SetPointDetail(self.rman_scene.rman.Tokens.Rix.k_P, bl_curve.points, "vertex", time_sample)  
            curves_sg.SetPrimVars(primvar)

    def update(self, ob, rman_sg_hair):
        if rman_sg_hair.sg_node:
            if rman_sg_hair.sg_node.GetNumChildren() > 0:
                self.clear_children(ob, rman_sg_hair)

        curves = self._get_strands_(ob)
        if not curves:
            return

        for i, bl_curve in enumerate(curves):
            curves_sg = self.rman_scene.sg_scene.CreateCurves("%s-%d" % (rman_sg_hair.db_name, i))
            curves_sg.Define(self.rman_scene.rman.Tokens.Rix.k_cubic, "nonperiodic", "catmull-rom", len(bl_curve.vertsArray), len(bl_curve.points))
            primvar = curves_sg.GetPrimVars()                  
            primvar.SetPointDetail(self.rman_scene.rman.Tokens.Rix.k_P, bl_curve.points, "vertex")

            primvar.SetIntegerDetail(self.rman_scene.rman.Tokens.Rix.k_Ri_nvertices, bl_curve.vertsArray, "uniform")
            index_nm = 'index'
            primvar.SetIntegerDetail(index_nm, bl_curve.index, "uniform")

            width_detail = "vertex" 
            primvar.SetFloatDetail(self.rman_scene.rman.Tokens.Rix.k_width, bl_curve.hair_width, width_detail)
            
            BlAttribute.set_rman_primvars(primvar, bl_curve.bl_hair_attributes)
                    
            curves_sg.SetPrimVars(primvar)
            rman_sg_hair.sg_node.AddChild(curves_sg)  
            rman_sg_hair.sg_curves_list.append(curves_sg)  
        
    def get_attributes(self, ob, bl_hair_attributes):
        detail_map = { len(ob.data.points): 'vertex', len(ob.data.curves): 'uniform'}
        BlAttribute.parse_attributes(bl_hair_attributes, ob, detail_map)
        if 'color' in bl_hair_attributes:
            # rename color to Cs
            v = bl_hair_attributes['color']
            v.rman_name = 'Cs'
            bl_hair_attributes['color'] = v
            
    def get_attributes_for_curves(self, ob, bl_hair_attributes, bl_curve, idx, fp_idx, npoints):
        uv_map = ob.original.data.surface_uv_map
        for attr in ob.data.attributes:
            if attr.name.startswith('.'):
                continue
            if attr.name not in bl_hair_attributes:
                continue
            hair_attr = bl_hair_attributes[attr.name]

            hair_curve_attr = bl_curve.bl_hair_attributes.get(attr.name, BlAttribute())
            hair_curve_attr.rman_name = hair_attr.rman_name
            hair_curve_attr.rman_detail = hair_attr.rman_detail
            hair_curve_attr.rman_type = hair_attr.rman_type
            if hair_attr.rman_detail == "uniform":
                hair_curve_attr.values.append(hair_attr.values[idx])
            else:
                # if the detail is vertex, use the first point index
                # and npoints to get the values we need
                # we also need to duplicate the end points, like we do for P
                vals = hair_attr.values[fp_idx:fp_idx+npoints]
                vals = vals[:1] + vals + vals[-1:]
                hair_curve_attr.values.append(vals)
            bl_curve.bl_hair_attributes[attr.name] = hair_curve_attr

    def _copy_uv_map(self, ob, bl_hair_attributes, bl_curve):
        # make a copy of the uv_map to scalpST         
        uv_map = ob.original.data.surface_uv_map
        hair_attr = bl_hair_attributes.get(uv_map, None)
        hair_curve_attr = bl_curve.bl_hair_attributes.get(uv_map, None)
        if hair_attr and hair_curve_attr and hair_attr.rman_type == 'float2':
            attr_copy = deepcopy(hair_curve_attr)
            attr_copy.rman_name = 'scalpST'
            bl_curve.bl_hair_attributes['scalpST'] = attr_copy

    @time_this
    def _get_strands_(self, ob):

        curve_sets = []
        bl_curve = BlHair()
        db = ob.data
        bl_hair_attributes = dict()
        self.get_attributes(ob, bl_hair_attributes)
        for curve in db.curves:
            if curve.points_length < 4:
                rfb_log().error("We do not support curves with only 4 control points")
                return []

            npoints = len(curve.points)
            strand_points = np.zeros(npoints*3, dtype=np.float32)
            widths = np.zeros(npoints, dtype=np.float32)
            curve.points.foreach_get('position', strand_points)
            curve.points.foreach_get('radius', widths)
            strand_points = np.reshape(strand_points, (npoints, 3))
            if np.count_nonzero(widths) == 0:
                # radius is 0. Default to 0.005
                widths.fill(0.005)
            widths = widths * 2
            strand_points = strand_points.tolist()
            widths = widths.tolist()

            
            # double the end points
            strand_points = strand_points[:1] + \
                strand_points + strand_points[-1:]

            widths = widths[:1] + widths + widths[-1:]
            
            vertsInStrand = len(strand_points)

            bl_curve.points.extend(strand_points)
            bl_curve.vertsArray.append(vertsInStrand)
            bl_curve.hair_width.extend(widths)
            bl_curve.index.append(curve.index)
            bl_curve.nverts += vertsInStrand           

            self.get_attributes_for_curves(ob, bl_hair_attributes, bl_curve, curve.index, curve.first_point_index, npoints)
               
            # FIXME: is this still needed? 
            # if we get more than 100000 vertices, start a new BlHair.  This
            # is to avoid a maxint on the array length        
            if bl_curve.nverts > 100000:
                self._copy_uv_map(ob, bl_hair_attributes, bl_curve)
                curve_sets.append(bl_curve)
                bl_curve = BlHair()
            

        if bl_curve.nverts > 0:
            self._copy_uv_map(ob, bl_hair_attributes, bl_curve)       
            curve_sets.append(bl_curve)

        return curve_sets              
            