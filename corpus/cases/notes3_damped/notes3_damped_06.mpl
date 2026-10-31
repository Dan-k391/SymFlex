# SOURCE: notes3_damped block 06 (page 11) - Check forced-oscillation general solution with dsolve
# NOTE: Maple 2024 names constants c__1, c__2; doc (older Maple) shows _C1, _C2. Steady-state term ordering also differs (equivalent).
restart;
ode:= m*diff(x(t), t,t)+b*diff(x(t),t)+k*x(t)=F0*sin(omega*t):
dsolve(ode);
