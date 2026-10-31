restart;
m:=1: k:=1: x0:=1:
ode:= m*diff(x(t), t,t)+b*diff(x(t),t)+k*x(t)=0;
ics:= x(0)=x0, D(x)(0)=0;
assign(dsolve(subs([x=overdamped, b=4], {ode, ics})));
assign(dsolve(subs([x=critdamped, b=2], {ode, ics})));
assign(dsolve(subs([x=underdamped,b=1], {ode, ics})));
