# SOURCE: lab2 block 04 (para 88) - L11 main lecture problem, momentum + energy symbolic solve
restart:
pEqn:=M*(-vS1) = M*vS2+M/2*vJ2;
EEqn:=1/2*M*vS1^2 = 1/2*M*vS2^2+1/2*(M/2)*vJ2^2;
solve([pEqn, EEqn], [vS2, vJ2]);
