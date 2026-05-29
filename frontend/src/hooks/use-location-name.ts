import { useCallback } from 'react';

import { alpha3ToAlpha2 } from 'i18n-iso-countries/index';
import { useLocale, useTranslations } from 'next-intl';

type LocationLike = {
  code?: string | null;
  type?: string | null;
};

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

/**
 * Returns a function that resolves a Strapi location (or a `{code, type}` literal)
 * to a localized display name.
 *
 * Resolution order:
 *   1. type === 'country' with a `*` suffix → resolve the base country, then
 *      wrap with the `andTerritories` template.
 *   2. type === 'country' → per-locale override map, then `Intl.DisplayNames`
 *      with the alpha-2 of the code.
 *   3. type ∈ {region, custom_region, worldwide, highseas} → the
 *      `locations.<type>.<code>` message key.
 *   4. Anything else (inactive, inactive_region, unknown) → the raw code, so
 *      misses are visible.
 */
export default function useLocationName() {
  const locale = useLocale();
  const t = useTranslations('locations');

  return useCallback(
    (location: LocationLike = {}): string => {
      const code = location.code;
      if (!code) return '';

      const type = location.type ?? 'country';

      if (type === 'country') {
        if (code.endsWith('*')) {
          const country = resolveCountry(code.slice(0, -1), locale);
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
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        return t(`${type}.${code}` as any);
      }

      return code;
    },
    [locale, t]
  );
}
