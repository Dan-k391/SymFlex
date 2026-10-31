# SOURCE: notes1_kinematics block 23 (page 49) - Check Your Understanding: Which IVP is this code solving?
# EXPECT: error
# NOTE: as printed, the parentheses are unbalanced ("b*(diff(x(t),t)+k*x(t)" is never closed), so Maple reports a syntax error. Kept verbatim (likely author typo for b*diff(x(t),t)+k*x(t)).
dsolve({m*diff(x(t),t,t)+b*(diff(x(t),t)+k*x(t)=Fext(t),
x(0)=0, D(x)(0)=0});
