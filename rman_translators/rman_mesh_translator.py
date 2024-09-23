from .rman_translator import RmanTranslator
from ..rman_sg_nodes.rman_sg_mesh import RmanSgMesh
from ..rfb_utils import object_utils
from ..rfb_utils import mesh_utils
from ..rfb_utils import string_utils
from ..rfb_utils import property_utils
from ..rfb_utils import scenegraph_utils
from ..rfb_utils.scene_utils import BlAttribute
from ..rfb_logger import rfb_log
from ..rman_constants import BLENDER_41

import bpy
import math
import bmesh
import numpy as np

def _get_mats_faces_(nverts, material_ids):

    mats = {}
    for face_id, num_verts in enumerate(nverts):
        mat_id = material_ids[face_id]
        if mat_id not in mats:
            mats[mat_id] = []
        mats[mat_id].append(face_id)
    return mats

def _is_multi_material_(ob, mesh):
    if len(ob.data.materials) < 2 or len(mesh.polygons) == 0:
        return False

    first_mat = mesh.polygons[0].material_index
    for p in mesh.polygons:
        if p.material_index != first_mat:
            return True
    return False

# requires facevertex interpolation
def _get_mesh_uv_(mesh, name="", ob=None):
    uvs = []
    data = "uv"
    if not name:
        uv_loop_layer = mesh.uv_layers.active
        if ob and uv_loop_layer is None:
            if not hasattr(ob.original.data, 'uv_layers'):
                return None            
            # when dealing geometry nodes, uv_layers are actually
            # on the attributes property.
            # Look up from original object what the active
            # uv layer was
            active = ob.original.data.uv_layers.active
            if active:
                uv_loop_layer = mesh.attributes.get(active.name)
                data = "vector"        
    else:
        uv_loop_layer = mesh.uv_layers.get(name, None)
        if uv_loop_layer is None:
            uv_loop_layer = mesh.attributes.get(name, None)
            data = "vector"

    if uv_loop_layer is None:
        return None

    uv_count = len(uv_loop_layer.data)
    fastuvs = np.zeros(uv_count * 2)
    uv_loop_layer.data.foreach_get(data, fastuvs)   
    uvs = fastuvs.tolist()

    return uvs

def _get_mesh_vcol_(mesh, name="", ob=None):    
    if not name:
        vcol_layer = mesh.vertex_colors.active
        if ob and not vcol_layer:
            if not hasattr(ob.original.data, 'vertex_colors'):
                return None
            # same issue with uv's
            # vertex colors for geometry nodes are on the attributes
            # property
            active = ob.original.data.vertex_colors.active
            if active:
                vcol_layer = mesh.attributes.get(active.name, None)        
    else:
        vcol_layer = mesh.vertex_colors[name]
        if not vcol_layer:
            vcol_layer = mesh.attributes.get(name, None)

    if vcol_layer is None:
        return None

    vcol_count = len(vcol_layer.data)
    fastvcols = np.zeros(vcol_count * 4)
    vcol_layer.data.foreach_get("color", fastvcols)
    fastvcols = np.reshape(fastvcols, (vcol_count, 4))
    pre_cols = fastvcols.tolist()     
    
    cols = [ [c[0], c[1], c[2]] for c in pre_cols ]

    return cols    

def _get_mesh_vattr_(mesh, name=""):
    if not name in mesh.attributes and mesh != "":
        rfb_log().error("Cannot find color attribute ")
        return None
    vattr_layer = mesh.attributes[name] if name != "" \
        else mesh.attributes.active

    if vattr_layer is None:
        return None

    vcol_count = len(vattr_layer.data)
    fastvattrs = np.zeros(vcol_count * 4)
    vattr_layer.data.foreach_get("color", fastvattrs)
    fastvattrs = np.reshape(fastvattrs, (vcol_count, 4))
    pre_cols = fastvattrs.tolist()     
    
    attrs = [ [a[0], a[1], a[2]] for a in pre_cols ]

    return attrs 

