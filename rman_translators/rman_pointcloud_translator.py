from .rman_translator import RmanTranslator
from ..rman_sg_nodes.rman_sg_pointcloud import RmanSgPointCloud
from ..rfb_utils.scene_utils import BlAttribute
from mathutils import Vector
import numpy as np

class RmanPointCloudTranslator(RmanTranslator):

    def __init__(self, rman_scene):
        super().__init__(rman_scene)
        self.bl_type = 'POINTCLOUD' 

    def export(self, ob, db_name):

        sg_node = self.rman_scene.sg_scene.CreatePoints(db_name)
        rman_sg_pointcloud = RmanSgPointCloud(self.rman_scene, sg_node, db_name)

        return rman_sg_pointcloud

    def export_deform_sample(self, rman_sg_pointcloud, ob, time_sample):
        return
    
    def update_primvar(self, ob, rman_sg_pointcloud, prop_name):
        primvars = rman_sg_pointcloud.sg_node.GetPrimVars()
        super().update_object_primvar(ob, primvars, prop_name)
        rman_sg_pointcloud.sg_mesh.SetPrimVars(primvars)

    def get_attributes_for_points(self, ob):    
        bl_attributes = dict()    
        detail_map = {len(ob.data.points): 'vertex'}
        BlAttribute.parse_attributes(bl_attributes, ob, detail_map, detail_default='uniform')
        return bl_attributes

    def update(self, ob, rman_sg_pointcloud): 

        inv_mtx = ob.matrix_world.inverted_safe()   
        pointcloud = ob.data
        nvertices = len(pointcloud.points)
        P = np.zeros(nvertices*3, dtype=np.float32)
        radius = np.zeros(nvertices, dtype=np.float32)
        pointcloud.points.foreach_get('co', P)
        pointcloud.points.foreach_get('radius', radius)
        P = np.reshape(P, (nvertices, 3))

        if np.count_nonzero(radius) == 0:
            radius = []
        else:
            radius = radius * 2.0
            radius = radius.tolist()
        P = [Vector(p) @ inv_mtx for p in P]

        # if this is empty continue:
        if not P or len(P) < 1:
            rman_sg_pointcloud.sg_node = None
            rman_sg_pointcloud.is_transforming = False
            rman_sg_pointcloud.is_deforming = False
            return None        
        
        bl_attributes = self.get_attributes_for_points(ob)        

        npoints = len(P)
        rman_sg_pointcloud.sg_node.Define(npoints)
        rman_sg_pointcloud.npoints = npoints

        primvar = rman_sg_pointcloud.sg_node.GetPrimVars()
        primvar.Clear()      

        primvar.SetPointDetail(self.rman_scene.rman.Tokens.Rix.k_P, P, "vertex")
        if radius:
            primvar.SetFloatDetail(self.rman_scene.rman.Tokens.Rix.k_width, radius, "vertex")

        BlAttribute.set_rman_primvars(primvar, bl_attributes)         
            
        super().export_object_primvars(ob, primvar)            
        rman_sg_pointcloud.sg_node.SetPrimVars(primvar)         