# SOURCE: lab2 block 03 (para 54) - L10 universal gravitational potential, satellite speed at B
restart: G:=6.674e-11: M:=5.976e24: vA:=40e6/3600;
UA:=-G*M*m/20e6; UB:=-G*M*m/80e6;
KEA:=.5*m*vA^2: KEB:=solve(KEA+UA=KEB+UB, KEB);
vB:=simplify(sqrt(2*KEB/m)); vB_metres_per_hour:=vB*3600;
