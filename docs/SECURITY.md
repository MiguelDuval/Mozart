# Mozart Security

## Rules

- Never commit API keys.
- Never put secrets in Gradle resources.
- Never log full authorization headers.
- Never include provider tokens in crash reports.
- Cap network request and response sizes.
- Validate all external structured data.
- Network operations run off realtime threads.
- User can disable all network generation.

For a personal Android build, store secrets in Android Keystore-backed storage or equivalent secure platform storage.

## Supply chain

Pin external source revisions.

Prefer official repositories.

Record dependency licenses and update provenance after upgrades.

## Release readiness

Before redistribution:

- review dependency licenses;
- run dependency/update audit;
- review network endpoints;
- review privacy behavior;
- remove debug diagnostics that expose sensitive state;
- sign release builds with a real release key.
