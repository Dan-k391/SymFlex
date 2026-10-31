# SOURCE: lab1 block 02 (para 95) - First find by solving the equations above, then integrate to find posi...
restart: m:=40: P:=400: mu_k:=0.3: theta:=15*Pi/180:
g:=9.81: W:=m*g; ff:=mu_k*N:
solve([
P*cos(Pi/6)-ff-W*sin(theta)=m*ax,
P*sin(Pi/6)+N-W*cos(theta)=0]);
assign(%):
vx:=int(ax, t=0..t);
x:=int(vx, t=0..t);
x_at_3s:=subs(t=3, x);
