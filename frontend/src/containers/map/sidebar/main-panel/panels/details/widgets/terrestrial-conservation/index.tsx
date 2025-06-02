import { useMemo } from 'react';

import { useAtom } from 'jotai';
import { useLocale, useTranslations } from 'next-intl';

import ConservationChart from '@/components/charts/conservation-chart';
import { Button } from '@/components/ui/button';
import Icon from '@/components/ui/icon';
import Widget from '@/components/widget';
import { terrestrialDataDisclaimerDialogAtom } from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { formatKM, formatPercentage } from '@/lib/utils/formats';
import Notification from '@/styles/icons/notification.svg';
import { FCWithMessages } from '@/types';
import { useGetDataInfos } from '@/types/generated/data-info';
import { useGetProtectionCoverageStats } from '@/types/generated/protection-coverage-stat';
import type {
  LocationGroupsDataItemAttributes,
  ProtectionCoverageStatListResponseDataItem,
} from '@/types/generated/strapi.schemas';

type TerrestrialConservationWidgetProps = {
  location: LocationGroupsDataItemAttributes;
};

const TerrestrialConservationWidget: FCWithMessages<TerrestrialConservationWidgetProps> = ({
  location,
}) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();

  const [{ tab }, setSettings] = useSyncMapContentSettings();

  const [, setDisclaimerDialogOpen] = useAtom(terrestrialDataDisclaimerDialogAtom);

  const { data, isFetching } = useGetProtectionCoverageStats<
    ProtectionCoverageStatListResponseDataItem[]
  >(
    {
      locale,
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      populate: {
        location: {
          fields: ['code', 'total_terrestrial_area'],
        },
        environment: {
          fields: ['slug'],
        },
      },
      sort: 'year:desc',
      'pagination[pageSize]': 1,
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      fields: ['year', 'protected_area', 'updatedAt'],
      filters: {
        location: {
          code: {
            $eq: location?.code || 'GLOB',
          },
        },
        environment: {
          slug: {
            $eq: 'terrestrial',
          },
        },
      },
    },
    {
      query: {
        select: ({ data }) => data ?? [],
        placeholderData: [],
        refetchOnWindowFocus: false,
      },
    }
  );

  const aggregatedData = useMemo(() => {
    if (!data.length) return null;
    return {
      year: Number(data[0].attributes.year),
      protectedArea: data[0].attributes.protected_area,
    };
  }, [data]);

  const { data: metadata } = useGetDataInfos(
    {
      locale,
      filters: {
        slug: 'coverage-widget',
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

  const stats = useMemo(() => {
    if (!aggregatedData) return null;

    const totalArea = Number(location.total_terrestrial_area);
    const { protectedArea } = aggregatedData;
    const percentageFormatted = formatPercentage(locale, (protectedArea / totalArea) * 100, {
      displayPercentageSign: false,
    });
    const protectedAreaFormatted = formatKM(locale, protectedArea);
    const totalAreaFormatted = formatKM(locale, totalArea);

    return {
      protectedPercentage: percentageFormatted,
      protectedArea: protectedAreaFormatted,
      totalArea: totalAreaFormatted,
    };
  }, [locale, location, aggregatedData]);

  const noData = useMemo(() => {
    if (!aggregatedData) {
      return true;
    }
    return false;
  }, [aggregatedData]);

  return (
    <Widget
      title={t('terrestrial-conservation-coverage')}
      lastUpdated={data[data.length - 1]?.attributes.updatedAt}
      noData={noData}
      loading={isFetching}
      info={metadata?.info}
      sources={metadata?.sources}
      tooltipExtraContent={
        <Button
          type="button"
          variant="text-link"
          size="sm"
          className="-mt-3 block px-0 py-0 text-left text-xs font-bold normal-case text-red"
          onClick={() => setDisclaimerDialogOpen(true)}
        >
          <Icon icon={Notification} className="mr-1.5 inline-block h-4 w-4" />

          {t('data-disclaimer')}
        </Button>
      }
    >
      {stats && (
        <div className="mb-4 mt-6 flex flex-col">
          <span className="space-x-1">
            {t.rich('terrestrial-protected-percentage', {
              b1: (chunks) => <span className="text-[64px] font-bold leading-[90%]">{chunks}</span>,
              b2: (chunks) => <span className="text-lg">{chunks}</span>,
              percentage: stats?.protectedPercentage,
            })}
          </span>
          <span className="space-x-1 text-xs">
            <span>
              {t('terrestrial-protected-area', {
                protectedArea: stats?.protectedArea,
                totalArea: stats?.totalArea,
              })}
            </span>
          </span>
        </div>
      )}
      {tab !== 'terrestrial' && (
        <Button
          variant="white"
          size="full"
          className="mt-5 flex h-10 px-5 md:px-8"
          onClick={() => setSettings((settings) => ({ ...settings, tab: 'terrestrial' }))}
        >
          <span className="font-mono text-xs font-semibold normal-case">
            {t('explore-terrestrial-conservation')}
          </span>
        </Button>
      )}
    </Widget>
  );
};

TerrestrialConservationWidget.messages = [
  'containers.map-sidebar-main-panel',
  ...Widget.messages,
  ...ConservationChart.messages,
];

export default TerrestrialConservationWidget;
