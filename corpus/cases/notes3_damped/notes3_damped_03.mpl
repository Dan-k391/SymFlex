# SOURCE: notes3_damped block 03 (page 6) - Plot the over/crit/underdamped solutions
# EXPECT: error
# NOTE: author code has an empty argument ("t=0..20, , legend") -> 1-D parser gives "syntax error, `,` unexpected"; the document (2-D worksheet) shows the plot rendered. Same plot is exercised (with legend) in notes3_damped_04.
# DEPENDS: notes3_damped_01
restart;
m:=1: k:=1: x0:=1:
ode:= m*diff(x(t), t,t)+b*diff(x(t),t)+k*x(t)=0;
ics:= x(0)=x0, D(x)(0)=0;
assign(dsolve(subs([x=overdamped, b=4], {ode, ics})));
assign(dsolve(subs([x=critdamped, b=2], {ode, ics})));
assign(dsolve(subs([x=underdamped,b=1], {ode, ics})));
plot([overdamped(t), critdamped(t), underdamped(t)], t=0..20, , legend =
["overdamped", "critdamped", "underdamped"]);
