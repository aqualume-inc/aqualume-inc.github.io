# Fountain menu, local profiles and ratings

Marker clicks open Info / Meldung / Route / Bewertung. Routing starts only through the explicit Route action; cluster expansion is unchanged.

Ratings use one to five water drops and optional text up to 500 characters. They are local-only, not submitted to a server and not included in a public average. Anonymous mode stores no profile ID in the rating; it is not a promise of network anonymity or protection against access by another person using the same browser.

A random profile ID is created only when a profile is explicitly opened or selected. It is not a hardware identifier, authentication token, device fingerprint or cross-device account. ID display is off by default. Names, avatar selection and accent preference are stored locally. Clearing browser data loses the profile and ratings. Export downloads a local JSON file containing the chosen profile and ratings. Delete removes those two local storage keys, not downloaded maps or favorites.

No public rating sync or anonymous public upload backend is provided. Existing GitHub fountain reports remain public and account-linked. A future shared rating service needs consent, moderation, spam controls and backend storage. Ratings never certify drinking-water quality.

Syntax and isolated storage/ID tests passed during preparation. Full mobile, 2D/3D integration and accessibility testing remain required.
