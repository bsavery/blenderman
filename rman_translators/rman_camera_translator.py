from ..rfb_logger import rfb_log
from .rman_translator import RmanTranslator
from ..rman_sg_nodes.rman_sg_camera import RmanSgCamera, BlCameraProps
from ..rman_sg_nodes.rman_sg_node import RmanSgNode
from ..rfb_utils import transform_utils
from ..rfb_utils import property_utils
from ..rfb_utils import object_utils
from ..rfb_utils import scene_utils
from ..rfb_utils import shadergraph_utils
from ..rfb_utils import camera_utils
from .. import rman_constants 
from mathutils import Matrix, Vector
from copy import deepcopy
import math
import sys

# copied from Blender's source code
DEFAULT_SENSOR_WIDTH = 36.0
DEFAULT_SENSOR_HEIGHT = 24.0


class RmanCameraTranslator(RmanTranslator):

    def __init__(self, rman_scene):
        super().__init__(rman_scene)
        self.bl_type = 'CAMERA'
        self.s_rightHanded = self.rman_scene.rman.Types.RtMatrix4x4(1.0,0.0,0.0,0.0,
                                                               0.0,1.0,0.0,0.0,
                                                               0.0,0.0,-1.0,0.0,
                                                               0.0,0.0,0.0,1.0) 

    def _set_orientation(self, rman_sg_camera):
        camtransform = self.rman_scene.rman.Types.RtMatrix4x4()
        camtransform.Identity()
        rman_sg_camera.sg_camera_node.SetOrientTransform(self.s_rightHanded)        

    def update_transform_num_samples(self, rman_sg_camera, motion_steps ):
        rman_sg_camera.sg_node.SetTransformNumSamples(len(motion_steps))

    def _update_viewport_transform(self, rman_sg_camera):
        region_data = self.rman_scene.context.region_data
        if not region_data:
            return
        mtx = region_data.view_matrix.inverted()
        v = transform_utils.convert_matrix(mtx)
        if rman_sg_camera.cam_matrix == v:
            return 
        rman_sg_camera.cam_matrix = v
        rman_sg_camera.sg_node.SetTransform( v )    

    def _update_render_cam_transform(self, ob, rman_sg_camera, index=0, seg=0.0):

        mtx = ob.matrix_world
        
        # normalize the matrix
        try:
            mtx.normalize()
        except SystemError as e:
            rfb_log().debug("Could not normalize matrix: %s" % str(e))

        v = transform_utils.convert_matrix(mtx)
        if rman_sg_camera.cam_matrix == v:
            return False

        rman_sg_camera.cam_matrix = v
        if rman_sg_camera.is_transforming:
            rman_sg_camera.sg_node.SetTransformSample(index, v, seg )              
        else:
            rman_sg_camera.sg_node.SetTransform( v )    
               
        return True

    def update_transform(self, ob, rman_sg_camera, index=0, seg=0):
        if self.rman_scene.is_viewport_render:
            self._update_viewport_transform(rman_sg_camera)
        elif self.rman_scene.is_interactive and not ob:
            self._update_viewport_transform(rman_sg_camera)
        else:
            self._update_render_cam_transform(ob, rman_sg_camera, index, seg)

    def _export_viewport_cam(self, db_name=""):  
        sg_group = self.rman_scene.sg_scene.CreateGroup(db_name) 
        rman_sg_camera = RmanSgCamera(self.rman_scene, sg_group, db_name)
        rman_sg_camera.sg_camera_node = self.rman_scene.sg_scene.CreateCamera('%s-CAMERA' % db_name)  
        sg_group.AddChild(rman_sg_camera.sg_camera_node)      
        self.update_viewport_resolution(rman_sg_camera)
        self.update_viewport_cam(None, rman_sg_camera)
        self._set_orientation(rman_sg_camera)
        self._update_viewport_transform(rman_sg_camera)  
        return rman_sg_camera        

    def _export_render_cam(self, ob, db_name=""):
        sg_group = self.rman_scene.sg_scene.CreateGroup(db_name) 
        rman_sg_camera = RmanSgCamera(self.rman_scene, sg_group, db_name)
        rman_sg_camera.sg_camera_node = self.rman_scene.sg_scene.CreateCamera('%s-CAMERA' % db_name) 
        sg_group.AddChild(rman_sg_camera.sg_camera_node)             
        if self.rman_scene.do_motion_blur:
            rman_sg_camera.is_transforming = object_utils.is_transforming(ob)
            mb_segs = self.rman_scene.bl_scene.renderman.motion_segments
            if ob.renderman.motion_segments_override:
                mb_segs = ob.renderman.motion_segments
            if mb_segs > 1:
                subframes = scene_utils._get_subframes_(mb_segs, self.rman_scene.bl_scene)
                rman_sg_camera.motion_steps = subframes  
                self.update_transform_num_samples(rman_sg_camera, subframes )                
            else:
                rman_sg_camera.is_transforming = False
        self._update_render_cam(ob, rman_sg_camera)
        self._set_orientation(rman_sg_camera)
        self._update_render_cam_transform(ob, rman_sg_camera)
        return rman_sg_camera                  

    def export(self, ob, db_name=""):
        if self.rman_scene.is_viewport_render:
            return self._export_viewport_cam(db_name)
        elif self.rman_scene.is_interactive and not ob:
            return self._export_viewport_cam(db_name)
        else:
            return self._export_render_cam(ob, db_name)

    def update(self, ob, rman_sg_camera):
        if self.rman_scene.is_viewport_render:
            return self.update_viewport_cam(ob, rman_sg_camera, force_update=True)
        else:
            return self._update_render_cam(ob, rman_sg_camera)   

    def set_tilt_shift_focus(self, ob, cam, params):
        rm = cam.renderman
        tilt_shift_ob = rm.rman_tilt_shift_object
        if tilt_shift_ob is None:
            return
        mesh = tilt_shift_ob.data
        if len(mesh.vertices) != 3:
            rfb_log().error("The selected tilt-shift object is not a triangle.")

        mtx = tilt_shift_ob.matrix_world
        params.SetPoint('focus1', mtx @ mesh.vertices[0].co )
        params.SetPoint('focus2', mtx @ mesh.vertices[1].co )
        params.SetPoint('focus3', mtx @ mesh.vertices[2].co )

    def find_scene_camera(self):
        if not self.rman_scene.is_viewport_render:
            return self.rman_scene.bl_scene.camera

        region_data = self.rman_scene.context.region_data   
        ob = None

        if region_data: 
            if region_data.view_perspective == 'CAMERA':
                ob = self.rman_scene.bl_scene.camera    
                if self.rman_scene.context.space_data.use_local_camera:
                    ob = self.rman_scene.context.space_data.camera      
            else: 
                ob = self.rman_scene.context.space_data.camera 
        return ob        

    def update_viewport_resolution(self, rman_sg_camera):
        region = self.rman_scene.context.region
        region_data = self.rman_scene.context.region_data

        # get the current resolution multiplier
        res_mult = self.rman_scene.viewport_render_res_mult

        width = int(region.width * res_mult)
        height = int(region.height * res_mult)      

        updated = False
        resolution_updated = False
        ob = None

        clip_start = None
        clip_end = None

        prop = rman_sg_camera.sg_camera_node.GetProperties()
        
        bl_cam_props = deepcopy(rman_sg_camera.bl_cam_props)
        bl_cam_props.res_width = width
        bl_cam_props.res_height = height 
        bl_cam_props.crop_window = [0.0, 1.0, 0.0, 1.0]  

        if region_data:
            bl_cam_props.view_perspective = region_data.view_perspective
            bl_cam_props.view_camera_zoom = region_data.view_camera_zoom
            bl_cam_props.view_camera_offset = tuple(region_data.view_camera_offset)

            if region_data.view_perspective == 'CAMERA':
                ob = self.rman_scene.bl_scene.camera    
                if self.rman_scene.context.space_data.use_local_camera:
                    ob = self.rman_scene.context.space_data.camera      

                cam = ob.data
                r = self.rman_scene.bl_scene.render

                xaspect, yaspect, aspectratio = camera_utils.render_get_aspect_(r, cam, x=width, y=height)

                # magic zoom formula copied from blenderseed, which got it from cycles
                zoom = 4 / ((math.sqrt(2) + bl_cam_props.view_camera_zoom / 50) ** 2)   

                if cam.type == 'ORTHO':
                    lens = cam.ortho_scale
                    xaspect = xaspect * lens / (aspectratio * 2.0)
                    yaspect = yaspect * lens / (aspectratio * 2.0)    
                    aspectratio = lens / 2.0   
                else:
                    lens = ob.data.lens             
                    
                # shift and offset            
                #offset = tuple(rman_sg_camera.view_camera_offset)
                offset = tuple(bl_cam_props.view_camera_offset)
                dx = 2.0 * (aspectratio * cam.shift_x + offset[0] * xaspect * 2.0)
                dy = 2.0 * (aspectratio * cam.shift_y + offset[1] * yaspect * 2.0)    

                clip_start = cam.clip_start
                clip_end = cam.clip_end   
                
                bl_cam_props.lens = lens
                bl_cam_props.shift_x = cam.shift_x
                bl_cam_props.shift_y = cam.shift_y
                bl_cam_props.xaspect = xaspect
                bl_cam_props.yaspect = yaspect
                bl_cam_props.aspectratio = aspectratio

                sw = [-xaspect * zoom, xaspect * zoom, -yaspect * zoom, yaspect * zoom]
                sw[0] += dx
                sw[1] += dx
                sw[2] += dy
                sw[3] += dy
 
                bl_cam_props.screenwindow = sw
                
                prop.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_ScreenWindow, sw, 4)  

                if self.rman_scene.is_viewport_render and r.use_border:

                    x0, x1, y0, y1 = camera_utils.get_viewport_cam_borders(ob, r, region, region_data, self.rman_scene.bl_scene)
                    min_x = (x0) / width
                    max_x = (x1) / width
                    min_y = 1.0 - (y0 / height)
                    max_y = 1.0 - (y1 / height)

                    bl_cam_props.crop_window = [min_x, max_x, min_y, max_y]          

                # aperature
                bl_cam_props.aperture_ratio = cam.renderman.rman_aperture_ratio
                bl_cam_props.aperture_blades = cam.renderman.rman_aperture_blades
                bl_cam_props.aperture_rotation = cam.renderman.rman_aperture_rotation
                bl_cam_props.aperture_roundness = cam.renderman.rman_aperture_roundness
                bl_cam_props.aperture_density = cam.renderman.rman_aperture_density

            elif region_data.view_perspective ==  'PERSP': 
                if self.rman_scene.is_viewport_render and self.rman_scene.context.space_data.use_render_border:
                    space = self.rman_scene.context.space_data
                    min_x = space.render_border_min_x
                    max_x = space.render_border_max_x
                    min_y = 1.0 - space.render_border_min_y
                    max_y = 1.0 - space.render_border_max_y
                    bl_cam_props.crop_window = [min_x, max_x, min_y, max_y]

                ob = self.rman_scene.context.space_data.camera 
                cam = None
                if ob:
                    cam = ob.data
                r = self.rman_scene.bl_scene.render

                xaspect, yaspect, aspectratio = camera_utils.render_get_aspect_(r, cam, x=width, y=height)          
                zoom = 2.0
                if not cam:
                    zoom = 1.0

                # shift and offset            
                shift_x = 0.0
                shift_y = 0.0
                
                # FIXME: for now, don't take camera shift into account
                #if cam:
                #    shift_x = cam.shift_x
                #    shift_y = cam.shift_y

                # FIXME? It seems like we don't need the view_camera_offset for some reason
                # Need to do some more testing, but taking it into account seems to shift the image
                offset = (0.0, 0.0) #tuple(rman_sg_camera.view_camera_offset)
                dx = 2.0 * (aspectratio * shift_x + offset[0] * xaspect * 2.0)
                dy = 2.0 * (aspectratio * shift_y + offset[1] * yaspect * 2.0)    

                clip_start = self.rman_scene.context.space_data.clip_start
                clip_end = self.rman_scene.context.space_data.clip_end

                bl_cam_props.lens = self.rman_scene.context.space_data.lens
                bl_cam_props.shift_x = shift_x
                bl_cam_props.shift_y = shift_y
                bl_cam_props.xaspect = xaspect
                bl_cam_props.yaspect = yaspect
                bl_cam_props.aspectratio = aspectratio                

                sw = [-xaspect * zoom, xaspect * zoom, -yaspect * zoom, yaspect * zoom]
                sw[0] += dx
                sw[1] += dx
                sw[2] += dy
                sw[3] += dy

                bl_cam_props.screenwindow = sw                
                
                prop.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_ScreenWindow, sw, 4)    

            else: 
                ob = self.rman_scene.context.space_data.camera 
                cam = None
                if ob:
                    cam = ob.data
                
                r = self.rman_scene.bl_scene.render

                xaspect, yaspect, aspectratio = camera_utils.render_get_aspect_(r, cam, x=width, y=height)

                # 2.0 zoom value copied from cycles
                zoom = 2.0
                lens = self.rman_scene.context.space_data.lens
                sensor = DEFAULT_SENSOR_WIDTH

                ortho_scale = region_data.view_distance * sensor / lens
                xaspect = xaspect * ortho_scale / (aspectratio * 2.0)
                yaspect = yaspect * ortho_scale / (aspectratio * 2.0)
                aspectratio = ortho_scale / 2.0  

                clip_start = self.rman_scene.context.space_data.clip_start
                clip_end = self.rman_scene.context.space_data.clip_end                
                      
                # shift and offset   
                shift_x = 0.0
                shift_y = 0.0
                if cam:
                    shift_x = cam.shift_x
                    shift_y = cam.shift_y       

                # FIXME? See comment above                      
                offset = (0.0, 0.0) #tuple(rman_sg_camera.view_camera_offset)
                dx = 2.0 * (aspectratio * shift_x + offset[0] * xaspect * 2.0)
                dy = 2.0 * (aspectratio * shift_y + offset[1] * yaspect * 2.0)      

                bl_cam_props.lens = self.rman_scene.context.space_data.lens
                bl_cam_props.shift_x = shift_x
                bl_cam_props.shift_y = shift_y
                bl_cam_props.xaspect = xaspect
                bl_cam_props.yaspect = yaspect
                bl_cam_props.aspectratio = aspectratio                                        

                sw = [-xaspect * zoom, xaspect * zoom, -yaspect * zoom, yaspect * zoom]
                sw[0] += dx
                sw[1] += dx
                sw[2] += dy
                sw[3] += dy
 
                bl_cam_props.screenwindow = sw                

                prop.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_ScreenWindow, sw, 4) 

        if clip_start and clip_end:
            if clip_start > clip_end:
                rfb_log().debug("Clipping start is greater than clipping end.") 
                clip_start = None
                clip_end = None
                bl_cam_props.clip_start = -1
                bl_cam_props.clip_end = -1
            elif clip_start == clip_end:
                rfb_log().debug("Clipping start is equal to clipping end.") 
                clip_start = None
                clip_end = None
                bl_cam_props.clip_start = -1
                bl_cam_props.clip_end = -1                
            else: 
                bl_cam_props.clip_start = clip_start
                bl_cam_props.clip_end = clip_end

        if bl_cam_props != rman_sg_camera.bl_cam_props:
            if bl_cam_props.res_width != rman_sg_camera.bl_cam_props.res_width:
                resolution_updated = True
            
            if bl_cam_props.res_height != rman_sg_camera.bl_cam_props.res_height:
                resolution_updated = True                
            rman_sg_camera.bl_cam_props = bl_cam_props            
            updated = True

        if updated:
            # clipping planes    
            if clip_start:
                prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_nearClip, clip_start)
            if clip_end:
                prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_farClip, clip_end)    

            options = self.rman_scene.sg_scene.GetOptions()
            options.SetFloat(self.rman_scene.rman.Tokens.Rix.k_Ri_FormatPixelAspectRatio, 1.0)   
            options.SetIntegerArray(self.rman_scene.rman.Tokens.Rix.k_Ri_FormatResolution, (width, height), 2)
            if resolution_updated:

                # This is super yucky. We need to be able to tell the 
                # crop handler to stop drawing and reset the 
                # crop window when the resolution changes. Unfortunately
                # Blender doesn't seem to allow us to call operators during this
                # state, so we tell the handler to reset directly. 
                from ..rman_ui.rman_ui_viewport import __DRAW_CROP_HANDLER__ as crop_handler
                if crop_handler and crop_handler.crop_windowing:
                    crop_handler.reset()
                    crop_window = [0.0, 1.0, 0.0, 1.0]

            crop_window = deepcopy(bl_cam_props.crop_window) 
            if crop_window != [0.0, 1.0, 0.0, 1.0]:     
                # Make sure the cropwindow isn't out of bounds
                if crop_window[0] < 0.0 or crop_window[0] > 1.0:
                    crop_window[0] = 0.0
                if crop_window[1] < 0.0 or crop_window[1] > 1.0 or crop_window[1] <= crop_window[0]:
                    crop_window[1] = 1.0
                if crop_window[3] < 0.0 or crop_window[3] > 1.0:
                    crop_window[3] = 0.0
                if crop_window[2] < 0.0 or crop_window[2] > 1.0 or crop_window[2] <= crop_window[3]:
                    crop_window[2] = 1.0   

            prop.SetInteger(self.rman_scene.rman.Tokens.Rix.k_apertureNSides, bl_cam_props.aperture_blades)
            prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_apertureAngle, bl_cam_props.aperture_rotation)
            prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_apertureRoundness, bl_cam_props.aperture_roundness)
            prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_apertureDensity, bl_cam_props.aperture_density)

            prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_dofaspect, bl_cam_props.aperture_ratio)


            options.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_CropWindow, crop_window, 4)
            self.rman_scene.sg_scene.SetOptions(options)
            rman_sg_camera.sg_camera_node.SetProperties(prop)
            return True
        return False

    def update_viewport_cam(self, ob, rman_sg_camera, force_update=False):
        region = self.rman_scene.context.region
        region_data = self.rman_scene.context.region_data

        # get the current resolution multiplier
        res_mult = self.rman_scene.viewport_render_res_mult

        width = rman_sg_camera.bl_cam_props.res_width
        height = rman_sg_camera.bl_cam_props.res_height
        view_camera_zoom = rman_sg_camera.bl_cam_props.view_camera_zoom

        rman_sg_camera.projection_shader = None
        fov = -1

        updated = False

        bl_cam_props = deepcopy(rman_sg_camera.bl_cam_props)
        if rman_sg_camera.bl_cam_props.view_perspective == 'CAMERA':
            if ob is None:
                ob = self.rman_scene.bl_scene.camera    
                if self.rman_scene.context.space_data.use_local_camera:
                    ob = self.rman_scene.context.space_data.camera                
            ob = ob.original
            cam = ob.data
            rman_sg_camera.bl_camera = ob
            cam_rm = cam.renderman

            aspectratio = rman_sg_camera.bl_cam_props.aspectratio
            lens = cam.lens
            sensor = cam.sensor_height \
                if cam.sensor_fit == 'VERTICAL' else cam.sensor_width

            if cam.type == 'ORTHO':
                rman_sg_camera.projection_shader = self.rman_scene.rman.SGManager.RixSGShader("Projection", "PxrOrthographic", "proj")   
                updated = True
            else:
                fov = 360.0 * math.atan((sensor * 0.5) / lens / aspectratio) / math.pi

                bl_cam_props.rman_fov = fov

                node = shadergraph_utils.find_projection_node(ob)        
                if node:
                    rman_sg_camera.projection_shader = self.rman_scene.rman.SGManager.RixSGShader("Projection", node.bl_label, "proj")
                    rman_sg_node = RmanSgNode(self.rman_scene, rman_sg_camera.projection_shader, "")                           
                    property_utils.property_group_to_rixparams(node, rman_sg_node, rman_sg_camera.projection_shader, ob=cam) 
                    projparams = rman_sg_camera.projection_shader.params
                    if cam_rm.rman_use_cam_fov:
                        projparams.SetFloat(self.rman_scene.rman.Tokens.Rix.k_fov, fov) 
                    if node.bl_label == 'PxrCamera':
                        self.set_tilt_shift_focus(ob, cam, projparams)
  
                else:                
                    rman_sg_camera.projection_shader = self.rman_scene.rman.SGManager.RixSGShader("Projection", "PxrCamera", "proj")
                    projparams = rman_sg_camera.projection_shader.params         
                    projparams.SetFloat(self.rman_scene.rman.Tokens.Rix.k_fov, fov) 
                    self.set_tilt_shift_focus(ob, cam, projparams)

                self._set_dof(ob, rman_sg_camera, cam, projparams)            

        elif rman_sg_camera.bl_cam_props.view_perspective ==  'PERSP': 
            if ob is None:
                ob = self.rman_scene.context.space_data.camera 
            cam = None
            if ob:
                cam = ob.data
            rman_sg_camera.bl_camera = ob
            
            aspectratio = rman_sg_camera.bl_cam_props.aspectratio
            lens = rman_sg_camera.bl_cam_props.lens 
            if cam:
                sensor = DEFAULT_SENSOR_WIDTH                     
                fov = 360.0 * math.atan((sensor * 0.5) / lens / aspectratio) / math.pi
            else:
                # code from: 
                # https://blender.stackexchange.com/questions/46391/how-to-convert-spaceview3d-lens-to-field-of-view
                region_data = self.rman_scene.context.region_data
                vmat_inv = region_data.view_matrix.inverted()
                pmat = region_data.perspective_matrix @ vmat_inv
                fov = 2.0 * math.atan(1.0/pmat[1][1]) * 180.0 / math.pi

            bl_cam_props.rman_fov = fov

            rman_sg_camera.projection_shader = self.rman_scene.rman.SGManager.RixSGShader("Projection", "PxrCamera", "proj")
            projparams = rman_sg_camera.projection_shader.params         
            projparams.SetFloat(self.rman_scene.rman.Tokens.Rix.k_fov, fov)  
            rman_sg_camera.use_focus_object = False
            rman_sg_camera.rman_focus_object = None             

        else:
            # orthographic
            rman_sg_camera.use_focus_object = False
            rman_sg_camera.rman_focus_object = None            
            rman_sg_camera.projection_shader = self.rman_scene.rman.SGManager.RixSGShader("Projection", "PxrOrthographic", "proj")  
            updated = True        

        if bl_cam_props != rman_sg_camera.bl_cam_props:
            rman_sg_camera.bl_cam_props = bl_cam_props
            updated = True

        if updated or force_update:   
            rman_sg_camera.sg_camera_node.SetProjection(rman_sg_camera.projection_shader)         

    def _set_fov(self, ob, rman_sg_camera, cam, aspectratio, projparams):
        lens = cam.lens
        cam_rm = cam.renderman
        sensor = cam.sensor_height \
            if cam.sensor_fit == 'VERTICAL' else cam.sensor_width

        fov = 360.0 * math.atan((sensor * 0.5) / lens / aspectratio) / math.pi            
        
        dx = 2.0 * (aspectratio * cam.shift_x) 
        dy = 2.0 * (aspectratio * cam.shift_y)   
        projparams.SetFloat(self.rman_scene.rman.Tokens.Rix.k_fov, fov)

    def _set_dof(self, ob, rman_sg_camera, cam, projparams):
        cam_rm = cam.renderman

        if cam_rm.rman_use_dof:
            rman_sg_camera.use_focus_object = cam_rm.rman_focus_object
            if cam_rm.rman_focus_object:
                dof_focal_distance = (ob.location - cam_rm.rman_focus_object.location).length
                rman_sg_camera.bl_cam_props.dof_focal_length = dof_focal_distance
                rman_sg_node = self.rman_scene.get_rman_prototype(object_utils.prototype_key(cam_rm.rman_focus_object))
                if rman_sg_node:
                    rman_sg_camera.rman_focus_object = rman_sg_node                
            else:
                dof_focal_distance = cam_rm.rman_focus_distance
                rman_sg_camera.bl_cam_props.dof_focal_length = dof_focal_distance
                rman_sg_camera.rman_focus_object = None
            if dof_focal_distance > 0.0:
                dof_focal_length = (cam.lens * 0.001)
                rman_sg_camera.bl_cam_props.dof_focal_length = dof_focal_distance
                projparams.SetFloat(self.rman_scene.rman.Tokens.Rix.k_fStop, cam_rm.rman_aperture_fstop)
                projparams.SetFloat(self.rman_scene.rman.Tokens.Rix.k_focalLength, dof_focal_length)
            projparams.SetFloat(self.rman_scene.rman.Tokens.Rix.k_focalDistance, dof_focal_distance)   
        else:       
            rman_sg_camera.bl_cam_props.dof_focal_length = -1
            rman_sg_camera.use_focus_object = False
            rman_sg_camera.rman_focus_object = None

    def _update_render_resolution(self, ob, rman_sg_camera):
        r = self.rman_scene.bl_scene.render
        cam = ob.data
        rm = self.rman_scene.bl_scene.renderman
        cam_rm = cam.renderman
        rman_sg_camera.bl_camera = ob

        xaspect, yaspect, aspectratio = camera_utils.render_get_aspect_(r, cam)

        options = self.rman_scene.sg_scene.GetOptions()
        use_border = self.rman_scene.bl_scene.render.use_border
        use_crop_to_border = self.rman_scene.bl_scene.render.use_crop_to_border

        if not self.rman_scene.is_interactive and use_border and not use_crop_to_border:
            min_x = self.rman_scene.bl_scene.render.border_min_x
            max_x = self.rman_scene.bl_scene.render.border_max_x
            min_y = 1.0 - self.rman_scene.bl_scene.render.border_min_y
            max_y = 1.0 - self.rman_scene.bl_scene.render.border_max_y

            options.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_CropWindow, (min_x, max_x, min_y, max_y), 4)   

        # convert the crop border to screen window, flip y
        resolution = camera_utils.render_get_resolution_(self.rman_scene.bl_scene.render)
        if not self.rman_scene.is_interactive and use_border and use_crop_to_border:
            res_x = resolution[0] * (self.rman_scene.bl_scene.render.border_max_x -
                                    self.rman_scene.bl_scene.render.border_min_x)
            res_y = resolution[1] * (self.rman_scene.bl_scene.render.border_max_y -
                                    self.rman_scene.bl_scene.render.border_min_y)

            options.SetIntegerArray(self.rman_scene.rman.Tokens.Rix.k_Ri_FormatResolution, (int(res_x), int(res_y)), 2)
            options.SetFloat(self.rman_scene.rman.Tokens.Rix.k_Ri_FormatPixelAspectRatio, 1.0)        
        else:            
            options.SetIntegerArray(self.rman_scene.rman.Tokens.Rix.k_Ri_FormatResolution, (resolution[0], resolution[1]), 2)
            options.SetFloat(self.rman_scene.rman.Tokens.Rix.k_Ri_FormatPixelAspectRatio, 1.0)

        self.rman_scene.sg_scene.SetOptions(options)  

        # update screen window
        prop = rman_sg_camera.sg_camera_node.GetProperties()
        self._update_screen_window(ob, xaspect, yaspect, aspectratio, prop)    
        rman_sg_camera.sg_camera_node.SetProperties(prop)

    def _update_screen_window(self, ob, xaspect, yaspect, aspectratio, prop):
        cam = ob.data

        dx = 0
        dy = 0

        if self.rman_scene.bl_scene.render.use_border and self.rman_scene.bl_scene.render.use_crop_to_border:
            screen_min_x = -xaspect + 2.0 * self.rman_scene.bl_scene.render.border_min_x * xaspect
            screen_max_x = -xaspect + 2.0 * self.rman_scene.bl_scene.render.border_max_x * xaspect
            screen_min_y = -yaspect + 2.0 * (self.rman_scene.bl_scene.render.border_min_y) * yaspect
            screen_max_y = -yaspect + 2.0 * (self.rman_scene.bl_scene.render.border_max_y) * yaspect

            prop.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_ScreenWindow, (screen_min_x, screen_max_x, screen_min_y, screen_max_y), 4)   
        else:            
            if cam.type == 'PANO':
                prop.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_ScreenWindow, (-1, 1, -1, 1), 4)
            elif cam.type == 'ORTHO':
                lens = cam.ortho_scale
                xaspect = xaspect * lens / (aspectratio * 2.0)
                yaspect = yaspect * lens / (aspectratio * 2.0)    
                aspectratio = lens / 2.0   
                dx = 2.0 * (aspectratio * cam.shift_x) 
                dy = 2.0 * (aspectratio * cam.shift_y)   
                sw = [-xaspect, xaspect, -yaspect, yaspect]
                sw[0] += dx
                sw[1] += dx
                sw[2] += dy
                sw[3] += dy                
                prop.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_ScreenWindow, sw, 4)   
            else:
                dx = 2.0 * (aspectratio * cam.shift_x) 
                dy = 2.0 * (aspectratio * cam.shift_y)   
                prop.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_ScreenWindow, (-xaspect+dx, xaspect+dx, -yaspect+dy, yaspect+dy), 4)        

    def _update_render_cam(self, ob, rman_sg_camera):

        r = self.rman_scene.bl_scene.render
        cam = ob.data
        rm = self.rman_scene.bl_scene.renderman
        cam_rm = cam.renderman
        rman_sg_camera.bl_camera = ob

        xaspect, yaspect, aspectratio = camera_utils.render_get_aspect_(r, cam)
        rman_sg_camera.projection_shader = None

        node = shadergraph_utils.find_projection_node(ob)        
        if node:
            rman_sg_camera.projection_shader = self.rman_scene.rman.SGManager.RixSGShader("Projection", node.bl_label, "proj")
            rman_sg_node = RmanSgNode(self.rman_scene, rman_sg_camera.projection_shader, "")                           
            property_utils.property_group_to_rixparams(node, rman_sg_node, rman_sg_camera.projection_shader, ob=cam)   
            projparams = rman_sg_camera.projection_shader.params
            if cam_rm.rman_use_cam_fov:
                self._set_fov(ob, rman_sg_camera, cam, aspectratio, projparams)

            self._set_dof(ob, rman_sg_camera, cam, projparams)

            if node.bl_label == 'PxrCamera':
                self.set_tilt_shift_focus(ob, cam, projparams)

        elif cam.type == 'PERSP':
            rman_sg_camera.projection_shader = self.rman_scene.rman.SGManager.RixSGShader("Projection", "PxrCamera", "proj")
            self._set_fov(ob, rman_sg_camera, cam, aspectratio, rman_sg_camera.projection_shader.params)
            self.set_tilt_shift_focus(ob, cam, rman_sg_camera.projection_shader.params)
                     
        elif cam.type == 'PANO':
            rman_sg_camera.projection_shader = self.rman_scene.rman.SGManager.RixSGShader("Projection", "PxrSphereCamera", "proj")
            projparams = rman_sg_camera.projection_shader.params
            projparams.SetFloat("hsweep", 360)
            projparams.SetFloat("vsweep", 180)           
        else:
            lens = cam.ortho_scale
            xaspect = xaspect * lens / (aspectratio * 2.0)
            yaspect = yaspect * lens / (aspectratio * 2.0)
            rman_sg_camera.projection_shader = self.rman_scene.rman.SGManager.RixSGShader("Projection", "PxrOrthographic", "proj")

        rman_sg_camera.sg_camera_node.SetProjection(rman_sg_camera.projection_shader)
        prop = rman_sg_camera.sg_camera_node.GetProperties()

        # Update screen window. Ortho scale may have change
        self._update_screen_window(ob, xaspect, yaspect, aspectratio, prop)        

        # Shutter Timings
        prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_shutterOpenTime, self.rman_scene.bl_scene.renderman.shutter_open)
        prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_shutterCloseTime, self.rman_scene.bl_scene.renderman.shutter_close)

        # Shutter Opening
        if cam_rm.rman_use_shutteropening:
            shutteropenings = [
                cam_rm.rman_shutteropening_c1,
                cam_rm.rman_shutteropening_c2,
                cam_rm.rman_shutteropening_d1,
                cam_rm.rman_shutteropening_d2,
                cam_rm.rman_shutteropening_e1,
                cam_rm.rman_shutteropening_e2,
                cam_rm.rman_shutteropening_f1,
                cam_rm.rman_shutteropening_f2
            ]
            prop.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_shutteropening, shutteropenings, 8)

        # Stereo Planes
        rman_stereoplanedepths_arraylen = getattr(cam_rm, 'rman_stereoplanedepths_arraylen', 0)
        rman_stereoplaneoffsets_arraylen = getattr(cam_rm, 'rman_stereoplaneoffsets_arraylen', 0)
        if (rman_stereoplanedepths_arraylen > 0) and (rman_stereoplaneoffsets_arraylen > 0) and (rman_stereoplanedepths_arraylen == rman_stereoplaneoffsets_arraylen):
            stereoplanedepths = []
            for i in range(rman_stereoplanedepths_arraylen):
                val = getattr(cam_rm, 'rman_stereoplanedepths[%d]' % i)
                stereoplanedepths.append(val)

            prop.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_stereoplanedepths, stereoplanedepths, rman_stereoplanedepths_arraylen)

            stereoplaneoffsets = []
            for i in range(rman_stereoplaneoffsets_arraylen):
                val = getattr(cam_rm, 'rman_stereoplaneoffsets[%d]' % i)
                stereoplaneoffsets.append(val)

            prop.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_stereoplaneoffsets, stereoplaneoffsets, rman_stereoplaneoffsets_arraylen)            

        # clipping planes         
        if cam.clip_end > cam.clip_start:
            prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_nearClip, cam.clip_start)
            prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_farClip, cam.clip_end)
        else:
            rfb_log().debug("Clipping start is greater than clipping end.")             

        # aperture
        prop.SetInteger(self.rman_scene.rman.Tokens.Rix.k_apertureNSides, cam_rm.rman_aperture_blades)
        prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_apertureAngle, cam_rm.rman_aperture_rotation)
        prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_apertureRoundness, cam_rm.rman_aperture_roundness)
        prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_apertureDensity, cam_rm.rman_aperture_density)

        prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_dofaspect, cam_rm.rman_aperture_ratio)    

        rman_sg_camera.sg_camera_node.SetProperties(prop)
    
