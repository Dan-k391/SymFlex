> restart: with(VectorCalculus): BasisFormat(false):
rho:=2: m:=1e-3: q1q2:=-3*3e-9: ke:=8.99e9:
FC:=abs(ke*q1q2/rho^2);
an:=FC/m; at:=0; v:=sqrt(rho*an);
