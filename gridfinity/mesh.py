"""STL validation and planar sections, using only Python's standard library."""
from collections import Counter, defaultdict
import math
from pathlib import Path
import struct

def load_stl(path):
    data=Path(path).read_bytes()
    if len(data)>=84:
        n=struct.unpack_from('<I',data,80)[0]
        if len(data)==84+50*n:
            return [[tuple(t[3:6]),tuple(t[6:9]),tuple(t[9:12])]
                    for t in struct.iter_unpack('<12fH',data[84:])]
    vertices=[tuple(map(float,line.split()[1:])) for line in data.decode('ascii').splitlines()
              if line.strip().startswith('vertex ')]
    if not vertices or len(vertices)%3:
        raise ValueError('STL文件格式无效。')
    return [vertices[i:i+3] for i in range(0,len(vertices),3)]

def mesh_info(path,allow_bridge_z=None):
    triangles=load_stl(path)
    edges=Counter(); orientation=Counter(); adjacency=defaultdict(set)
    low=[float('inf')]*3; high=[-float('inf')]*3
    volume=0.; overhang=0
    for a,b,c in triangles:
        u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
        normal=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        magnitude=math.sqrt(sum(n*n for n in normal))
        on_bed=max(a[2],b[2],c[2])<.001
        bridge=allow_bridge_z is not None and all(abs(p[2]-allow_bridge_z)<.001 for p in (a,b,c))
        if magnitude>1e-12 and not on_bed and not bridge and -normal[2]/magnitude>math.sin(math.pi/4)+.001:
            overhang+=1
        vertices=[tuple(round(v,6) for v in p) for p in (a,b,c)]
        for i in range(3):
            p,q=vertices[i],vertices[(i+1)%3]
            if p==q:continue
            edges[tuple(sorted((p,q)))]+=1
            orientation[tuple(sorted((p,q)))]+=1 if p<q else -1
            adjacency[p].add(q);adjacency[q].add(p)
        volume+=(a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6
        for p in (a,b,c):
            for i in range(3):low[i]=min(low[i],p[i]);high[i]=max(high[i],p[i])
    bad=sum(n!=2 for n in edges.values())
    inconsistent=sum(n!=0 for n in orientation.values())
    components=0;seen=set()
    for v in adjacency:
        if v in seen:continue
        components+=1;pending=[v];seen.add(v)
        while pending:
            for q in adjacency[pending.pop()]:
                if q not in seen:seen.add(q);pending.append(q)
    if bad or inconsistent or components!=1 or abs(volume)<1e-5:
        raise ValueError(f'STL未通过实体检查：非闭合边{bad}，法向不一致{inconsistent}，连通体{components}。')
    return dict(triangles=len(triangles),watertight=True,components=components,
                volume_mm3=abs(volume),min_mm=low,max_mm=high,size_mm=[high[i]-low[i] for i in range(3)],
                overhang_triangles_above_45deg=overhang,
                standard_foot_bridge_z=allow_bridge_z),triangles

def sections(triangles,z):
    graph=defaultdict(set)
    for tri in triangles:
        hits=[]
        for a,b in zip(tri,tri[1:]+tri[:1]):
            if (a[2]<z)!=(b[2]<z):
                f=(z-a[2])/(b[2]-a[2])
                p=tuple(round(a[i]+f*(b[i]-a[i]),5) for i in range(2))
                if p not in hits:hits.append(p)
        if len(hits)==2 and hits[0]!=hits[1]:
            a,b=hits;graph[a].add(b);graph[b].add(a)
    if any(len(v)!=2 for v in graph.values()):
        raise ValueError(f'z={z:g}mm的STL截面不是闭环。')
    loops=[];seen=set()
    for start in graph:
        if start in seen:continue
        loop=[start];seen.add(start);prev=None;current=start
        while True:
            nxt=next(v for v in graph[current] if v!=prev)
            if nxt==start:break
            if nxt in seen:raise ValueError('截面路径自交。')
            loop.append(nxt);seen.add(nxt);prev,current=current,nxt
        loops.append(loop)
    return loops

def bounds(loop):
    return min(p[0] for p in loop),max(p[0] for p in loop),min(p[1] for p in loop),max(p[1] for p in loop)

def inside(point,poly):
    x,y=point;yes=False
    for a,b in zip(poly,poly[1:]+poly[:1]):
        if (a[1]>y)!=(b[1]>y) and x<a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1]):yes=not yes
    return yes

