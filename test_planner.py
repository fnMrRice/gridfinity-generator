import unittest
from planner import Settings, plan


class LayoutTests(unittest.TestCase):
    def test_printer_bounds_include_keys(self):
        p = plan(Settings())
        self.assertEqual(len(p['tiles']), 4)
        for t in p['tiles']:
            self.assertLessEqual(t['printed_x'], 240)
            self.assertLessEqual(t['printed_y'], 240)

    def test_grid_continues_across_seams(self):
        p = plan(Settings())
        for a in p['tiles']:
            for b in p['tiles']:
                if b['col'] == a['col']+1 and b['row'] == a['row']:
                    left = a['x']+a['first_x']+42*(a['nx']-1)
                    right = b['x']+b['first_x']
                    self.assertAlmostEqual(right-left, 42)
                if b['row'] == a['row']+1 and b['col'] == a['col']:
                    low = a['y']+a['first_y']+42*(a['ny']-1)
                    high = b['y']+b['first_y']
                    self.assertAlmostEqual(high-low, 42)

    def test_upgrade_printer_changes_piece_count(self):
        p = plan(Settings(max_x=500, max_y=500))
        self.assertEqual(len(p['tiles']), 1)

    def test_no_tiny_remainder_tiles(self):
        p = plan(Settings(length=511, width=301))
        self.assertEqual(sum(t['nx']*t['ny'] for t in p['tiles']), p['nx']*p['ny'])
        self.assertEqual(len(p['tiles']), 6)

    def test_exact_grid_drawer_and_one_cell(self):
        p = plan(Settings(length=85, width=85, max_x=50, max_y=100))
        self.assertEqual(len(p['tiles']), 2)
        self.assertEqual(p['margin_x'], 0)
        self.assertEqual(p['margin_y'], 0)

    def test_invalid_inputs_fail_before_cad(self):
        for cfg in (Settings(height=4.9), Settings(length=20), Settings(max_x=40),
                    Settings(width=float('nan'))):
            with self.assertRaises(ValueError):
                plan(cfg)

    def test_half_keys_allow_single_row(self):
        p = plan(Settings(length=85,width=43,max_x=50,max_y=50))
        self.assertEqual(len(p['tiles']), 2)

    def test_crossing_corners_avoid_orthogonal_keys(self):
        from gridfinity.baseplate import corner_centers
        cfg=Settings()
        p=plan(cfg)
        for t in p['tiles']:
            self.assertEqual(len(corner_centers(cfg,t,'x')),2)
            self.assertEqual(len(corner_centers(cfg,t,'y')),1)

    def test_key_offset_rejects_reverse_alignment(self):
        from planner import KEY_OFFSET, KEY_TIP_HALF, KEY_ROOT_HALF, MALE_PROJECTION
        import math
        slope = (KEY_TIP_HALF-KEY_ROOT_HALF)/MALE_PROJECTION
        for c in (.1, .15, .25):
            allowed = c*math.sqrt(1+slope*slope)
            self.assertGreater(2*KEY_OFFSET, allowed)


if __name__ == '__main__':
    unittest.main()
