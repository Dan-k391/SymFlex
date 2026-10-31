# SOURCE: notes3_damped block 11 (page 27) - Resonance curves for several damping ratios with gridlines
restart;
w0:=10: x0:=1: #zeta:=1:
A:=zeta->x0*w0^2/sqrt((w^2-w0^2)^2+(2*zeta*w0*w)^2):
phi:=-arctan((w^2-w0^2)/(2*zeta*w0*w))-Pi/2:
with(plots):
plot(2*[A(1/16), A(1/8), A(1/4), A(1/2), A(1), A(2)], w=0.1..40,
numpoints=1000, labels=["omega", "Amplitude"], axis=[gridlines=[10,
color=blue]]);
