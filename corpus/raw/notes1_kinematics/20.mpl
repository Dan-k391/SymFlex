 restart:
g:=9.81: r:=0.1: muk:=0.3:
DE:=diff(q(t),t,t)=muk*((diff(q(t),t))^2+g/r*cos(q(t))-g/r*sin(q(t)));
ICs:=[q(0)=Pi/2, D(q)(0)=0];
dsolve({DE, op(ICs)});
