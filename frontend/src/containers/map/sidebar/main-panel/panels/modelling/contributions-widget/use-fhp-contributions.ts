import { useMemo } from 'react';

import { useLocale, useTranslations } from 'next-intl';

import {
  FHP_LEVEL,
  useFhpAnalysis,
} from '@/containers/map/content/map/modelling/use-modelling-stat';
import { GLOBAL_CODE, buildContributions } from '@/lib/utils/modelling-contributions';
import { useGetDataInfos } from '@/types/generated/data-info';
import { useGetMpaaProtectionLevelStats } from '@/types/generated/mpaa-protection-level-stat';
import { MpaaProtectionLevelStat } from '@/types/generated/strapi.schemas';

import { toStatus } from './stat-status';

/**
 * "Fully/Highly Protected" stats for the Conservation Builder panel (marine only), keyed by
 * location code, with `GLOB` for the Global section
 *
 * The added area comes from cb_api's protection-level analysis of the drawn shape; the
 * existing fully/highly protected area and the total area come from Strapi's MPAA
 * protection level stats. A location without a Strapi row has no entry. Also returns the
 * heading's info tooltip, with its linked source, from Strapi
 *
 * @param codes locations listed in the panel
 * @param seaCodes IHO seas, left out of the Global sum because they overlap national waters
 * @param enabled false on the terrestrial tab
 */
const useFhpContributions = (codes: string[], seaCodes: ReadonlySet<string>, enabled: boolean) => {
  const locale = useLocale();
  const t = useTranslations('containers.map-sidebar-main-panel');

  // Added fully/highly protected area per location
  const analysis = useFhpAnalysis(enabled);

  // Existing fully/highly protected area per location, plus global
  const stats = useGetMpaaProtectionLevelStats<MpaaProtectionLevelStat[]>(
    {
      filters: {
        location: {
          code: {
            $in: [...codes, GLOBAL_CODE],
          },
        },
        mpaa_protection_level: {
          slug: {
            $eq: FHP_LEVEL,
          },
        },
      },
      // @ts-ignore
      populate: {
        location: {
          fields: ['code'],
        },
      },
      // @ts-ignore
      fields: ['area', 'total_area'],
      'pagination[limit]': codes.length + 1,
    },
    {
      query: {
        enabled: enabled && codes.length > 0,
        select: ({ data }) => data ?? [],
        refetchOnWindowFocus: false,
      },
    }
  );

  const byCode = useMemo(
    () =>
      analysis.data && stats.data
        ? buildContributions(
            stats.data.map(({ location, area, total_area }) => ({
              code: location?.code,
              existing: Number(area ?? 0),
              total: Number(total_area),
            })),
            analysis.data.locations_area,
            seaCodes
          )
        : new Map(),
    [analysis.data, stats.data, seaCodes]
  );

  // Info tooltip for the "Fully / Highly Protected" heading, with its linked source
  const { data: tooltip } = useGetDataInfos(
    { locale, filters: { slug: 'cb-fully-highly-protected' }, populate: 'data_sources' },
    {
      query: {
        enabled,
        select: ({ data }) =>
          data[0]
            ? {
                text: data[0].content,
                sources: data[0].data_sources?.map(({ documentId, slug, title, url }) => ({
                  documentId,
                  slug,
                  title,
                  url,
                })),
                sourcesLabel: t('fully-highly-protected-sources'),
              }
            : undefined,
      },
    }
  );

  return { byCode, status: toStatus(analysis, stats), tooltip };
};

export default useFhpContributions;
