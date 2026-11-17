"""Lightweight UI for the three independent OpenSCAD generators."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import ttk,messagebox

from gridfinity import baseplate as baseplate_model,battery as battery_model,bin as bin_model
from gridfinity.shared import find_openscad

Settings=baseplate_model.Settings
plan=baseplate_model.plan
BatterySettings=battery_model.Settings
PRESETS=battery_model.PRESETS
plan_battery=battery_model.plan

ROOT=Path(__file__).parent
MODELS={'baseplate':baseplate_model,'battery':battery_model,'bin':bin_model}


class Tab:
    def __init__(self,app,notebook,title,kind):
        self.app=app;self.kind=kind;self.values={};self.entries={};self.output=None;self.source=None
        self.frame=ttk.Frame(notebook,padding=15);notebook.add(self.frame,text=title)
        self.left=ttk.Frame(self.frame);self.left.pack(side='left',fill='y')
        scroll_area=ttk.Frame(self.left);scroll_area.pack(side='top',fill='both',expand=True)
        scroll=tk.Canvas(scroll_area,width=345,bg='#edf2f5',highlightthickness=0)
        scrollbar=ttk.Scrollbar(scroll_area,orient='vertical',command=scroll.yview)
        scroll.configure(yscrollcommand=scrollbar.set)
        scroll.pack(side='left',fill='both',expand=True);scrollbar.pack(side='left',fill='y')
        self.form=ttk.Frame(scroll,padding=(0,0,12,10))
        scroll.create_window((0,0),window=self.form,anchor='nw')
        self.form.bind('<Configure>',lambda e:scroll.configure(scrollregion=scroll.bbox('all')))
        self.row=0
        right=ttk.Frame(self.frame,padding=(18,0,0,0));right.pack(side='left',fill='both',expand=True)
        self.summary=tk.StringVar()
        ttk.Label(right,textvariable=self.summary,wraplength=760,font=('Microsoft YaHei UI',11,'bold')).pack(anchor='w',pady=(0,10))
        self.canvas=tk.Canvas(right,bg='white',highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        self.caption=tk.StringVar()
        ttk.Label(right,textvariable=self.caption,wraplength=760,foreground='#526b77').pack(anchor='w',pady=8)
        self.log=tk.Text(right,height=7,font=('Microsoft YaHei UI',9),bg='#192731',fg='#d3eee4',
                         borderwidth=0,padx=12,pady=10,wrap='word')
        self.log.pack(fill='x')
        self.log.insert('end','就绪。\n')
        self.canvas.bind('<Configure>',lambda e:self.preview(True))

    def field(self,label,key,value,unit='mm',options=None):
        ttk.Label(self.form,text=label).grid(row=self.row,column=0,sticky='w',pady=5)
        var=tk.StringVar(value=str(value));self.values[key]=var
        widget=ttk.Combobox(self.form,textvariable=var,values=options,state='readonly',width=17) if options else ttk.Entry(self.form,textvariable=var,width=13)
        widget.grid(row=self.row,column=1,sticky='e',padx=(12,3))
        if unit:ttk.Label(self.form,text=unit).grid(row=self.row,column=2,sticky='w')
        self.entries[key]=widget;self.row+=1
        return widget

    def parameter(self,key,value):
        module=MODELS[self.kind]
        spec=next(p for p in module.PARAMETERS if p.name==key)
        if spec.type in (int,float):value=f'{float(value):g}'
        return self.field(spec.label,key,value,spec.unit)

    def note(self,text):
        ttk.Label(self.form,text=text,wraplength=320,foreground='#526b77').grid(row=self.row,column=0,columnspan=3,sticky='w',pady=9)
        self.row+=1

    def button(self,text,command,requires_output=False):
        button=ttk.Button(self.button_form,text=text,command=command)
        button.grid(row=self.button_row,column=0,sticky='ew',pady=3);self.button_row+=1
        if requires_output:
            button.configure(state='disabled');self.open_buttons.append(button)
        else:self.app.work_buttons.append(button)
        return button

    def actions(self):
        self.button_form=ttk.Frame(self.left,padding=(0,8,12,0))
        self.button_form.pack(side='bottom',fill='x')
        self.button_form.columnconfigure(0,weight=1);self.button_row=0
        self.open_buttons=[]
        self.button('更新预览',self.preview)
        self.button('生成 SCAD + STL',self.start)
        self.button('仅生成 SCAD',lambda:self.start(source_only=True))
        self.button('OpenSCAD 3D 预览',self.open_model,True)
        self.button('打开输出文件夹',self.open_folder,True)
        try:
            previous=json.loads((ROOT/'scad_outputs.json').read_text(encoding='utf-8')).get(self.kind)
            if previous and Path(previous['source']).is_file():
                self.output=Path(previous['folder']);self.source=Path(previous['source'])
                for b in self.open_buttons:b.configure(state='normal')
        except (OSError,ValueError,KeyError):pass

    def draw_setup(self,w,h):
        c=self.canvas;c.delete('all')
        cw=max(c.winfo_width(),500);ch=max(c.winfo_height(),350)
        scale=min((cw-55)/w,(ch-55)/h)
        return c,scale,(cw-w*scale)/2,(ch-h*scale)/2

    def start(self,source_only=False):
        if self.app.busy:return
        try:
            cfg=self.settings()
            MODELS[self.kind].plan(cfg)
            if not source_only:find_openscad()
        except (ValueError,RuntimeError) as exc:
            messagebox.showerror('参数需要调整',str(exc));return
        (ROOT/('scad_'+self.kind+'_settings.json')).write_text(json.dumps(asdict(cfg),indent=2,ensure_ascii=False),encoding='utf-8')
        self.app.busy=True
        for b in self.app.work_buttons:b.configure(state='disabled')
        self.log.insert('end','\n开始生成…\n');self.log.see('end')
        def worker():
            try:
                logger=lambda msg:self.app.events.put((self,'log',msg))
                module=MODELS[self.kind]
                result=module.generate(cfg,source_only=source_only,log=logger)
                self.app.events.put((self,'done',result))
            except Exception as exc:
                import traceback
                (ROOT/'scad_last_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
                self.app.events.put((self,'error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def open_model(self):
        if self.source:
            subprocess.Popen([str(find_openscad(gui=True)),str(self.source)],cwd=str(self.source.parent))

    def open_folder(self):
        if self.output:os.startfile(self.output)


class PlateTab(Tab):
    def __init__(self,app,notebook):
        super().__init__(app,notebook,'  镂空拼接底板  ','baseplate')
        cfg=Settings()
        try:cfg=Settings(**json.loads((ROOT/'scad_baseplate_settings.json').read_text(encoding='utf-8')))
        except (OSError,ValueError,TypeError):pass
        for spec in baseplate_model.PARAMETERS:self.parameter(spec.name,getattr(cfg,spec.name))
        self.actions()
        self.preview()

    def settings(self):return baseplate_model.settings_from({k:v.get() for k,v in self.values.items()})

    def preview(self,silent=False):
        try:cfg=self.settings();p=plan(cfg)
        except ValueError as exc:
            if not silent:messagebox.showerror('参数需要调整',str(exc))
            return
        self.summary.set(f'{p["nx"]} × {p["ny"]} Grid · {len(p["tiles"])}块（{p["columns"]}列 × {p["rows"]}行）\n'
                         f'拼好 {p["length"]:g} × {p["width"]:g} × {cfg.height:g} mm')
        self.caption.set(f'打印上限 {cfg.max_x:g} × {cfg.max_y:g} mm · 接缝 {cfg.seam_gap:g} mm · 榫槽间隙 {cfg.joint_clearance:g} mm')
        c,s,ox,oy=self.draw_setup(p['length'],p['width'])
        colors=['#c9e4e9','#d3e6cc','#f0dec5','#dcd4ec']
        for t in p['tiles']:
            x=ox+t['x']*s;y=oy+(p['width']-t['y']-t['width'])*s
            x1=x+t['length']*s;y1=y+t['width']*s
            c.create_rectangle(x,y,x1,y1,fill=colors[(t['row']+t['col'])%4],outline='#526b77')
            for i in range(t['nx']):
                for j in range(t['ny']):
                    cx=ox+(t['x']+t['first_x']+42*i)*s;cy=oy+(p['width']-t['y']-t['first_y']-42*j)*s;r=18.15*s
                    c.create_rectangle(cx-r,cy-r,cx+r,cy+r,fill='white',outline='#a4b4b8')
            c.create_text((x+x1)/2,(y+y1)/2,text=f'{t["id"]}\n{t["printed_x"]:.1f} × {t["printed_y"]:.1f}',
                          font=('Segoe UI',10,'bold'),fill='#294551')


class BatteryTab(Tab):
    def __init__(self,app,notebook):
        super().__init__(app,notebook,'  电池收纳盒  ','battery')
        cfg=BatterySettings()
        try:cfg=BatterySettings(**json.loads((ROOT/'scad_battery_settings.json').read_text(encoding='utf-8')))
        except (OSError,ValueError,TypeError):pass
        self.parameter('columns',cfg.columns)
        self.parameter('rows',cfg.rows)
        self.labels={v['label']:k for k,v in PRESETS.items()};self.labels['自定义']='Custom'
        label=next(k for k,v in self.labels.items() if v==cfg.battery_type)
        preset=self.field('电池类型','battery_type',label,'',list(self.labels))
        preset.bind('<<ComboboxSelected>>',self.choose_preset)
        packing=self.field('排列方式','packing','密排（自动择优）' if cfg.packing=='dense' else '规则行列','',
                           ['密排（自动择优）','规则行列'])
        packing.bind('<<ComboboxSelected>>',lambda e:self.preview(True))
        self.field('自定义形状','custom_shape','圆柱 / 纽扣' if cfg.custom_shape=='round' else '方形','',['圆柱 / 纽扣','方形'])
        for name in ('custom_a','custom_b','custom_height','clearance','web','wall','seat_depth','top_clearance'):
            self.parameter(name,getattr(cfg,name))
        self.align=tk.BooleanVar(value=cfg.align_height)
        ttk.Checkbutton(self.form,text='盒高向上取整为 7 mm 单位',variable=self.align,command=lambda:self.preview(True)).grid(
            row=self.row,column=0,columnspan=3,sticky='w',pady=7);self.row+=1
        self.parameter('max_x',cfg.max_x)
        self.parameter('max_y',cfg.max_y)
        self.actions()
        self.choose_preset()

    def choose_preset(self,event=None):
        key=self.labels[self.values['battery_type'].get()]
        for name in ('custom_shape','custom_a','custom_b','custom_height'):
            self.entries[name].configure(state='readonly' if key!='Custom' or name=='custom_shape' else 'normal')
        if key!='Custom':
            b=PRESETS[key]
            for name,value in [('custom_shape','圆柱 / 纽扣' if b['shape']=='round' else '方形'),
                               ('custom_a',b['a']),('custom_b',b['b']),('custom_height',b['height'])]:
                self.values[name].set(str(value))
        self.preview(True)

    def settings(self):
        values={k:v.get() for k,v in self.values.items()}
        values.update(battery_type=self.labels[values['battery_type']],
                      packing='dense' if values['packing'].startswith('密排') else 'regular',
                      custom_shape='round' if values['custom_shape'].startswith('圆柱') else 'rect',
                      align_height=self.align.get())
        return battery_model.settings_from(values)

    def preview(self,silent=False):
        if not hasattr(self,'align'):return
        try:cfg=self.settings();p=plan_battery(cfg)
        except ValueError as exc:
            if not silent:messagebox.showerror('参数需要调整',str(exc))
            return
        unit=f'（{p["nominal_height"]/7:g}U）' if cfg.align_height else ''
        self.summary.set(f'{int(cfg.columns)}列 × {int(cfg.rows)}行 Grid · 自动容纳 {p["count"]} 节\n'
                         f'{p["width"]:g} × {p["depth"]:g} mm · 本体 {p["nominal_height"]:g} mm {unit} + 堆叠边3.8 mm · 总高 {p["height"]:g} mm')
        self.caption.set(f'底部定位深 {p["hole_depth"]:g} mm · 上部可抓取 {p["grip_height"]:g} mm · '
                         f'电池顶距堆叠面 {p["head_clearance"]:g} mm')
        c,s,ox,oy=self.draw_setup(p['width'],p['depth'])
        c.create_rectangle(ox,oy,ox+p['width']*s,oy+p['depth']*s,fill='#b9dadd',outline='#476570')
        rim=2.6*s
        c.create_rectangle(ox+rim,oy+rim,ox+p['width']*s-rim,oy+p['depth']*s-rim,fill='#e8f1f1',outline='#476570')
        for i in range(1,int(cfg.columns)):
            x=ox+(42*i-.25)*s
            for yy in (oy,oy+p['depth']*s-rim):
                c.create_rectangle(x-1.1*s,yy,x+1.1*s,yy+rim,fill='#86b6bd',outline='')
        for j in range(1,int(cfg.rows)):
            y=oy+(p['depth']-(42*j-.25))*s
            for xx in (ox,ox+p['width']*s-rim):
                c.create_rectangle(xx,y-1.1*s,xx+rim,y+1.1*s,fill='#86b6bd',outline='')
        for i,(x,y,r) in enumerate(p['positions']):
            cx=ox+x*s;cy=oy+(p['depth']-y)*s
            if p['battery']['shape']=='round':
                radius=p['hole_a']/2*s
                c.create_oval(cx-radius,cy-radius,cx+radius,cy+radius,fill='#f9fbfc',outline='#476570',width=1)
            else:
                a,b=(p['hole_b'],p['hole_a']) if r==90 else (p['hole_a'],p['hole_b'])
                c.create_rectangle(cx-a/2*s,cy-b/2*s,cx+a/2*s,cy+b/2*s,fill='#f9fbfc',outline='#476570')
            if len(p['positions'])<=150:
                c.create_text(cx,cy,text=str(i+1),font=('Segoe UI',9),fill='#64818b')


class BinTab(Tab):
    def __init__(self,app,notebook):
        super().__init__(app,notebook,'  通用收纳盒  ','bin')
        cfg=bin_model.Settings()
        try:cfg=bin_model.settings_from(json.loads((ROOT/'scad_bin_settings.json').read_text(encoding='utf-8')))
        except (OSError,ValueError,TypeError):pass
        for name in ('columns','rows','height_u'):
            self.parameter(name,getattr(cfg,name))
        self.hollow=tk.BooleanVar(value=cfg.hollow)
        ttk.Checkbutton(self.form,text='侧壁菱形镂空',variable=self.hollow,command=self.toggle_hollow).grid(
            row=self.row,column=0,columnspan=3,sticky='w',pady=7);self.row+=1
        for name in ('wall','bottom','opening','rib','max_x','max_y','max_z'):
            self.parameter(name,getattr(cfg,name))
        self.actions()
        self.toggle_hollow()

    def settings(self):
        values={k:v.get() for k,v in self.values.items()}
        values['hollow']=self.hollow.get()
        return bin_model.settings_from(values)

    def toggle_hollow(self):
        for name in ('opening','rib'):
            self.entries[name].configure(state='normal' if self.hollow.get() else 'disabled')
        self.preview(True)

    def preview(self,silent=False):
        try:cfg=self.settings();p=bin_model.plan(cfg)
        except ValueError as exc:
            if not silent:messagebox.showerror('参数需要调整',str(exc))
            return
        mode='侧壁镂空' if cfg.hollow else '完整侧壁'
        self.summary.set(f'{cfg.columns} × {cfg.rows} Grid · {cfg.height_u}U · {mode}\n'
                         f'{p["width"]:g} × {p["depth"]:g} mm · 本体 {p["nominal_height"]:g} + 堆叠边 3.8 = 总高 {p["height"]:g} mm')
        self.caption.set(f'内部深度 {p["interior_depth"]:g} mm · 完整底面 · {p["opening_count"]} 个侧壁孔'
                         + ('（高度不足，自动保留完整侧壁）' if cfg.hollow and not p['opening_count'] else ''))
        c=self.canvas;c.delete('all')
        cw=max(c.winfo_width(),500);ch=max(c.winfo_height(),350)
        w,d,h=p['width'],p['depth'],p['height']
        extent_x=w+.38*d;extent_y=h+.23*d
        s=min((cw-65)/extent_x,(ch-65)/extent_y)
        ox=(cw-extent_x*s)/2;oy=(ch-extent_y*s)/2
        def project(x,y,z):return ox+(x+.38*y)*s,oy+(h-z+.23*(d-y))*s
        def face(points,fill,outline='#476570'):
            c.create_polygon(*[v for q in points for v in project(*q)],fill=fill,outline=outline)
        face([(0,d,0),(w,d,0),(w,d,h),(0,d,h)],'#b3d2d7')
        face([(0,0,0),(0,d,0),(0,d,h),(0,0,h)],'#c5dfe2')
        face([(0,0,p['floor_z']),(w,0,p['floor_z']),(w,d,p['floor_z']),(0,d,p['floor_z'])],'#e4eded')
        face([(0,0,0),(w,0,0),(w,0,h),(0,0,h)],'#85b8c0')
        face([(w,0,0),(w,d,0),(w,d,h),(w,0,h)],'#6da2ac')
        for q in p['windows']:
            if (q['axis']=='x' and q['side']==0) or (q['axis']=='y' and q['side']==1):
                u,z,r=q['center'],q['z'],q['size']/2
                vertices=[(u,z+r),(u+r,z),(u,z-r),(u-r,z)]
                points=[(a,0,b) if q['axis']=='x' else (w,a,b) for a,b in vertices]
                face(points,'#eaf2f2')
        # The ring is a top-view outline in this schematic; OpenSCAD shows the exact profile.
        wall=2.6
        for outer,inner in [([(0,0,h),(w,0,h)],[(wall,wall,h),(w-wall,wall,h)]),
                            ([(w,0,h),(w,d,h)],[(w-wall,wall,h),(w-wall,d-wall,h)]),
                            ([(w,d,h),(0,d,h)],[(w-wall,d-wall,h),(wall,d-wall,h)]),
                            ([(0,d,h),(0,0,h)],[(wall,d-wall,h),(wall,wall,h)])]:
            face(outer+list(reversed(inner)),'#d7eaec')


class App:
    def __init__(self,root):
        self.root=root;self.events=queue.Queue();self.busy=False;self.work_buttons=[]
        root.title('Gridfinity · OpenSCAD')
        root.geometry('1200x880');root.minsize(1050,760)
        style=ttk.Style();style.theme_use('clam')
        style.configure('TFrame',background='#edf2f5');style.configure('TLabel',background='#edf2f5',font=('Microsoft YaHei UI',10))
        style.configure('TButton',font=('Microsoft YaHei UI',10),padding=7)
        root.configure(bg='#edf2f5')
        self.notebook=ttk.Notebook(root);self.notebook.pack(fill='both',expand=True,padx=12,pady=(0,12))
        self.plate=PlateTab(self,self.notebook);self.battery=BatteryTab(self,self.notebook)
        self.bin=BinTab(self,self.notebook)
        self.notebook.select(self.bin.frame)
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.after(200,self.poll)

    def poll(self):
        while not self.events.empty():
            tab,kind,value=self.events.get()
            if kind=='done':
                tab.output,tab.source=value
                tab.log.insert('end',f'完成：{tab.output}\n')
                for b in tab.open_buttons:b.configure(state='normal')
                messagebox.showinfo('已生成',f'SCAD与打印文件已保存：\n{tab.output}')
            else:tab.log.insert('end',str(value)+'\n')
            tab.log.see('end')
            if kind in ('done','error'):
                self.busy=False
                for b in self.work_buttons:b.configure(state='normal')
            if kind=='error':messagebox.showerror('生成未完成',str(value))
        self.root.after(200,self.poll)

    def close(self):
        if self.busy:messagebox.showinfo('正在生成','请等待当前导出完成后再关闭。')
        else:self.root.destroy()


if __name__=='__main__':
    root=tk.Tk();app=App(root);root.mainloop()
