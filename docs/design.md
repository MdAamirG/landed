# Design

The screens in `design/screens/` are the approved designs. Open them in a browser and match them; they are static HTML, so take the layout, type and colour from them, not the markup.

## Direction

- Built with the Hallmark design skill, theme **Coral**: warm grey paper, a lorry receipt drawn as cotton stationery, one coral ink kept for the settled state ("Verified").
- The client asked for minimal design: clean layouts, white space, a restrained palette, nothing without a purpose. Drivers read poorly: one big button, icons, a clear colour for success or retake, no forms.
- Product name: **Landed**. The delivery landed, and so did its proof.

## Tokens

`design/tokens.css` holds every colour and font as a CSS variable. Use only these; no literal colours or font names in components.

- Type: Instrument Sans for everything, Noto Sans Devanagari for Hindi and Marathi, Geist Mono for figures in columns (trip codes, LR numbers, amounts, times).
- Ink on paper. One dark primary button style (`btn--ink`), one secondary (`btn--card`, a pressed paper card). One primary per screen.
- Coral (`--color-paid`) only on "Verified", link underlines and focus rings. Never as a fill or a band.
- Driver screens only: green (`--color-ok`) for done, ochre (`--color-retake`) for retake. The brief requires a clear success and retake colour, and coral would read as an error at a gate.

## Rules from the Hallmark skill that matter here

- No labels in tracked capitals, no eyebrow labels above headings, no text joined with " · ".
- No gradients, no cards inside cards, no emoji as icons, no drawn browser or phone frames.
- Tables before cards on office screens. A top bar, not a sidebar (four destinations).
- Every focusable element has a visible `:focus-visible` ring. Animate only `transform` and `opacity`, with a `prefers-reduced-motion` fallback.
- Every region that loads data has loading (skeleton rows), empty (what belongs here plus one action) and error (what broke plus what to do) states.
- Never invent a metric, logo or testimonial. Sample figures are labelled as sample data.

## Screens

| File | Who | What it must show |
| --- | --- | --- |
| `Driver_Home.html` | Driver, phone | Trip from the SMS link: trip code, number plate, route, LR, e-way bill, one big "फोटो लें" button, language switch, speaker button, location and network state |
| `Checking.html` | Driver | The photo, then three steps: phone check passed, compressed and sent (3.1 MB to 214 KB), AI reading the six fields |
| `Retake.html` | Driver | "फिर से फोटो लें", the reason, six field checks with tick or cross, retake button, "Retake 1 of 2" |
| `Received.html` | Driver | Big green tick, "हो गया", trip, photo size, location, time, "Sent to billing" |
| `Offline.html` | Driver | "Saved on the phone, sends by itself", queued item, phone check result, SMS note for later retakes |
| `Main.html` | Office | Sign in, two demo-role buttons, QR to the driver demo |
| `Review.html` | Billing executive | Queue on the left, the photo in the middle, editable AI fields with confidence, trip checks, masked consignee contact with a logged reveal, approve and retake |
| `Billing.html` | Billing executive | Verified trips grouped by client, cycle switch, total, export to Tally, download POD photos |
| `Dashboard.html` | Operations head | Four figures, delivered trips without a POD, POD-to-invoice days by branch against the 4-day target, client link |
| `Trips.html` | Office | Daily CSV import with per-row checks (missing e-way bill, duplicate LR) |
| `States.html` | Office | Loading, empty and error states for the review queue |
| `Landing.html` | Public | Landing page. Build it last, after the core works |

Once the app runs, replace the drawn product on the landing page with real screenshots.
