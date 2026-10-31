# SOURCE: notes1_kinematics block 07 (page 20) - Parametric plotting & sublisting
# NOTE: author's comment says LOL[1][3][2] is "too deep, can't sublist an equation", but Maple 2024 does NOT error: it returns the unevaluated indexed expression (theta = 0 .. 3*Pi/2)[2]. The final rhs(...) line gives 0 .. 3*Pi/2.
restart;
plot([cos(theta),sin(theta)], theta=0..3*Pi/2); #plot 2 functions: y = cos(theta) and y = sin(theta) from theta = 0..3*Pi/2
plot([cos(theta),sin(theta), theta=0..3*Pi/2]); #plot 1 parametric function: x = cos(theta), y = sin(theta) from theta = 0..3*Pi/2
plot([[cos(theta),sin(theta), theta=0..3*Pi/2], [x^3/4, x*cos(x), x=-Pi/2..Pi/2]]); #plot 2 parametric functions; argument is now a list of lists
LOL:=[[cos(theta),sin(theta), theta=0..3*Pi/2], [x^3/4, x*cos(x), x=-Pi/2..Pi/2]];
LOL[1]; #Sublist1
LOL[2];
LOL[1][3]; #listception
LOL[1][3][2]; #too deep, can't sublist an equation
rhs(LOL[1][3]); #can find its RHS though
