# SOURCE: lab1 block 07 (para 232) - This then leads to higher acceleration (4.25 m/s2) & shorter time (1.1...
restart: m:=40: g:=9.81: mu_s:=.8: mu_k:=.3: P:=468:
fsMax:=mu_s*N: W:=m*g;
ff:=mu_k*N:
FNetx:=P*1-W*sin(Pi/6)-ff;
FNety:=P*0-W*cos(Pi/6)+N;
solve([FNetx=m*ax,FNety]);
assign(%):
s:=int(int(ax, t=0..t), t=0..t);
solve(s=3);
