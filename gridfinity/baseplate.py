"""Gridfinity open baseplate: planning, SCAD generation and command-line entry."""
from dataclasses import asdict,dataclass
import math
import json
from .shared import ROOT,SCAD,create_output,register,export_stl,render_png
from .mesh import check_baseplate

PITCH = 42.0

MALE_PROJECTION = 1.6

KEY_RECESS = .4

KEY_OFFSET = .2

KEY_ROOT_HALF = 1.2

KEY_TIP_HALF = 2.

KEY_RAMP_DROP = .8

@dataclass
class Settings:
    length: float = 450
    width: float = 320
    height: float = 5
    max_x: float = 240
    max_y: float = 240
    wall_clearance: float = .5
    seam_gap: float = .2
    joint_clearance: float = .15

    def validate(self):
        for name, value in asdict(self).items():
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f'{name}: 请输入有限数值。')
        if self.height < 5:
            raise ValueError('总厚度至少5mm，标准配合轮廓不会随厚度缩放。')
        if not 0 <= self.wall_clearance <= 5:
            raise ValueError('抽屉每侧间隙应为0～5mm。')
        if not .1 <= self.seam_gap <= .4:
            raise ValueError('板缝应为0.1～0.4mm。')
        if not .1 <= self.joint_clearance <= .25:
            raise ValueError('榫槽单边间隙应为0.1～0.25mm，请先打印试拼件。')
        if min(self.max_x, self.max_y) < 44:
            raise ValueError('本生成器沿整格分块，打印长宽上限至少44mm。')

def partition_axis(cells, extent, margin, limit, gap, min_cells=1):
    """Minimize pieces, then balance lengths; include projecting connectors."""
    edges = [0.] + [margin + PITCH * i for i in range(1, cells)] + [extent]
    best = {0: (0, 0., [])}
    for end in range(1, cells + 1):
        options = []
        for start in range(end):
            if end-start < min_cells:
                continue
            if start not in best:
                continue
            low = edges[start] + (gap / 2 if start else 0)
            high = edges[end] - (gap / 2 if end < cells else 0)
            printed = high - low + (MALE_PROJECTION if end < cells else 0)
            if printed <= limit + 1e-8:
                count, score, spans = best[start]
                options.append((count + 1, score + printed ** 2,
                                spans + [(start, end, low, high, printed)]))
        if options:
            best[end] = min(options, key=lambda v: (v[0], v[1]))
    if cells not in best:
        raise ValueError('打印范围不足以容纳单格及外侧补边；请增大打印范围或减小抽屉尺寸。')
    return best[cells][2]

def plan(cfg: Settings):
    cfg.validate()
    length = cfg.length - 2 * cfg.wall_clearance
    width = cfg.width - 2 * cfg.wall_clearance
    nx, ny = math.floor((length + 1e-8) / PITCH), math.floor((width + 1e-8) / PITCH)
    if min(nx, ny) < 1:
        raise ValueError('扣除安装间隙后，长宽都必须至少42mm。')
    if nx * ny > 2500:
        raise ValueError('单次最多2500个格子，请拆成多个区域生成。')
    mx, my = (length - nx * PITCH) / 2, (width - ny * PITCH) / 2
    xs = partition_axis(nx, length, mx, cfg.max_x, cfg.seam_gap)
    ys = partition_axis(ny, width, my, cfg.max_y, cfg.seam_gap)
    tiles = []
    for row, (j0, j1, y0, y1, ph) in enumerate(ys):
        for col, (i0, i1, x0, x1, pw) in enumerate(xs):
            tiles.append(dict(id=f'R{row+1:02d}_C{col+1:02d}', row=row, col=col,
                              x=x0, y=y0, length=x1-x0, width=y1-y0,
                              printed_x=pw, printed_y=ph, nx=i1-i0, ny=j1-j0,
                              first_x=mx + i0*PITCH + 21 - x0,
                              first_y=my + j0*PITCH + 21 - y0,
                              male_x=col < len(xs)-1, male_y=row < len(ys)-1,
                              female_x=col > 0, female_y=row > 0,
                              rows_total=len(ys), cols_total=len(xs)))
    return dict(settings=asdict(cfg), length=length, width=width, nx=nx, ny=ny,
                margin_x=mx, margin_y=my, columns=len(xs), rows=len(ys), tiles=tiles)

