/* [Gridfinity footprint] */
Grid_Columns = 2; // [1:1:30]
Grid_Rows = 2; // [1:1:30]
/* [Battery] */
Battery_Type = "AA"; // [AA,AAA,C,D,LR9,LR44,CR2032,CR123A,18650,21700,9V,Custom]
Packing = "dense"; // [dense,regular]
Custom_Shape = "round"; // [round,rect]
Custom_A = 14.5;
Custom_B = 14.5;
Custom_Height = 50.5;
/* [Fit and height] */
Hole_Clearance = 0.25;
Outer_Wall = 2;
Hole_Web = 1.6;
Seat_Depth = 0; // 0 = approximately 30% battery height, rounded to 0.2mm
Top_Clearance = 0.5;
Align_Height_To_7 = true;
/* [Print area] */
Print_Max_X = 240;
Print_Max_Y = 240;
/* [Preview only] */
Show_Batteries = false;
Stacking_Notches = true;
/* [Hidden] */
$fn=96;
include <battery_presets.scad>
use <gridfinity_core.scad>

function best(v,i=1,b=0)=i>=len(v)?v[b]:best(v,i+1,len(v[i])>len(v[b])?i:b);
function centered(p,w,h)=len(p)==0?[]:
    let(xs=[for(q=p)q[0]],ys=[for(q=p)q[1]],
        dx=w/2-(min(xs)+max(xs))/2,dy=h/2-(min(ys)+max(ys))/2)
    [for(q=p)[q[0]+dx,q[1]+dy,q[2]]];
function nfit(span,size,gap)=max(0,floor((span+gap+1e-8)/(size+gap)));
function grid(w,h,d,wall,gap)=let(nx=nfit(w-2*wall,d,gap),ny=nfit(h-2*wall,d,gap))
    centered([if(nx>0 && ny>0) for(j=[0:ny-1],i=[0:nx-1])
        [wall+d/2+i*(d+gap),wall+d/2+j*(d+gap),0]],w,h);
function hexgrid(w,h,d,wall,gap,phase=0)=let(p=d+gap,dy=p*sqrt(3)/2,
    nr=max(0,floor((h-2*wall-d+1e-8)/dy)+1))
    centered([if(nr>0)for(j=[0:nr-1])let(shift=((j+phase)%2)*p/2,
        nc=max(0,floor((w-2*wall-d-shift+1e-8)/p)+1))
        if(nc>0)for(i=[0:nc-1]) [wall+d/2+shift+i*p,wall+d/2+j*dy,0]],w,h);
function transpose(p)=[for(q=p)[q[1],q[0],(q[2]+90)%180]];
function circle_fit(q,w,h,d,wall)=let(r=max(3.75-wall-d/2,0),
    x=max(abs(q[0]-w/2)-(w/2-wall-d/2-r),0),
    y=max(abs(q[1]-h/2)-(h/2-wall-d/2-r),0))r==0 || sqrt(x*x+y*y)<=r+1e-8;
function round_pack(w,h,d,wall,gap,mode)=let(v=mode=="regular"?[grid(w,h,d,wall,gap)]:
    [hexgrid(w,h,d,wall,gap,0),hexgrid(w,h,d,wall,gap,1),
     transpose(hexgrid(h,w,d,wall,gap,0)),transpose(hexgrid(h,w,d,wall,gap,1)),grid(w,h,d,wall,gap)])
    best([for(p=v)[for(q=p)if(circle_fit(q,w,h,d,wall))q]]);

function rect_rows(w,h,a,b,wall,gap,k0,k1)=let(total=k0*b+k1*a+max(0,k0+k1-1)*gap,y0=(h-total)/2)
    [if(k0+k1>0)for(j=[0:k0+k1-1])let(rot=j>=k0,ww=rot?b:a,hh=rot?a:b,
        nx=nfit(w-2*wall,ww,gap),
        yy=y0+(rot?k0*b+(j-k0)*a:j*b)+j*gap+hh/2,
        x0=(w-(nx*ww+(nx-1)*gap))/2+ww/2)
        if(nx>0)for(i=[0:nx-1])[x0+i*(ww+gap),yy,rot?90:0]];
function rect_options(w,h,a,b,wall,gap,mode)=let(m0=nfit(h-2*wall,b,gap),m1=nfit(h-2*wall,a,gap))
    mode=="regular"?[rect_rows(w,h,a,b,wall,gap,m0,0),rect_rows(w,h,a,b,wall,gap,0,m1)]:
    [for(k0=[0:m0],k1=[0:m1])if(k0+k1>0 && k0*b+k1*a+(k0+k1-1)*gap<=h-2*wall+1e-8)
        rect_rows(w,h,a,b,wall,gap,k0,k1)];
