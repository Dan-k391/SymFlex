# SOURCE: notes4_rigidbody block 07 (page 18) - example 16.13 solution 2 with IC
# NOTE: output matches document: vB := 2.50 (trailing-zero float), 58.60000001, solve of 4 eqns
restart:
deg2rad:=3.14159/180:
rBC:=.75: vB:=.25*10;
#angles:
ic:=45*deg2rad: c:=(90-13.6)*deg2rad: b:=3.14159-ic-c:
b/deg2rad;
solve([
rBIC/sin(c)=rBC/sin(ic),
rCIC/sin(b)=rBC/sin(ic),
vB=omegaBC*rBIC,
vC=omegaBC*rCIC
]);
