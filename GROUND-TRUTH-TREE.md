# Ground truth: the 00:02:09 sidebar tree, per Tristan's reading of the frame

The calibration fixture. The deterministic layer is DONE when its tree output
matches this row for row: name, folder/file, chevron state, and depth.

```
˅ 02 - Carson James                     folder, expanded, depth 0
│ ˃ Assets                              folder, collapsed, depth 1
│ ˅ Buckaroo Crew                       folder, expanded, depth 1
│ │ ˃ Books (Downloads)                 folder, collapsed, depth 2
│ │ ˃ Courses                           folder, collapsed, depth 2
│ │   Beyond the Basics                 FILE, depth 2
│ │   Buckaroo Crew                     FILE, depth 2
│ │   Carson Al                         FILE, depth 2
│ │   Carson Al Video Recommendations   FILE, depth 2
│ │   Horse.TV                          FILE, depth 2
│ │   HorseTracks                       FILE, depth 2
│ │   The Facebook Group                FILE, depth 2
│ │   Video Library                     FILE, depth 2
│ ˃ Carson's DVD Club                   folder, collapsed, depth 1
│ ˃ Dev                                 folder, collapsed, depth 1
│ ˃ Misc                                folder, collapsed, depth 1
│ ˅ Operations                          folder, expanded, depth 1
│ │ ˃ Campaigns                         folder, collapsed, depth 2
│ │ ˃ Email Queue                       folder, collapsed, depth 2
│ │ ˅ Jobs                              folder, expanded, depth 2
│ │   ˅ Creating Campaigns              folder, expanded, depth 3
│ │   │ Campaign Types                  FILE, depth 4
│ │   │ Creating A Core Offer           FILE, depth 4
│ │   │ Creating A Lead Magnet          FILE, depth 4
│ │   │ Creating A Profit Maximizer     FILE, depth 4
│ │   │ Creating A Tripwire             FILE, depth 4
│ │   │ Creating A Webinar              FILE, depth 4
│ │   │ Creating Campaigns              FILE, depth 4
│ │   │ Make the LeadPage               FILE, depth 4
│ │   ˃ Drafting Emails                 folder, collapsed, depth 3
│ │   ˃ Facebook Ads                    folder, collapsed, depth 3
```

Corrections banked against my previous H-tree:
- "Assets" is a FOLDER under 02 - Carson James (I had it as a root-level file).
- "Beyond the Basics" is a FILE under Buckaroo Crew (I had it under Courses).
- Everything under Buckaroo Crew at depth 2 is a FILE except the two folder
  siblings Books (Downloads) and Courses.
- The OCR rows "Jobs" (second) and "APIs & Credentials" appear below
  "Facebook Ads" in the strip but are outside this example's range:
  unconfirmed, marked H until verified.

Uniform laws observed (the render rules):
- Every folder row carries a triangle (˅ expanded / ˃ collapsed); every
  file row carries no triangle.
- The vertical guide lines carry the nesting: one line per ancestor level.
- The triangle sits immediately left of the name at the row's indent.
