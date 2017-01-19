import bpy
import mathutils

def export_rib_box(ri, text_name):
    ''' Injects the string from text block named text_name into the rib '''
    if text_name not in bpy.data.texts:
        return
    text_block = bpy.data.texts.get(text_name)
    for line in text_block.lines:
        ri.ArchiveRecord(ri.VERBATIM, line.body + "\n")

def rib(v, type_hint=None):

    # float, int
    if type_hint == 'color':
        return list(v)[:3]

    if type(v) in (mathutils.Vector, mathutils.Color) or\
            v.__class__.__name__ == 'bpy_prop_array'\
            or v.__class__.__name__ == 'Euler':
        # BBM modified from if to elif
        return list(v)

    # matrix
    elif type(v) == mathutils.Matrix:
        return [v[0][0], v[1][0], v[2][0], v[3][0],
                v[0][1], v[1][1], v[2][1], v[3][1],
                v[0][2], v[1][2], v[2][2], v[3][2],
                v[0][3], v[1][3], v[2][3], v[3][3]]
    elif type_hint == 'int':
        return int(v)
    elif type_hint == 'float':
        return float(v)
    else:
        return v