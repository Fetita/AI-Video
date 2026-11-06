# Seed to Shelf: the AI impact case film

Creative treatment for the 2:46 case film (1920×1080, 30 fps, stereo 48 kHz) and its 1:30 teaser.
Deliverables: `out/eagerworks-ai-impact.mp4` and `out/eagerworks-ai-impact-teaser.mp4` (burned-in captions).

---

## 1. Central idea

**Impact isn't a promise. It's a result.** Every AI project starts with the result it has to deliver: less waste,
more output, better decisions.

The film follows **one fresh-produce grower's season, from seed to shelf**, through six AI cases. The grower is never
named, and no client data appears. Each case closes on one beat, **the gain card**: what the grower gains, told in
plain words, with a figure in some stations. There are no formulas, and each gain line is phrased differently, so
the six chapters never fall into the same template.

| Station | Case | Gain (kicker · headline) | Chips | Figure |
|---|---|---|---|---|
| 01 Nursery | Seedling survival (proposal) | Higher yield · More of every tray reaches the field | More seedlings survive · Less replanting · Planting on schedule | — |
| 02 Field | Harvest forecast (lettuce) | Less waste · Harvest cut to the order | Less lettuce thrown away · Every delivery complete | ≈ $25K a season* |
| 03 Harvest | Onion sizing on the windrower (proposal) | Better planning · Every field planned on its real sizes | No hand sampling · Harvest planned on real sizes · Sold by size band | ~45% of the tonnage sells by count |
| 04 Packhouse | Pumpkin count & quality | Better margins · Every pumpkin sells in its real class | Right class, right price · No hand counts | +$60 / t in the right class* |
| 05 Dispatch | Crate labeling | Reliable deliveries · Right crate, right store, first time | No fines · No returns · No product lost | ≈ $1,500 per rejected load avoided* |
| 06 Office | Dashboard, reports, alerts & AI assistant | Faster decisions · Hours of reporting, now minutes | Reports in minutes · Decisions on live data | 100% of the weekly forecast covered |

\* Illustrative estimates in USD, labeled on screen. The other two figures are rounded, anonymous figures from the
grower's season (see §6).

The order follows the value chain (nursery → field → harvest → packhouse → dispatch → office), so the season reads as
one story. The close widens the frame from one grower to the industry: less waste, better prices and faster decisions
make a whole operation more productive.

**Viewer takeaway:** *"Eagerworks builds AI that pays back, across the whole operation."*

### Recurring devices

1. **The violet line**: the signature of the AI Studio film. It becomes the value chain with six stations. Between
   chapters, every scene collapses into one standard line (`CHAIN`, y = 540), and the next scene turns it into its
   own horizon, rail, belt or slab. Because every scene enters and exits the same way, any order works, so the teaser
   reuses the scenes as they are.
2. **The gain card**: the closing beat of each chapter.
   - The scene dims; the kicker (the kind of gain) and the headline land as the gain line starts.
   - The chips pop as the voiceover names them. Some fly out of the scene itself: the coral surplus and shortfall
     become the field's chips, and the "One rejection costs" chips become *No fines · No returns · No product lost*.
   - In four stations a figure counts up under the chips; illustrative money figures carry an *Illustrative
     estimate* note.
   - When the card is complete, a violet underline sweeps under the headline on a chime, and the card docks into
     its station on the chain map.
3. **The chain map** (top right): six dots. Coral means a leak not yet fixed, violet means fixed. Each dot turns
   violet as its gain card docks.
4. **Need → Solution** (nursery, onions): two matte panels in the film's own look, unfolding out of the line and
   joined by a violet connector.
   - *NEED* carries a coral chip and an alert icon; *SOLUTION* a violet chip and a camera icon.
   - The content comes from the proposals, rewritten and anonymized. There is no slide layout, proposal label, logo or
     corner glow, so it never reads as a picture of the proposal.
   - The *Solution* panel opens into the working system.

---

## 2. Storyboard (final timings, film)

