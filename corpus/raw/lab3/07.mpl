> restart: m:=5: rho:=10: CD:=.8: A:=2: with(LinearAlgebra):
vvec:=<3,-2>: v:=sqrt(vvec.vvec); vhat:=vvec/v;
.5*rho*CD*A;
FD:=.5*rho*CD*A*v^2*(-vhat); evalf(%);
