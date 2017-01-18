from .base_classes import RendermanPropertyGroup

''' Object Properties ''' 
class RendermanObjectSettings(RendermanPropertyGroup):
    ''' Object Properties, also handles ribgen for mesh data '''
    ### object specific properties ###

    ### overrides of base class methods ###
    def to_rib(self, ri, **kwargs):
        ''' creates an attribute block for the object, reads in the data archive(s)
            and recursively calls any children to_ribs''' 
        ob = self.id_data
        ri.AttributeBegin()
        ri.Attribute("identifier", {"string name": ob.name})

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