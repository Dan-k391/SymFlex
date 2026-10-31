# SOURCE: notes4_rigidbody block 05 (page 10) - example 16.6 via differentiating position
# NOTE: output matches document: yA := sqrt(2)/10, vB := 2, 2.
restart:
yA:=1/5*cos(Pi/4); vA:=2:
vB:=5/sqrt(1-(5*yA)^2)*(yA*vA); evalf(%);
