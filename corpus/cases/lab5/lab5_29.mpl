# SOURCE: lab5 block 29 (para 701) - L32 mod: v2 and KE
# DEPENDS: lab5_28
restart: R:=.2: m:=5: kG:=.15: IG:=m*kG^2:
h:=.03: v1:=3: w1:=v1/R: w2:=v2/R: w3:=v3/R:
HC1:=(R-h)*m*v1+IG*w1*0;
HC2:=R*m*v2+IG*w2;
v2:=solve(HC1=HC2);
T2:=1/2*(m*v2^2+IG*w2^2); T3:=1/2*(m*v3^2+IG*w3^2);
