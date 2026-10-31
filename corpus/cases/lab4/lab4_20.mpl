# SOURCE: lab4 block 20 (para 513) - L25 P25.1 b) trajectories of B & C
# DEPENDS: lab4_19
restart: r:=.25: L:=1: theta:=2*Pi*t:
phi:=arcsin(r/L*sin(theta));
plot([theta, phi], t=0..1);
xB:=r*cos(theta); yB:=r*sin(theta); xC:=r*cos(theta)+L*cos(phi);
plot([[xB,yB,t=0..1],[xC,0,t=0..1]]);
