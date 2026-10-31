> restart: Vol:=4/3*Pi*r^3: A:=Pi*r^2: g:=9.81: CD:=.47: rho_b:=8600: rho_a:=1.2: Vol:=4/3*Pi*r^3:
m:=rho_b*Vol;
Fd:=1/2*rho_a*CD*A*v^2;
Fg:=m*g;
solve(Fd=Fg,v);
