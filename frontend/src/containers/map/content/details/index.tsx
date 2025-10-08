import { useCallback, useMemo } from 'react';

import { useRouter } from 'next/router';

import { useLocale, useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import Icon from '@/components/ui/icon';
import GlobalRegionalTable from '@/containers/map/content/details/tables/global-regional';
import NationalHighSeasTable from '@/containers/map/content/details/tables/national-highseas';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import useNameField from '@/hooks/use-name-field';
import CloseIcon from '@/styles/icons/close.svg';
import { FCWithMessages } from '@/types';
import { getGetLocationsQueryOptions, useGetLocations } from '@/types/generated/location';

const MapDetails: FCWithMessages = () => {
  const t = useTranslations('containers.map');
  const locale = useLocale();
  const nameField = useNameField();

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
        locationTypes: ['worldwide', 'region', 'custom_region'],
        component: GlobalRegionalTable,
        title: {
          summary: {
            worldwide: t('environmental-conservation-national-regional-levels'),
            region: t('environmental-conservation-location'),
            // Fallback to use in case the slug/code isn't defined, in order to prevent crashes
            fallback: t('environmental-conservation'),
          },
          marine: {
            worldwide: t('marine-conservation-national-regional-levels'),
            region: t('marine-conservation-location'),
            // Fallback to use in case the slug/code isn't defined, in order to prevent crashes
            fallback: t('marine-conservation'),
          },
          terrestrial: {
            worldwide: t('terrestrial-conservation-national-regional-levels'),
            region: t('terrestrial-conservation-location'),
            // Fallback to use in case the slug/code isn't defined, in order to prevent crashes
            fallback: t('terrestrial-conservation'),
          },
        },
      },
      countryHighseas: {
        locationTypes: ['country', 'highseas'],
        component: NationalHighSeasTable,
        title: {
          summary: {
            country: t('environmental-conservation-location'),
            highseas: t('environmental-conservation-high-seas'),
            // Fallback to use in case the slug/code isn't defined, in order to prevent crashes
            fallback: t('environmental-conservation'),
          },
          marine: {
            country: t('marine-conservation-location'),
            highseas: t('marine-conservation-high-seas'),
            // Fallback to use in case the slug/code isn't defined, in order to prevent crashes
            fallback: t('marine-conservation'),
          },
          terrestrial: {
            country: t('terrestrial-conservation-location'),
            highseas: t('terrestrial-conservation-high-seas'),
            // Fallback to use in case the slug/code isn't defined, in order to prevent crashes
            fallback: t('terrestrial-conservation'),
          },
        },
      },
    }),
    [t]
  );

  const table = useMemo(() => {
    const type = locationsQuery.data?.type;
    let selectedTable = tablesSettings.worldwideRegion;

    for (const table in tablesSettings) {
      if (tablesSettings[table].locationTypes.includes(type)) {
        selectedTable = tablesSettings[table];
      }
    }

    const locationName = locationsQuery.data?.[nameField];

    const parsedTitle =
      selectedTable.title[tab][locationsQuery.data?.type]?.replace('{location}', locationName) ||
      selectedTable.title[tab].fallback;

    return {
      title: parsedTitle,
      component: selectedTable.component,
    };
  }, [tablesSettings, tab, locationsQuery.data, nameField]);

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
