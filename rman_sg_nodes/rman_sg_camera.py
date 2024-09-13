from .rman_sg_node import RmanSgNode

class BlCameraProps:

    def __init__(self):
        self.res_width = -1
        self.res_height = -1
        self.rman_fov = -1
        self.view_perspective = None
        self.view_camera_zoom = -1
        self.xaspect = -1
        self.yaspect = -1
        self.aspectratio = -1
        self.lens = -1
        self.sensor = -1
        self.view_camera_offset = (-1000.0, -1000.0)
        self.shift_x = -1
        self.shift_y = -1
        self.screenwindow = None
        self.clip_start = -1
        self.clip_end = -1
        self.dof_focal_length = -1
        self.crop_window = [0.0, 1.0, 0.0, 1.0]

    def __eq__(self, other):
        if self.res_width != other.res_width:
            return False
        if self.res_height != other.res_height:
            return False
        if self.view_perspective != other.view_perspective:
            return False
        if self.view_camera_zoom != other.view_camera_zoom:
            return False
        if self.view_camera_offset[0] != other.view_camera_offset[0]:
            return False
        if self.view_camera_offset[1] != other.view_camera_offset[1]:
            return False            
        if self.lens != other.lens:
            return False
        if self.shift_x != other.shift_x:
            return False
        if self.shift_y != other.shift_y:
            return False
        if self.xaspect != other.xaspect:
            return False
        if self.yaspect != other.yaspect:
            return False
        if self.aspectratio != other.aspectratio:
            return False
        if self.screenwindow != other.screenwindow:
            return False            
        if self.sensor != other.sensor:
            return False
        if self.clip_start != other.clip_start:
            return False   
        if self.clip_end != other.clip_end:
            return False   
        if self.rman_fov != other.rman_fov:
            return False
        if self.dof_focal_length != other.dof_focal_length:
            return False      
        if self.crop_window != other.crop_window:
            return False      
        return True                                   

class RmanSgCamera(RmanSgNode):

    def __init__(self, rman_scene, sg_node, db_name):
        super().__init__(rman_scene, sg_node, db_name)
        self.bl_camera = None
        self.cam_matrix = None
        self.sg_camera_node = None
        self.projection_shader = None        
        self.use_focus_object = False
        self.rman_focus_object = None
        self.bl_cam_props = BlCameraProps()

    @property
    def bl_camera(self):
        return self.__bl_camera

    @bl_camera.setter
    def bl_camera(self, bl_camera):
        self.__bl_camera = bl_camera

    @property
    def cam_matrix(self):
        return self.__cam_matrix

    @cam_matrix.setter
    def cam_matrix(self, mtx):
        self.__cam_matrix = mtx
