from .base_classes import RendermanPropertyGroup
from .rib_helpers import rib

''' Object Properties ''' 
class RendermanObjectSettings(RendermanPropertyGroup):
    ''' Object Properties, also handles ribgen for mesh data '''
    ### object specific properties ###

    # raytrace panel
    raytrace_pixel_variance = FloatProperty(
        name="Relative Pixel Variance",
        description="Allows this object ot render to a different quality level than the main scene.  Actual pixel variance will be this number multiplied by the main pixel variance.",
        default=1.0)

    raytrace_maxdiffusedepth_override = BoolProperty(
        name="Diffuse Depth Override",
        description="Sets the diffuse bounces for this object separately from the scene default",
        default=False)

    raytrace_maxdiffusedepth = IntProperty(
        name="Max Diffuse Depth",
        description="Limit the number of diffuse bounces",
        default=0)

    raytrace_maxspeculardepth_override = BoolProperty(
        name="Specular Depth Override",
        description="Sets the specular bounces for this object separately from the scene default",
        default=False)

    raytrace_maxspeculardepth = IntProperty(
        name="Max Specular Depth",
        description="Limit the number of specular bounces",
        default=0)

    raytrace_tracedisplacements = BoolProperty(
        name="Trace Displacements",
        description="Ray Trace true displacement in rendered results",
        default=True)

    raytrace_intersectpriority = IntProperty(
        name="Intersect Priority",
        description="Dictates a priority used when ray tracing overlapping materials",
        default=0)

    raytrace_ior = FloatProperty(
        name="Index of Refraction",
        description="When using nested dielectrics (overlapping materials), this should be set to the same value as the ior of your material",
        default=1.0)

    ### overrides of base class methods ###
    def to_rib(self, ri, **kwargs):
        ''' creates an attribute block for the object, reads in the data archive(s)
            and recursively calls any children to_ribs''' 
        ob = self.id_data
        ri.AttributeBegin()
        ri.Attribute("identifier", {"string name": ob.name})

        m = ob.matrix_local
        ri.ConcatTransform(rib(m))

        for data in self.get_data_items():
            archive_name = data.renderman.get_archive_filename(paths=kwargs['paths'], ob=ob)
            if archive_name:
                ri.ReadArchive(archive_name)

        for child in ob.children:
            child.renderman.to_rib(ri, **kwargs)

        ri.AttributeEnd()

    def get_data_items(self):
        ''' Gets any data blocks on this object, such as mesh or particle systems '''
        ob = self.id_data
        if ob.type == 'MESH':
            return [ob.data]
        return []