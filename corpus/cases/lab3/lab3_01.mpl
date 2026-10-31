# SOURCE: lab3 block 01 (para 15) - L15 terminal velocity symbolic
restart: Vol:=4/3*Pi*r^3: A:=Pi*r^2:
m:=rho_b*Vol;
Fd:=1/2*rho_a*CD*A*v^2;
Fg:=m*g;
solve(Fd=Fg,v);
