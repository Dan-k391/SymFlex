restart;
ode:= m*diff(x(t), t,t)+b*diff(x(t),t)+k*x(t)=F0*sin(omega*t):
dsolve(ode);
