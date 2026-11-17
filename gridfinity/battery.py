"""Gridfinity hollow stackable battery holder and command-line entry."""
from dataclasses import asdict,dataclass
import math
import json
import re
import shutil
from .shared import ROOT,SCAD,create_output,register,export_stl,render_png
from .mesh import check_battery

PRESETS = {
    'AA': dict(label='AA / 5号', shape='round', a=14.5, b=14.5, height=50.5,
               source='https://energizer.com/apac/china/wp-content/uploads/sites/18/2024/05/e91_max_na_AA.pdf'),
    'AAA': dict(label='AAA / 7号', shape='round', a=10.5, b=10.5, height=44.5,
                source='https://data.energizer.com/pdfs/E92_Max_EU.pdf'),
    'C': dict(label='C / 2号', shape='round', a=26.2, b=26.2, height=50.,
              source='https://data.energizer.com/pdfs/e93_ap.pdf'),
    'D': dict(label='D / 1号', shape='round', a=34.2, b=34.2, height=61.5,
              source='https://data.energizer.com/pdfs/EP95_Max_Plus_AP.pdf'),
    'LR9': dict(label='LR9 / 625A 纽扣', shape='round', a=16., b=16., height=6.2,
                source='https://www.varta-ag.com/fileadmin/varta/consumer/downloads/general-catalogue/en/9018212241_EN_GC_AW2025-26_v01_SS-LQ_w-o-SHD.pdf'),
    'LR44': dict(label='LR44 / A76 纽扣', shape='round', a=11.6, b=11.6, height=5.4,
                 source='https://www.varta-ag.com/fileadmin/varta/consumer/downloads/general-catalogue/en/9018212241_EN_GC_AW2025-26_v01_SS-LQ_w-o-SHD.pdf'),
    'CR2032': dict(label='CR2032 纽扣', shape='round', a=20., b=20., height=3.2,
                   source='https://data.energizer.com/pdfs/cr2032_eu.pdf'),
    'CR123A': dict(label='CR123A', shape='round', a=17., b=17., height=34.5,
                   source='https://data.energizer.com/pdfs/123.pdf'),
    '18650': dict(label='18650（平头参考）', shape='round', a=18.6, b=18.6, height=65.2,
                  source='https://www.molicel.com/product/inr-18650-p28a/'),
    '21700': dict(label='21700（平头参考）', shape='round', a=21.6, b=21.6, height=70.2,
                  source='https://www.molicel.com/product/inr-21700-p45b/'),
    '9V': dict(label='9V / 6F22 方块', shape='rect', a=26.5, b=17.5, height=48.5,
               source='https://data.energizer.com/pdfs/6f22hd_eu.pdf'),
}

@dataclass
class BatterySettings:
    columns: int = 2
    rows: int = 2
    battery_type: str = 'AA'
    packing: str = 'dense'
    custom_shape: str = 'round'
    custom_a: float = 14.5
    custom_b: float = 14.5
    custom_height: float = 50.5
    clearance: float = .25
    wall: float = 2.
    web: float = 1.6
    seat_depth: float = 0.
    top_clearance: float = .5
    align_height: bool = True
    max_x: float = 240.
    max_y: float = 240.

    def battery(self):
        if self.battery_type in PRESETS:
            return PRESETS[self.battery_type]
        return dict(label='自定义', shape=self.custom_shape,a=self.custom_a,
                    b=self.custom_a if self.custom_shape=='round' else self.custom_b,
                    height=self.custom_height,source='用户输入尺寸')

    def validate(self):
        for n in ('columns','rows'):
            value=getattr(self,n)
            if not isinstance(value,(int,float)) or not math.isfinite(value) or int(value)!=value or not 1<=value<=30:
                raise ValueError('Grid行列数必须是1～30的整数。')
        for n in ('custom_a','custom_b','custom_height','clearance','wall','web','seat_depth','top_clearance','max_x','max_y'):
            if not math.isfinite(getattr(self,n)):
                raise ValueError(f'{n}: 请输入有限数值。')
        b=self.battery()
        if min(b['a'],b['b'],b['height'])<1:
            raise ValueError('电池长宽/直径和高度至少1mm。')
        if self.battery_type not in PRESETS and self.battery_type!='Custom':
            raise ValueError('未知电池类型。')
        if self.packing not in ('regular','dense') or self.custom_shape not in ('round','rect'):
            raise ValueError('未知形状或排列方式。')
        if not .1<=self.clearance<=1.5 or not 1.2<=self.web<=20 or not 1.5<=self.wall<=20:
            raise ValueError('单边间隙0.1～1.5mm，孔间壁1.2～20mm，外壁1.5～20mm。')
        if self.seat_depth<0 or (self.seat_depth and self.seat_depth>b['height']-.4):
            raise ValueError('定位孔深需小于电池高度减0.4mm；0表示自动按约30%高度。')
        if not .5<=self.top_clearance<=20:
            raise ValueError('堆叠净空应为0.5～20mm。')
        if min(self.max_x,self.max_y)<=0:
            raise ValueError('打印长宽上限必须大于0。')

