# SOURCE: lab4 block 13 (para 355) - Gear point P: vector method (3d)
restart: r1:=.05: r2:=.25: alpha1:=1: alpha:=alpha1*r1/r2;
omega:=0+int(alpha,t=0..t); theta:=-Pi/2+int(omega,t=0..t);
with(VectorCalculus): BasisFormat(false):
rO:=<0,r2,0>: rOP:=r2*<cos(theta),sin(theta),0>: rP:=rO+rOP;
omegavec:=<0,0,omega>: alphavec:=<0,0,alpha>:
vO:=<0,0,0>: vP:=vO+omegavec &x rOP;
aO:=<0,0,0>: aP:=aO+alphavec &x rOP - omega^2*rOP;
