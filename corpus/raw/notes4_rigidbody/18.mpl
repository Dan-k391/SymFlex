> restart:
m:=8: k:=.35: IG:=k^2*m; g:=9.81:
solve([
m*aGy=100+T-m*g,
IG*alpha=.5*T-.2*100,
aGy=-.5*alpha]);
> restart:
m:=8: k:=.35: IG:=k^2*m; g:=9.81:
IIC:=m*.5^2+IG;
solve(.5*78.48-(.5+.2)*100=IIC*alpha);
