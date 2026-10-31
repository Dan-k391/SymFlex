# SOURCE: lab4 block 21 (para 520) - L25 P25.1 c) velocities by differentiation
# DEPENDS: lab4_19, lab4_20
restart: r:=.25: L:=1: theta:=2*Pi*t:
phi:=arcsin(r/L*sin(theta));
plot([theta, phi], t=0..1);
xB:=r*cos(theta); yB:=r*sin(theta); xC:=r*cos(theta)+L*cos(phi);
plot([[xB,yB,t=0..1],[xC,0,t=0..1]]);
vBx:=diff(xB,t); vBy:=diff(yB,t); vCx:=diff(xC,t);
