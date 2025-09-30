import { useCallback, useEffect, useMemo, useRef } from 'react';

import { useRouter } from 'next/router';

import { useSetAtom } from 'jotai';
import { useLocale, useTranslations } from 'next-intl';

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PAGES } from '@/constants/pages';
import { NEW_LOCS } from '@/constants/territories'; // TODO TECH-3174: Clean up
import { CUSTOM_REGION_CODE } from '@/containers/map/constants';
import {
  useMapSearchParams,
  useSyncCustomRegion,
} from '@/containers/map/content/map/sync-settings';
import { sharedMarineAreaCountriesAtom } from '@/containers/map/store';
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
import EmptyRegionWidget from './widgets/empty-region-widget';
import MarineWidgets from './widgets/marine-widgets';
import SummaryWidgets from './widgets/summary-widgets';
import TerrestrialWidgets from './widgets/terrestrial-widgets';

const SidebarDetails: FCWithMessages = () => {
  const locale = useLocale();
  const t = useTranslations('containers.map-sidebar-main-panel');

  const containerRef = useRef<HTMLDivElement | null>(null);
  const containerScroll = useScrollPosition(containerRef);

  // TODO TECH-3174: Clean up
  const areTerritoriesActive = useFeatureFlag('are_territories_active');

  const {
    push,
    query: { locationCode = 'GLOB' },
  } = useRouter();

  const [customRegionLocations] = useSyncCustomRegion();
  const searchParams = useMapSearchParams();
  const [{ tab }, setSettings] = useSyncMapContentSettings();

  const setSharedMarineAreasCountries = useSetAtom(sharedMarineAreaCountriesAtom);

  const isCustomRegion = locationCode === CUSTOM_REGION_CODE;
  const location =
    isCustomRegion && customRegionLocations
      ? [...[...customRegionLocations].map((loc) => loc.toUpperCase()), locationCode]
      : [locationCode];

  const { data: locationsData } = useGetLocations(
    {
      locale,
      // @ts-ignore
      fields: ['name', 'name_es', 'name_fr', 'type', 'code', 'has_shared_marine_area'],
      filters: {
        code: {
          $in: location,
        },
      },
      // @ts-ignore
      ...(!isCustomRegion
        ? {
            populate: {
              members: {
                fields: ['code', 'name', 'name_es', 'name_fr'],
              },
              groups: {
                fields: ['code', 'name', 'name_es', 'name_fr'],
              },
            },
          }
        : {}),
    },
    {
      query: {
        placeholderData: { data: [] },
      },
    }
  );

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

  const mapLocationRelations = useCallback(
    (relation: string) => {
      const mappedLocs = locationsData?.data[0]?.attributes[relation]?.data?.map(
        ({ attributes }) => ({
          code: attributes?.code,
          name: attributes?.[locationNameField],
        })
      );

      if (areTerritoriesActive) {
        return mappedLocs;
      }

      return mappedLocs?.filter((loc) => !NEW_LOCS.has(loc?.code)); // TODO TECH-3174: Clean up NEW_LOCS filter
    },
    [areTerritoriesActive, locationsData?.data, locationNameField]
  );

  const titleCountry = useMemo(() => {
    if (isCustomRegion) {
      return locationsData?.data?.find((loc) => loc?.attributes.code === CUSTOM_REGION_CODE);
    }
    return locationsData?.data[0];
  }, [locationsData, isCustomRegion]);

  const [memberCountries, sharedMarineAreaCountries] = useMemo(() => {
    if (!isCustomRegion) {
      return [mapLocationRelations('members'), []];
    }
    const members = [];
    const hasSharedMarineArea = [];
    for (const country of locationsData?.data) {
      if (country.attributes.code !== CUSTOM_REGION_CODE) {
        members.push({
          code: country.attributes.code,
          name: country.attributes[locationNameField],
        });
        if (country.attributes.has_shared_marine_area) {
          hasSharedMarineArea.push(country.attributes[locationNameField]);
        }
      }
    }
    return [members, hasSharedMarineArea];
  }, [mapLocationRelations, isCustomRegion, locationNameField, locationsData]);

  setSharedMarineAreasCountries(sharedMarineAreaCountries);

  const sovereignCountries = useMemo(() => {
    if (isCustomRegion) {
      return [];
    }
    const groupCountries = mapLocationRelations('groups');
    return groupCountries?.filter((loc) => loc?.code[loc?.code?.length - 1] === '*');
  }, [mapLocationRelations, isCustomRegion]);

  const handleLocationSelected = useCallback(
    (locationCode) => {
      push(
        `${PAGES.progressTracker}/${locationCode}?${decodeURIComponent(searchParams.toString())}`
      );
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
          'flex-wrap': containerScroll > 0,
        })}
      >
        <h1
          className={cn({
            'text-ellipsis font-black transition-all': true,
            'min-h-[3rem] text-5xl': containerScroll === 0,
            'min-h-[1.75rem] text-xl': containerScroll > 0,
          })}
        >
          {titleCountry?.attributes?.[locationNameField]}
        </h1>
        <LocationSelector
          theme="orange"
          isCustomRegionActive={isCustomRegion}
          sharedMarineAreaCountries={sharedMarineAreaCountries}
          onChange={handleLocationSelected}
          isTerrestrial={tab === 'terrestrial'}
          size={containerScroll > 0 && 'size'}
        />
        {/* TODO TECH-3174: Clean up Feature flag checks */}
        {areTerritoriesActive && sovereignCountries?.length ? t('claimed-by') : ''}
        {areTerritoriesActive ? (
          <CountriesList
            className="w-full shrink-0"
            bgColorClassName="bg-orange"
            countries={sovereignCountries}
          />
        ) : null}
        {areTerritoriesActive && memberCountries?.length ? t('includes') : ''}
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
          {isCustomRegion && !customRegionLocations?.size ? (
            <EmptyRegionWidget />
          ) : (
            <SummaryWidgets />
          )}
        </TabsContent>
        <TabsContent value="terrestrial">
          {isCustomRegion && !customRegionLocations?.size ? (
            <EmptyRegionWidget />
          ) : (
            <TerrestrialWidgets />
          )}
        </TabsContent>
        <TabsContent value="marine">
          {isCustomRegion && !customRegionLocations?.size ? (
            <EmptyRegionWidget />
          ) : (
            <MarineWidgets />
          )}
        </TabsContent>
      </div>
      <div className="shrink-0 border-t border-t-black bg-white px-4 py-5 md:px-8">
        <DetailsButton
          disabled={isCustomRegion && !customRegionLocations?.size}
          locationType={titleCountry?.attributes.type}
        />
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
