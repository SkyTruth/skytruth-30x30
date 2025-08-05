import { useMemo } from 'react';

import { useLocale, useTranslations } from 'next-intl';

import HorizontalBarChart from '@/components/charts/horizontal-bar-chart';
import Widget from '@/components/widget';
import {
  MARINE_HABITAT_CHART_COLORS,
  TERRESTRIAL_HABITAT_CHART_COLORS,
} from '@/constants/habitat-chart-colors';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { FCWithMessages } from '@/types';
import { useGetDataInfos } from '@/types/generated/data-info';
import { useGetHabitatStats } from '@/types/generated/habitat-stat';
import type {
  HabitatStatHabitatData,
  LocationGroupsDataItemAttributes,
} from '@/types/generated/strapi.schemas';

type HabitatWidgetProps = {
  location: LocationGroupsDataItemAttributes;
};

const HabitatWidget: FCWithMessages<HabitatWidgetProps> = ({ location }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();

  const [{ tab }] = useSyncMapContentSettings();

  const [HABITAT_CHART_COLORS, total_habitats] = useMemo(() => {
    const total =
      tab === 'marine'
        ? Object.keys(MARINE_HABITAT_CHART_COLORS).length
        : Object.keys(TERRESTRIAL_HABITAT_CHART_COLORS).length;

    return [{ ...MARINE_HABITAT_CHART_COLORS, ...TERRESTRIAL_HABITAT_CHART_COLORS }, total];
  }, [tab]);

  const { data: habitatMetadatas } = useGetDataInfos<
    { slug: string; info: string; sources?: { id: number; title: string; url: string }[] }[]
  >(
    {
      locale,
      filters: {
        slug: Object.keys(HABITAT_CHART_COLORS),
      },
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      populate: {
        data_sources: {
          fields: ['title', 'url'],
        },
      },
      sort: 'updatedAt:desc',
    },
    {
      query: {
        select: ({ data }) =>
          data?.map((item) => ({
            slug: item.attributes.slug,
            info: item.attributes.content,
            sources: item.attributes.data_sources?.data?.map(
              ({ id, attributes: { title, url } }) => ({
                id,
                title,
                url,
              })
            ),
          })) ?? [],
      },
    }
  );

  const { data: chartData, isFetching } = useGetHabitatStats<
    {
      title: string;
      slug: string;
      background: string;
      totalArea: number;
      protectedArea: number;
      info?: string;
      sources?: { id: number; title: string; url: string }[];
      updatedAt: string;
    }[]
  >(
    {
      locale,
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      populate: {
        habitat: {
          // This part is for the English version only
          populate: {
            // This part is for the Spanish and French versions
            localizations: {
              fields: ['slug', 'name', 'locale'],
            },
          },
        },
      },
      'sort[year]': 'desc',
      'pagination[limit]': total_habitats,
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      fields: ['protected_area', 'total_area', 'updatedAt'],
      filters: {
        location: {
          code: location?.code,
        },
        environment: {
          slug: {
            $eq: tab === 'marine' ? tab : 'terrestrial',
          },
        },
      },
    },
    {
      query: {
        select: ({ data }) => {
          if (!data) {
            return [];
          }

          const parsedHabitats = new Set();
          const parsedData = data.reduce((parsed, entry) => {
            if (parsedHabitats.has(entry.attributes.habitat.data.attributes.slug)) {
              return parsed;
            }
            parsedHabitats.add(entry.attributes.habitat.data.attributes.slug);
            
            const stats = entry?.attributes;

            let habitat = stats?.habitat?.data.attributes;
            if (habitat.locale !== locale) {
              habitat = (habitat.localizations.data as HabitatStatHabitatData[]).find(
                (localization) => localization.attributes.locale === locale
              )?.attributes;
            }

            const metadata = habitatMetadatas?.find(({ slug }) => slug === habitat?.slug);

            parsed.push({
              title: habitat?.name,
              slug: habitat?.slug,
              background: HABITAT_CHART_COLORS[habitat?.slug],
              totalArea: stats.total_area,
              protectedArea: stats.protected_area,
              info: metadata?.info,
              sources: metadata?.sources,
              updatedAt: stats.updatedAt,
            });
            return parsed;
          },[]);

          return parsedData
            .sort((d1, d2) => {
              const keys = Object.keys(HABITAT_CHART_COLORS);
              return keys.indexOf(d1.slug) - keys.indexOf(d2.slug);
            })
            .filter(({ totalArea }) => totalArea !== 0);
        },
        placeholderData: [],
        refetchOnWindowFocus: false,
      },
    }
  );

  const { data: metadata } = useGetDataInfos(
    {
      locale,
      filters: {
        slug: `habitat-widget-${tab}`,
      },
      populate: 'data_sources',
    },
    {
      query: {
        select: ({ data }) =>
          data[0]
            ? {
                info: data[0].attributes.content,
                sources: data[0].attributes?.data_sources?.data?.map(
                  ({ id, attributes: { title, url } }) => ({
                    id,
                    title,
                    url,
                  })
                ),
              }
            : undefined,
      },
    }
  );

  return (
    <Widget
      title={t('proportion-habitat-within-protected-areas')}
      lastUpdated={chartData[0]?.updatedAt}
      noData={!chartData.length}
      loading={isFetching}
      info={metadata?.info}
      sources={metadata?.sources}
    >
      {chartData.map((chartData) => (
        <HorizontalBarChart
          key={chartData.slug}
          className="py-2"
          data={chartData}
          showTarget={false}
        />
      ))}
    </Widget>
  );
};

HabitatWidget.messages = [
  'containers.map-sidebar-main-panel',
  ...Widget.messages,
  ...HorizontalBarChart.messages,
];

export default HabitatWidget;
