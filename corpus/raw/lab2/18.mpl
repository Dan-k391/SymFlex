m0=500
mfuel0 = m0*0.9
qfuel =20
ve = 1200
tfuel = mfuel0/qfuel
m=if(t<tfuel) then(m0-qfuel*t) else (m0-qfuel*tfuel)
Ftmag = if(t<tfuel) then(qfuel*ve) else (0)
