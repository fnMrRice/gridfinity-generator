import itertools
import math
import unittest

from gridfinity import bin as model


class BinTests(unittest.TestCase):
    def test_dimensions_floor_and_short_tray(self):
        p=model.plan(model.Settings(columns=3,rows=2,height_u=6))
        self.assertEqual((p['width'],p['depth'],p['nominal_height'],p['height']),(125.5,83.5,42,45.8))
        self.assertEqual(p['opening_count'],0)
        self.assertAlmostEqual(p['interior_depth'],35.65)
        tray=model.plan(model.Settings(columns=1,rows=1,height_u=1,hollow=True))
        self.assertGreater(tray['interior_depth'],0)
        self.assertEqual(tray['opening_count'],0)

    def test_openings_leave_frames_and_real_ligaments(self):
        for columns,rows,height,opening,rib in itertools.product((1,2,5),(1,3),(2,3,6,12),(4,12,24),(1.6,2.4,8)):
            cfg=model.Settings(columns=columns,rows=rows,height_u=height,opening=opening,rib=rib,hollow=True)
            p=model.plan(cfg)
            for axis,side in itertools.product(('x','y'),(0,1)):
                holes=[q for q in p['windows'] if q['axis']==axis and q['side']==side]
                span=p['width'] if axis=='x' else p['depth']
                for q in holes:
                    self.assertGreaterEqual(q['center']-q['size']/2,5-1e-7)
                    self.assertLessEqual(q['center']+q['size']/2,span-5+1e-7)
                    self.assertGreaterEqual(q['z']-q['size']/2,p['floor_z']+rib-1e-7)
                    self.assertLessEqual(q['z']+q['size']/2,p['nominal_height']-1-rib+1e-7)
                for a,b in itertools.combinations(holes,2):
                    # Equal diamonds: the separating normal is 45 degrees.
                    separation=abs(a['center']-b['center'])+abs(a['z']-b['z'])
                    self.assertGreaterEqual(separation-a['size'],rib*math.sqrt(2)-1e-7)

    def test_invalid_or_oversize_parameters(self):
        for values in ({'columns':0},{'rows':1.5},{'height_u':0},{'height_u':1,'bottom':5},
                       {'columns':6},{'height_u':40},{'max_z':30},{'wall':.8},{'rib':1},{'opening':float('nan')}):
            with self.subTest(values=values),self.assertRaises(ValueError):
                model.plan(model.Settings(**values))


if __name__=='__main__':unittest.main()