function rect_pack(w,h,a,b,wall,gap,mode)=best(concat(
    rect_options(w,h,a,b,wall,gap,mode),
    [for(p=rect_options(h,w,a,b,wall,gap,mode))transpose(p)]));
function preset(name,i=0)=i>=len(battery_presets)?["Custom",Custom_Shape=="round"?0:1,
    Custom_A,Custom_Shape=="round"?Custom_A:Custom_B,Custom_Height]:
    battery_presets[i][0]==name?battery_presets[i]:preset(name,i+1);

battery=preset(Battery_Type);
w=42*Grid_Columns-.5; d=42*Grid_Rows-.5;
ha=battery[2]+2*Hole_Clearance; hb=battery[3]+2*Hole_Clearance;
hole_depth=Seat_Depth>0?Seat_Depth:min(battery[4]-.4,max(.4,ceil((battery[4]*.3-1e-8)/.2)*.2));
nominal_height=Align_Height_To_7?ceil((7+battery[4]+Top_Clearance-1e-8)/7)*7:7+battery[4]+Top_Clearance;
body_height=nominal_height+3.8;
head_gap=nominal_height-7-battery[4];
pack_wall=max(Outer_Wall,2.6-head_gap-Hole_Clearance+.2);
positions=battery[1]==0?round_pack(w,d,ha,pack_wall,Hole_Web,Packing):
    rect_pack(w,d,ha,hb,pack_wall+max(0,(3.75-pack_wall-.5)*(1-1/sqrt(2))),Hole_Web,Packing);
floor_z=7;
seat_top=floor_z+hole_depth;
chamfer=min(.3,hole_depth/2);
assert(Grid_Columns>=1 && Grid_Columns==floor(Grid_Columns) && Grid_Rows>=1 && Grid_Rows==floor(Grid_Rows));
assert(w<=Print_Max_X && d<=Print_Max_Y,"Holder exceeds the printable rectangle");
assert(Hole_Clearance>=.1 && Hole_Web>=1.2 && Outer_Wall>=1.5);
assert(hole_depth>=.4 && hole_depth<=battery[4]-.4 && Top_Clearance>=.5 && len(positions)>0,"Battery does not fit or seat is too deep");
echo("GF_CAPACITY",len(positions),"GF_HEIGHT",body_height,"GF_HOLE_DEPTH",hole_depth);

module pocket(a,b,depth,shape) {
    if(shape==0) {
        cylinder(h=depth+.02,r=a/2);
        translate([0,0,depth-chamfer]) cylinder(h=chamfer+.02,r1=a/2,r2=a/2+chamfer+.02);
    } else {
        linear_extrude(height=depth+.02) rr(a,b,.5);
        translate([0,0,depth-chamfer])rr_loft([[0,a,b,.5],
            [chamfer+.02,a+2*(chamfer+.02),b+2*(chamfer+.02),.5+chamfer+.02]]);
    }
}

module battery_holder() {
    union() {
        difference() {
            gridfinity_solid(Grid_Columns,Grid_Rows,body_height);
            translate([w/2,d/2,0])rr_loft([
                [seat_top,w-2*Outer_Wall,d-2*Outer_Wall,max(.01,3.75-Outer_Wall)],
                [nominal_height-max(.01,2.6-Outer_Wall),w-2*Outer_Wall,d-2*Outer_Wall,max(.01,3.75-Outer_Wall)],
                [nominal_height,w-5.2,d-5.2,1.15],
                [nominal_height+.7,w-3.8,d-3.8,1.85],
                [nominal_height+2.5,w-3.8,d-3.8,1.85],
                [nominal_height+3.8,w-1.2,d-1.2,3.15],
                [nominal_height+3.82,w-1.16,d-1.16,3.17]]);
            // Keep entry chamfers out of the outer wall: no little roof above an edge pocket.
            intersection() {
                union()for(p=positions)translate([p[0],p[1],floor_z])rotate([0,0,p[2]])
                    pocket(ha,hb,hole_depth,battery[1]);
                translate([w/2,d/2,floor_z-.02])linear_extrude(height=hole_depth+.06)
                    rr(w-2*Outer_Wall,d-2*Outer_Wall,max(.01,3.75-Outer_Wall));
            }
        }
        if(Stacking_Notches)stacking_notches(Grid_Columns,Grid_Rows,nominal_height);
    }
}
color([.25,.6,.65])battery_holder();
if(Show_Batteries && $preview)for(p=positions)color([.65,.7,.73,.7])
    translate([p[0],p[1],floor_z])rotate([0,0,p[2]])
        if(battery[1]==0)cylinder(h=battery[4],d=battery[2]);
        else translate([-battery[2]/2,-battery[3]/2,0])cube([battery[2],battery[3],battery[4]]);
