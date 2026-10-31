import { runFlex } from '../../src/flex/index.js';

// Minimal ngrid=1 IVP script around the given sections.
export const ivp = ({ vars, defs = '', init = '', eqs, time, plots = '', select = '' }) => `TITLE 'test'
COORDINATES cartesian1
VARIABLES
${vars}
SELECT ngrid=1 ${select}
DEFINITIONS
${defs}
INITIAL VALUES
${init}
EQUATIONS
${eqs}
BOUNDARIES
  REGION 1 START(0) LINE TO (1)
TIME ${time}
PLOTS
${plots}
END
`;

export const report = (res, label) => {
  const r = res.reports.find(x => x.label === label);
  if (!r) throw new Error(`no report ${label}: ${JSON.stringify(res.reports)} ${JSON.stringify(res.errors)}`);
  return r.value;
};

export { runFlex };
