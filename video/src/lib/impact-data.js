// Seed to Shelf: the value chain and the six impact formulas, shared by the chapters,
// the top-right chain map and the closing ledger. Formulas are symbolic on purpose: no numbers.

export const STATIONS = [
  { id: 'nursery', label: 'Nursery', icon: 'tray' },
  { id: 'lettuce', label: 'Field', icon: 'lettuce' },
  { id: 'onions', label: 'Harvest', icon: 'onion' },
  { id: 'pumpkins', label: 'Packhouse', icon: 'pumpkin' },
  { id: 'labels', label: 'Dispatch', icon: 'crate' },
  { id: 'dashboard', label: 'Office', icon: 'dashboard' },
];
export const stationIndex = (sceneId) => STATIONS.findIndex((s) => s.id === sceneId);

// Token kinds: term (a quantity, `tone` ai = what the AI changes, base = a unit value),
// op (× / +), open / close (parentheses), eq (=) and result (the IMPACT pill).
// `say` is the phrase in the VO line that brings the token on screen.
const T = (label, icon, tone, say) => ({ t: 'term', label, icon, tone, say });
const X = (say) => ({ t: 'op', sym: '×', say });
const P = (say) => ({ t: 'op', sym: '+', say });

export const EQUATIONS = {
  nursery: {
    line: 'n4',
    tokens: [T('Seedlings saved', 'seedling', 'ai', 'seedlings saved'), X('times'), T('Cost per seedling', 'coins', 'base', 'the cost'), { t: 'eq' }, { t: 'result' }],
  },
  lettuce: {
    line: 'l4',
    tokens: [T('Boxes not wasted', 'box', 'ai', 'boxes not wasted'), X('times'), T('Cost / box', 'coins', 'base', 'their cost'),
      P('plus'), T('Shortfalls avoided', 'truck', 'ai', 'shortfalls avoided'), X('times the'), T('Penalty', 'ticket', 'base', 'penalty'), { t: 'eq' }, { t: 'result' }],
  },
  onions: {
    line: 'u4',
    tokens: [T('Sampling hours saved', 'clock', 'ai', 'sampling hours saved'), X('times'), T('Cost / hour', 'coins', 'base', 'their cost'),
      P('plus'), T('Tonnes in the right band', 'scale', 'ai', 'tonnes'), X('times the'), T('Price difference', 'tag', 'base', 'price difference'), { t: 'eq' }, { t: 'result' }],
  },
  pumpkins: {
    line: 'k3',
    tokens: [T('Hours saved', 'clock', 'ai', 'hours saved'), X('times'), T('Cost / hour', 'coins', 'base', 'cost per hour'),
      P('plus'), T('Kg graded right', 'scale', 'ai', 'kilos graded right'), X('times the'), T('Price difference', 'tag', 'base', 'price difference'), { t: 'eq' }, { t: 'result' }],
  },
  labels: {
    line: 'b4',
    tokens: [T('Rejections avoided', 'shield', 'ai', 'rejections avoided'), X('times'), { t: 'open', say: 'times' }, T('Fine', 'ticket', 'base', 'the fine'),
      P('plus the product'), T('Product', 'leaf', 'base', 'product'), P('plus the freight'), T('Freight', 'truck', 'base', 'freight'), { t: 'close', say: 'freight' }, { t: 'eq' }, { t: 'result' }],
  },
  dashboard: {
    line: 'g4',
    tokens: [T('Reporting hours saved', 'report', 'ai', 'reporting hours saved'), X('times'), T('Cost / hour', 'coins', 'base', 'cost per hour'), { t: 'eq' }, { t: 'result' }],
  },
};

/** Compact text form for the closing ledger. */
export function formulaText(sceneId) {
  return EQUATIONS[sceneId].tokens.map((k) => (k.t === 'term' ? k.label : k.t === 'op' ? k.sym : k.t === 'open' ? '(' : k.t === 'close' ? ')' : '')).filter(Boolean).join(' ');
}
