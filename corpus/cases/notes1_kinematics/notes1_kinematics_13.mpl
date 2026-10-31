# SOURCE: notes1_kinematics block 13 (page 22) - Differential Equation Solving
restart:
DE:=diff(x(t),t,t)+4*diff(x(t),t)+4*x(t)=sin(t);  #A differential equation
ICs:=x(0)=3, D(x)(0)=0; #Initial conditions x(0)=0 & x'(0) =0
dsolve([DE, ICs]);
assign(%):
plot(x(t),t=0..10);
t1:=fsolve(x(t)=0, t=3..5);
t2:=fsolve(x(t)=0, t=6..8);
v:=t->diff(x(t),t); #velocity
a:=t->diff(v(t),t); #acceleration
plot([x(t),v(t),a(t)], t=0..10, -3..3); #how do they all change in time?
