import bpy
from .render_manager import RenderManager

class RendermanRenderEngine(bpy.types.RenderEngine):
    """ RenderEngine subclass which gives the hook to Blender that allows you to render.
        All the methods here are callbacks to blender. """
    bl_idname = 'PRMAN_RENDER'
    bl_label = "RenderMan Render"
    bl_use_preview = True
    bl_use_save_buffers = True

    def __init__(self):
        ''' Create the Engine and a renderpass '''
        self.render_pass = None

    def __del__(self):
        ''' Delete the RenderEngine and render pass '''
        if hasattr(self, "render_pass") and self.render_pass:
            del self.render_pass

    def update(self, data, scene):
        ''' Update the render pass to the current scene, and tell it to write rib out '''
        if not self.render_pass:
            self.render_pass = RenderManager(scene, engine=self)
        else:
            self.render_pass.reset(scene)

        # update the rib
        self.render_pass.write_rib()

    def render(self, scene):
        ''' Start the render '''
        if self.render_pass:
            self.render_pass.render(self)

    def view_update(self, context=None):
        ''' If this is a viewport render update any data via the render pass. '''
        scene = context.scene
        if not self.render_pass:
            self.render_pass = RenderManager(scene, engine=self, is_interactive=True)
        else:
            self.render_pass.ipr_update(context.scene)

    def view_draw(self, context=None):
        ''' Tell the Render Pass to continually update display until further notice ''' 
        self.render_pass.ipr_draw_view(self)