def centered(points,w,h):
    if not points:
        return []
    dx=w/2-(min(p[0] for p in points)+max(p[0] for p in points))/2
    dy=h/2-(min(p[1] for p in points)+max(p[1] for p in points))/2
    return [[round(x+dx,8),round(y+dy,8),r] for x,y,r in points]

def round_candidates(w,h,d,wall,web):
    p=d+web; v=p*math.sqrt(3)/2
    result=[]
    for swap in (False,True):
        a,b=(h,w) if swap else (w,h)
        for phase in (0,1):
            points=[]
            nr=max(0,math.floor((b-2*wall-d+1e-8)/v)+1)
            for j in range(nr):
                shift=((j+phase)%2)*p/2
                nc=max(0,math.floor((a-2*wall-d-shift+1e-8)/p)+1)
                for i in range(nc):
                    x,y=wall+d/2+shift+i*p,wall+d/2+j*v
                    points.append([y,x,0] if swap else [x,y,0])
            result.append(centered(points,w,h))
    nx=max(0,math.floor((w-2*wall-d+1e-8)/p)+1)
    ny=max(0,math.floor((h-2*wall-d+1e-8)/p)+1)
    regular=centered([[wall+d/2+i*p,wall+d/2+j*p,0] for j in range(ny) for i in range(nx)],w,h)
    return result+[regular]

def rect_rows(w,h,a,b,wall,web,k0,k1):
    heights=[b]*k0+[a]*k1
    total=sum(heights)+web*max(0,len(heights)-1)
    y=(h-total)/2
    points=[]
    for j,hh in enumerate(heights):
        ww=a if j<k0 else b
        n=max(0,math.floor((w-2*wall+web+1e-8)/(ww+web)))
        x=(w-(n*ww+(n-1)*web))/2+ww/2
        for i in range(n):
            points.append([round(x+i*(ww+web),8),round(y+hh/2,8),0 if j<k0 else 90])
        y+=hh+web
    return points

def rect_candidates(w,h,a,b,wall,web,mode):
    result=[]
    for swap in (False,True):
        ww,hh=(h,w) if swap else (w,h)
        m0=max(0,math.floor((hh-2*wall+web+1e-8)/(b+web)))
        m1=max(0,math.floor((hh-2*wall+web+1e-8)/(a+web)))
        options=[(m0,0),(0,m1)] if mode=='regular' else [
            (k0,k1) for k0 in range(m0+1) for k1 in range(m1+1)
            if k0+k1 and k0*b+k1*a+(k0+k1-1)*web<=hh-2*wall+1e-8]
        for k0,k1 in options:
            points=rect_rows(ww,hh,a,b,wall,web,k0,k1)
            if swap:
                points=[[y,x,(r+90)%180] for x,y,r in points]
            result.append(points)
    return result

