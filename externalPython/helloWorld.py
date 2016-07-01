import time
import bpy
print("Hello World") #Print will show in console


rm = bpy.context.scene.renderman
rm.render_selected_objects_only = True #Direct modification of renderman properties.
#Do be careful though as Blender will not tolerate the UI and this thread acessing the
# same resource. You have been warned.

#Just note your context or your script will terminate.

time.sleep(12) #We can Have the operator going without interupting the drawing thread.
