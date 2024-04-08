def set_material(sg_node, sg_material_node):
    '''Sets the material on a scenegraph group node and sets the materialid
    user attribute at the same time.

    Arguments:
        sg_node (RixSGGroup) - scene graph group node to attach the material.
        sg_material_node (RixSGMaterial) - the scene graph material node
    '''    

    if sg_material_node is None:
        return

    sg_node.SetMaterial(sg_material_node)
    attrs = sg_node.GetAttributes()
    attrs.SetString('user:__materialid', sg_material_node.GetIdentifier().CStr())
    sg_node.SetAttributes(attrs) 

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