def _get_mesh_vgroup_(ob, mesh, name=""):
    vgroup = ob.vertex_groups[name] if name != "" else ob.vertex_groups.active
    weights = []

    if vgroup is None:
        return None

    for v in mesh.vertices:
        if len(v.groups) == 0:
            weights.append(0.0)
        else:
            weights.extend([g.weight for g in v.groups
                            if g.group == vgroup.index])

    return weights

def _get_material_ids(ob, geo):        
    fast_material_ids = np.zeros(len(geo.polygons), dtype=np.int32)
    geo.polygons.foreach_get("material_index", fast_material_ids)
    material_ids = fast_material_ids.tolist()
    return material_ids

def _export_reference_pose(ob, rman_sg_mesh, rm, rixparams):
    rman__Pref = []
    rman__WPref = []
    rman__Nref = []
    rman__WNref = []

    vertex_detail = rman_sg_mesh.npoints 
    facevarying_detail = rman_sg_mesh.nverts 
    uniform_detail = rman_sg_mesh.npolys

    for rp in rm.reference_pose:
        if rp.has_Pref:
            rman__Pref.append( rp.rman__Pref)
        if rp.has_WPref:
            rman__WPref.append( rp.rman__WPref)

    for rp in rm.reference_pose_normals:
        if rp.has_Nref:
            rman__Nref.append( rp.rman__Nref)
        if rp.has_WNref:
            rman__WNref.append( rp.rman__WNref)

    if rman__Pref:
        if len(rman__Pref) == vertex_detail:
            rixparams.SetPointDetail('__Pref', rman__Pref, 'vertex')
        else:
            rfb_log().error("Number of Pref primvars do not match. Please re-freeze the reference position.")

    if rman__WPref:
        if len(rman__WPref) == vertex_detail:
            rixparams.SetPointDetail('__WPref', rman__WPref, 'vertex')
        else:
            rfb_log().error("Number of WPref primvars do not match. Please re-freeze the reference position.")
                
    if rman__Nref:
        if len(rman__Nref) == vertex_detail:
            rixparams.SetNormalDetail('__Nref', rman__Nref, 'vertex')
        elif len(rman__Nref) == facevarying_detail:
            rixparams.SetNormalDetail('__Nref', rman__Nref, 'facevarying')
        elif len(rman__Nref) == uniform_detail:
            rixparams.SetNormalDetail('__Nref', rman__Nref, 'uniform')            
        else:
            rfb_log().error("Number of Nref primvars do not match. Please re-freeze the reference position.")
        
    if rman__WNref:
        if len(rman__WNref) == vertex_detail:
            rixparams.SetNormalDetail('__Nref', rman__Nref, 'vertex')
        elif len(rman__WNref) == facevarying_detail:
            rixparams.SetNormalDetail('__WNref', rman__WNref, 'facevarying')
        elif len(rman__WNref) == uniform_detail:
            rixparams.SetNormalDetail('__WNref', rman__WNref, 'uniform')            
        else:
            rfb_log().error("Number of WNref primvars do not match. Please re-freeze the reference position.")
            print("%d vs %d vs %d" % (len(rman__Nref), vertex_detail, facevarying_detail))

def export_tangents(ob, geo, rixparams, uvmap="", name=""):
    # also export the tangent and bitangent vectors
    try:
        if uvmap == "":
            geo.calc_tangents(uvmap=geo.uv_layers.active.name)         
        else:
            geo.calc_tangents(uvmap=uvmap)
        loops = len(geo.loops)
        fasttangent = np.zeros(loops*3, dtype=np.float32)
        geo.loops.foreach_get('tangent', fasttangent)
        fasttangent = np.reshape(fasttangent, (loops, 3))
        tangents = fasttangent.tolist()    

        fastbitangent = np.zeros(loops*3, dtype=np.float32)
        geo.loops.foreach_get('bitangent', fastbitangent)
        bitangent = fastbitangent.tolist()      
        geo.free_tangents()    

        if name == "":
            rixparams.SetVectorDetail('Tn', tangents, 'facevarying')
            rixparams.SetVectorDetail('Bn', bitangent, 'facevarying')    
        else:
            rixparams.SetVectorDetail('%s_Tn' % name, tangents, 'facevarying')
            rixparams.SetVectorDetail('%s_Bn' % name, bitangent, 'facevarying')                
    except RuntimeError as err:
        rfb_log().debug("Can't export tangent vectors: %s" % str(err))       

