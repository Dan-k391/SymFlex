> restart:
lam1:=(s(t))=sqrt(2^2+1^2-2*2*1*cos(theta(t)));
#assume(s(t),positive);
diff(lam1, t);
omega(t):=subs(diff(s(t),t)=.5, solve(%, diff(theta(t),t)));
s30:=solve(subs(theta(t)=30*Pi/180, lam1), s(t)); evalf(%);
omega30:=subs([theta(t)=30*Pi/180], omega(t)); evalf(%);
alpha(t):=diff(omega(t),t);
alpha30:=subs([theta(t)=30*Pi/180, diff(theta(t),t)=omega30],
alpha(t)); evalf(%);
