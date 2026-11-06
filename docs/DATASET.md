# Evaluation and accuracy policy

## Dataset

Capture consented real PUBG Mobile inventories with multiple device aspect ratios, UI languages, compression settings, scrolling speeds, seasons, inventory categories and rare lookalike icons. Keep user identifiers and account credentials out of public GitHub.

Each video needs an independently reviewed list of **present catalog item IDs**, **absent but visually similar IDs**, and approximate visible time spans. Reference images must be lawfully obtained, manually cropped, and labeled with canonical official English names. Do not use a purported model confidence score as a substitute for manual ground truth.

## Benchmark

Use a separate holdout set of real videos unseen during threshold selection. For each catalog item, compute:

- precision = true positives / (true positives + false positives)
- recall = true positives / (true positives + false negatives)
- false-positive reports per 100 videos
- abstention rate / unknown item rate, and coverage of known item IDs

Report all denominators and confidence intervals. A test set with no observed false positives is not a guarantee of 0% real-world error. With 0 errors in N approximately independent test cases, the rule-of-three 95% upper bound is about 3/N. Independence may not hold across nearly identical clips.

## Suggested release gate (not yet achieved)

- At least 100 independently labeled permissioned real inventory videos spanning different capture settings.
- Manual review of every reported positive in the holdout.
- No unconfirmed item name or rarity reported as a confirmed fact.
- Clear notice that inventory totals are partial if catalog coverage is incomplete.
- Pilot with human verification until confidence intervals and failure modes meet operational needs.

## Known model risks

- UI overlays, scrolling motion blur, compression and changed themes.
- Similar or cloned item thumbnails, multiple inventory pages and duplicate appearances.
- Hardcoded tile grid calibrated for the wrong screen profile.
- Frames repeatedly showing the same false candidate (temporal repetition is not independence in the statistical sense).
- Valid items with references missing from the catalog.
- Color and rarity labels may not be inferred purely from a border.

## Next implementation order

1. Gather and annotate real examples.
2. Implement screen/layout detection and scroll-aware frame selection.
3. Add negative exemplar bank and independently measured thresholds.
4. Implement verified rarity marker detection and collection-level OCR.
5. Integrate queue, rate limiting, event logging and failure recovery.