def _get_primvars_(ob, rman_sg_mesh, geo, rixparams):
    #rm = ob.data.renderman
    # Stange problem here : ob seems to not be in sync with the scene
    # when a geometry node is active...
    rm = ob.original.data.renderman

    facevarying_detail = rman_sg_mesh.nverts 

    if rm.export_default_uv:
        uvs = _get_mesh_uv_(geo, ob=ob)
        if uvs and len(uvs) > 0:
            detail = "facevarying" if (facevarying_detail*2) == len(uvs) else "vertex"
            rixparams.SetFloatArrayDetail("st", uvs, 2, detail)
            if rm.export_default_tangents:
                export_tangents(ob, geo, rixparams)    

    if rm.export_default_vcol:
        vcols = _get_mesh_vcol_(geo, ob=ob)
        if vcols and len(vcols) > 0:
            detail = "facevarying" if facevarying_detail == len(vcols) else "vertex"
            rixparams.SetColorDetail("Cs", vcols, detail)

    # reference pose
    if hasattr(rm, 'reference_pose'):
        _export_reference_pose(ob, rman_sg_mesh, rm, rixparams)

    output_all_primvars = getattr(rm, 'output_all_primvars', False)
    if output_all_primvars:
        # export all of the attributes
        detail_map = { facevarying_detail: 'facevarying',
                    rman_sg_mesh.npoints: 'vertex', rman_sg_mesh.npolys: 'uniform'}
        attrs_dict = dict()
        BlAttribute.parse_attributes(attrs_dict, ob, detail_map)
        BlAttribute.set_rman_primvars(rixparams, attrs_dict)

        # vertex group
        for nm in ob.vertex_groups.keys():
            weights = _get_mesh_vgroup_(ob, geo, nm)
            if weights and len(weights) > 0:
                detail = "facevarying" if facevarying_detail == len(weights) else "vertex"
                rixparams.SetFloatDetail(nm, weights, detail)        
        
    else:
        # custom prim vars
        for p in rm.prim_vars:
            if p.data_source == 'VERTEX_COLOR':
                vcols = _get_mesh_vcol_(geo, p.data_name)
                
                if vcols and len(vcols) > 0:
                    detail = "facevarying" if facevarying_detail == len(vcols) else "vertex"
                    rixparams.SetColorDetail(p.name, vcols, detail)
                
            elif p.data_source == 'UV_TEXTURE':
                uvs = _get_mesh_uv_(geo, p.data_name)
                if uvs and len(uvs) > 0:
                    detail = "facevarying" if (facevarying_detail*2) == len(uvs) else "vertex"
                    rixparams.SetFloatArrayDetail(p.name, uvs, 2, detail)
                    if p.export_tangents:
                        export_tangents(ob, geo, rixparams, uvmap=p.data_name, name=p.name) 

            elif p.data_source == 'VERTEX_GROUP':
                weights = _get_mesh_vgroup_(ob, geo, p.data_name)
                if weights and len(weights) > 0:
                    detail = "facevarying" if facevarying_detail == len(weights) else "vertex"
                    rixparams.SetFloatDetail(p.name, weights, detail)
            elif p.data_source == 'VERTEX_ATTR_COLOR':
                vattr = _get_mesh_vattr_(geo, p.data_name)            
                if vattr and len(vattr) > 0:
                    detail = "facevarying" if facevarying_detail == len(vattr) else "vertex"
                    rixparams.SetColorDetail(p.data_name, vattr, detail)

    rm_scene = rman_sg_mesh.rman_scene.bl_scene.renderman
    property_utils.set_primvar_bl_props(rixparams, rm, inherit_node=rm_scene)