def check_baseplate(path,tile,height,max_x,max_y):
    info,triangles=mesh_info(path)
    if any(abs(a-b)>.003 for a,b in zip(info['size_mm'],[tile['printed_x'],tile['printed_y'],height])):
        raise ValueError('底板含榫头实际外形与分块计划不一致。')
    if info['size_mm'][0]>max_x+.003 or info['size_mm'][1]>max_y+.003 or info['overhang_triangles_above_45deg']:
        raise ValueError('底板超出打印范围或存在超过45°的悬垂。')
    samples=[]
    for z,width in ((height-4.85,36.3),(height-3.5,37.7),(height-1.5,39.),(height-.2,41.6)):
        loops=sections(triangles,z)
        for i in range(tile['nx']):
            for j in range(tile['ny']):
                p=(tile['first_x']+42*i,tile['first_y']+42*j)
                if sum(inside(p,q) for q in loops)%2:raise ValueError('网格中间未贯通。')
        regular=sum(abs(bounds(q)[1]-bounds(q)[0]-width)<.01 and abs(bounds(q)[3]-bounds(q)[2]-width)<.01 for q in loops)
        samples.append(dict(z=z,standard_apertures=regular,all_cell_centers_open=True))
    info['sections']=samples
    return info

def check_bin(path,p):
    info,triangles=mesh_info(path,allow_bridge_z=4.75)
    if any(abs(a-b)>.003 for a,b in zip(info['size_mm'],[p['width'],p['depth'],p['height']])):
        raise ValueError('收纳盒实际外形与输入不一致。')
    if info['overhang_triangles_above_45deg']:
        raise ValueError('收纳盒存在标准底脚之外超过45°的悬垂。')
    center=(p['width']/2,p['depth']/2)
    floor=sections(triangles,p['floor_z']-.2)
    cavity=sections(triangles,p['floor_z']+.02)
    if len(floor)!=1 or sum(inside(center,q) for q in floor)%2!=1:
        raise ValueError('收纳盒底面未封闭。')
    if len(cavity)!=2 or sum(inside(center,q) for q in cavity)%2:
        raise ValueError('收纳盒内部未形成单一空腔。')
    cfg=p['settings'];foot_count=int(cfg['columns'])*int(cfg['rows'])
    for z,w in ((.4,36.4),(1.5,37.2),(3.5,39.)):
        loops=sections(triangles,z)
        if len(loops)!=foot_count or any(abs(bounds(q)[1]-bounds(q)[0]-w)>.01 or abs(bounds(q)[3]-bounds(q)[2]-w)>.01 for q in loops):
            raise ValueError('收纳盒Gridfinity底脚数量或剖面尺寸错误。')
    for dz,shrink in ((.35,4.5),(1.5,3.8),(3.5,1.8)):
        loops=sections(triangles,p['nominal_height']+dz)
        if len(loops)!=2 or not any(abs((bounds(q)[1]-bounds(q)[0])-(p['width']-shrink))<.01 and abs((bounds(q)[3]-bounds(q)[2])-(p['depth']-shrink))<.01 for q in loops):
            raise ValueError('收纳盒堆叠边剖面错误。')
    lip_loops=sections(triangles,p['nominal_height']+3.4)
    nubs=[]
    for i in range(1,int(cfg['columns'])):
        nubs.extend([(42*i-.25,2.5),(42*i-.25,p['depth']-2.5)])
    for j in range(1,int(cfg['rows'])):
        nubs.extend([(2.5,42*j-.25),(p['width']-2.5,42*j-.25)])
    if not all(sum(inside(q,loop) for loop in lip_loops)%2 for q in nubs):
        raise ValueError('收纳盒格间堆叠定位凸起缺失。')
    cached={}
    for window in p['windows']:
        z=window['z']+.013
        if z not in cached:cached[z]=sections(triangles,z)
        axis=window['axis'];side=window['side'];wall=cfg['wall']
        point=(window['center'],wall/2 if side==0 else p['depth']-wall/2) if axis=='x' else (wall/2 if side==0 else p['width']-wall/2,window['center'])
        if sum(inside(point,q) for q in cached[z])%2:
            raise ValueError('侧壁镂空孔未贯通。')
    info.update(floor_verified=True,hollow_interior_verified=True,foot_count_verified=foot_count,
                wall_openings_verified=len(p['windows']),stacking_lip_profile_verified=True,
                stacking_notches_verified=len(nubs))
    return info


