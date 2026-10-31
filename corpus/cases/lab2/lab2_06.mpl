# SOURCE: lab2 block 06 (para 119) - L11 toboggan, Barry jumps off
restart: mb:=70: mg:=60: mt:=40:
mgt:=mg+mt:
h1:=3: g:=9.81:
v2:=sqrt(2*g*h1);
vt:=solve((mgt+mb)*v2=mgt*vt+mb*(vt-3));
