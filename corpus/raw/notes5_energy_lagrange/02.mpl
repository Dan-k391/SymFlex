> restart:
m:=10: g:=9.81: deltaH:=.4-(0.4/sqrt(2.)); #drop of G from start
to 45deg
WG:=m*g*deltaH;
P:=50: WP:=50*.8/sqrt(2.); #work done by P based on distance
travelled
vG:=.4*omega: #relating linear and angular velocity
IG:=1/12*m*.8^2;
T:=.5*(m*vG^2+IG*omega^2);
solve(T=WP+WG);
