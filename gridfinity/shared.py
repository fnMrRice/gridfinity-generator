"""Shared OpenSCAD process, resource paths and output management."""
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SCAD=ROOT/'scad'

def find_openscad(gui=False):
    suffix='openscad.exe' if gui else 'openscad.com'
    override=os.environ.get('GRIDFINITY_OPENSCAD')
    if override:
        path=Path(override)
        if gui and path.suffix.lower()=='.com' and path.with_suffix('.exe').is_file():path=path.with_suffix('.exe')
        if not path.is_file():raise RuntimeError(f'OpenSCAD路径不存在：{path}')
        return path
    local=ROOT.parent/'tools'/'OpenSCAD'/'runtime'/'openscad-2021.01'/suffix
    choices=[local,Path(r'C:\Program Files\OpenSCAD')/suffix]
    on_path=shutil.which(suffix)
    if on_path:choices.insert(0,Path(on_path))
    native=shutil.which('openscad')
    if native:choices.insert(0,Path(native))
    for path in choices:
        if path.is_file():return path
    raise RuntimeError('没有找到OpenSCAD，请检查 tools/OpenSCAD/runtime 或安装OpenSCAD。')

def call(args,log_path,timeout=900):
    result=subprocess.run([str(find_openscad())]+[str(x) for x in args],capture_output=True,
                          text=True,encoding='utf-8',errors='replace',timeout=timeout,
                          creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    content=result.stdout+'\n'+result.stderr
    Path(log_path).write_text(content,encoding='utf-8')
    if result.returncode or re.search(r'\b(ERROR|WARNING):',content):
        raise RuntimeError(f'OpenSCAD编译未通过。详情：{log_path}\n{content[-1400:]}')
    return content

def export_stl(source,output):
    text=call(['--export-format','binstl','-o',output,source],Path(output).with_suffix('.log'))
    if not Path(output).is_file() or Path(output).stat().st_size<100:
        raise RuntimeError('OpenSCAD未生成有效STL。')
    return text

def render_png(source,output):
    return call(['--preview','--viewall','--autocenter','--projection=o','--imgsize=1280,960',
                 '--camera=0,0,0,55,0,25,200','-o',output,source],Path(output).with_suffix('.png.log'),300)

def create_output(kind,output=None):
    folder=Path(output) if output else ROOT/'OpenSCAD输出'/(kind+'_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    folder.mkdir(parents=True,exist_ok=False)
    shutil.copy2(SCAD/'gridfinity_core.scad',folder/'gridfinity_core.scad')
    return folder

def register(kind,folder,source):
    path=ROOT/'scad_outputs.json'
    try:data=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):data={}
    data[kind]=dict(folder=str(folder),source=str(source))
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
