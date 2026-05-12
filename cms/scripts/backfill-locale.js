#!/usr/bin/env node
/*
 * One-off backfill script: clone every default-locale entry into a new locale.
 *
 * Why this exists:
 *   The Localazy plugin handles TEXT translation only. It does not propagate
 *   relations, media, components, or dynamic-zone data across locales. When a
 *   new locale is added (e.g. `id`), every existing entry in the source locale
 *   needs a sibling entry in the new locale before Localazy can translate it.
 *
 * What it does:
 *   1. Verifies the target locale is registered in i18n.
 *   2. For each localized collection type (in dependency order), reads the
 *      source-locale entries with deep populate and creates a sibling entry
 *      under the same documentId in the target locale.
 *   3. Localized text fields are copied verbatim from the source locale as
 *      placeholders. Localazy overwrites them on the next download cycle.
 *   4. Relation fields are passed through as documentId references; Strapi v5
 *      resolves each relation to the correct locale at read time.
 *   5. Components are deep-cloned (component row IDs stripped so Strapi makes
 *      fresh rows per locale).
 *   6. For dataset <-> layer (which form a relation cycle), `dataset.layers`
 *      is written in a second pass after both sides exist in the target locale.
 *   7. For D&P (only `layer`), the new-locale entry is published if the source
 *      entry was published; `publishedAt` is set to the current time.
 *
 * Idempotent:
 *   Re-running skips any documentId+locale that already exists.
 *
 * Localazy upload noise:
 *   This script does NOT suppress the Localazy plugin's afterCreate hook.
 *   Expect one upload trigger per entry created. For a few hundred entries
 *   this is tolerable; just wait for the queue to drain before kicking off
 *   the manual Localazy upload from the plugin UI.
 *
 * Out of scope:
 *   `api::location.location` carries inline translations via `name_es`,
 *   `name_fr`, `name_pt` columns (it is NOT an i18n-plugin localized CT).
 *   Adding a new locale `<code>` means it has no `name_<code>` column. Handle
 *   that via a schema migration in a separate change.
 *
 * Usage:
 *   cd cms
 *   node scripts/backfill-locale.js --locale=id [--source-locale=en] [--dry-run] [--yes]
 *
 * Flags:
 *   --locale         (required) target locale code, must already exist in Strapi
 *   --source-locale  source locale (default: en)
 *   --dry-run        log what would happen, don't write
 *   --yes            skip the "Have you backed up the DB?" prompt
 */

const { createStrapi, compileStrapi } = require('@strapi/strapi');
const readline = require('readline');
const { parseArgs } = require('util');

// --- Dependency-ordered list of LOCALIZED collection types ---
// Tier 0 (leaves) are processed first so later tiers can reference them.
// `data-tool-language` is intentionally placed after `data-tool` so its
// `data_tool` FK resolves to an existing target row in the new locale.
const PASS_1_ORDER = [
  // singleType
  'api::contact-detail.contact-detail',
  // leaves
  'api::data-source.data-source',
  'api::data-tool-ecosystem.data-tool-ecosystem',
  'api::data-tool-resource-type.data-tool-resource-type',
  'api::environment.environment',
  'api::fishing-protection-level.fishing-protection-level',
  'api::habitat.habitat',
  'api::mpa-iucn-category.mpa-iucn-category',
  'api::mpaa-establishment-stage.mpaa-establishment-stage',
  'api::mpaa-protection-level.mpaa-protection-level',
  'api::protection-status.protection-status',
  'api::static-indicator.static-indicator',
  // depend on leaves
  'api::data-info.data-info',
  'api::data-tool.data-tool',
  'api::data-tool-language.data-tool-language',
  'api::dataset.dataset',
  'api::layer.layer',
];

// Relation attributes to defer until pass 2 (cycle handling).
// `dataset.layers` is the only true deferral: the inverse side
// `layer.dataset` is owning and is written in pass 1 once dataset exists.
const DEFERRED_RELATIONS = {
  'api::dataset.dataset': ['layers'],
};

// Fields never copied through to the new-locale entry.
const SKIPPED_ATTRIBUTES = new Set([
  'id',
  'documentId',
  'createdAt',
  'updatedAt',
  'publishedAt',
  'locale',
  'localizations',
  'createdBy',
  'updatedBy',
]);