| Time | Scene | What happens |
|---|---|---|
| 0:00.0 – 0:25.2 | **Open** | Six small leaks flash by: a tray cell that never came up, a forecast that misses the orders, a crate REJECTED at the wrong store. Three more land on music hits: counted by hand, Ø ?, `report_v7_FINAL.xlsx`. They snap into a 3×2 grid and collapse into one line. **"Impact isn't a promise." → "It's a result."** ("promise" decodes into "result"). The Eagerworks AI Studio lockup follows, with three ghost results (*Less waste · More output · Better decisions*) that turn solid as the voiceover names them. The line becomes the value chain (`FROM SEED TO SHELF`, *One grower · one season · six results*) and shrinks into the chain map. |
| 0:25.2 – 0:43.2 | **01 Nursery · Seedling survival** | Need → Solution unfolds out of the line. Two lanes of trays roll under a camera gantry; every cell is ringed (healthy), flagged `SMALL` or marked empty. Tray summaries appear, and one tray is flagged `EARLY INTERVENTION` before it is fully scanned. A tray-audit column and size histogram sit alongside. Gain card: *Higher yield · More of every tray reaches the field*. |
| 0:43.2 – 1:01.2 | **02 Field · Harvest forecast** | The line becomes the horizon. The AI Studio film's line-art tractor drives in, and the view pushes into its camera: every head is boxed with a Ø and a `READY · <day>` tag. The feed shrinks to an inset while its plants stream into a *Harvest forecast* (boxes ready per day). Orders appear: coral surplus (waste) and coral shortfall (penalty), then boxes move from surplus days to short days until supply matches orders. Gain card: *Less waste · Harvest cut to the order*, ≈ $25K a season (illustrative). |
| 1:01.2 – 1:21.6 | **03 Harvest · Onion sizing** | Need → Solution. The NEED panel carries the proposal's proof-of-concept photo as a small *OFF-THE-SHELF MODEL* monitor, with coral rings on what that model missed (`MISSED ONIONS`). Then the windrower's rod belt: a custom model gives every onion an ID, counts it once at the line, measures it and colours it by size band. Panels show *Field 12 · lifting* (count, `Hand samples needed 0`, size split by band) and a field map by predominant band. Gain card: *Better planning*, ~45% of the tonnage sells by count. |
| 1:21.6 – 1:39.6 | **04 Packhouse · Count & quality** | The line splits into the two rails of the AI Studio film's pumpkin line. Pumpkins get IDs and are counted at the line. A quality scan grades each one: `CLASS I`, `CLASS II · SCAR / COLOR` or `OUT-GRADE · SHAPE`, with an estimated weight. The belt splits into three lanes, and the panel shows kg by class and `Hand counts 0`. Gain card: *Better margins*, +$60 / t in the right class (illustrative). |
| 1:39.6 – 2:04.8 | **05 Dispatch · Crate labeling** | First the leak, *without AI*: a wrongly labeled crate reaches STORE B and is REJECTED, and the cost appears as Fine · Product · Freight. Then *with AI*: a camera gantry recognizes each crate, checks it against the order, and a print-and-apply arm labels it. Crates route to their store dock, and the one mismatch is held back (`MISMATCH · HELD`). Gain card: *Reliable deliveries*, ≈ $1,500 per rejected load avoided (illustrative, also in the voiceover). |
| 2:04.8 – 2:26.4 | **06 Office · Dashboard & alerts** | Five stations stream data into one glowing *data foundation*. A paper-style dashboard rises out of it: KPIs, a cell-by-cell field map, size distribution, size split by field, and stock vs weekly demand. Reports build themselves (PDF/CSV), an alert arrives in time, and the assistant answers *"Which fields are furthest below target population?"* with the filters it applied. Gain card: *Faster decisions · Hours of reporting, now minutes*, 100% of the weekly forecast covered. |
| 2:26.4 – 2:45.6 | **Close** | The line becomes the chain again: six problems in coral, then six results (a ledger: kicker, headline and figure per station), each station turning violet, then one season. The ledger rows fly onto the logo's three E strokes, and the **Eagerworks AI Studio** lockup builds. Tagline **"Impact you can see, from seed to shelf."**, CTA **"Let's build what's next →"** · eagerworks.com, fade to black. |

**Teaser** (1:30.0, captions): open without the Eagerworks line (0:00–0:16.8) → Field (01) → Packhouse (02) →
Dispatch (03) → the same close. The ledger still shows all six results, as a pointer to the full film. The gain
lines are not captioned, because the gain card carries them on screen.

---

## 3. Voiceover (Kokoro `af_heart`, the AI Studio film's narrator)

> A seedling that never comes up. A harvest that misses the order. A crate at the wrong store.
> Impact isn't a promise. It's a result.
> At Eagerworks, every AI project starts with the result it has to deliver: less waste, more output, better decisions.
> Here's one grower's season, from seed to shelf.
>
> It starts in the nursery. Cameras over the moving trays count and size every seedling, and flag weak trays early.
> For the grower, more of every tray reaches the field, with less replanting, and planting that stays on schedule.
>
> In the field, a camera on the tractor measures every lettuce. The model forecasts the boxes ready each day, and matches them to the orders.
> So the harvest is cut to the order: less lettuce thrown away, and every delivery arrives complete.
>
> At harvest, every field needs its size split.
> Off-the-shelf models missed onions, so a custom model over the windrower counts each one once, and sorts it by size.
> No more crews sampling by hand. Every field is planned, and sold, on its real sizes.
>
> In the packhouse, every pumpkin is counted and graded for quality, with no hand counts.
> Every pumpkin sells in the class it earned, and the team stops counting, and starts running the line.
>
> At dispatch, one crate at the wrong supermarket means a rejection, and a fine.
> AI recognizes each crate, checks the order, labels it, and holds back any mismatch.
> The right crate reaches the right store, the first time. No fines, no returns, no product lost. Every rejection avoided keeps around fifteen hundred dollars in the business.
>
> Finally, it all lands in one place. One data foundation powers a live dashboard, self-building reports, and alerts while there's still time to act.
> Ask in plain English, and the answer comes from live data.
> Hours of reporting turn into minutes, and every decision rests on live data.
>
> Six problems. Six results. One season.
> Less waste, better prices, and faster decisions. That's how AI makes a whole industry more productive.
> Eagerworks AI Studio. Let's build what's next.

