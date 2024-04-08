from .rman_translator import RmanTranslator
from ..rman_sg_nodes.rman_sg_group import RmanSgGroup
from ..rfb_utils import transform_utils
from ..rfb_utils import object_utils
from mathutils import Matrix
import math

class RmanEmptyTranslator(RmanTranslator):

    def __init__(self, rman_scene):
        super().__init__(rman_scene)

    def update_transform(self, ob, rman_sg_group):
        pass

    def update_transform_sample(self, ob, rman_sg_group, index, seg):
        pass

    def update_transform_num_samples(self, rman_sg_group, motion_steps):
        pass

    def clear_children(self, rman_sg_group):
        if rman_sg_group.sg_attributes:
            for c in [ rman_sg_group.sg_attributes.GetChild(i) for i in range(0, rman_sg_group.sg_attributes.GetNumChildren())]:
                rman_sg_group.sg_attributes.RemoveChild(c)     

    def export(self, ob, db_name=""):
        sg_group = self.rman_scene.sg_scene.CreateGroup(db_name)
        rman_sg_group = RmanSgGroup(self.rman_scene, sg_group, db_name)
        return rman_sg_group   