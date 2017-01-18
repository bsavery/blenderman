import os
from .base_classes import RendermanPropertyGroup

''' Mesh Properties ''' 

def get_mesh(mesh, get_normals=False):
    ''' returns the nverts, verts, P, N from a mesh for doing rib gen ''' 
    nverts = []
    verts = []
    P = []
    N = []

    for v in mesh.vertices:
        P.extend(v.co)

    for p in mesh.polygons:
        nverts.append(p.loop_total)
        verts.extend(p.vertices)
        if get_normals:
            if p.use_smooth:
                for vi in p.vertices:
                    N.extend(mesh.vertices[vi].normal)
            else:
                N.extend(list(p.normal) * p.loop_total)

    if len(verts):
        P = P[:int(max(verts) + 1) * 3]
    # return the P's minus any unconnected
    return (nverts, verts, P, N)

class RendermanMeshSettings(RendermanPropertyGroup):
    ''' Mesh Properties, also handles ribgen for mesh data ''' 
    ### mesh properties ###

    ### overrides of base class methods ###
    def to_rib(self, ri, **kwargs):
        ''' Uses cached motion data for rib gen if deforming, 
            else gets the mesh data and does rib gen '''
        ob = kwargs['ob']
        scene = kwargs['scene']
        mesh = ob.to_mesh(scene, True, 'RENDER', calc_tessface=False, calc_undeformed=True)

        primvars = {}
        (nverts, verts, P, N) = get_mesh(mesh, get_normals=True)

        primvars['P'] = P
        primvars['facevarying normal N'] = N
        ri.PointsPolygons(nverts, verts, primvars)

    def get_archive_filename(self, **kwargs):
        ''' returns the name of file to save this archive to '''
        path = kwargs['paths']['static_archives']
        return os.path.join(path, self.id_data.name + '.rib')

    ### mesh specific methods ###
    