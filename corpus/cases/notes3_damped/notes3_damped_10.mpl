# SOURCE: notes3_damped block 10 (page 23) - Quality factor: exact Q from FWHM vs 1/(2 zeta)
restart:
f:=omegar/((omegar^2-1)^2+(2*zeta*omegar)^2);
wmax:=solve(diff(f, omegar), omegar)[1];
f_max:=subs(omegar=wmax, f); simplify(%);
zeta:=.01: fac:=1.2:
whalf:=fsolve(f=f_max/2, omegar=wmax..wmax*fac) -
fsolve(f=f_max/2, omegar=wmax/fac..wmax);
Qexpr:=wmax/whalf;
Qapprox:=1/(2*zeta);
relErr:=(Qapprox-Qexpr)/Qapprox;
