# SOURCE: lab1 block 23 (para 520) - This isn't part of the question, but in class we also showed that , so...
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
#Check: what's utdot vs. un*v/rho?
diff(ut,t);
un*v/rho;