function buildDeepPopulate(strapi, uid) {
  const ct = strapi.contentType(uid);
  const populate = {};
  for (const [name, attr] of Object.entries(ct.attributes)) {
    if (attr.type === 'relation') {
      populate[name] = { fields: ['documentId'] };
    } else if (attr.type === 'media') {
      populate[name] = true;
    } else if (attr.type === 'component' || attr.type === 'dynamiczone') {
      populate[name] = { populate: '*' };
    }
  }
  return populate;
}

function stripIds(value) {
  if (Array.isArray(value)) return value.map(stripIds);
  if (value && typeof value === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(value)) {
      if (k === 'id') continue;
      out[k] = stripIds(v);
    }
    return out;
  }
  return value;
}

function extractDocumentIds(relValue) {
  if (relValue == null) return null;
  if (Array.isArray(relValue)) {
    return relValue.map((r) => r?.documentId).filter(Boolean);
  }
  return relValue.documentId ?? null;
}

function buildCreatePayload(strapi, uid, sourceEntry, skipRelations) {
  const ct = strapi.contentType(uid);
  const data = {};
  const skipSet = new Set(skipRelations || []);
  for (const [name, attr] of Object.entries(ct.attributes)) {
    if (SKIPPED_ATTRIBUTES.has(name)) continue;
    const value = sourceEntry[name];
    if (value === undefined) continue;

    if (attr.type === 'relation') {
      if (skipSet.has(name)) continue;
      const docIds = extractDocumentIds(value);
      if (docIds === null) continue;
      data[name] = docIds;
    } else if (attr.type === 'component' || attr.type === 'dynamiczone') {
      data[name] = value == null ? value : stripIds(value);
    } else if (attr.type === 'media') {
      if (value == null) {
        data[name] = value;
      } else if (Array.isArray(value)) {
        data[name] = value.map((m) => m.id);
      } else {
        data[name] = value.id;
      }
    } else {
      data[name] = value;
    }
  }
  return data;
}

async function fetchSourceEntries(strapi, uid, opts) {
  const ct = strapi.contentType(uid);
  const findParams = {
    locale: opts.sourceLocale,
    populate: buildDeepPopulate(strapi, uid),
  };
  if (ct.options?.draftAndPublish) findParams.status = 'published';

  if (ct.kind === 'singleType') {
    const single = await strapi.documents(uid).findFirst(findParams);
    return single ? [single] : [];
  }
  return strapi.documents(uid).findMany(findParams);
}

async function processContentType(strapi, uid, opts, stats) {
  const ct = strapi.contentType(uid);
  const isLocalized = !!ct.pluginOptions?.i18n?.localized;
  if (!isLocalized) {
    console.log(`[${uid}] not localized — skipping`);
    return;
  }
  const hasDP = !!ct.options?.draftAndPublish;
  const skipRelations = DEFERRED_RELATIONS[uid] || [];

  const sources = await fetchSourceEntries(strapi, uid, opts);
  console.log(`\n[${uid}] processing ${sources.length} entries`);
  if (skipRelations.length) {
    console.log(`  deferred to pass 2: ${skipRelations.join(', ')}`);
  }

  for (const src of sources) {
    const documentId = src.documentId;
    try {
      const existing = await strapi
        .documents(uid)
        .findOne({ documentId, locale: opts.targetLocale });
      if (existing) {
        console.log(`  skip   ${documentId} (already exists in ${opts.targetLocale})`);
        stats.skipped += 1;
        continue;
      }

      const data = buildCreatePayload(strapi, uid, src, skipRelations);

      if (opts.dryRun) {
        console.log(`  [dry] would create ${documentId} (${Object.keys(data).length} fields)`);
        stats.created += 1;
        continue;
      }

      await strapi
        .documents(uid)
        .update({ documentId, locale: opts.targetLocale, data });

      if (hasDP && src.publishedAt) {
        await strapi
          .documents(uid)
          .publish({ documentId, locale: opts.targetLocale });
      }

      console.log(`  create ${documentId}`);
      stats.created += 1;
    } catch (err) {
      console.error(`  ERROR  ${documentId}: ${err.message}`);
      stats.errored += 1;
    }
  }
}

