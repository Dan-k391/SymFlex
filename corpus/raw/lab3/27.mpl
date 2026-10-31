> restart: m:=1: b:=1: k:=10:
omega0:=evalf(sqrt(k/m));
zeta:=solve(2*zeta*omega0=b/m, zeta);
omegad:=omega0*sqrt(1-zeta^2);
