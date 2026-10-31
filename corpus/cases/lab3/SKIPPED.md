# lab3 skipped blocks

| block | para | reason |
|---|---|---|
| 17 | 455 | FlexPDE fragment (3 DEFINITIONS lines: zeta/omegad/Td for the L18 damped-period modification), extracted as .mpl. Already present in full in block 14 (lab3_14.pde). Note the source line `zeta=b/(2*sqrt(m*k)` is missing a closing paren; block 14 has it correct. |
| 18 | 460 | FlexPDE fragment `TIME 0 TO 2*Td` (same modification), extracted as .mpl. Already present in block 14 as `TIME 0 TO Td*2`. |

Block 06 (also FlexPDE lines extracted as .mpl) was not skipped: it is applied to block 04 as lab3_06.pde.
