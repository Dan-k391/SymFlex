# SOURCE: notes3_damped block 07 (page 14) - Example: Resonance - driven response at omega=2,10,50
# NOTE: Maple 2024 prints x(t) over common denominator 816*omega^4-161925*omega^2+8160000; doc shows 16/51*.../(160000-3175*omega^2+16*omega^4) form (equivalent). Plot (doc p15) shows 3 curves, resonant one grows to ~8.
restart;
w0:=10: x0:=1: zeta:=1/16:
ode:= diff(x(t), t,t)+2*zeta*w0*diff(x(t),t)+w0^2*x(t)=x0*w0^2*sin(omega*t):
ics:=x(0)=0, D(x)(0)=0;
dsolve({ode, ics});
assign(%):
plot([subs(omega=2, x(t)), subs(omega=10, x(t)), subs(omega=50, x(t))],
t=0..10);
