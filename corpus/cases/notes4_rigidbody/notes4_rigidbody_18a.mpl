# SOURCE: notes4_rigidbody block 18 (page 41) - eg 17.13 spool
# NOTE: raw block 18 contained two separate restart groups; this is the first. Output matches document (IG := 0.9800)
restart:
m:=8: k:=.35: IG:=k^2*m; g:=9.81:
solve([
m*aGy=100+T-m*g,
IG*alpha=.5*T-.2*100,
aGy=-.5*alpha]);
