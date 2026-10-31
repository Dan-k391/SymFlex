# SOURCE: lab1 block 22 (para 516) - d) 95% of one circle would be 95%T, which is 95%*2*Pi/omega:
# DEPENDS: lab1_20, lab1_21
restart: with(VectorCalculus): BasisFormat(false):
rho:=2: m:=1e-3: q1q2:=-3*3e-9: ke:=8.99e9:
FC:=abs(ke*q1q2/rho^2);
an:=FC/m; at:=0; v:=sqrt(rho*an);
omega:=v/rho:
rvec:=rho*<cos(omega*t),sin(omega*t)>;
vvec:=diff(rvec,t); avec:=diff(vvec,t);
ut:=Normalize(vvec); atvec:=(avec.ut)*ut; anvec:=avec-atvec; un:=Normalize(anvec);
#ub is in the +z-direction
plot([rvec[1],rvec[2],t=0..0.95*2*Pi/omega]);
