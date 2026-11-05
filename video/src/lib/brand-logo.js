// The cut's brand lockup: the hook and the finale import the lockup and its geometry from here.
// `size` scales the lockup height each scene asks for (the FS Studio mark is a tall icon with a light
// wordmark, so it needs about twice the Eagerworks height to carry the same weight in frame).
import { BRAND } from '../engine.js';
import * as ew from './logo.js';
import * as ewData from './logo-data.js';
import * as fs from './logo-fsstudio.js';
import * as fsData from './logo-data-fsstudio.js';

const pick = BRAND.id === 'fsstudio'
  ? { makeLockup: fs.makeLockup, VIEWBOX: fsData.VIEWBOX, ICON_VIEWBOX: fsData.ICON_VIEWBOX, STROKES: fsData.STROKES, size: 2 }
  : { makeLockup: ew.makeLockup, VIEWBOX: ewData.VIEWBOX, ICON_VIEWBOX: ewData.ICON_VIEWBOX, STROKES: ewData.STROKES, size: 1 };

export const { makeLockup, VIEWBOX, ICON_VIEWBOX, STROKES } = pick;
export const LOCK_SIZE = pick.size;
