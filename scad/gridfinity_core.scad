// Gridfinity interface: 42mm pitch, 41.5mm feet. Dimensions in mm.
// Profiles checked against gridfinity.xyz and Gridfinity Rebuilt.
function rr_points(w,h,r,n=16) = [for (k=[0:3], i=[0:n])
    let(a=k*90+i*90/n, cx=(k==0 || k==3)?w/2-r:-w/2+r,
        cy=k<2?h/2-r:-h/2+r) [cx+r*cos(a),cy+r*sin(a)]];

module rr(w,h,r) { polygon(rr_points(w,h,r)); }

// Explicit matching rings retain the exact straight and 45-degree profile bands.
module rr_loft(layers) {
    n=len(rr_points(layers[0][1],layers[0][2],layers[0][3]));
    points=[for (s=layers, p=rr_points(s[1],s[2],s[3])) [p[0],p[1],s[0]]];
    faces=concat([[for(i=[n-1:-1:0]) i]],
        [for(k=[0:len(layers)-2],i=[0:n-1],t=[0:1])
            t==0?[k*n+i,k*n+(i+1)%n,(k+1)*n+(i+1)%n]:
                 [k*n+i,(k+1)*n+(i+1)%n,(k+1)*n+i]],
        [[for(i=[0:n-1]) (len(layers)-1)*n+i]]);
    polyhedron(points=points,faces=faces,convexity=10);
}

module socket_cutter(height=5) {
    assert(height>=5);
    rr_loft([[-.02,36.3,36.3,1.15], [height-4.65,36.3,36.3,1.15],
        [height-3.95,37.7,37.7,1.85], [height-2.15,37.7,37.7,1.85],
        [height,42,42,4], [height+.02,42.04,42.04,4.02]]);
}

module gridfinity_foot() {
    rr_loft([[0,35.6,35.6,.8],[.8,37.2,37.2,1.6],
        [2.6,37.2,37.2,1.6],[4.75,41.5,41.5,3.75]]);
}

module gridfinity_solid(columns,rows,height) {
    assert(columns>=1 && rows>=1 && height>=7);
    w=42*columns-.5; d=42*rows-.5;
    union() {
        for(i=[0:columns-1],j=[0:rows-1])
            translate([20.75+42*i,20.75+42*j,0]) gridfinity_foot();
        translate([w/2,d/2,4.75]) linear_extrude(height=height-4.75)
            rr(w,d,3.75);
    }
}

// The female stacking profile is separate from the baseplate profile.
module stacking_socket_cutter() {
    rr_loft([[-.02,36.3,36.3,1.15],[0,36.3,36.3,1.15],
        [.7,37.7,37.7,1.85],[2.5,37.7,37.7,1.85],
        [3.8,40.3,40.3,3.15],[3.82,40.34,40.34,3.17]]);
}

// Local edge nubs at 42mm joins. The central cavity stays completely open.
module stacking_notches(columns,rows,nominal_height) {
    w=42*columns-.5;d=42*rows-.5;
    difference() {
        union() {
            if(columns>1)for(i=[1:columns-1]) {
                translate([42*i-.25-4,0,nominal_height])cube([8,2.6,3.8]);
                translate([42*i-.25-4,d-2.6,nominal_height])cube([8,2.6,3.8]);
            }
            if(rows>1)for(j=[1:rows-1]) {
                translate([0,42*j-.25-4,nominal_height])cube([2.6,8,3.8]);
                translate([w-2.6,42*j-.25-4,nominal_height])cube([2.6,8,3.8]);
            }
        }
        for(i=[0:columns-1],j=[0:rows-1])
            translate([20.75+42*i,20.75+42*j,nominal_height])stacking_socket_cutter();
    }
}
