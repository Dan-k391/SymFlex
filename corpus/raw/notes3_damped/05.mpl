restart;
m:=1: k:=1: x0:=1:
w0:=m/k:
ode:= diff(x(t), t,t)+2*zeta*w0*diff(x(t),t)+w0^2*x(t)=0:
ics:= x(0)=x0, D(x)(0)=0:
assign(dsolve(subs([x=X1, zeta=1/4], {ode, ics})));
assign(dsolve(subs([x=X2, zeta=1/8], {ode, ics})));
assign(dsolve(subs([x=X3, zeta=1/16], {ode, ics})));
plot([X1(t), X2(t), X3(t), cos(w0*t), exp(-t/16)], t=0..20,
legend=[zeta=1/4,zeta=1/8,zeta=1/16, cosine, exp]);
