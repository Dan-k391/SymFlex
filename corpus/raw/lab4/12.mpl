> restart: r1:=.05: r2:=.25: alpha1:=1: alpha:=alpha1*r1/r2;
omega:=0+int(alpha,t=0..t); theta:=-Pi/2+int(omega,t=0..t);
with(VectorCalculus): BasisFormat(false):
rO:=<0,r2>: rOP:=r2*<cos(theta),sin(theta)>: rP:=rO+rOP;
vP:=diff(rP,t); aP:=diff(vP,t);
