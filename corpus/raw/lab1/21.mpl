> omega:=v/rho:
rvec:=rho*<cos(omega*t),sin(omega*t)>;
vvec:=diff(rvec,t); avec:=diff(vvec,t);
ut:=Normalize(vvec); atvec:=(avec.ut)*ut; anvec:=avec-atvec; un:=Normalize(anvec);
#ub is in the +z-direction
