# SOURCE: lab2 block 15 (para 430) - L13 concept: true g at 221 km vs surface
restart: h:=220840:
G:=6.674e-11: mEarth:=5.97e24: rEarth:=6371e3:
rrel:=rEarth+h:
gtrue:=G*mEarth/rrel^2;
gsurface:=9.81:
Deltag:=gsurface-gtrue;
gFraction:=gtrue/gsurface;
