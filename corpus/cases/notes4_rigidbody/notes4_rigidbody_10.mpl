# SOURCE: notes4_rigidbody block 10 (page 25) - rotating reference frame tour bus
# NOTE: output matches document: vbus := 33.33333333, Omega := 0.3926990818, R := 84.88263629
restart:
vbus:=120*1e3/3600;
t_turn:=4:
s_turn:=vbus*t_turn:
Omega:=(Pi/2.)/t_turn;
R:=vbus/Omega;
