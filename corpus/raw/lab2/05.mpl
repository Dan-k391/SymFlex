> restart: g:=9.81: r:=4.5:
v1:=sqrt(2*g*r);
p1:=v1*M:
p2:=vS2*M+vJ2*M/2;
E1:=.5*M*v1^2: E2:=.5*M*vS2^2+.5*M/2*vJ2^2:
v2:=solve([p2=p1, E1=E2], [vS2, vJ2]);
#solve(.5*(1.5*M)*v2^2=(1.5*M)*g*h3, h3);
