// The story board's layout (story scene), shared with scripts/render_board.py through
// video/tools/dump_shot_inputs.mjs. Board space: origin at the board centre, film pixels at zoom 1.
export const BOARD = {
  SLOTS: [
    { kind: 'sloth', x: -470, y: -30, label: 'CHARACTER · SLOTH' },
    { kind: 'scout', x: -150, y: 70, label: 'CHARACTER · SCOUT' },
    { kind: 'wizard', x: 170, y: -70, label: 'CHARACTER · WIZARD' },
    { kind: 'samurai', x: 480, y: 40, label: 'CHARACTER · SAMURAI' },
  ],
  BW: 1560, BH: 880, PD: 230,      // board size, piece diameter
  /** When each piece lands (scene time): the sloth is there from the start, the others drop on "places a few pieces". */
  drops: (cPlace) => [0.15, cPlace + 0.35, cPlace + 0.85, cPlace + 1.35],
  DROP: 0.55,                      // fall time
  FACE: {                          // how each character sits on its piece's face (% of the face circle), as lib/story-art.js
    sloth: { src: 'sloth-lotus.png', w: 92, x: 4, y: 9 },
    scout: { src: 'scout.png', w: 124, x: -4, y: 8 },
    wizard: { src: 'wizard.png', w: 112, x: -6, y: 4 },
    samurai: { src: 'samurai.png', w: 122, x: -6, y: 6 },
  },
  inputs(cPlace) {
    return { t0: -0.2, slots: this.SLOTS, BW: this.BW, BH: this.BH, PD: this.PD, drops: this.drops(cPlace), DROP: this.DROP, face: this.FACE };
  },
};
