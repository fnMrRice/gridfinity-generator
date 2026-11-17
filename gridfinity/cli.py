"""Shared parameter schema and command-line behavior; never imports Tkinter."""
import argparse
from dataclasses import asdict,dataclass
import json
import math
import os
from pathlib import Path
import sys


@dataclass(frozen=True)
class Parameter:
    name: str
    label: str
    type: type = float
    unit: str = 'mm'
    choices: tuple = ()
    aliases: tuple = ()


def _convert(parameter,value):
    if parameter.type is bool:
        if isinstance(value,bool):return value
        if isinstance(value,str) and value.lower() in ('true','false','1','0'):
            return value.lower() in ('true','1')
        raise ValueError(f'{parameter.label}必须为true或false。')
    if parameter.type is int:
        number=float(value)
        if isinstance(value,bool) or not math.isfinite(number) or not number.is_integer():
            raise ValueError(f'{parameter.label}必须是整数。')
        return int(number)
    if parameter.type is float:
        if isinstance(value,bool):raise ValueError(f'{parameter.label}必须是数值。')
        return float(value)
    value=str(value)
    if parameter.choices:
        for choice in parameter.choices:
            if value.casefold()==str(choice).casefold():return choice
        raise ValueError(f'{parameter.label}请选择：{", ".join(parameter.choices)}')
    return value


def make_settings(settings_type,parameters,values):
    """One coercion/validation path for CLI JSON, command arguments and GUI fields."""
    schema={p.name:p for p in parameters}
    unknown=set(values)-schema.keys()
    if unknown:raise ValueError('未知参数：'+', '.join(sorted(unknown)))
    try:
        cfg=settings_type(**{name:_convert(schema[name],value) for name,value in values.items()})
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValueError(str(exc)) from exc
    cfg.validate()
    return cfg


def build_parser(settings_type,parameters,description,presets=None):
    parser=argparse.ArgumentParser(description=description,formatter_class=argparse.RawDescriptionHelpFormatter)
    defaults=settings_type()
    for parameter in parameters:
        flags=['--'+parameter.name.replace('_','-'),*parameter.aliases]
        help_text=f'{parameter.label}'+(f' ({parameter.unit})' if parameter.unit else '')
        help_text+=f'; default: {getattr(defaults,parameter.name)}'
        options=dict(dest=parameter.name,default=argparse.SUPPRESS,help=help_text)
        if parameter.type is bool:
            options['action']=argparse.BooleanOptionalAction
        else:
            def convert(value,p=parameter):
                try:return _convert(p,value)
                except (ValueError,TypeError,OverflowError) as exc:raise argparse.ArgumentTypeError(str(exc)) from exc
            options['type']=convert
            if parameter.choices:options['choices']=parameter.choices
        parser.add_argument(*flags,**options)
    parser.add_argument('--settings',type=Path,help='Load settings from JSON; explicit arguments override the file.')
    parser.add_argument('--save-settings',type=Path,help='Save the effective settings as JSON.')
    parser.add_argument('--output',type=Path,help='New output directory. Existing directories are never overwritten.')
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--plan-only',action='store_true',help='Print the computed layout as JSON without OpenSCAD.')
    modes.add_argument('--source-only',action='store_true',help='Write SCAD and layout files without rendering STL.')
    parser.add_argument('--no-preview',action='store_true',help='Export STL without PNG rendering; suitable for headless use.')
    parser.add_argument('--openscad',type=Path,help='OpenSCAD executable path (also supports GRIDFINITY_OPENSCAD).')
    parser.add_argument('--json',action='store_true',help='Return output_directory and source as JSON.')
    parser.add_argument('--quiet',action='store_true',help='Suppress progress messages on stderr.')
    if presets is not None:parser.add_argument('--list-presets',action='store_true',help='Print available battery presets as JSON.')
    return parser


def run_cli(settings_type,parameters,plan,generate,description,argv=None,presets=None):
    # JSON is always UTF-8, including Windows redirected stdout.
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    parser=build_parser(settings_type,parameters,description,presets)
    args=parser.parse_args(argv)
    if presets is not None and args.list_presets:
        print(json.dumps(presets,ensure_ascii=False,indent=2));return 0
    try:
        values={}
        if args.settings:
            values=json.loads(args.settings.read_text(encoding='utf-8-sig'))
            if not isinstance(values,dict):raise ValueError('参数JSON必须是一个对象。')
        values.update({p.name:getattr(args,p.name) for p in parameters if hasattr(args,p.name)})
        cfg=make_settings(settings_type,parameters,values)
        layout=plan(cfg)
    except (OSError,ValueError,TypeError) as exc:
        parser.error(str(exc))
    if args.save_settings:
        args.save_settings.parent.mkdir(parents=True,exist_ok=True)
        args.save_settings.write_text(json.dumps(asdict(cfg),indent=2,ensure_ascii=False),encoding='utf-8')
    if args.plan_only:
        print(json.dumps(layout,ensure_ascii=False,indent=2));return 0
    if args.openscad:os.environ['GRIDFINITY_OPENSCAD']=str(args.openscad.resolve())
    log=(lambda _:None) if args.quiet else (lambda message:print(message,file=sys.stderr,flush=True))
    try:
        folder,source=generate(cfg,source_only=args.source_only,
                               output=args.output.resolve() if args.output else None,
                               preview=not args.no_preview,log=log,update_recent=False)
    except FileExistsError:
        print(f'输出目录已存在，不覆盖：{args.output}',file=sys.stderr);return 1
    except Exception as exc:
        print(str(exc),file=sys.stderr);return 1
    if args.json:print(json.dumps(dict(output_directory=str(folder),source=str(source)),ensure_ascii=False))
    else:print(f'输出目录：{folder}\nSCAD文件：{source}')
    return 0
