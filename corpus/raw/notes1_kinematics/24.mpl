> restart:
e2:=(vB2-v)/(v-vB1);
e1:=(v-vA2)/(vA1-v);
solve(e1=e2,v);
subs(v=%, e1); simplify(%);
