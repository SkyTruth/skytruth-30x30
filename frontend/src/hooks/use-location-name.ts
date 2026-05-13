import { useCallback } from 'react';

import { useLocale, useTranslations } from 'next-intl';

import { resolveLocationName } from '@/lib/i18n/locationName';

type LocationLike = {
  code?: string | null;
  type?: string | null;
};

/**
 * Returns a function that resolves a Strapi location (or an alpha-3 country
 * code passed as a string) to a localized display name. The returned function
 * is stable across renders for the same locale.
 *
 * Pass `{ code, type }`. When `type` is omitted, `'country'` is assumed —
 * include it in your Strapi `fields` query when the result may be a region,
 * worldwide, etc.
 */
export default function useLocationName() {
  const locale = useLocale();
  const t = useTranslations('locations');

  return useCallback(
    (location: LocationLike | string | null | undefined): string => {
      if (!location) return '';
      const code = typeof location === 'string' ? location : location.code;
      if (!code) return '';
      const type = typeof location === 'string' ? 'country' : (location.type ?? 'country');
      // next-intl's typed t() doesn't match the dynamic key shape resolveLocationName uses;
      // the resolver only ever passes well-known shapes.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return resolveLocationName(code, type, locale, t as any);
    },
    [locale, t]
  );
}
