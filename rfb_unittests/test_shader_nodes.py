import unittest
import bpy
from ..rfb_utils import string_utils, property_utils
from .. import rfb_api
import rman

class ShaderNodesTest(unittest.TestCase):

    @classmethod
    def add_tests(self, suite):
        suite.addTest(ShaderNodesTest('test_value_conversion'))
        suite.addTest(ShaderNodesTest('test_rtparamlist'))

    # test getvar 
    def test_value_conversion(self):
        import mathutils

        mat, n1 = rfb_api.create_bxdf('PxrSurface')
        n2 = rfb_api.create_pattern('PxrPrimvar', mat)
        n3 = rfb_api.create_pattern('PxrDirt', mat)

        diffuse_color = [0.18, 0.18, 0.18]
        diffuse_color_test = string_utils.convert_val(n1.diffuseColor, type_hint='color')
        bias_direction = [0.0, 0.0, 0.0]
        bias_direction_test = string_utils.convert_val(n3.biasDirection)

        bl_mtx = string_utils.convert_val(mathutils.Matrix.Identity(4))
        rman_mtx = [1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0
        ]
        
        unitLength = 0.1
        diffuseDoubleSided = 0
        var_type = 'float'

        for i in range(3):
            self.assertAlmostEqual(diffuse_color[i], diffuse_color_test[i])

        for i in range(3):
            self.assertAlmostEqual(bias_direction[i], bias_direction_test[i])            
        
        for i in range(16):
            self.assertAlmostEqual(rman_mtx[i], bl_mtx[i])

        self.assertAlmostEqual(unitLength, string_utils.convert_val(n1.unitLength, type_hint='float'))
        self.assertEqual(diffuseDoubleSided, string_utils.convert_val(n1.diffuseDoubleSided, type_hint='int'))
        self.assertEqual(var_type, string_utils.convert_val(n2.rman_type, type_hint='string'))

        bpy.data.materials.remove(mat)

    # test RtParamList
    def test_rtparamlist(self):
        from ..rfb_utils import prefs_utils
        diffuse_params = [
            'diffuseColor',
            'transmissionBehavior',
            'transmissionColor',
            'presence',
            'bumpNormal',
            'shadowBumpTerminator'
        ]

        def test_eq(a, b, msg=None):
            # for now, we can only check the existence
            # of a parameter
            # we cannot retrieve its value
            for nm in diffuse_params:
                if not b.HasParam(nm):
                    msg = "%s is not in RtParamList" % nm
                    raise self.failureException(msg) 

        mat, node = rfb_api.create_bxdf('PxrDiffuse')
        params = rman.Types.RtParamList()
        params_test = rman.Types.RtParamList()      

        params.SetColor("diffuseColor", [0.5, 0.5, 0.5])
        params.SetInteger("transmissionBehavior", 2)
        params.SetColor("transmissionColor", [0.0, 0.0, 0.0])
        params.SetFloat("presence", 1.0)
        params.SetNormal("bumpNormal", [0.0, 0.0, 0.0])
        params.SetInteger("shadowBumpTerminator", 1)
        
        prefs = prefs_utils.get_addon_prefs()
        pref_val = prefs_utils.get_pref('rman_emit_default_params', False)
        prefs.rman_emit_default_params = True
        property_utils.set_node_rixparams(node, None, params_test)
        self.addTypeEqualityFunc(rman.Types.RtParamList, test_eq)
        self.assertEqual(params, params_test)

        prefs.rman_emit_default_params =  pref_val
        bpy.data.materials.remove(mat)        
        