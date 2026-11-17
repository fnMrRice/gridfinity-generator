import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).parent.resolve()

class CLITests(unittest.TestCase):
    def run_cli(self,module,*args,**options):
        env=dict(os.environ)
        env['GRIDFINITY_OPENSCAD']=str(ROOT/'not-installed.exe')
        return subprocess.run([sys.executable,'-m','gridfinity.'+module,*map(str,args)],cwd=ROOT,
                              env=env,capture_output=True,text=True,encoding='utf-8',**options)

    def test_independent_commands_and_no_gui_import(self):
        a=self.run_cli('baseplate','--length','450','--width','320','--plan-only')
        self.assertEqual(a.returncode,0,a.stderr)
        self.assertEqual(len(json.loads(a.stdout)['tiles']),4)
        b=self.run_cli('battery','--columns','2','--rows','2','--battery','aa','--packing','dense','--plan-only')
        self.assertEqual(b.returncode,0,b.stderr)
        self.assertEqual(json.loads(b.stdout)['count'],20)
        result=subprocess.run([sys.executable,'-c',
            "import sys; import gridfinity.baseplate,gridfinity.battery,gridfinity.bin; assert 'tkinter' not in sys.modules"],cwd=ROOT,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_json_file_explicit_overrides_and_boolean(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            cfg=Path(tmp)/'my settings.json';saved=Path(tmp)/'effective.json'
            cfg.write_text(json.dumps(dict(columns=3,rows=1,battery_type='AAA',packing='dense')),encoding='utf-8')
            result=self.run_cli('battery','--settings',cfg,'--columns','2','--packing','regular',
                                '--no-align-height','--save-settings',saved,'--plan-only')
            self.assertEqual(result.returncode,0,result.stderr)
            p=json.loads(result.stdout);effective=json.loads(saved.read_text(encoding='utf-8'))
            self.assertEqual((p['settings']['columns'],p['settings']['rows']),(2,1))
            self.assertEqual(effective['battery_type'],'AAA')
            self.assertEqual(effective['packing'],'regular')
            self.assertFalse(effective['align_height'])

    def test_source_exports_work_without_cad_and_keep_gui_recent(self):
        manifest=ROOT/'scad_outputs.json'
        before=manifest.read_bytes() if manifest.exists() else None
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            for kind in ('baseplate','battery','bin'):
                target=Path(tmp)/kind
                result=self.run_cli(kind,'--source-only','--output',target,'--json','--quiet')
                self.assertEqual(result.returncode,0,result.stderr)
                output=json.loads(result.stdout)
                self.assertEqual(Path(output['output_directory']),target)
                self.assertTrue(Path(output['source']).is_file())
                self.assertTrue((target/'layout.json').is_file())
                self.assertFalse(list(target.glob('*.STL')))
        self.assertEqual(before,manifest.read_bytes() if manifest.exists() else None)

    def test_invalid_args_do_not_create_outputs(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            target=Path(tmp)/'invalid'
            result=self.run_cli('battery','--rows','1.5','--output',target,'--source-only')
            self.assertEqual(result.returncode,2)
            self.assertFalse(target.exists())
            cfg=Path(tmp)/'bad.json';cfg.write_text('{"unknown": 3}',encoding='utf-8')
            result=self.run_cli('baseplate','--settings',cfg,'--source-only','--output',target)
            self.assertEqual(result.returncode,2)
            self.assertFalse(target.exists())

    def test_existing_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            marker=Path(tmp)/'keep.txt';marker.write_text('keep',encoding='utf-8')
            result=self.run_cli('baseplate','--output',tmp,'--source-only')
            self.assertEqual(result.returncode,1)
            self.assertEqual(marker.read_text(encoding='utf-8'),'keep')
            self.assertFalse((Path(tmp)/'gridfinity_core.scad').exists())

    def test_presets_and_help(self):
        result=self.run_cli('battery','--list-presets')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('LR9',json.loads(result.stdout))
        for kind in ('baseplate','battery','bin'):
            result=self.run_cli(kind,'--help')
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('--output',result.stdout)
            self.assertIn('--no-preview',result.stdout)
            self.assertNotIn('RuntimeWarning',result.stderr)

    def test_bin_parameters_and_dispatch(self):
        result=self.run_cli('bin','--columns','3','--rows','2','--height-u','6','--hollow','--plan-only')
        self.assertEqual(result.returncode,0,result.stderr)
        p=json.loads(result.stdout)
        self.assertEqual(p['nominal_height'],42)
        self.assertGreater(p['opening_count'],0)
        result=subprocess.run([sys.executable,'-m','gridfinity','bin','--columns','1','--height','3',
                               '--no-hollow','--plan-only'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['opening_count'],0)

if __name__=='__main__':unittest.main()