def plan_battery(cfg):
    cfg.validate()
    w,h=42*int(cfg.columns)-.5,42*int(cfg.rows)-.5
    if w>cfg.max_x+.001 or h>cfg.max_y+.001:
        raise ValueError(f'盒体{w:g}×{h:g}mm超过打印上限；请减少Grid行列或增大打印范围。电池盒整体打印。')
    b=cfg.battery()
    a=b['a']+2*cfg.clearance; d=b['b']+2*cfg.clearance
    depth=cfg.seat_depth or min(b['height']-.4,max(.4,math.ceil((b['height']*.3-1e-8)/.2)*.2))
    nominal=7+b['height']+cfg.top_clearance
    if cfg.align_height:nominal=math.ceil((nominal-1e-8)/7)*7
    actual_head_gap=nominal-(7+b['height'])
    # Reserve clearance where the 45-degree underside of the stacking rim leans inward.
    pack_wall=max(cfg.wall,2.6-actual_head_gap-cfg.clearance+.2)
    if b['shape']=='round':
        options=round_candidates(w,h,a,pack_wall,cfg.web)
        # Small custom circles also obey the rounded outer corners.
        def fit(p):
            rr=max(3.75-pack_wall-a/2,0)
            if rr==0:
                return True
            qx=max(abs(p[0]-w/2)-(w/2-pack_wall-a/2-rr),0)
            qy=max(abs(p[1]-h/2)-(h/2-pack_wall-a/2-rr),0)
            return math.hypot(qx,qy)<=rr+1e-8
        options=[[p for p in pts if fit(p)] for pts in options]
        if cfg.packing=='regular':
            options=options[-1:]
    else:
        pack_wall=pack_wall+max(0,(3.75-pack_wall-.5)*(1-1/math.sqrt(2)))
        options=rect_candidates(w,h,a,d,pack_wall,cfg.web,cfg.packing)
    points=max(options,key=len) if options else []
    if not points:
        raise ValueError('当前网格内放不下电池，请增加Grid行列或减小孔径/壁厚。')
    if len(points)>2000:
        raise ValueError('单盒最多2000个孔，请减少Grid行列。')
    return dict(settings=asdict(cfg), battery=b, width=w,depth=h,height=nominal+3.8,
                nominal_height=nominal,height_units=nominal/7,lip_height=3.8,
                hole_a=a,hole_b=d,hole_depth=depth,seat_depth=depth,seat_top=7+depth,floor_z=7,
                exposed=b['height']-depth,grip_height=b['height']-depth,battery_top=7+b['height'],
                head_clearance=actual_head_gap,packing_wall=pack_wall,count=len(points),positions=points,
                packing_note='比较横纵交错排列及规则排列；不是任意圆堆积的全局最优证明' if b['shape']=='round'
                else '比较横纵方向、两种旋转及混合行；不是任意矩形装箱的全局最优证明')

BATTERY_MAP=dict(Grid_Columns='columns',Grid_Rows='rows',Battery_Type='battery_type',Packing='packing',
                 Custom_Shape='custom_shape',Custom_A='custom_a',Custom_B='custom_b',Custom_Height='custom_height',
                 Hole_Clearance='clearance',Outer_Wall='wall',Hole_Web='web',Seat_Depth='seat_depth',Top_Clearance='top_clearance',Align_Height_To_7='align_height',
                 Print_Max_X='max_x',Print_Max_Y='max_y')

def battery_source(cfg):
    source=(SCAD/'battery_holder.scad').read_text(encoding='utf-8')
    for name,field in BATTERY_MAP.items():
        value=json.dumps(getattr(cfg,field))
        source=re.sub(r'^'+name+r'\s*=\s*[^;]*;',lambda _:f'{name} = {value};',source,flags=re.M)
    return source

def battery_svg(p):
    w,h=p['width'],p['depth']
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-5 -14 {w+10} {h+26}" width="900" height="800">',
         f'<rect x="-5" y="-14" width="{w+10}" height="{h+26}" fill="white"/>',
         f'<text x="0" y="-6" font-size="4">{p["settings"]["battery_type"]}: {p["count"]} cells | {p["height"]:g} mm high</text>',
         f'<rect width="{w}" height="{h}" rx="3.75" fill="#b6d9dc" stroke="#344d55" stroke-width=".4"/>']
    for x,y,r in p['positions']:
        if p['battery']['shape']=='round':out.append(f'<circle cx="{x}" cy="{h-y}" r="{p["hole_a"]/2}" fill="white" stroke="#476570" stroke-width=".2"/>')
        else:
            a,b=(p['hole_b'],p['hole_a']) if r==90 else (p['hole_a'],p['hole_b'])
            out.append(f'<rect x="{x-a/2}" y="{h-y-b/2}" width="{a}" height="{b}" rx=".5" fill="white" stroke="#476570" stroke-width=".2"/>')
    return '\n'.join(out+['</svg>'])

