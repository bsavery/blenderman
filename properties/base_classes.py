import bpy
from bpy.props import *

''' Base classes that Object, Mesh, Lamp, etc property groups should subclass ''' 

class RendermanBasePropertyGroup(bpy.types.PropertyGroup):
    ''' Base class, to be used for scene properties'''
    def to_rib(self, ri, **kwargs):
        ''' Convert this item to ri calls ''' 
        pass

    def get_archive_filename(self, **kwargs):
        ''' get the name of the rib archive for this item '''
        pass


class RendermanPropertyGroup(RendermanBasePropertyGroup):
    '''Anything other than scene should subclass this class and implement these functions'''

    motion_data = None

    def cache_motion(self):
        ''' Update the motion_data member with the motion data at current scene time '''
        pass

    def clear_motion(self):
        ''' free anything in motion_data '''
        self.motion_data = None

    def check_motion(self):
        ''' verify that motion_data is not none and item is actually in motion, 
        clear if it's not. '''
        pass

    def get_data_items(self):
        ''' get the data blocks attached to this object, for example meshes or particles'''
        pass

    def has_motion(self):
        ''' check if item has motion'''
        return False

    motion_blur = BoolProperty(
        name="Motion Blur",
        description="Enable motion blur",
        default=False)

    motion_segments_override = BoolProperty(
        name="Override Motion Samples",
        description="Override the global number of motion samples for this item",
        default=False)

    motion_segments = IntProperty(
        name="Motion Samples",
        description="Number of motion samples to take for motion blur.  Set this higher if motion blur is choppy on fast moving items.",
        min=2, max=16, default=2)

class RendermanPlugin(RendermanPropertyGroup):
    pass

