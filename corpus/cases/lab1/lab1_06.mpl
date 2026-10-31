# SOURCE: lab1 block 06 (para 218) - In this situation we can modify the previous solution by changing the ...
restart: m:=40: g:=9.81: mu_s:=.8: mu_k:=.3:
fsMax:=mu_s*N: W:=m*g;
ff:=fsMax:
FNetx:=P*1-W*sin(Pi/6)-ff;
FNety:=P*0-W*cos(Pi/6)+N;
solve([FNetx,FNety]); #just barely moving when net force = 0 and at max static friction
