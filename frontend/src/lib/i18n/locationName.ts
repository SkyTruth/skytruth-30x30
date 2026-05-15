// Slim import: `i18n-iso-countries/index` skips the registerLocale loop in `entry-node`,
// so none of the langs/*.json files are bundled. We only use alpha3ToAlpha2; localized
// names come from Intl.DisplayNames (built-in CLDR data, no bundle cost).
import { alpha3ToAlpha2 } from 'i18n-iso-countries/index';

export type LocationType =
  | 'country'
  | 'region'
  | 'custom_region'
  | 'worldwide'
  | 'highseas'
  | 'inactive'
  | 'inactive_region';

// CLDR's strings differ from our product copy in these cases. Keyed by alpha-3,
// then by locale. A missing locale entry falls through to CLDR (not to English),
// so the user always sees a name in their language even if we haven't curated one.
// Add new entries sparingly — accepting CLDR is the default.
const COUNTRY_OVERRIDES: Record<string, Record<string, string>> = {
  KOR: {
    en: 'Republic of Korea',
    es: 'República de Corea',
    fr: 'République de Corée',
    pt: 'República da Coreia',
    id: 'Republik Korea',
    sw: 'Jamhuri ya Korea',
  },
  COD: {
    en: 'Democratic Republic of the Congo',
    es: 'República Democrática del Congo',
    fr: 'République démocratique du Congo',
    pt: 'República Democrática do Congo',
    id: 'Republik Demokratik Kongo',
    sw: 'Jamhuri ya Kidemokrasia ya Kongo',
  },
  COG: {
    en: 'Republic of the Congo',
    es: 'República del Congo',
    fr: 'République du Congo',
    pt: 'República do Congo',
    id: 'Republik Kongo',
    sw: 'Jamhuri ya Kongo',
  },
  BES: {
    en: 'Bonaire, Sint Eustatius and Saba',
    es: 'Bonaire, San Eustaquio y Saba',
    fr: 'Bonaire, Saint-Eustache et Saba',
    pt: 'Bonaire, Santo Eustáquio e Saba',
    id: 'Bonaire, Sint Eustatius dan Saba',
    sw: 'Bonaire, Sint Eustatius na Saba',
  },
  MMR: {
    en: 'Myanmar',
    es: 'Myanmar',
    fr: 'Myanmar',
    pt: 'Myanmar',
    id: 'Myanmar',
    sw: 'Myanmar',
  },
};

type TranslateFn = (key: string, values?: Record<string, string | number>) => string;

/**
 * Resolve a location to a display string.
 *
 * Resolution order:
 *   1. type === 'country' with `*` suffix → resolve the base country, then wrap
 *      with the andTerritories template.
 *   2. type === 'country' → per-locale override map, then Intl.DisplayNames with
 *      the alpha-2 of the code.
 *   3. type ∈ {region, custom_region, worldwide, highseas} → Localazy key
 *      under `<type>.<code>`.
 *   4. Anything else (inactive, inactive_region, unknown) → fall through to the
 *      raw code so misses are visible.
 *
 * `t` must be scoped to the `locations` namespace.
 */
export function resolveLocationName(
  code: string,
  type: string,
  locale: string,
  t: TranslateFn
): string {
  if (!code) return '';

  if (type === 'country') {
    if (code.endsWith('*')) {
      const baseCode = code.slice(0, -1);
      const country = resolveCountry(baseCode, locale);
      return t('andTerritories', { country });
    }
    return resolveCountry(code, locale);
  }

  if (
    type === 'region' ||
    type === 'custom_region' ||
    type === 'worldwide' ||
    type === 'highseas'
  ) {
    return t(`${type}.${code}`);
  }

  return code;
}

function resolveCountry(alpha3: string, locale: string): string {
  const override = COUNTRY_OVERRIDES[alpha3]?.[locale];
  if (override) return override;

  const alpha2 = alpha3ToAlpha2(alpha3);
  if (!alpha2) return alpha3;

  try {
    const name = new Intl.DisplayNames([locale], { type: 'region' }).of(alpha2);
    return name ?? alpha3;
  } catch {
    return alpha3;
  }
}
