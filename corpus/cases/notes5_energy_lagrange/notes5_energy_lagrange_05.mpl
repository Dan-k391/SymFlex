# SOURCE: notes5_energy_lagrange block 05 (page 10) - eg 19.4 disk and hanging block, impulse-momentum FBD method
restart:
mb:=6: ma:=20: IA:=.4:
R:=.2: tf:=3: g:=9.81:
vbi:=2: omegai:=vbi/R:
omegaf:=vbf/R:
solve([
IA*(omegaf-omegai) = int(R*T, t=0..tf),
mb*(vbf-vbi) = int(mb*g-T, t=0..tf)]);
