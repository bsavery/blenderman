from . import transform_utils
from . import object_utils

def set_material(sg_node, sg_material_node, rman_sg_material, mat=None, ob=None):
    '''Sets the material on a scenegraph group node and sets the materialid
    user attribute at the same time.

    Arguments:
        sg_node (RixSGGroup) - scene graph group node to attach the material.
        sg_material_node (RixSGMaterial) - the scene graph material node
        rman_sg_material (RmanSgMaterial) - the RmanSgMaterial instance
        mat (bpy.types.Materail) - Blender material instance
        ob (bpy.types.Object) - object we are attaching material to. Needed for light filters.
    '''    

    if sg_material_node is None:
        return

    sg_node.SetMaterial(sg_material_node)
    attrs = sg_node.GetAttributes()
    attrs.SetString('user:__materialid', sg_material_node.GetIdentifier().CStr())
    sg_node.SetAttributes(attrs) 
    if rman_sg_material.has_meshlight and len(mat.renderman_light.light_filters) > 0:
        # This mesh light has light filters
        # We need emit coordinate systems for each filter, plus the mesh filter
        sg_node.RemoveChild(rman_sg_material.sg_group)
        sg_node.RemoveCoordinateSystem(rman_sg_material.sg_group)
        sg_node.AddChild(rman_sg_material.sg_group)
        sg_node.AddCoordinateSystem(rman_sg_material.sg_group)

        for item in mat.renderman_light.light_filters:
            light_filter = item.linked_filter_ob                           
            rman_sg_lightfilter = rman_sg_material.rman_scene.get_rman_prototype(object_utils.prototype_key(light_filter), ob=light_filter, create=True)
            child = None
            db_name = object_utils.get_db_name(light_filter)
            for c in rman_sg_material.sg_lightfilters:                
                if c.GetIdentifier().CStr() == db_name:
                    child = c
                    break
            if child:
                update_lightfilter_transform(light_filter, ob, child)
                sg_node.AddChild(child)
                sg_node.AddCoordinateSystem(child)
                if rman_sg_lightfilter and ob.original not in rman_sg_lightfilter.lights_list:
                    rman_sg_lightfilter.lights_list.append(ob.original)

def update_lightfilter_transform(ob, light_ob, sg_node):
    lightfilter_shader = ob.data.renderman.get_light_node_name()  
    if lightfilter_shader in ['PxrCheatShadowLightFilter']:
        # PxrCheatShadowLightFilter's coordsys is a little different
        # it wants the light space to lightfilter space coordinate system
        mtx = light_ob.matrix_world @ ob.matrix_local.copy()
        mtx = transform_utils.convert_matrix(mtx)
        sg_node.SetTransform( mtx )        
    else:
        mtx = transform_utils.convert_matrix(ob.matrix_world.copy())
        sg_node.SetTransform( mtx )               

def update_sg_integrator(context):
    from .. import rman_render
    rr = rman_render.RmanRender.get_rman_render()
    rr.rman_scene_sync.update_integrator(context)           

def update_sg_samplefilters(context):
    from .. import rman_render
    rr = rman_render.RmanRender.get_rman_render()
    rr.rman_scene_sync.update_samplefilters(context)       

def update_sg_displayfilters(context):
    from .. import rman_render
    rr = rman_render.RmanRender.get_rman_render()
    rr.rman_scene_sync.update_displayfilters(context)    

def update_sg_options(prop_name, context):
    from .. import rman_render
    rr = rman_render.RmanRender.get_rman_render()
    rr.rman_scene_sync.update_global_options(prop_name, context)   

def update_sg_root_node(prop_name, context):
    from .. import rman_render
    rr = rman_render.RmanRender.get_rman_render()
    rr.rman_scene_sync.update_root_node_func(prop_name, context)    

def update_sg_node_riattr(prop_name, context, bl_object=None):
    from .. import rman_render
    rr = rman_render.RmanRender.get_rman_render()
    rr.rman_scene_sync.update_sg_node_riattr(prop_name, context, bl_object=bl_object)   

def update_sg_node_primvar(prop_name, context, bl_object=None):
    from .. import rman_render
    rr = rman_render.RmanRender.get_rman_render()
    rr.rman_scene_sync.update_sg_node_primvar(prop_name, context, bl_object=bl_object)

def update_sg_displays(context):
    from .. import rman_render
    rr = rman_render.RmanRender.get_rman_render()
    rr.rman_scene_sync.update_displays(context)    

def update_root_lightlinks(context):
    from .. import rman_render
    rr = rman_render.RmanRender.get_rman_render()
    rr.rman_scene_sync.update_displays(context)       

def export_vol_aggregate(bl_scene, primvar, ob):
    vol_aggregate_group = []
    for i,v in enumerate(bl_scene.renderman.vol_aggregates):
        if i == 0:
            continue
        for member in v.members:
            if member.ob_pointer.original == ob.original:
                vol_aggregate_group.append(v.name)
                break

    if vol_aggregate_group:
        primvar.SetStringArray("volume:aggregate", vol_aggregate_group, len(vol_aggregate_group))
    elif ob.renderman.volume_global_aggregate:
        # we assume the first group is the global aggregate
        primvar.SetStringArray("volume:aggregate", [bl_scene.renderman.vol_aggregates[0].name], 1)
    else:
        primvar.SetStringArray("volume:aggregate", [""], 1)