class RmanMeshTranslator(RmanTranslator):

    def __init__(self, rman_scene):
        super().__init__(rman_scene)
        self.bl_type = 'MESH' 

    def _get_subd_tags_(self, ob, mesh, primvar):
        rm = mesh.renderman

        tags = ['interpolateboundary', 'facevaryinginterpolateboundary']
        nargs = [1, 0, 0, 1, 0, 0]
        intargs = [ int(ob.data.renderman.rman_subdivInterp),
                int(ob.data.renderman.rman_subdivFacevaryingInterp)]
        floatargs = []
        stringargs = []   

        # get creases
        edges_len = len(mesh.edges)
        creases = np.zeros(edges_len, dtype=np.float32)
        if BLENDER_41:
            if mesh.edge_creases:
                mesh.edge_creases.data.foreach_get('value', creases)
        else:
            mesh.edges.foreach_get('crease', creases)
        if (creases > 0.0).any():
            # we have edges where their crease is > 0.0
            # grab only those edges
            crease_edges = np.zeros(edges_len*2, dtype=np.int32)
            mesh.edges.foreach_get('vertices', crease_edges)
            crease_edges = np.reshape(crease_edges, (edges_len, 2))
            crease_edges = crease_edges[creases > 0.0]
            
            # squared, to match blender appareance better
            #: range 0 - 10 (infinitely sharp)
            creases = creases * creases * 10.0
            
            creases = creases[creases > 0.0]
            edges_subset_len = len(creases) 

            tags.extend(['crease'] * edges_subset_len)
            nargs.extend([2, 1, 0] * edges_subset_len)
            intargs.extend(crease_edges.flatten().tolist())
            floatargs.extend(creases.tolist())   

        '''
        # Blender 4.0 removed face maps, also adding holes
        # in subdivs won't work in XPU
        holes_facemap = getattr(rm, 'rman_holesFaceMap', '')
        if holes_facemap != '' and holes_facemap in ob.face_maps:
            # use this facemap for face edit holes
            holes_idx = ob.face_maps[holes_facemap].index
            bm = bmesh.new()
            bm.from_mesh(mesh)
            fm = bm.faces.layers.face_map.verify()

            holes = []
            for face in bm.faces:
                face_idx = face.index
                map_idx = face[fm]  
                if map_idx == holes_idx:
                    holes.append(face_idx)
            if holes:
                tags.append('faceedit')
                num_holes = len(holes)
                for h in holes:
                    intargs.extend([1, h])
                nargs.extend([num_holes*2, 0, num_holes])
                stringargs.extend(['hole'] * num_holes)

            bm.free()
        '''

        primvar.SetStringArray(self.rman_scene.rman.Tokens.Rix.k_Ri_subdivtags, tags, len(tags))
        primvar.SetIntegerArray(self.rman_scene.rman.Tokens.Rix.k_Ri_subdivtagnargs, nargs, len(nargs))
        primvar.SetIntegerArray(self.rman_scene.rman.Tokens.Rix.k_Ri_subdivtagintargs, intargs, len(intargs))
        primvar.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_subdivtagfloatargs, floatargs, len(floatargs))
        primvar.SetStringArray(self.rman_scene.rman.Tokens.Rix.k_Ri_subdivtagstringtags, stringargs, len(stringargs))        

    def export(self, ob, db_name):
        
        sg_node = self.rman_scene.sg_scene.CreateGroup('')
        rman_sg_mesh = RmanSgMesh(self.rman_scene, sg_node, db_name)
        rman_sg_mesh.sg_mesh = self.rman_scene.sg_scene.CreateMesh(db_name)
        rman_sg_mesh.sg_node.AddChild(rman_sg_mesh.sg_mesh)

        if self.rman_scene.do_motion_blur:
            rman_sg_mesh.is_transforming = object_utils.is_transforming(ob)
            rman_sg_mesh.is_deforming = object_utils._is_deforming_(ob)

        return rman_sg_mesh

    def export_deform_sample(self, rman_sg_mesh, ob, time_sample, sg_node=None):

        mesh = None
        mesh = ob.to_mesh()
        if not sg_node:
            sg_node = rman_sg_mesh.sg_mesh
        primvar = sg_node.GetPrimVars()
        P = mesh_utils.get_mesh_points_(mesh)
        npoints = len(P)

        if rman_sg_mesh.npoints != npoints:
            primvar.SetTimes([])
            sg_node.SetPrimVars(primvar)
            rman_sg_mesh.is_transforming = False
            rman_sg_mesh.is_deforming = False
            if rman_sg_mesh.is_multi_material:
                for c in rman_sg_mesh.multi_material_children:
                    pvar = c.GetPrimVars()
                    pvar.SetTimes( [] )                               
                    c.SetPrimVars(pvar)            
            return       

        primvar.SetPointDetail(self.rman_scene.rman.Tokens.Rix.k_P, P, "vertex", time_sample)                            

        sg_node.SetPrimVars(primvar)

        if rman_sg_mesh.is_multi_material:
            for c in rman_sg_mesh.multi_material_children:
                pvar = c.GetPrimVars()
                pvar.SetPointDetail(self.rman_scene.rman.Tokens.Rix.k_P, P, "vertex", time_sample)                                  
                c.SetPrimVars(pvar)

        ob.to_mesh_clear()    

    def update_primvar(self, ob, rman_sg_mesh, prop_name):
        mesh = ob.to_mesh()
        primvars = rman_sg_mesh.sg_mesh.GetPrimVars()
        if prop_name in mesh.renderman.prop_meta:
            rm = mesh.renderman
            meta = rm.prop_meta[prop_name]
            rm_scene = self.rman_scene.bl_scene.renderman
            property_utils.set_primvar_bl_prop(primvars, prop_name, meta, rm, inherit_node=rm_scene)        
        else:
            super().update_object_primvar(ob, primvars, prop_name)
        rman_sg_mesh.sg_mesh.SetPrimVars(primvars)
        ob.to_mesh_clear()

    def update(self, ob, rman_sg_mesh, input_mesh=None, sg_node=None):
        rm = ob.original.data.renderman
        mesh = input_mesh
        if not mesh:
            mesh = ob.to_mesh()
            if not mesh:
                return True

        if not sg_node:
            sg_node = rman_sg_mesh.sg_mesh

        rman_sg_mesh.is_subdiv = object_utils.is_subdmesh(ob.original)
        use_subdiv_modifer = (rman_sg_mesh.is_subdiv and rm.rman_subdiv_scheme == "none")
        use_smooth_normals = getattr(rm, 'rman_smoothnormals', False)
        get_normals = (rman_sg_mesh.is_subdiv == 0 and not use_smooth_normals)
        if use_subdiv_modifer:
            # always get the normals when we're using the subdiv modifier
            get_normals = True
        rman_mesh = mesh_utils.get_mesh(mesh, get_normals=get_normals)
        nverts = rman_mesh.nverts
        verts = rman_mesh.verts
        P = rman_mesh.P
        N = rman_mesh.N
        
        # if this is empty continue:
        if nverts == []:
            if not input_mesh:
                ob.to_mesh_clear()
            rman_sg_mesh.npoints = 0
            rman_sg_mesh.npolys = 0
            rman_sg_mesh.nverts = 0
            rman_sg_mesh.is_transforming = False
            rman_sg_mesh.is_deforming = False
            rman_sg_mesh.sg_node.RemoveChild(rman_sg_mesh.sg_mesh)
            return None
        
        # double check that sg_mesh has been added
        # as a child
        if rman_sg_mesh.sg_node.GetNumChildren() < 1:
            rman_sg_mesh.sg_node.AddChild(rman_sg_mesh.sg_mesh)

        npolys = len(nverts) 
        npoints = len(P)
        numnverts = len(verts)

        rman_sg_mesh.npoints = npoints
        rman_sg_mesh.npolys = npolys
        rman_sg_mesh.nverts = numnverts

        sg_node.Define( npolys, npoints, numnverts )
        rman_sg_mesh.is_multi_material = _is_multi_material_(ob, mesh)
            
        primvar = sg_node.GetPrimVars()
        primvar.Clear()

        if rman_sg_mesh.is_deforming and len(rman_sg_mesh.deform_motion_steps) > 1:
            super().set_primvar_times(rman_sg_mesh.deform_motion_steps, primvar)
        
        primvar.SetPointDetail(self.rman_scene.rman.Tokens.Rix.k_P, P, "vertex")
        _get_primvars_(ob, rman_sg_mesh, mesh, primvar)   

        primvar.SetIntegerDetail(self.rman_scene.rman.Tokens.Rix.k_Ri_nvertices, nverts, "uniform")
        primvar.SetIntegerDetail(self.rman_scene.rman.Tokens.Rix.k_Ri_vertices, verts, "facevarying")                  

        if rman_sg_mesh.is_subdiv:
            creases = self._get_subd_tags_(ob, mesh, primvar)
            if use_subdiv_modifer:
                # we were tagged as a subdiv by a modifier
                # use bilinear
                sg_node.SetScheme(self.rman_scene.rman.Tokens.Rix.k_bilinear) 
            else:
                sg_node.SetScheme(rm.rman_subdiv_scheme) 

        else:
            sg_node.SetScheme(None)

        if not rman_sg_mesh.is_subdiv or use_subdiv_modifer:
            if N:
                if len(N) == numnverts:
                    primvar.SetNormalDetail(self.rman_scene.rman.Tokens.Rix.k_N, N, "facevarying")         
                else:
                    primvar.SetNormalDetail(self.rman_scene.rman.Tokens.Rix.k_N, N, "uniform")         
        subdiv_scheme = getattr(rm, 'rman_subdiv_scheme', 'none')
        rman_sg_mesh.subdiv_scheme = subdiv_scheme

        super().export_object_primvars(ob, primvar)

        if rman_sg_mesh.is_multi_material:
            material_ids = _get_material_ids(ob, mesh)
            i = 1
            mat_faces_dict = _get_mats_faces_(nverts, material_ids)
            min_idx = min(mat_faces_dict.keys()) # find the minimun material index
            for mat_id, faces in mat_faces_dict.items():
                # If the face has a mat index that is higher than the number of
                # material slots, use the last material. This is what
                # Eevee/Cycles does.
                if mat_id >= len(ob.data.materials):
                    mat = ob.data.materials[-1]
                else:
                    mat = ob.data.materials[mat_id]
                if not mat:
                    continue
                sg_material = self.rman_scene.rman_materials.get(mat.original, None)

                if mat_id == min_idx:
                    primvar.SetIntegerArray(self.rman_scene.rman.Tokens.Rix.k_shade_faceset, faces, len(faces))
                    scenegraph_utils.set_material(sg_node, sg_material.sg_node, sg_material, mat=mat, ob=ob)
                else:                
                    sg_sub_mesh =  self.rman_scene.sg_scene.CreateMesh("%s-%d" % (rman_sg_mesh.db_name, i))
                    i += 1
                    sg_sub_mesh.Define( npolys, npoints, numnverts )                   
                    if rman_sg_mesh.is_subdiv:
                        sg_sub_mesh.SetScheme(self.rman_scene.rman.Tokens.Rix.k_catmullclark)
                    pvars = sg_sub_mesh.GetPrimVars()  
                    if rman_sg_mesh.is_deforming and len(rman_sg_mesh.deform_motion_steps) > 1:
                        super().set_primvar_times(rman_sg_mesh.deform_motion_steps, pvars)
                    pvars.Inherit(primvar)
                    pvars.SetIntegerArray(self.rman_scene.rman.Tokens.Rix.k_shade_faceset, faces, len(faces))                    
                    sg_sub_mesh.SetPrimVars(pvars)
                    scenegraph_utils.set_material(sg_sub_mesh, sg_material.sg_node, sg_material, mat=mat, ob=ob)
                    sg_node.AddChild(sg_sub_mesh)
                    rman_sg_mesh.multi_material_children.append(sg_sub_mesh)
        else:
            rman_sg_mesh.multi_material_children = []

        sg_node.SetPrimVars(primvar)

        if not input_mesh:
            ob.to_mesh_clear()  

        return True    