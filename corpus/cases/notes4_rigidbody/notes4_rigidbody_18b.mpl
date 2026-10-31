# SOURCE: notes4_rigidbody block 18 (page 41) - eg 17.13 spool
# NOTE: second half of raw block 18; output matches document (IIC := 2.9800, -10.32214765)
restart:
m:=8: k:=.35: IG:=k^2*m; g:=9.81:
IIC:=m*.5^2+IG;
solve(.5*78.48-(.5+.2)*100=IIC*alpha);