---

## 4. Visual direction

- **Palette:** the AI Studio film's palette, from Eagerworks' white-on-black logo.
  - Graphite base, warm white text.
  - Violet `#8234FE` → blue `#6686F6` marks what the AI sees, infers or produces, and what the grower gains.
  - Coral marks leaks, problems and needs; amber partial issues.
  - The dashboard is a cream "paper" screen floating on graphite. Size bands run blue → green → amber → orange.
- **Typography:** the Eagerworks pairing.
  - *Archivo* at 118–125 % width for display type. It matches the proposals' titles; a test render was compared
    against them.
  - *Manrope* for interface, body and tracked uppercase labels. Its use in the proposal decks was checked in the PDF
    and the Figma styles.
- **Look:** a premium dark SaaS film, matching the AI Studio film: matte panels, hairline borders, an engineering
  grid, vignette and fine grain. Glow is reserved for AI signals and the gain card.
- **Reused from the AI Studio film:** the line-art tractor (moved to `video/src/lib/tractor.js`, pixel-identical in
  the original film), the field sprites, the pumpkin line (sprites, belt, rails, IDs, count line), the HUD and
  stepper, detection overlays, and the logo build.

## 5. Sound

Same engine (`audio/synth.py`), 100 BPM, A minor / C major.
- The open is sparse, with impacts on each leak, a riser into the collapse hit, a hit on "result" and a swell on the
  lockup.
- Chapters: the nursery is soft (bells, shaker), the field mechanical, the onion harvest the peak (16th bass, stabs),
  the packhouse a mechanical groove, dispatch tense in Dm9 while the leak plays and resolving to C on the fix, and
  the office lighter.
- The close drops, rises and resolves on the logo.
- The gain card opens on a whoosh and a pop, each chip rings a bell (ascending pentatonic), a figure counts up on a
  data shimmer, the completed card lands on a chime with its underline, and docking plays a suck and a lock. These live in `sfx.py`, so the ducked music doesn't swallow them.
- New sounds: the REJECTED stamp, a label printer, a pneumatic applicator, and the rattle of the windrower's rods.

## 6. Anonymization and accuracy rules

- **The client is never named or hinted.** There are no company names, locations, real field or grower names,
  grower codes or retailer brands (stores are `STORE A/B/C`), and no project fees.
- **Money figures are illustrative.** The client's dashboards and proposals hold no money figures, so the three
  amounts (≈ $25K a season, +$60 / t, ≈ $1,500 per rejected load) are example estimates in USD. On screen each
  carries an *Illustrative estimate* note, and the closing ledger marks them with `*`.
- **Real figures are rounded and anonymous.** Only two come from the grower's own season: ~45% of the onion tonnage
  is traded by count (≥ 70 mm), and 100% of the weekly forecast is covered (the sourcing planner). They carry no
  field, grower, place or date.
- Counters, kg, field names (North 4, Weir 2, Hill 7…) and dates inside the interfaces are invented demo content.
- **Proposals are not reproduced.** Need → Solution is told in the film's own look, with the content rewritten and
  anonymized. The voiceover describes what the systems do without claiming a deployment.
- **The only client-origin image is the onion proof-of-concept photo.** It comes from the proposal (707×391, no
  identifying content, metadata stripped) and sits as a small inset inside the NEED panel. The nursery proposal's tray
  photos were not used, because they come from other vendors' trials.
- **The three HTML dashboards were references for content types only.** Field maps cell by cell, size distributions,
  size splits and planners inspired the dashboard; its layout, palette and data are new.

## 7. Production

| Stage | Files |
|---|---|
| Voiceover | `audio/vo_script.impact.json`, `audio/vo_script.impact-teaser.json` → `tts.py` |
| Timeline | `build_timeline.py` → `video/src/timeline-impact*.js` |
| Scenes | `video/src/scenes/{impact-open,nursery,lettuce,onions,pumpkins,labels,dashboard,impact-close}.js` |
| Shared | `video/src/lib/{vo,impact-data,gain,chain,chapter,proposal,icons,produce,conveyor,tractor,impact-theme}.js` |
| Score / SFX | impact sections in `audio/music.py` and `audio/sfx.py` (old cuts are unaffected: their music and sfx are bit-identical) |
| Delivery | `scripts/finalize.sh` |

The gain card's item times (headline, chips, figure) are computed from the voiceover's clause timings in
`video/src/lib/vo.js` and `gain.js`. `audio/sfx.py` mirrors that computation, so each bell lands on the frame its
chip appears.
