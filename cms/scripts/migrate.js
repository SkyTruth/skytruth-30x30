'use strict';

// TODO(post-v4-to-v5-migration): Delete this file once v4→v5 is complete in
// prod. Schema-sync on an already-migrated DB runs in seconds during normal
// `yarn start`, so the dedicated migration Job is no longer needed. See the
// matching TODOs in cms/Dockerfile.prod and .github/workflows/deploy-cms.yml.
//
// One-shot migration runner for Strapi v5.
//
// Why this exists:
//   v4 -> v5 internal migrations (table rename _links -> _lnk, document_id
//   backfill, locale column add, etc.) run during `bootstrap()` inside
//   `createStrapi().load()`. Running this on a developer laptop against
//   Cloud SQL pays per-row RTT and can take hours; running it as a
//   one-shot Cloud Run Job in the same region as the DB takes minutes.
//
// What this does:
//   1. Builds a Strapi instance and calls `.load()` (= register + bootstrap).
//      Bootstrap performs db.init({ models }) and db.schema.sync() — that's
//      where every v5 migration is committed.
//   2. Calls destroy() so DB pool connections close cleanly.
//   3. Exits non-zero on any failure so the calling CI step fails the deploy.
//
// Idempotent: once strapi_migrations is populated, subsequent runs are no-ops.

const { createStrapi } = require('@strapi/strapi');

(async () => {
  const start = Date.now();
  console.log('migrate: loading Strapi (migrations run during load)…');

  let app;
  try {
    app = await createStrapi({ distDir: './dist' }).load();
    console.log(`migrate: load complete in ${Date.now() - start}ms`);
  } catch (err) {
    console.error('migrate: load failed', err);
    process.exit(1);
  }

  try {
    await app.destroy();
  } catch (err) {
    console.error('migrate: destroy failed (continuing to exit)', err);
  }

  process.exit(0);
})();
