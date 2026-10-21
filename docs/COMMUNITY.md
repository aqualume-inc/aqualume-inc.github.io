# Moderated community reports

Initial scope: AT and NL. Reporting requires a GitHub account. Issues and original attachments are public. The form requires a photo, coordinates, observed status and observation date. Photo uploads use GitHub's upload field (public-preview feature). No automatic import or publication from issues is implemented.

## Review before publication
Check the actual photo, coordinates, duplicates, public access, observation date and image rights. A photo does not certify potability or current operation. Never invent a reopening date. If supplied, retain a public evidence URL and label the date as reported, not guaranteed. Remove faces, plates and EXIF/location metadata before public upload; sanitizing a later copy cannot erase an already public original.

A maintainer must prepare a sanitized image under images/community/ and add an approved record to data/community.json. Required fields: issue (positive GitHub issue number), approved (true), country (AT or NL), name, lat, lon, photo (local image path), status (unknown/active/dry/repair/seasonal/removed), observed_on (YYYY-MM-DD). Optional: osm_type and osm_id to reference an existing OSM record; reopens_on with reopening_source (public HTTP(S) evidence URL). Use one current record per fountain and update it after review. Validate before committing.

The website loads approved records only when the referenced image can be loaded. Older than 30 days is flagged as stale. Status means community-reported, never official certification. An automatically passed reopening date must not be treated as proof the fountain is open.

The workflow validates publication files and integrates the UI; it is not a complete deployment gate for every other existing Pages workflow. A separate writable backend and private upload/moderation flow are future work. No client-side GitHub token is used.
