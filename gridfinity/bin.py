"""General stackable Gridfinity bins, with optional self-supporting wall openings."""
from dataclasses import asdict, dataclass
import json
import math
import re

from .shared import SCAD, create_output, export_stl, register, render_png
from .mesh import check_bin
from .cli import Parameter, make_settings, run_cli


@dataclass
class Settings:
    columns: int = 2
    rows: int = 2
    height_u: int = 6
    wall: float = 1.6
    bottom: float = 1.6
    hollow: bool = False
    opening: float = 12.
    rib: float = 2.4
    max_x: float = 240.
    max_y: float = 240.
    max_z: float = 256.

    def validate(self):
        for name, limit in (('columns', 30), ('rows', 30), ('height_u', 40)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or int(value) != value or not 1 <= value <= limit:
                raise ValueError(f'{name} 必须是1～{limit}的整数。')
        for name in ('wall', 'bottom', 'opening', 'rib', 'max_x', 'max_y', 'max_z'):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f'{name} 请输入有限数值。')
        if not isinstance(self.hollow, bool):
            raise ValueError('镂空选项必须为布尔值。')
        if not 1.2 <= self.wall <= 4 or not 1.2 <= self.bottom <= 5:
            raise ValueError('外壁厚度1.2～4mm，底厚1.2～5mm（底脚连接面以上）。')
        if not 4 <= self.opening <= 24 or not 1.6 <= self.rib <= 8:
            raise ValueError('菱形孔宽4～24mm，孔间肋宽1.6～8mm。')
        if min(self.max_x, self.max_y, self.max_z) <= 0:
            raise ValueError('打印长宽高上限必须大于0。')
        if 4.75 + self.bottom > self.height_u * 7 - .4:
            raise ValueError('当前高度放不下底厚；请增加高度U或减小底厚。')


def wall_windows(span, nominal, floor_z, wall, opening, rib):
    """Diamond vertices leave full corner posts and top/bottom rails intact."""
    corner = max(5., wall + 2)
    low = floor_z + rib
    high = nominal - max(0., 2.6 - wall) - rib
    size = min(opening, high - low, span - 2 * corner)
    if size < 4 - 1e-8:
        return []
    pitch = size + rib * math.sqrt(2)
    nx = math.floor((span - 2 * corner - size + 1e-8) / pitch) + 1
    step = pitch / 2 if nx > 1 else pitch
    nr = math.floor((high - low - size + 1e-8) / step) + 1
    z0 = (low + high - (nr - 1) * step) / 2
    result = []
    for j in range(nr):
        count = nx - j % 2 if nx > 1 else 1
        x0 = (span - (count - 1) * pitch) / 2
        for i in range(count):
            result.append(dict(center=x0 + i * pitch, z=z0 + j * step, size=size))
    return result


def plan(cfg):
    cfg.validate()
    w, d, nominal = 42 * cfg.columns - .5, 42 * cfg.rows - .5, 7 * cfg.height_u
    if w > cfg.max_x + 1e-8 or d > cfg.max_y + 1e-8:
        raise ValueError(f'盒体{w:g}×{d:g}mm超过打印上限；请减少Grid行列或调整打印范围。收纳盒整体打印。')
    if nominal + 3.8 > cfg.max_z + 1e-8:
        raise ValueError(f'含堆叠边总高{nominal+3.8:g}mm超过打印高度上限{cfg.max_z:g}mm。')
    floor_z = 4.75 + cfg.bottom
    windows = []
    if cfg.hollow:
        for axis, span in (('x', w), ('y', d)):
            for q in wall_windows(span, nominal, floor_z, cfg.wall, cfg.opening, cfg.rib):
                for side in (0, 1):
                    windows.append(dict(axis=axis, side=side, **q))
    return dict(settings=asdict(cfg), width=w, depth=d, nominal_height=nominal,
                height=nominal + 3.8, height_units=cfg.height_u, lip_height=3.8,
                floor_z=floor_z, interior_depth=nominal - floor_z,
                interior_width=w - 2 * cfg.wall, interior_length=d - 2 * cfg.wall,
                windows=windows, opening_count=len(windows),
                mode='lattice' if cfg.hollow else 'solid')


SCAD_MAP = dict(Grid_Columns='columns', Grid_Rows='rows', Height_U='height_u',
                Outer_Wall='wall', Bottom_Thickness='bottom', Hollow_Walls='hollow',
                Opening_Width='opening', Rib_Width='rib', Print_Max_X='max_x', Print_Max_Y='max_y', Print_Max_Z='max_z')


def source_text(cfg):
    source = (SCAD / 'storage_bin.scad').read_text(encoding='utf-8')
    for name, field in SCAD_MAP.items():
        source = re.sub(r'^' + name + r'\s*=\s*[^;]*;',
                        lambda _, v=json.dumps(getattr(cfg, field)): f'{name} = {v};', source, flags=re.M)
    return source