async function wireDeferredRelations(strapi, uid, fields, opts, stats) {
  const ct = strapi.contentType(uid);
  const hasDP = !!ct.options?.draftAndPublish;
  const populate = {};
  for (const f of fields) populate[f] = { fields: ['documentId'] };

  const findParams = { locale: opts.sourceLocale, populate };
  if (hasDP) findParams.status = 'published';

  const sources =
    ct.kind === 'singleType'
      ? [await strapi.documents(uid).findFirst(findParams)].filter(Boolean)
      : await strapi.documents(uid).findMany(findParams);

  console.log(`\n[${uid}] pass 2: wiring ${fields.join(', ')} on ${sources.length} entries`);

  for (const src of sources) {
    const documentId = src.documentId;
    try {
      const data = {};
      for (const f of fields) {
        const docIds = extractDocumentIds(src[f]);
        if (docIds === null) continue;
        data[f] = docIds;
      }
      if (Object.keys(data).length === 0) {
        stats.skipped += 1;
        continue;
      }

      if (opts.dryRun) {
        console.log(`  [dry] would wire ${documentId}: ${JSON.stringify(data)}`);
        continue;
      }

      await strapi
        .documents(uid)
        .update({ documentId, locale: opts.targetLocale, data });

      if (hasDP && src.publishedAt) {
        await strapi
          .documents(uid)
          .publish({ documentId, locale: opts.targetLocale });
      }

      console.log(`  wire   ${documentId}`);
    } catch (err) {
      console.error(`  ERROR  ${documentId}: ${err.message}`);
      stats.errored += 1;
    }
  }
}

function confirmBackup() {
  return new Promise((resolve, reject) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });
    rl.question('Have you backed up the database for this environment? (yes/no) ', (answer) => {
      rl.close();
      const v = answer.trim().toLowerCase();
      if (v === 'yes' || v === 'y') resolve();
      else reject(new Error('Aborted: backup not confirmed. Re-run with --yes to bypass.'));
    });
  });
}

async function main() {
  const parsed = parseArgs({
    options: {
      locale: { type: 'string' },
      'source-locale': { type: 'string', default: 'en' },
      'dry-run': { type: 'boolean', default: false },
      yes: { type: 'boolean', default: false },
    },
    allowPositionals: false,
  });

  const targetLocale = parsed.values.locale;
  if (!targetLocale) {
    console.error('Missing required --locale=<code>');
    process.exit(1);
  }
  const sourceLocale = parsed.values['source-locale'];
  if (targetLocale === sourceLocale) {
    console.error('--locale and --source-locale must differ');
    process.exit(1);
  }

  const opts = {
    targetLocale,
    sourceLocale,
    dryRun: parsed.values['dry-run'],
  };

  console.log(`Backfill locale: source=${sourceLocale} -> target=${targetLocale}${opts.dryRun ? ' (dry-run)' : ''}`);

  if (!parsed.values.yes) {
    await confirmBackup();
  }

  const appContext = await compileStrapi();
  const strapi = await createStrapi(appContext).load();

  try {
    const localeRow = await strapi.db
      .query('plugin::i18n.locale')
      .findOne({ where: { code: targetLocale } });
    if (!localeRow) {
      throw new Error(
        `Locale '${targetLocale}' is not registered in Strapi. Add it under Settings -> Internationalization first.`
      );
    }
    const sourceRow = await strapi.db
      .query('plugin::i18n.locale')
      .findOne({ where: { code: sourceLocale } });
    if (!sourceRow) {
      throw new Error(`Source locale '${sourceLocale}' is not registered in Strapi.`);
    }

    const stats = { created: 0, skipped: 0, errored: 0 };

    for (const uid of PASS_1_ORDER) {
      await processContentType(strapi, uid, opts, stats);
    }

    for (const [uid, fields] of Object.entries(DEFERRED_RELATIONS)) {
      await wireDeferredRelations(strapi, uid, fields, opts, stats);
    }

    console.log('\n=== Summary ===');
    console.log(`created: ${stats.created}`);
    console.log(`skipped: ${stats.skipped}`);
    console.log(`errored: ${stats.errored}`);
    if (stats.errored > 0) process.exitCode = 1;
  } finally {
    await strapi.destroy();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
