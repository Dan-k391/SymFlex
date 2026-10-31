# SOURCE: notes1_kinematics block 20 (page 46) - (Try this, if you dare:) symbolic dsolve of the nonlinear halfpipe DE
# NOTE: slow - the document says "This doesn't work"; in Maple 2024 the final dsolve does not return within 120 s (killed). DE and ICs print normally before it. An emulator should give up / return no solution rather than hang. The DE parenthesization (g/r*sin inside muk*(...)) is as written by the author.
restart:
g:=9.81: r:=0.1: muk:=0.3:
DE:=diff(q(t),t,t)=muk*((diff(q(t),t))^2+g/r*cos(q(t))-g/r*sin(q(t)));
ICs:=[q(0)=Pi/2, D(q)(0)=0];
dsolve({DE, op(ICs)});