def layout_svg(p):
    w, d = p['width'], p['depth']
    wall = p['settings']['wall']
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-5 -12 {w+10} {d+18}">',
           f'<rect x="-5" y="-12" width="{w+10}" height="{d+18}" fill="white"/>',
           f'<text y="-4" font-size="4">{p["settings"]["columns"]} x {p["settings"]["rows"]} Grid / {p["height_units"]}U / {p["opening_count"]} wall openings</text>',
           f'<rect width="{w}" height="{d}" rx="3.75" fill="#9bc8cf"/>',
           f'<rect x="{wall}" y="{wall}" width="{w-2*wall}" height="{d-2*wall}" rx="{max(.01,3.75-wall)}" fill="#edf4f4"/>']
    return '\n'.join(out + ['</svg>'])


def generate(cfg, source_only=False, output=None, log=print, preview=True, update_recent=True):
    p = plan(cfg)
    folder = create_output('通用收纳盒', output)
    source, stl = folder / 'storage_bin.scad', folder / 'storage_bin.STL'
    source.write_text(source_text(cfg), encoding='utf-8')
    (folder / 'layout.json').write_text(json.dumps(p, indent=2, ensure_ascii=False), encoding='utf-8')
    (folder / 'layout.svg').write_text(layout_svg(p), encoding='utf-8')
    log(f'{cfg.columns}×{cfg.rows} Grid · {cfg.height_u}U · 总高{p["height"]:g}mm · {p["opening_count"]}个侧壁孔')
    check = None
    if not source_only:
        log('OpenSCAD正在导出收纳盒STL…')
        text = export_stl(source, stl)
        match = re.search(r'GF_OPENINGS",\s*(\d+)', text)
        if not match or int(match.group(1)) != p['opening_count']:
            raise RuntimeError('OpenSCAD侧壁孔数与布局计划不一致。')
        check = check_bin(stl, p)
        preview_source = folder / 'preview.scad'
        preview_source.write_text('color([.25,.6,.65])import("storage_bin.STL",convexity=20);', encoding='utf-8')
        if preview:
            render_png(preview_source, folder / 'preview.png')
        log('STL闭合、底面、底脚、堆叠边及镂空检查通过')
    (folder / 'verification.json').write_text(json.dumps(dict(plan=p, mesh=check, physical_fit_tested=False), indent=2, ensure_ascii=False), encoding='utf-8')
    (folder / '使用说明.txt').write_text(
        f'{cfg.columns}列×{cfg.rows}行Grid，{cfg.height_u}U；本体{p["nominal_height"]:g}mm（含底脚），堆叠边另加3.8mm，总高{p["height"]:g}mm。\n'
        f'壁厚{cfg.wall:g}mm；底脚连接面上方底厚{cfg.bottom:g}mm；底面位于Z={p["floor_z"]:g}mm；至堆叠面的内部深度{p["interior_depth"]:g}mm。\n'
        f'侧壁孔{p["opening_count"]}个，保留四角、上下框和完整底面；矮盒空间不足时不切孔。\n'
        '无内部隔板。底脚、堆叠边与格间定位凸起沿用电池盒接口。\n'
        '竖直放置底脚朝下打印。菱形孔顶为45°；底脚之间仍有标准小跨度桥接，请检查切片。\n'
        '镂空款适合较大物件，小件可能从孔中掉出；承载和实际配合需试印确认。\n'
        '在OpenSCAD中打开storage_bin.scad可继续调整；公共gridfinity_core.scad须放在同目录。\n', encoding='utf-8')
    if update_recent:
        register('bin', folder, source)
    return folder, source


PARAMETERS = (
    Parameter('columns', 'Grid列数', int, '列', aliases=('--grid-columns',)),
    Parameter('rows', 'Grid行数', int, '行', aliases=('--grid-rows',)),
    Parameter('height_u', '盒体高度', int, 'U', aliases=('--height',)),
    Parameter('hollow', '侧壁镂空', bool, ''),
    Parameter('wall', '盒体外壁厚度'),
    Parameter('bottom', '连接面以上底厚'),
    Parameter('opening', '菱形孔最大宽'),
    Parameter('rib', '孔间肋 / 边框宽'),
    Parameter('max_x', '打印长上限'),
    Parameter('max_y', '打印宽上限'),
    Parameter('max_z', '打印高上限'),
)


def settings_from(values):
    return make_settings(Settings, PARAMETERS, values)


def main(argv=None):
    return run_cli(Settings, PARAMETERS, plan, generate,
                   'Stackable Gridfinity bin: grid rows/columns and height U; optional diamond wall openings.', argv)


if __name__ == '__main__':
    raise SystemExit(main())
