g:=9.81;
ax:=FThrust*(-sin(theta))/mtotal:
vx:=int(subs(t=t2, %), t2=0 ..t);
rx:=int(subs(t=t2, %), t2=0 ..t);
ay:=FThrust*(cos(theta))/mtotal:
vy:=int(subs(t=t2, %), t2=0 ..t)+433:
ry:=int(subs(t=t2, %), t2=0 ..t)+11617:
plot([ax, vx, rx],t=0..60);
