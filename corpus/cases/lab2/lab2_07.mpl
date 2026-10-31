# SOURCE: lab2 block 07 (para 136) - L11 toboggan picks up Steve (perfectly inelastic)
restart: mb:=70: mg:=60: mt:=40:
mgt:=mg+mt:
h1:=3: g:=9.81:
v2:=sqrt(2*g*h1);
vt:=solve((mgt+mb)*v2=mgt*vt+mb*(vt-3));
ms:=100:
solve(mgt*vt=(mgt+ms)*vtf);
