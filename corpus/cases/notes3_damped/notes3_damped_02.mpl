# SOURCE: notes3_damped block 02 (page 6) - Demonstrate that it worked (show assigned solutions)
# NOTE: doc shows critdamped as e^(-t)+e^(-t)*t; Maple 2024 prints exp(-t)*(1+t) (equivalent)
# DEPENDS: notes3_damped_01
# NOTE: x(t) stays unevaluated because dsolve results were assigned to overdamped/critdamped/underdamped via subs
restart;
m:=1: k:=1: x0:=1:
ode:= m*diff(x(t), t,t)+b*diff(x(t),t)+k*x(t)=0;
ics:= x(0)=x0, D(x)(0)=0;
assign(dsolve(subs([x=overdamped, b=4], {ode, ics})));
assign(dsolve(subs([x=critdamped, b=2], {ode, ics})));
assign(dsolve(subs([x=underdamped,b=1], {ode, ics})));
overdamped(t);
critdamped(t);
underdamped(t);
x(t);