def svg_layout(layout):
    w, h = layout['length'], layout['width']
    colors = ['#d8eaf2', '#dcead8', '#f7e2c5', '#e8dff2']
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="800" '
           f'viewBox="-12 -28 {w+24} {h+55}">',
           '<rect x="-12" y="-28" width="100%" height="100%" fill="white"/>',
           f'<text x="0" y="-13" font-size="9">Gridfinity {layout["nx"]} x {layout["ny"]} | '
           f'{w:g} x {h:g} mm | {len(layout["tiles"])} tiles</text>']
    for t in layout['tiles']:
        x, y = t['x'], h-t['y']-t['width']
        color = colors[(t['row']+t['col']) % len(colors)]
        out.append(f'<rect x="{x}" y="{y}" width="{t["length"]}" height="{t["width"]}" '
                   f'fill="{color}" stroke="#38454e" stroke-width=".4"/>')
        for i in range(t['nx']):
            for j in range(t['ny']):
                cx, cy = x+t['first_x']+42*i, h-(t['y']+t['first_y']+42*j)
                out.append(f'<rect x="{cx-18.15}" y="{cy-18.15}" width="36.3" height="36.3" '
                           'rx="1.15" fill="white" stroke="#96a6ad" stroke-width=".3"/>')
        out.append(f'<text x="{x+3}" y="{y+7}" font-size="5">{t["id"]} '
                   f'{t["printed_x"]:.1f} x {t["printed_y"]:.1f}</text>')
    out += [f'<text x="0" y="{h+14}" font-size="6">Assembly: R01 first; left to right; then next row. '
            'Dimensions include male keys.</text>', '</svg>']
    return '\n'.join(out)

def male_polygon():
    return [[-.5,-KEY_ROOT_HALF],[0,-KEY_ROOT_HALF],[MALE_PROJECTION,-KEY_TIP_HALF],
            [MALE_PROJECTION,KEY_TIP_HALF],[0,KEY_ROOT_HALF],[-.5,KEY_ROOT_HALF]]

def female_polygon(cfg):
    slope=(KEY_TIP_HALF-KEY_ROOT_HALF)/MALE_PROJECTION
    offset=cfg.joint_clearance*math.sqrt(1+slope*slope)
    depth=MALE_PROJECTION-cfg.seam_gap+cfg.joint_clearance
    half=lambda x:KEY_ROOT_HALF+(x+cfg.seam_gap)*slope+offset
    return [[-.5,-half(-.5)],[depth,-half(depth)],[depth,half(depth)],[-.5,half(-.5)]]

def moved(poly,axis,edge,center):
    return [[edge+u,center+v] if axis=='x' else [center+v,edge+u] for u,v in poly]

def clip_polygon(poly,axis,low=None,high=None):
    for bound,above in ((low,True),(high,False)):
        if bound is None or not poly:continue
        result=[]
        for a,b in zip(poly,poly[1:]+poly[:1]):
            ia=a[axis]>=bound-1e-10 if above else a[axis]<=bound+1e-10
            ib=b[axis]>=bound-1e-10 if above else b[axis]<=bound+1e-10
            if ia:result.append(a)
            if ia!=ib:
                f=(bound-a[axis])/(b[axis]-a[axis])
                result.append([a[k]+f*(b[k]-a[k]) for k in range(2)])
        poly=result
    return poly

def corner_centers(cfg,t,axis):
    extent=t['width'] if axis=='x' else t['length']
    if axis=='x':
        return [('Start',(-cfg.seam_gap/2 if t['row'] else 0)+KEY_OFFSET),
                ('End',extent+(cfg.seam_gap/2 if t['row']<t['rows_total']-1 else 0)+KEY_OFFSET)]
    return ([('Start',KEY_OFFSET)] if t['col']==0 else [])+(
        [('End',extent+KEY_OFFSET)] if t['col']==t['cols_total']-1 else [])

def plate_source(cfg,t):
    l,w,h=t['length'],t['width'],cfg.height
    males=[];females=[];ramps=[]
    for axis in ('x','y'):
        count=(t['ny'] if axis=='x' else t['nx'])-1
        center=(t['first_y'] if axis=='x' else t['first_x'])+21+KEY_OFFSET
        extent=w if axis=='x' else l
        centers=[center+42*i for i in range(count)]
        corners=corner_centers(cfg,t,axis)
        if t['male_'+axis]:
            edge=l if axis=='x' else w
            profiles=[moved(male_polygon(),axis,edge,c) for c in centers]
            profiles += [moved(clip_polygon(male_polygon(),1,-c,extent-c),axis,edge,c) for _,c in corners]
            for poly in profiles:
                males.append(f'linear_extrude(height={h-KEY_RECESS:.9g}) polygon({json.dumps(poly)});')
            u1=edge+MALE_PROJECTION+.2
            z0=h-KEY_RECESS;z1=z0-KEY_RAMP_DROP*(u1-edge)/MALE_PROJECTION
            poly=[[edge,z0],[u1,z1],[u1,h+.2],[edge,h+.2]]
            if axis=='x':
                ramps.append(f'translate([0,{w/2},0])rotate([90,0,0])linear_extrude(height={w+10},center=true)polygon({json.dumps(poly)});')
            else:
                ramps.append(f'translate([{l/2},0,0])rotate([90,0,90])linear_extrude(height={l+10},center=true)polygon({json.dumps(poly)});')
        if t['female_'+axis]:
            for c in centers+[c for _,c in corners]:
                poly=moved(female_polygon(cfg),axis,0,c)
                females.append(f'translate([0,0,-.02])linear_extrude(height={h+.04})polygon({json.dumps(poly)});')
    sockets=[f'translate([{t["first_x"]+42*i},{t["first_y"]+42*j},0])socket_cutter({h});'
             for i in range(t['nx']) for j in range(t['ny'])]
    return (f'// {t["id"]}: open lattice, reinforced dovetails and corner half keys. Millimetres.\n'
            '// Regenerate in the input window when drawer dimensions or tile count change.\n'
            'use <gridfinity_core.scad>\n'
            'difference(){\n union(){\n'+f'cube([{l},{w},{h}]);\n'+'\n'.join(males)+
            '\n}\n'+'\n'.join(sockets+females+ramps)+'\n}\n')

