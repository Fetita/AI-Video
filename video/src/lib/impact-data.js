// Seed to Shelf: the value chain and what the grower gains at each station, shared by the chapters,
// the top-right chain map and the closing ledger.

export const STATIONS = [
  { id: 'nursery', label: 'Nursery', icon: 'tray' },
  { id: 'lettuce', label: 'Field', icon: 'lettuce' },
  { id: 'onions', label: 'Harvest', icon: 'onion' },
  { id: 'pumpkins', label: 'Packhouse', icon: 'pumpkin' },
  { id: 'labels', label: 'Dispatch', icon: 'crate' },
  { id: 'dashboard', label: 'Office', icon: 'dashboard' },
];
export const stationIndex = (sceneId) => STATIONS.findIndex((s) => s.id === sceneId);

// Each station closes on one gain card: a kicker (the kind of gain), a headline, chips that pop as the VO
// names them (`say` is the phrase in the gain line), and in some stations a stat.
// Stats: `note` 'Illustrative estimate' marks example money figures (USD, not client data); stats without
// a note are rounded, anonymous figures from the grower's own season.
const C = (text, say, dir = 'up') => ({ text, say, dir });

export const GAINS = {
  nursery: {
    line: 'n3', icon: 'seedling', kicker: 'Higher yield',
    headline: 'More of every tray reaches the field',
    chips: [C('More seedlings survive', 'more of every tray'), C('Less replanting', 'less replanting', 'down'), C('Planting on schedule', 'on schedule')],
  },
  lettuce: {
    line: 'l3', icon: 'box', kicker: 'Less waste',
    headline: 'Harvest cut to the order',
    chips: [C('Less lettuce thrown away', 'thrown away', 'down'), C('Every delivery complete', 'complete')],
    stat: { pre: '≈ $', to: 25, post: 'K', label: 'a season in lettuce no longer thrown away', note: 'Illustrative estimate' },
  },
  onions: {
    line: 'u3', icon: 'scale', kicker: 'Better planning',
    headline: 'Every field planned on its real sizes',
    chips: [C('No hand sampling', 'sampling by hand', 'down'), C('Harvest planned on real sizes', 'planned'), C('Sold by size band', 'sold')],
    stat: { pre: '~', to: 45, post: '%', label: 'of the crop’s tonnage sells by count: the size split is the price' },
  },
  pumpkins: {
    line: 'k2', icon: 'tag', kicker: 'Better margins',
    headline: 'Every pumpkin sells in its real class',
    chips: [C('Right class, right price', 'class it earned'), C('No hand counts', 'stops counting', 'down')],
    stat: { pre: '+$', to: 60, post: ' / t', label: 'sold in the right class instead of a lower one', note: 'Illustrative estimate' },
  },
  labels: {
    line: 'b3', icon: 'shield', kicker: 'Reliable deliveries',
    headline: 'Right crate, right store, first time',
    chips: [C('No fines', 'no fines', 'down'), C('No returns', 'no returns', 'down'), C('No product lost', 'no product lost', 'down')],
    stat: { pre: '≈ $', to: 1500, post: '', label: 'kept per rejected load avoided: fine, product and freight', note: 'Illustrative estimate', say: 'fifteen hundred' },
  },
  dashboard: {
    line: 'g4', icon: 'report', kicker: 'Faster decisions',
    headline: 'Hours of reporting, now minutes',
    chips: [C('Reports in minutes', 'minutes'), C('Decisions on live data', 'live data')],
    stat: { pre: '', to: 100, post: '%', label: 'of the weekly forecast covered, planned weeks ahead' },
  },
};

/** Stat text at count-up progress p (0..1). */
export function statText(st, p = 1) {
  const v = Math.round(st.to * Math.max(0, Math.min(1, p)));
  return `${st.pre}${v.toLocaleString('en-US')}${st.post}`;
}