def generate(cfg,source_only=False,output=None,log=print,preview=True,update_recent=True):
    make_preview=preview
    p=plan_battery(cfg)
    folder=create_output('中空堆叠盒_'+cfg.battery_type,output)
    for name in ('battery_presets.scad','battery_presets.json'):
        shutil.copy2(SCAD/name,folder/name)
    source=folder/'battery_holder.scad';stl=folder/'battery_holder.STL'
    source.write_text(battery_source(cfg),encoding='utf-8')
    (folder/'layout.json').write_text(json.dumps(p,indent=2,ensure_ascii=False),encoding='utf-8')
    (folder/'layout.svg').write_text(battery_svg(p),encoding='utf-8')
    log(f'{cfg.columns}×{cfg.rows} Grid：{p["count"]}节{cfg.battery_type}，本体{p["nominal_height"]:g}mm + 堆叠边3.8mm')
    check=None
    if not source_only:
        log('OpenSCAD正在导出电池盒STL…')
        text=export_stl(source,stl)
        match=re.search(r'GF_CAPACITY",\s*(\d+)',text)
        if not match or int(match.group(1))!=p['count']:
            raise RuntimeError('OpenSCAD计算孔数与输入窗口预览不一致。')
        check=check_battery(stl,p)
        preview_source=folder/'preview.scad'
        preview_source.write_text('color([.25,.6,.65])import("battery_holder.STL");',encoding='utf-8')
        if make_preview:render_png(preview_source,folder/'preview.png')
        log('STL实体、孔数、孔径、底脚剖面检查通过')
    (folder/'verification.json').write_text(json.dumps(dict(plan=p,mesh=check,physical_fit_tested=False),indent=2,ensure_ascii=False),encoding='utf-8')
    (folder/'使用说明.txt').write_text(
        f'{cfg.columns}列×{cfg.rows}行Grid；容量{p["count"]}节；本体{p["nominal_height"]:g}mm（含底脚）+ 堆叠边3.8mm，总高{p["height"]:g}mm。\n'
        f'底部定位深度{p["hole_depth"]:g}mm；电池上段可抓取{p["grip_height"]:g}mm；电池顶距堆叠面{p["head_clearance"]:g}mm。\n'
        '电池竖直独立放置，一孔一节；纽扣电池平放，一孔一枚。\n'
        '规则排列与密排均在给定Grid面积内自动计算孔数。\n'
        '圆柱密排比较横纵交错和规则排列；方形比较旋转及混合行。并非全局最优装箱证明。\n'
        '在OpenSCAD打开battery_holder.scad，可在Customizer中继续改Grid行列、预设、排列及间隙。\n'
        'Show_Batteries仅在F5预览中显示占位电池，不会导出进STL。\n'
        '底部部分填充并布置定位孔，上方为连通空腔，无内部隔板；保留薄外壁及堆叠唇。\n'
        '多格边缘每42mm有堆叠定位凸起，让上层小盒按格定位。\n'
        '默认本体按7mm单位向上取整；电池全部位于堆叠面下。定位深度默认约电池高度30%，可调整。\n'
        '预设按厂商参考尺寸，外包皮/凸头/保护板型号需实际测量并自定义。\n'
        '底脚为标准45°外扩，脚之间有小跨度桥接；打印前检查切片，先少量试印确认孔径。\n'
        '此为整体打印盒体，超出打印长宽上限时请减少Grid行列。\n'
        f'尺寸来源：{p["battery"]["source"]}\n',encoding='utf-8')
    if update_recent:register('battery',folder,source)
    log(f'完成：{folder}')
    return folder,source


from .cli import Parameter,make_settings,run_cli

Settings=BatterySettings
plan=plan_battery
PARAMETERS=(
    Parameter('columns','Grid列数',int,'列',aliases=('--grid-columns',)),
    Parameter('rows','Grid行数',int,'行',aliases=('--grid-rows',)),
    Parameter('battery_type','电池类型',str,'',tuple(PRESETS)+('Custom',),('--battery',)),
    Parameter('packing','排列方式',str,'',('regular','dense')),
    Parameter('custom_shape','自定义形状',str,'',('round','rect')),
    Parameter('custom_a','电池直径 / 长'),
    Parameter('custom_b','方形电池宽'),
    Parameter('custom_height','电池总高度'),
    Parameter('clearance','孔单边间隙'),
    Parameter('web','孔之间的壁厚'),
    Parameter('wall','盒体外壁'),
    Parameter('seat_depth','定位孔深（0自动）'),
    Parameter('top_clearance','距堆叠面最小间隙'),
    Parameter('align_height','本体高度对齐7mm',bool,''),
    Parameter('max_x','打印长上限'),
    Parameter('max_y','打印宽上限'),
)

def settings_from(values):return make_settings(Settings,PARAMETERS,values)

def main(argv=None):
    return run_cli(Settings,PARAMETERS,plan,generate,
                   'Gridfinity battery holder: grid rows/columns → hollow stackable box with automatic packing.',
                   argv,presets=PRESETS)

if __name__=='__main__':raise SystemExit(main())
