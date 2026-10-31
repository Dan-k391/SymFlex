> restart:
lam1:=(s(t))=sqrt(2^2+1^2-2*2*1*cos(theta(t)));
#assume(s(t),positive);
#Ang:=60*Pi/180:
diff(lam1, t);
omega(t):=subs(diff(s(t),t)=.5, solve(%, diff(theta(t),t)));
s30:=solve(subs(theta(t)=Ang, lam1), s(t)); evalf(%);
omega30:=subs([theta(t)=Ang], omega(t)); evalf(%);
alpha(t):=diff(omega(t),t);
alpha30:=subs([theta(t)=Ang, diff(theta(t),t)=omega30],
alpha(t)); evalf(%);
plot(alpha30, Ang);
