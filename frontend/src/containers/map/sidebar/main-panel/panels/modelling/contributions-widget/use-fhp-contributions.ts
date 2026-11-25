import { useMemo } from 'react';

import { useTranslations } from 'next-intl';

import useDataInfoTooltips from '@/hooks/use-data-info-tooltips';
import { FHP_LEVEL, useFhpAnalysis } from '@/hooks/use-modelling-stat';
import { GLOBAL_CODE, buildContributions } from '@/lib/utils/modelling-contributions';
import { useGetMpaaProtectionLevelStats } from '@/types/generated/mpaa-protection-level-stat';
import { MpaaProtectionLevelStat } from '@/types/generated/strapi.schemas';

import { toStatus } from './helpers';

const FHP_TOOLTIP_SLUG = 'cb-fully-highly-protected';

const useFhpContributions = (codes: string[], seaCodes: ReadonlySet<string>, enabled: boolean) => {
  const t = useTranslations('containers.map-sidebar-main-panel');

  const analysis = useFhpAnalysis(enabled);

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

  const tooltips = useDataInfoTooltips([FHP_TOOLTIP_SLUG], { enabled });
  const tooltip = tooltips[FHP_TOOLTIP_SLUG] && {
    ...tooltips[FHP_TOOLTIP_SLUG],
    sourcesLabel: t('fully-highly-protected-sources'),
  };

  return { byCode, status: toStatus(analysis, stats), tooltip };
};

export default useFhpContributions;
