# SOURCE: notes4_rigidbody block 04 (page 9) - example 16.6 solve for omega
# NOTE: output matches document: {omega = 14.14213562, vBx = 2.}
restart:
solve([
vBx=omega*0.2/sqrt(2),
0=-2+omega*0.2/sqrt(2)]);
