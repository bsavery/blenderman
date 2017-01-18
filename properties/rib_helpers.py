import bpy

def export_rib_box(ri, text_name):
    ''' Injects the string from text block named text_name into the rib '''
    if text_name not in bpy.data.texts:
        return
    text_block = bpy.data.texts.get(text_name)
    for line in text_block.lines:
        ri.ArchiveRecord(ri.VERBATIM, line.body + "\n")

