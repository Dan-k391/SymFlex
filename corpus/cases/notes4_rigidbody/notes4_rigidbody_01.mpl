# SOURCE: notes4_rigidbody block 01 (page 4) - example 16.5 piston thetadot via cosine law
# NOTE: output matches document (doc typesets thetadot as s*sdot/(2*sin(theta)); cmaple prints 1/2*s*sdot/sin(theta))
restart:
OA:=2: OB:=1: ang:=Pi/6:
coslaw:=sqrt(OA^2+OB^2-2*OA*OB*cos(theta)):
s30:=evalf(subs(theta=ang, coslaw));
thetadot:=solve(2*s*sdot=2*OA*OB*sin(theta)*thetadot, thetadot);
thetadot30:=evalf(subs([theta=ang, s=s30, sdot=.5], thetadot));
