"""Compatibility facade. New CLI: python -m gridfinity.baseplate|battery."""
from pathlib import Path
import json
from gridfinity.shared import ROOT,SCAD,find_openscad,call,export_stl,render_png,create_output,register
from gridfinity import baseplate,battery
from gridfinity.baseplate import Settings,plate_source
from gridfinity.battery import BatterySettings,BATTERY_MAP,battery_source,battery_svg,generate as generate_battery

def generate_baseplate(cfg,fit_kit=False,source_only=False,output=None,log=print):
    return baseplate._generate(cfg,fit_kit=fit_kit,source_only=source_only,output=output,log=log)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('kind',choices=['battery','baseplate','fit'])
    parser.add_argument('--settings');parser.add_argument('--source-only',action='store_true')
    args=parser.parse_args()
    values=json.loads(Path(args.settings).read_text(encoding='utf-8')) if args.settings else {}
    logger=lambda s:print(s,flush=True)
    if args.kind=='battery':generate_battery(BatterySettings(**values),args.source_only,log=logger)
    else:generate_baseplate(Settings(**values),args.kind=='fit',args.source_only,log=logger)
