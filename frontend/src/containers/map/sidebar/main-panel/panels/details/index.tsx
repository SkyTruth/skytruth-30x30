import { useCallback, useEffect, useMemo, useRef } from 'react';

import { useRouter } from 'next/router';

import { useAtomValue } from 'jotai';
import { useLocale, useTranslations } from 'next-intl';

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PAGES } from '@/constants/pages';
import { NEW_LOCS } from '@/constants/territories'; // TODO TECH-3174: Clean up
import { useMapSearchParams } from '@/containers/map/content/map/sync-settings';
import { locationsAtom } from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { useFeatureFlag } from '@/hooks/use-feature-flag'; // TODO TECH-3174: Clean up
import useMapDefaultLayers from '@/hooks/use-map-default-layers';
import useScrollPosition from '@/hooks/use-scroll-position';
import useMapLocationBounds from '@/hooks/useMapLocationBounds';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';
import { useGetLocations } from '@/types/generated/location';

import LocationSelector from '../../location-selector';

import CountriesList from './countries-list';
import DetailsButton from './details-button';
import MarineWidgets from './widgets/marine-widgets';
import SummaryWidgets from './widgets/summary-widgets';
import TerrestrialWidgets from './widgets/terrestrial-widgets';

const SidebarDetails: FCWithMessages = () => {
  const locale = useLocale();
  const t = useTranslations('containers.map-sidebar-main-panel');

  const containerRef = useRef<HTMLDivElement | null>(null);
  const containerScroll = useScrollPosition(containerRef);
  const locationsState = useAtomValue(locationsAtom);

  // TODO TECH-3174: Clean up
  const areTerritoriesActive = useFeatureFlag('are_territories_active');

  const {
    push,
    query: { locationCode = 'GLOB' },
  } = useRouter();
  const searchParams = useMapSearchParams();

  const [{ tab }, setSettings] = useSyncMapContentSettings();

  const { data: locationsData } = useGetLocations({
    locale,
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-ignore
    fields: ['name', 'name_es', 'name_fr', 'type'],
    filters: {
      code: locationCode,
    },
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-ignore
    populate: {
      members: {
        fields: ['code', 'name', 'name_es', 'name_fr'],
      },
      groups: {
        fields: ['code', 'name', 'name_es', 'name_fr'],
      },
    },
  });

  const locationNameField = useMemo(() => {
    let res = 'name';
    if (locale === 'es') {
      res = 'name_es';
    }
    if (locale === 'fr') {
      res = 'name_fr';
    }
    return res;
  }, [locale]);

  const memberCountries = useMemo(() => {
    const mappedLocs = locationsData?.data[0]?.attributes?.members?.data?.map(({ attributes }) => ({
      code: attributes?.code,
      name: attributes?.[locationNameField],
    }));

    if (areTerritoriesActive) {
      return mappedLocs;
    }

    return mappedLocs?.filter((loc) => !NEW_LOCS.has(loc?.code)); // TODO TECH-3174: Clean up NEW_LOCS filter
  }, [areTerritoriesActive, locationsData?.data, locationNameField]);

  const groupCountries = useMemo(() => {
    const mappedLocs = locationsData?.data[0]?.attributes?.groups?.data?.map(({ attributes }) => ({
      code: attributes?.code,
      name: attributes?.[locationNameField],
    }));

    if (areTerritoriesActive) {
      return mappedLocs;
    }

    return mappedLocs?.filter((loc) => !NEW_LOCS.has(loc?.code)); // TODO TECH-3174: Clean up NEW_LOCS filter
  }, [areTerritoriesActive, locationsData?.data, locationNameField]);

  const locationName = useMemo(() => {
    const locName = locationsData?.data[0]?.attributes?.[locationNameField];

    // TODO TECH-3174: Clean up
    if (areTerritoriesActive && groupCountries?.length > 0) {
      const sovereigns = groupCountries.filter((loc) => loc?.code[loc?.code?.length - 1] === '*');
      const sovLabels = sovereigns.reduce((label, sov, idx) => {
        if (idx === 0) {
          return label + `Territory of ${locationsState[sov.code.slice(0, -1)][locationNameField]}`;
        }
        return (
          label + ` also claimed by ${locationsState[sov.code.slice(0, -1)][locationNameField]}`
        );
      }, `${locName}, `);
      return sovLabels;
    }

    return locName;
  }, [areTerritoriesActive, groupCountries, locationNameField]);

  const handleLocationSelected = useCallback(
    (locationCode) => {
      push(`${PAGES.progressTracker}/${locationCode}?${searchParams.toString()}`);
    },
    [push, searchParams]
  );

  const handleTabChange = useCallback(
    (tab: string) => setSettings((prevSettings) => ({ ...prevSettings, tab })),
    [setSettings]
  );

  // Scroll to the top when the tab changes (whether that's initiated by clicking on the tab trigger
  // or programmatically via `setSettings` in a different component) or when the location changes
  useEffect(() => {
    containerRef.current?.scrollTo({ top: 0 });
  }, [tab, locationCode]);

  // Update the map's default layers based on the tab
  useMapDefaultLayers();

  // Update the map's position based on the location
  useMapLocationBounds();

  return (
    <Tabs value={tab} onValueChange={handleTabChange} className="flex h-full w-full flex-col">
      <div
        className={cn({
          'flex flex-shrink-0 gap-x-5 gap-y-2 border-b border-black bg-orange px-4 pt-4 md:px-8 md:pt-6':
            true,
          'flex-col': containerScroll === 0,
          'flex-row flex-wrap': containerScroll > 0,
        })}
      >
        <h1
          className={cn({
            'text-ellipsis font-black transition-all': true,
            'text-5xl': containerScroll === 0,
            'text-xl': containerScroll > 0,
          })}
        >
          {locationName}
        </h1>
        <LocationSelector
          className="flex-shrink-0"
          theme="orange"
          size={containerScroll > 0 ? 'small' : 'default'}
          onChange={handleLocationSelected}
        />
        {/* TODO TECH-3174: Clean up Feature flag checks */}
        {areTerritoriesActive && groupCountries?.length ? 'Related Groups' : ''}
        {areTerritoriesActive ? (
          <CountriesList
            className="w-full shrink-0"
            bgColorClassName="bg-orange"
            countries={groupCountries}
          />
        ) : null}
        {areTerritoriesActive && memberCountries?.length ? 'Territories' : ''}
        <CountriesList
          className="w-full shrink-0"
          bgColorClassName="bg-orange"
          countries={memberCountries}
        />
        <TabsList className="relative top-px mt-5 w-full flex-shrink-0">
          <TabsTrigger value="summary">{t('summary')}</TabsTrigger>
          <TabsTrigger value="terrestrial">{t('terrestrial')}</TabsTrigger>
          <TabsTrigger value="marine">{t('marine')}</TabsTrigger>
        </TabsList>
      </div>
      <div ref={containerRef} className="flex-grow overflow-y-auto">
        <TabsContent value="summary">
          <SummaryWidgets />
        </TabsContent>
        <TabsContent value="terrestrial">
          <TerrestrialWidgets />
        </TabsContent>
        <TabsContent value="marine">
          <MarineWidgets />
        </TabsContent>
      </div>
      <div className="shrink-0 border-t border-t-black bg-white px-4 py-5 md:px-8">
        <DetailsButton locationType={locationsData?.data[0]?.attributes.type} />
      </div>
    </Tabs>
  );
};

SidebarDetails.messages = [
  'containers.map-sidebar-main-panel',
  ...LocationSelector.messages,
  ...CountriesList.messages,
  ...DetailsButton.messages,
  ...SummaryWidgets.messages,
  ...MarineWidgets.messages,
];

export default SidebarDetails;
