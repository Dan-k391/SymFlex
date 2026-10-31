# SOURCE: lab1 block 13 (para 374) - This is actually easier and doesn't rely on part b being correct:
restart: mc:=200: vc0:=.5: vc:=.5*(1+t*(sin(t))^2): g:=9.81:
W:=mc*g;
ac:=diff(vc,t); sc:=int(vc,t=0..t);
plot([sc, vc, ac],t=0..6, legend=['sc','vc','ac']);
