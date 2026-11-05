# FS Studio: co-branded AI film

Two FS Studio films made from the same scenes as the Eagerworks AI Studio film. Eagerworks appears only as a small partner credit at the very end.

| File | Length | Built from |
|---|---|---|
| `out/fsstudio-ai.mp4` | 3:08 | `audio/vo_script.fsstudio.json` (the full film) |
| `out/fsstudio-ai-linkedin.mp4` | 1:30, burned-in captions | `audio/vo_script.fsstudio-linkedin.json` (the LinkedIn overview cut) |

Both are 1920×1080, 30 fps, H.264 + AAC, −14 LUFS.

## 1. What the brand book asks for, and how the film uses it

The source is the *FS Studio Brand Book* (CT Consulting, October 2019).

| Brand book | In the film |
|---|---|
| **Logo:** a single rounded pink (#FF059F) line forming an "S" inside a rounded diamond, plus a light geometric **FSSTUDIO** wordmark. | The logo is the vector artwork from the book itself (page 1, extracted by `scripts/extract_fsstudio_logo.py`). The build draws the icon as **one continuous line**: the film's recurring signal line becomes the mark. It then resolves into the supplied artwork, and the wordmark slides in letter by letter. The wordmark is set white because it sits on charcoal. |
| **Neutrals:** #2F2F2F · #A5A5A5 · #D0D0D0 · #F2F2F2. Dark #2F2F2F pages carry the big statements. | The film sits on brand charcoal (a #363636 → #2A2A2A → #1E1E1E radial), with panels at #303030 and text at #F2F2F2 / #BCBCBC / #8E8E8E. |
| **Gradients:** FF059F→8154B1, 39DAE0→8154B1, FF9A43→FF059F. | **Pink #FF059F → purple #8154B1** is the AI signal: it marks what the AI sees, infers or produces. The old Eagerworks violet played this role. Small pink text uses #FF80C8. The pipeline stepper's progress uses **cyan → purple**, and the CTA uses **orange → pink**. |
| **Palette:** #0670E0 #134FFF #39DAE0 #40BF92 #59D570 #BDD342 #FFC543 #FF9A43 #FF2F2F #FF059F #8154B1 | Gaps and issues use brand red (#FF3B30, a touch lighter than #FF2F2F so it reads on charcoal), partial matches use #FFC543, and secondary data series use #39DAE0 and #FF9A43. |
| **Graphic elements:** a "technical layer" (a grid of "+" signs) and an "emotional layer" (soft mesh gradients). | The engineering line grid is replaced by a drifting **"+" grid** tinted pink → orange, as on the book's back cover. Two slow, faint colour fields (pink, cyan) give the emotional layer. A cyan "+" follows **Applied AI** in the lockup, echoing *Applied Imagination+*. |
| **Typography:** one typeface for everything, *Europa* (Bold for headlines, Regular for copy). | Europa is a commercial EuropaType font and is not in the repository. **Figtree** (SIL OFL) stands in: a geometric sans with humanist details, a double-storey *a* and single-storey *g*, like Europa. It is used for both the display and interface roles, at weight 600–700 for headlines. The children's story keeps Fraunces and the one code line keeps JetBrains Mono, because those are content inside the scenes. If FS Studio supplies licensed Europa web fonts, set `--font-ui` / `--font-display` in `video/src/brands/fsstudio.css` and `fonts.ui` in `video/src/brand.js`. |
| **Voice:** "ask the right questions", *Innovative Tech + Solid Code + Creative Vision + Strategic Capability*, *Applied Imagination*, "an agile product development and R&D technology partner". | The rewritten lines are listed in §2. |
| **Photography:** rounded corners, layered compositions, drop shadows. | The film's panels already work this way, so nothing changed. |

## 2. Copy changes

FS Studio is "we" throughout, as agreed, including the five client cases and the packing-line product. Every other line, and the order of scenes, is the same as in the Eagerworks film.

| Where | Eagerworks film | FS Studio film |
|---|---|---|
| Hook narration | Eagerworks AI Studio turns AI capabilities into… | **FS Studio** turns AI capabilities into real products, workflows and measurable outcomes. |
| Lockup | eagerworks \| AI Studio | **FSSTUDIO \| Applied AI+** |
| Intro narration | We're a team of designers and engineers who build digital products… | We're a team of **technologists and designers who solve product and R&D challenges**, from the first idea to launch. |
| Intro headline · sub-line | Designers & engineers. · We build digital products, from the first idea to launch. | **Technologists & designers.** · We solve product and R&D challenges, from idea to launch. |
| Intro pills | Product strategy · UX / UI design · Software engineering · Cloud & data · Applied AI | **Innovative tech + Solid code + Creative vision + Strategic capability +** Applied AI (taken from the brand book) |
| How we work, narration | We start by listening: to your people… | We start by **asking the right questions**: about your people… |
| How we work, pillars | Listen · Adapt · Stay | **Ask** · Adapt · Stay |
| Finale narration | Eagerworks AI Studio. | **FS Studio.** |
| URL | eagerworks.com | **fsstudio.com** |
| Partner credit | — | "In partnership with" + the Eagerworks logo: small, muted, under the URL, and the last thing to appear (about 2 s). This is the only place Eagerworks appears. The narration never names it. |

The TTS reads "FS" as the letters ("F S Studio"), and "R&D" as "R and D". Every rewritten line keeps the same clause and pause structure as the original. That matters because each scene keys its animations to individual clauses (`ctx.cue(line, k)`).

## 3. How it is built

The brand is a property of a cut. A narration script sets `"brand": "fsstudio"`, and `audio/build_timeline.py` copies it into the timeline. From there:

- `video/src/brand.js` holds a table per brand: palette (hex values and "r,g,b" triplets), fonts, URL, recap folder, on-screen copy, and the partner flag. The engine exposes the cut's entry as `BRAND`, `C` and `PAL`. Every scene takes its colours from these tokens; nothing is hard-coded.
- `video/src/brands/fsstudio.css` overrides the CSS tokens and a few component styles. `main.js` loads it, sets `data-brand` on `<html>`, and swaps the background for the charcoal, the "+" grid and the colour fields.
- `video/src/lib/brand-logo.js` gives the hook and the finale the right lockup. FS Studio's is in `video/src/lib/logo-fsstudio.js` and `logo-data-fsstudio.js`, generated from the PDF.
- `scripts/make_recap.sh` with `CUT=fsstudio` builds the finale's recap wall from the FS Studio film's own frames, into `video/assets/recap-fsstudio/`.

The Eagerworks films are unchanged. Stills rendered before and after the refactor are pixel-identical, apart from ±1 rendering noise that also shows up between two renders of the same code.

### Rebuild

```bash
python3 scripts/extract_fsstudio_logo.py path/to/FS_Studios_Brand_Book.pdf   # only if the logo changes
cd audio && export CUT=fsstudio
python3 tts.py && python3 build_timeline.py && python3 music.py && python3 sfx.py && python3 mix.py
cd .. && CUT=fsstudio scripts/make_recap.sh
cd video && node render.mjs --video --workers 4 --query cut=fsstudio --out build/frames-fsstudio.mkv
cd .. && scripts/finalize.sh video/build/frames-fsstudio.mkv audio/build/mix-fsstudio.wav out/fsstudio-ai.mp4
```

For the LinkedIn cut, repeat with `CUT=fsstudio-linkedin` and the `-linkedin` file names, and skip `make_recap.sh`: that cut reuses the full film's recap tiles.

If the installed Chromium doesn't match the pinned Playwright, set `CHROMIUM_PATH` to the browser binary.
