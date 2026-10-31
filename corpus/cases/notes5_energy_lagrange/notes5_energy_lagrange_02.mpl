# SOURCE: notes5_energy_lagrange block 02 (pages 6-7) - eg 18.5 rod with slider blocks, work-energy at 45 deg
# NOTE: two end-of-line comments were wrapped in the PDF ("...from start / to 45deg", "...based on distance / travelled"); rejoined onto one line.
restart:
m:=10: g:=9.81: deltaH:=.4-(0.4/sqrt(2.)); #drop of G from start to 45deg
WG:=m*g*deltaH;
P:=50: WP:=50*.8/sqrt(2.); #work done by P based on distance travelled
vG:=.4*omega: #relating linear and angular velocity
IG:=1/12*m*.8^2;
T:=.5*(m*vG^2+IG*omega^2);
solve(T=WP+WG);
