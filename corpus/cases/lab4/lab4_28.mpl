# SOURCE: lab4 block 28 (para 606) - L25 modification: vD by differentiation
restart: r:=.25: L:=1: theta:=2*Pi*t:
phi:=arcsin(r/L*sin(theta));
plot([theta, phi], t=0..1);
xB:=r*cos(theta); yB:=r*sin(theta); xC:=xB+L*cos(phi);
xD:=xB+L/2*cos(phi); yD:=yB-L/2*sin(phi);
#plot([[xB,yB,t=0..1],[xC,0,t=0..1], [xD,yD,t=0..1]]);
vDx:=diff(xD,t); vDy:=diff(yD,t);