def _generate(cfg,fit_kit=False,source_only=False,output=None,log=print,preview=True,update_recent=True):
    if fit_kit:
        cfg=Settings(length=85,width=85,height=cfg.height,max_x=50,max_y=100,
                     wall_clearance=.5,seam_gap=cfg.seam_gap,joint_clearance=cfg.joint_clearance)
    p=plan(cfg)
    folder=create_output('底板试拼' if fit_kit else '底板',output)
    p['backend']='OpenSCAD';p['joint_type']='reinforced_corner_half_through'
    (folder/'layout.json').write_text(json.dumps(p,indent=2,ensure_ascii=False),encoding='utf-8')
    (folder/'layout.svg').write_text(svg_layout(p),encoding='utf-8')
    records=[];assembly=['// Positioned layout. Each STL is printed separately.']
    log(f'{p["nx"]}×{p["ny"]}网格，共{len(p["tiles"])}块')
    for t in p['tiles']:
        src=folder/(t['id']+'.scad');stl=src.with_suffix('.STL')
        src.write_text(plate_source(cfg,t),encoding='utf-8')
        if not source_only:
            log(f'{t["id"]}：OpenSCAD正在导出STL…')
            export_stl(src,stl)
            check=check_baseplate(stl,t,cfg.height,cfg.max_x,cfg.max_y)
            records.append(dict(tile=t,stl=str(stl),check=check))
            assembly.append(f'translate([{t["x"]},{t["y"]},0])color([{.25+.1*(t["row"]%2)},.6,{.65+.1*(t["col"]%2)}])import("{stl.name}");')
            log(f'{t["id"]}：已验证 {t["printed_x"]:.1f}×{t["printed_y"]:.1f}mm，格子贯通')
    main=folder/'assembly.scad'
    if source_only:
        main=(folder/(p['tiles'][0]['id']+'.scad'))
    else:
        main.write_text('\n'.join(assembly),encoding='utf-8')
        if preview:render_png(main,folder/'preview.png')
    (folder/'verification.json').write_text(json.dumps(dict(layout=p,tiles=records,physical_fit_tested=False),indent=2,ensure_ascii=False),encoding='utf-8')
    (folder/'打印说明.txt').write_text(
        '每个Rxx_Cxx.STL单独打印，单位mm，平底朝下。格子贯通，无底面。\n'
        '榫颈2.4mm、头宽4mm，最高处低0.4mm，端部斜面避让；母槽贯通。\n'
        '端部半榫；四板交点X方向共享两半榫，Y方向端部让位。\n'
        '先打印小试拼件。默认单边榫槽间隙0.15mm，松紧和强度需实物确认。\n'
        '上提可拆，薄板靠抽屉辅助限位。不要作为可提起承重的整板。\n'
        'assembly.scad仅作整板预览，每个STL单独放入切片软件，并检查机器禁印区。\n'
        '更换抽屉或打印上限时在输入窗口重新生成。\n',encoding='utf-8')
    if update_recent:register('baseplate',folder,main)
    log(f'完成：{folder}')
    return folder,main


def generate(cfg,source_only=False,output=None,log=print,preview=True,update_recent=True):
    """Generate the baseplate using the same settings accepted by CLI and GUI."""
    return _generate(cfg,source_only=source_only,output=output,log=log,preview=preview,update_recent=update_recent)


from .cli import Parameter,make_settings,run_cli

PARAMETERS=(
    Parameter('length','抽屉 / 层内长'),
    Parameter('width','抽屉 / 层内宽'),
    Parameter('height','总厚度（≥5）'),
    Parameter('max_x','每块打印长上限'),
    Parameter('max_y','每块打印宽上限'),
    Parameter('wall_clearance','抽屉每侧间隙'),
    Parameter('seam_gap','板块接缝'),
    Parameter('joint_clearance','榫槽单边间隙'),
)

def settings_from(values):return make_settings(Settings,PARAMETERS,values)

def main(argv=None):
    return run_cli(Settings,PARAMETERS,plan,generate,
                   'Gridfinity baseplate: drawer dimensions → split open lattice with dovetails.',argv)

if __name__=='__main__':raise SystemExit(main())
