# SOURCE: notes1_kinematics block 24 (page 51) - Coefficient of restitution: rewrite eliminating v
# NOTE: doc final output (boxed): (-vA2+vB2)/(vA1-vB1)
restart:
e2:=(vB2-v)/(v-vB1);
e1:=(v-vA2)/(vA1-v);
solve(e1=e2,v);
subs(v=%, e1); simplify(%);
