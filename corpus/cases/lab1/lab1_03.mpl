# SOURCE: lab1 block 03 (para 146) - b)
restart: m:=40: g:=9.81: mu_s:=.8: mu_k:=.3:
fsMax:=mu_s*N: W:=m*g;
ff:=fsMax:
FNetx:=P*cos(Pi/6)-W*sin(Pi/6)-ff;
FNety:=P*sin(Pi/6)-W*cos(Pi/6)+N;
solve([FNetx,FNety]); #just barely moving when net force = 0 and at max static friction
