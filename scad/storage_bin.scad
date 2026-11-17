/* [Gridfinity] */
Grid_Columns = 2; // [1:1:30]
Grid_Rows = 2; // [1:1:30]
Height_U = 6; // [1:1:40]
/* [Walls and floor] */
Outer_Wall = 1.6;
Bottom_Thickness = 1.6;
Hollow_Walls = false;
Opening_Width = 12;
Rib_Width = 2.4;
/* [Print area] */
Print_Max_X = 240;
Print_Max_Y = 240;
Print_Max_Z = 256;
/* [Hidden] */
use <gridfinity_core.scad>
w=42*Grid_Columns-.5; d=42*Grid_Rows-.5;
nominal=Height_U*7;
floor_z=4.75+Bottom_Thickness;
taper_start=nominal-max(0,2.6-Outer_Wall);
floor_wall=max(Outer_Wall,2.6-(nominal-floor_z));
assert(Grid_Columns>=1 && Grid_Columns<=30 && Grid_Columns==floor(Grid_Columns));
assert(Grid_Rows>=1 && Grid_Rows<=30 && Grid_Rows==floor(Grid_Rows));
assert(Height_U>=1 && Height_U<=40 && Height_U==floor(Height_U));
assert(w<=Print_Max_X && d<=Print_Max_Y,"Bin exceeds print area");
assert(nominal+3.8<=Print_Max_Z,"Bin exceeds print height");
assert(Outer_Wall>=1.2 && Outer_Wall<=4 && Bottom_Thickness>=1.2 && Bottom_Thickness<=5);
assert(floor_z<=nominal-.4,"Increase height or reduce floor thickness");
assert(Opening_Width>=4 && Opening_Width<=24 && Rib_Width>=1.6 && Rib_Width<=8);

function windows(span)=let(corner=max(5,Outer_Wall+2),lo=floor_z+Rib_Width,
    hi=taper_start-Rib_Width,size=min(Opening_Width,hi-lo,span-2*corner),
    pitch=size+Rib_Width*sqrt(2))
    size<4-1e-8?[]:let(nx=floor((span-2*corner-size+1e-8)/pitch)+1,
        step=nx>1?pitch/2:pitch,nr=floor((hi-lo-size+1e-8)/step)+1,
        z0=(lo+hi-(nr-1)*step)/2)
    [for(j=[0:nr-1])let(n=nx>1?nx-j%2:1,x0=(span-(n-1)*pitch)/2)
        for(i=[0:n-1])[x0+i*pitch,z0+j*step,size]];
xwindows=Hollow_Walls?windows(w):[];
ywindows=Hollow_Walls?windows(d):[];
echo("GF_OPENINGS",2*(len(xwindows)+len(ywindows)),"GF_HEIGHT",nominal+3.8);

module cavity() {
    translate([w/2,d/2,0])rr_loft(concat(
        [[floor_z,w-2*floor_wall,d-2*floor_wall,max(.01,3.75-floor_wall)]],
        taper_start>floor_z+.001?[[taper_start,w-2*Outer_Wall,d-2*Outer_Wall,max(.01,3.75-Outer_Wall)]]:[],
        [[nominal,w-5.2,d-5.2,1.15],
         [nominal+.7,w-3.8,d-3.8,1.85],
         [nominal+2.5,w-3.8,d-3.8,1.85],
         [nominal+3.8,w-1.2,d-1.2,3.15],
         [nominal+3.82,w-1.16,d-1.16,3.17]]));
}

module diamond(size,thickness) {
    linear_extrude(height=thickness,center=true)
        polygon([[0,size/2],[size/2,0],[0,-size/2],[-size/2,0]]);
}

module wall_openings() {
    for(q=xwindows,side=[0,1])translate([q[0],side==0?Outer_Wall/2:d-Outer_Wall/2,q[1]])
        rotate([90,0,0])diamond(q[2],Outer_Wall+.1);
    for(q=ywindows,side=[0,1])translate([side==0?Outer_Wall/2:w-Outer_Wall/2,q[0],q[1]])
        rotate([90,0,90])diamond(q[2],Outer_Wall+.1);
}

color([.25,.6,.65])union() {
    difference() {
        gridfinity_solid(Grid_Columns,Grid_Rows,nominal+3.8);
        cavity();
        wall_openings();
    }
    stacking_notches(Grid_Columns,Grid_Rows,nominal);
}
