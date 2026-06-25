# samples/

Drop engage2win map photos here before running the validation harness.

## What to add
- Photos of thinking maps created during engage2win sessions
- Mix of individual and team maps, different sessions and topics
- Aim for 10–20 photos to get a meaningful validation result
- Both clean and messy maps — the AI needs to handle real conditions

## File formats
- `.jpg` / `.jpeg` (preferred)
- `.png`
- iPhone HEIC → export as JPG first (Photos app → Share → Save as JPEG)

## Optional: add context sidecars
For richer evaluations, place a `.json` file next to each photo with the same name:

```json
{
  "name": "Pablo Quintano",
  "role": "Senior Solutions Consultant",
  "department": "PreSales EMEA",
  "area": "Opportunity Qualification",
  "topic": "TechCorp Q3 deal",
  "language": "en"
}
```

Fields default to "—" if omitted. `language` defaults to `en`.

## Privacy
This folder is gitignored. Photos never leave your machine unless you explicitly share them.
