# SOURCE: lab1 block 21 (para 503) - b & c)
# DEPENDS: lab1_20
restart: with(VectorCalculus): BasisFormat(false):
rho:=2: m:=1e-3: q1q2:=-3*3e-9: ke:=8.99e9:
FC:=abs(ke*q1q2/rho^2);
an:=FC/m; at:=0; v:=sqrt(rho*an);
omega:=v/rho:
rvec:=rho*<cos(omega*t),sin(omega*t)>;
vvec:=diff(rvec,t); avec:=diff(vvec,t);
ut:=Normalize(vvec); atvec:=(avec.ut)*ut; anvec:=avec-atvec; un:=Normalize(anvec);
#ub is in the +z-direction
