> restart:
OA:=2: OB:=1: ang:=Pi/6:
coslaw:=sqrt(OA^2+OB^2-2*OA*OB*cos(theta)):
s30:=evalf(subs(theta=ang, coslaw));
thetadot:=solve(2*s*sdot=2*OA*OB*sin(theta)*thetadot, thetadot);
thetadot30:=evalf(subs([theta=ang, s=s30, sdot=.5], thetadot));
