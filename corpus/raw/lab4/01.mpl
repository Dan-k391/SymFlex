> restart: omega:=2*Pi*100.: sf0:=1e-3: omega0t:=2*Pi: omega0b:=2*Pi*100: Qt:=10: Qb:=20:
omegatr:=omega/omega0t; omegabr:=omega/omega0b;
Ht:=Qt/sqrt(Qt^2*(1-omegatr^2)^2+omegatr^2); phit:=arctan(omegatr, (1-omegatr^2)*Qt);
Hb:=Qb/sqrt(Qb^2*(1-omegabr^2)^2+omegabr^2); phib:=arctan(omegabr, (1-omegabr^2)*Qb);
A:=Ht*Hb*sf0; phi:=phit+phib;
