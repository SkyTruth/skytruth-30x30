import { alpha3ToAlpha2 } from 'i18n-iso-countries/index';

export type LocationType =
  | 'country'
  | 'region'
  | 'custom_region'
  | 'worldwide'
  | 'highseas'
  | 'inactive'
  | 'inactive_region';

// Specific cases where we want to diverge from CLDR's strings.
const COUNTRY_OVERRIDES: Record<string, Record<string, string>> = {
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
