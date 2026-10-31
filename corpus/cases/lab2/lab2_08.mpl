# SOURCE: lab2 block 08 (para 147) - L11 toboggan elastic collision with Steve
# NOTE: final solve returns a set of sets; doc image41 lists {vtf=..., vsf=...} order, Maple 2024 cmaple prints {vsf=..., vtf=...} (set ordering only; values match)
restart: mb:=70: mg:=60: mt:=40:
mgt:=mg+mt:
h1:=3: g:=9.81:
v2:=sqrt(2*g*h1);
vt:=solve((mgt+mb)*v2=mgt*vt+mb*(vt-3));
ms:=100:
solve([mgt*vt=mgt*vtf+ms*vsf,
mgt*vt^2/2 = mgt*vtf^2/2 + ms*vsf^2/2]
);
