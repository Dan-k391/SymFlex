# SOURCE: lab4 block 19 (para 507) - L25 P25.1 a) phi(theta)
restart: r:=.25: L:=1: theta:=2*Pi*t:
phi:=arcsin(r/L*sin(theta));
plot([theta, phi], t=0..1);
