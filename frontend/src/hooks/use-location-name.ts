import { useCallback } from 'react';

import { useLocale, useTranslations } from 'next-intl';

import { resolveLocationName } from '@/lib/i18n/locationName';

type LocationLike = {
  code?: string | null;
  type?: string | null;
};

/**
 * Returns a function that resolves a Strapi location (or a `{code, type}` literal)
 * to a localized display name.
 */
export default function useLocationName() {
  const locale = useLocale();
  const t = useTranslations('locations');

  return useCallback(
    (location: LocationLike = {}): string => {
      if (!location.code) return '';
      
      return resolveLocationName(location.code, location.type ?? 'country', locale, t);
    },
    [locale, t]
  );
}
