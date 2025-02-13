import { useCallback, useMemo } from 'react';

import { useRouter } from 'next/router';

import { useLocale, useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import Icon from '@/components/ui/icon';
import GlobalRegionalTable from '@/containers/map/content/details/tables/global-regional';
import NationalHighSeasTable from '@/containers/map/content/details/tables/national-highseas';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import CloseIcon from '@/styles/icons/close.svg';
import { FCWithMessages } from '@/types';
import { getGetLocationsQueryOptions, useGetLocations } from '@/types/generated/location';

const MapDetails: FCWithMessages = () => {
  const t = useTranslations('containers.map');
  const locale = useLocale();

  const [{ tab }, setSettings] = useSyncMapContentSettings();
  const {
    query: { locationCode = 'GLOB' },
  } = useRouter();

  const locationsQuery = useGetLocations(
    {
      locale,
      filters: {
        code: locationCode,
      },
    },
    {
      query: {
        ...getGetLocationsQueryOptions(
          {
            locale,
            filters: {
              code: locationCode,
            },
          },
          {
            query: {
              select: ({ data }) => data?.[0]?.attributes,
            },
          }
        ),
      },
    }
  );

  const handleOnCloseClick = useCallback(() => {
    setSettings((prevSettings) => ({ ...prevSettings, showDetails: false }));
  }, [setSettings]);

  const tablesSettings = useMemo(
    () => ({
      worldwideRegion: {
        locationTypes: ['worldwide', 'region'],
        component: GlobalRegionalTable,
        title: {
          worldwide: t('national-regional-levels'),
          region: t('location'),
          // Fallback to use in case the slug/code isn't defined, in order to prevent crashes
          fallback: {
            summary: t('environmental-conservation'),
            marine: t('marine-conservation'),
            terrestrial: t('terrestrial-conservation'),
          },
        },
      },
      countryHighseas: {
        locationTypes: ['country', 'highseas'],
        component: NationalHighSeasTable,
        title: {
          country: t('location'),
          highseas: t('high-seas'),
          // Fallback to use in case the slug/code isn't defined, in order to prevent crashes
          fallback: {
            summary: t('environmental-conservation'),
            marine: t('marine-conservation'),
            terrestrial: t('terrestrial-conservation'),
          },
        },
      },
    }),
    [t]
  );

  const table = useMemo(() => {
    // TODO: Improve to support more entries (although not needed right now)
    const tableSettings = tablesSettings.worldwideRegion.locationTypes.includes(
      locationsQuery.data?.type
    )
      ? tablesSettings.worldwideRegion
      : tablesSettings.countryHighseas;

    let locationName = locationsQuery.data?.name;
    if (locale === 'es') {
      locationName = locationsQuery.data?.name_es;
    }
    if (locale === 'fr') {
      locationName = locationsQuery.data?.name_fr;
    }

    const parsedTitle =
      tableSettings.title[locationsQuery.data?.type]?.replace('{location}', locationName) ||
      tableSettings.title.fallback[tab];

    return {
      title: parsedTitle,
      component: tableSettings.component,
    };
  }, [locale, tablesSettings, tab, locationsQuery.data]);

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-white px-4 py-4 md:px-6">
      <div className="mb-8 flex shrink-0 gap-8 md:justify-between">
        <span className="max-w-xl">
          <h2 className="text-4xl font-extrabold">{table.title}</h2>
        </span>
        <Button
          variant="text-link"
          className="m-0 cursor-pointer p-0 font-mono text-xs normal-case no-underline"
          onClick={handleOnCloseClick}
        >
          {t('close')}
          <Icon icon={CloseIcon} className="ml-2 h-3 w-3 pb-px" />
        </Button>
      </div>
      <div className="flex-grow overflow-hidden">
        <table.component />
      </div>
    </div>
  );
};

MapDetails.messages = [
  'containers.map',
  ...GlobalRegionalTable.messages,
  ...NationalHighSeasTable.messages,
];

export default MapDetails;