def check_battery(path,p):
    info,triangles=mesh_info(path,allow_bridge_z=4.75)
    for a,b in zip(info['size_mm'],[p['width'],p['depth'],p['height']]):
        if abs(a-b)>.003:raise ValueError('电池盒实际外形与输入不一致。')
    if info['overhang_triangles_above_45deg']:
        raise ValueError('电池盒存在标准底脚之外的悬垂。')
    z=p['floor_z']+p['hole_depth']/2
    loops=sections(triangles,z)
    if len(loops)!=p['count']+1:raise ValueError('实际电池孔数与计算容量不一致。')
    matched=set()
    for x,y,r in p['positions']:
        a,b=(p['hole_b'],p['hole_a']) if r==90 else (p['hole_a'],p['hole_b'])
        options=[]
        for i,q in enumerate(loops):
            x0,x1,y0,y1=bounds(q)
            if i not in matched and abs((x0+x1)/2-x)<.01 and abs((y0+y1)/2-y)<.01 and abs(x1-x0-a)<.01 and abs(y1-y0-b)<.01:
                options.append(i)
        if not options:raise ValueError('电池孔位置、孔径或旋转方向与计算不一致。')
        matched.add(options[0])
    if len(sections(triangles,p['floor_z']-.4))!=1:raise ValueError('电池孔下方底面未封闭。')
    hollow_z=(p['seat_top']+p['nominal_height']-2)/2
    hollow=sections(triangles,hollow_z)
    if len(hollow)!=2 or sum(inside((p['width']/2,p['depth']/2),q) for q in hollow)%2:
        raise ValueError('定位底块上方未形成连通空腔。')
    cfg=p['settings'];foot_count=int(cfg['columns'])*int(cfg['rows'])
    for z,w in ((.4,36.4),(1.5,37.2),(3.5,39.)):
        loops=sections(triangles,z)
        if len(loops)!=foot_count:raise ValueError('Gridfinity底脚数量错误。')
        if any(abs(bounds(q)[1]-bounds(q)[0]-w)>.01 or abs(bounds(q)[3]-bounds(q)[2]-w)>.01 for q in loops):
            raise ValueError('Gridfinity底脚剖面尺寸错误。')
    for dz,shrink in ((.35,4.5),(1.5,3.8),(3.5,1.8)):
        loops=sections(triangles,p['nominal_height']+dz)
        if len(loops)!=2:raise ValueError('堆叠边没有形成连通开口。')
        boxes=[bounds(q) for q in loops]
        if not any(abs((x1-x0)-(p['width']-shrink))<.01 and abs((y1-y0)-(p['depth']-shrink))<.01 for x0,x1,y0,y1 in boxes):
            raise ValueError('堆叠边剖面尺寸错误。')
    lip_loops=sections(triangles,p['nominal_height']+3.4)
    nubs=[]
    for i in range(1,int(cfg['columns'])):
        nubs.extend([(42*i-.25,2.5),(42*i-.25,p['depth']-2.5)])
    for j in range(1,int(cfg['rows'])):
        nubs.extend([(2.5,42*j-.25),(p['width']-2.5,42*j-.25)])
    if not all(sum(inside(q,loop) for loop in lip_loops)%2 for q in nubs):
        raise ValueError('格间堆叠定位凸起缺失。')
    info.update(capacity_verified=p['count'],pocket_floor_verified=True,foot_count_verified=foot_count,
                hollow_upper_verified=True,nominal_height=p['nominal_height'],stacking_lip_height=3.8,
                stacking_lip_profile_verified=True,stacking_notches_verified=len(nubs))
    return info
