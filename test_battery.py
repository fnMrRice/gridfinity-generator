import math
import unittest
from battery_planner import PRESETS,BatterySettings,plan_battery

class BatteryTests(unittest.TestCase):
    def test_grid_counts_are_not_battery_counts(self):
        self.assertEqual(plan_battery(BatterySettings(packing='regular'))['count'],16)
        p=plan_battery(BatterySettings())
        self.assertEqual(p['count'],20)
        self.assertEqual((p['width'],p['depth']),(83.5,83.5))

    def test_stackable_height_and_partial_seat(self):
        p=plan_battery(BatterySettings())
        self.assertEqual(p['nominal_height'],63)
        self.assertEqual(p['height'],66.8)
        self.assertAlmostEqual(p['hole_depth'],15.2)
        self.assertEqual(p['floor_z'],7)
        self.assertGreater(p['grip_height'],35)
        self.assertGreaterEqual(p['head_clearance'],.5)
        self.assertEqual(plan_battery(BatterySettings(align_height=False))['nominal_height'],58)

    def test_all_presets_fit_without_colliding(self):
        for key in PRESETS:
            p=plan_battery(BatterySettings(battery_type=key))
            self.assertEqual(p['nominal_height']%7,0)
            self.assertGreaterEqual(p['floor_z'],7)
            for i,(x,y,r) in enumerate(p['positions']):
                a,b=(p['hole_b'],p['hole_a']) if r==90 else (p['hole_a'],p['hole_b'])
                self.assertGreaterEqual(x-a/2,2-1e-6)
                self.assertGreaterEqual(y-b/2,2-1e-6)
                self.assertLessEqual(x+a/2,p['width']-2+1e-6)
                self.assertLessEqual(y+b/2,p['depth']-2+1e-6)
                for xx,yy,rr in p['positions'][i+1:]:
                    if p['battery']['shape']=='round':
                        self.assertGreaterEqual(math.hypot(x-xx,y-yy),p['hole_a']+1.6-1e-6)
                    else:
                        aa,bb=(p['hole_b'],p['hole_a']) if rr==90 else (p['hole_a'],p['hole_b'])
                        self.assertTrue(abs(x-xx)>=(a+aa)/2+1.6-1e-6 or abs(y-yy)>=(b+bb)/2+1.6-1e-6)

    def test_dense_capacity_is_never_lower(self):
        for key in PRESETS:
            for cols,rows in ((1,1),(1,3),(2,2),(3,2),(4,3)):
                a=plan_battery(BatterySettings(columns=cols,rows=rows,battery_type=key,packing='regular'))
                b=plan_battery(BatterySettings(columns=cols,rows=rows,battery_type=key,packing='dense'))
                self.assertGreaterEqual(b['count'],a['count'])

    def test_lr9_and_9v_are_distinct(self):
        self.assertEqual(PRESETS['LR9']['shape'],'round')
        self.assertEqual(PRESETS['9V']['shape'],'rect')
        self.assertEqual(PRESETS['LR9']['height'],6.2)

    def test_custom_and_invalid_inputs(self):
        p=plan_battery(BatterySettings(battery_type='Custom',custom_shape='rect',custom_a=22,custom_b=12,custom_height=32))
        self.assertGreater(p['count'],0)
        for cfg in (BatterySettings(rows=0),BatterySettings(columns=1.5),BatterySettings(seat_depth=60),
                    BatterySettings(columns=8),BatterySettings(custom_height=float('nan'))):
            with self.assertRaises(ValueError):plan_battery(cfg)

if __name__=='__main__':unittest.main()
