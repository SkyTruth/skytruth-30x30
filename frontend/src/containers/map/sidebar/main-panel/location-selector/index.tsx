import { useCallback, useMemo, useRef, useState } from 'react';

import { useRouter } from 'next/router';

import { useSetAtom } from 'jotai';
import { AlertTriangle, PlusCircle } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import Icon from '@/components/ui/icon';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { NEW_LOCS } from '@/constants/territories'; // TODO TECH-3174: Clean up
import { CUSTOM_REGION_CODE } from '@/containers/map/constants';
import { useSyncCustomRegion } from '@/containers/map/content/map/sync-settings';
import { popupAtom } from '@/containers/map/store';
import { useFeatureFlag } from '@/hooks/use-feature-flag'; // TODO TECH-3174: Clean up
import { cn } from '@/lib/classnames';
import GlobeIcon from '@/styles/icons/globe.svg';
import MagnifyingGlassIcon from '@/styles/icons/magnifying-glass.svg';
import { FCWithMessages } from '@/types';
import { useGetLocations } from '@/types/generated/location';
import {
  LocationGroupsDataItemAttributes,
  LocationListResponseDataItem,
} from '@/types/generated/strapi.schemas';

import LocationDropdown from './location-dropdown';
import LocationTypeToggle from './type-toggle';

export const FILTERS = {
  all: ['country', 'highseas', 'region', 'worldwide'],
  country: ['country'],
  regionsHighseas: ['region', 'highseas'],
  customRegion: ['country', 'highseas'],
};

const BUTTON_CLASSES =
  'font-mono text-xs font-semibold no-underline normal-case ring-offset-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2 transition-all px-0';

type LocationSelectorProps = {
  className?: HTMLDivElement['className'];
  theme: 'orange' | 'blue';
  isCustomRegionActive: boolean;
  sharedMarineAreaCountries: {
    code: string;
    name: string;
  }[];
  onChange: (locationCode: string) => void;
  isTerrestrial: boolean;
};

const LocationSelector: FCWithMessages<LocationSelectorProps> = ({
  className,
  theme,
  isCustomRegionActive,
  sharedMarineAreaCountries,
  onChange,
  isTerrestrial,
}) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();

  const {
    query: { locationCode = 'GLOB' },
  } = useRouter();

  const setPopup = useSetAtom(popupAtom);

  const [locationsFilter, setLocationsFilter] = useState<keyof typeof FILTERS>('all');
  const [locationPopoverOpen, setLocationPopoverOpen] = useState(false);

  const currentLocation = Array.isArray(locationCode) ? locationCode[0] : locationCode;
  const prevLocation = useRef(currentLocation !== CUSTOM_REGION_CODE ? currentLocation : 'GLOB');

  const [customRegionLocations, setCustomRegionLocations] = useSyncCustomRegion();

  // TODO TECH-3174: Clean up
  const areTerritoriesActive = useFeatureFlag('are_territories_active');

  // TODO TECH-3233 Clean up
  const isCustomRegionEnabled = useFeatureFlag('is_custom_region_active');

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

  const { data: locationsData } = useGetLocations(
    {
      locale,
      'pagination[limit]': -1,
      sort: `${locationNameField}:asc`,
    },
    {
      query: {
        placeholderData: { data: [] },
        select: ({ data }) => data,
      },
    }
  );

  const filtersSearchLabels = useMemo(
    () => ({
      all: t('search-country-region'),
      country: t('search-country'),
      regionsHighseas: t('search-region-high-seas'),
      customRegion: t('search-country'),
    }),
    [t]
  );

  const handleLocationsFilterChange = (value) => {
    setLocationsFilter(value);
  };

  const handleLocationSelected = useCallback(
    async (locationCode: LocationGroupsDataItemAttributes['code']) => {
      if (!isCustomRegionActive) setLocationPopoverOpen(false);
      setPopup({});
      onChange(locationCode.toUpperCase());
    },
    [setPopup, onChange, isCustomRegionActive]
  );

  const handleCustomRegionUpdated = useCallback(
    (code: string) => {
      if (code === 'clear') {
        setCustomRegionLocations(new Set());
      } else {
        const newLocs = new Set(customRegionLocations);
        if (customRegionLocations && customRegionLocations.has(code)) {
          newLocs.delete(code);
        } else {
          newLocs.add(code);
        }
        setCustomRegionLocations(newLocs);
      }
    },
    [customRegionLocations, setCustomRegionLocations]
  );

  const handleToggleCustomRegion = useCallback(() => {
    if (!isCustomRegionActive) {
      if (currentLocation !== CUSTOM_REGION_CODE) {
        prevLocation.current = currentLocation;
      }
      handleLocationSelected(CUSTOM_REGION_CODE);
    } else {
      if (locationsFilter === 'customRegion') {
        setLocationsFilter('all');
      }
      handleLocationSelected(prevLocation.current);
    }
  }, [
    isCustomRegionActive,
    prevLocation,
    handleLocationSelected,
    currentLocation,
    locationsFilter,
  ]);

  const reorderedLocations = useMemo(() => {
    const globalLocation = locationsData.find(({ attributes }) => attributes.type === 'worldwide');
    return [globalLocation, ...locationsData.filter(({ id }) => id !== globalLocation.id)].filter(
      Boolean
    );
  }, [locationsData]);

  const filteredLocations = useMemo(() => {
    if (!locationsFilter) {
      // TODO TECH-3174: Clean up
      return areTerritoriesActive
        ? reorderedLocations
        : reorderedLocations.filter(({ attributes }) => !NEW_LOCS.has(attributes.code));
    }
    let filtered = reorderedLocations.filter(
      ({ attributes }) =>
        // TODO TECH-3174: Clean up NEW_LOCS filter
        FILTERS[locationsFilter].includes(attributes.type) &&
        (areTerritoriesActive || !NEW_LOCS.has(attributes.code))
    );

    if (locationsFilter === 'customRegion') {
      if (!customRegionLocations?.size) return filtered;

      // Bit of a hack to add the "clear all" button to the custom regions list
      const clearAll = {
        attributes: {
          code: 'clear',
          name: t('clear-all'),
          name_es: t('clear-all'),
          name_fr: t('clear-all'),
        },
      } as LocationListResponseDataItem;

      const top = [clearAll];
      const bottom = [];
      for (const location of filtered) {
        const {
          attributes: { code },
        } = location;

        // Prevent adding soverigns to custom regions
        if (code.endsWith('*')) continue;

        if (customRegionLocations.has(code)) {
          top.push(location);
        } else {
          bottom.push(location);
        }
        filtered = [...top, ...bottom];
      }
    }
    return filtered;
  }, [locationsFilter, reorderedLocations, areTerritoriesActive, customRegionLocations, t]);

  return (
    <div className={cn('flex gap-4 gap-y-2', className, 'grid grid-cols-2')}>
      <Popover open={locationPopoverOpen} onOpenChange={setLocationPopoverOpen}>
        <PopoverTrigger asChild>
          <Button
            className={cn({ [BUTTON_CLASSES]: true }, 'h-auto justify-start py-0')}
            type="button"
            variant="text-link"
          >
            <Icon icon={MagnifyingGlassIcon} className="mr-2 h-4 w-4 pb-px" />
            {t('change-location')}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-96 max-w-screen" align="start">
          <LocationTypeToggle
            theme={theme}
            defaultValue={locationsFilter}
            value={locationsFilter}
            className="mb-4"
            onChange={handleLocationsFilterChange}
            isCustomRegionActive={isCustomRegionActive}
          />
          <LocationDropdown
            searchPlaceholder={filtersSearchLabels[locationsFilter]}
            filteredLocations={filteredLocations}
            selectedLocation={
              locationsFilter === 'customRegion'
                ? (customRegionLocations ?? new Set())
                : new Set([currentLocation])
            }
            isCustomRegionTab={locationsFilter === 'customRegion'}
            onSelected={
              locationsFilter === 'customRegion'
                ? handleCustomRegionUpdated
                : handleLocationSelected
            }
            dividerIndex={
              locationsFilter === 'customRegion' && customRegionLocations?.size
                ? customRegionLocations.size
                : null
            }
            sharedMarineAreaCountries={sharedMarineAreaCountries}
          />
        </PopoverContent>
      </Popover>
      {locationCode !== 'GLOB' && (
        <Button
          className={cn({ [BUTTON_CLASSES]: true }, 'h-auto justify-start py-0')}
          type="button"
          variant="text-link"
          onClick={() => handleLocationSelected('GLOB')}
        >
          <Icon icon={GlobeIcon} className="mr-2 h-4 w-4 pb-px" />
          {t('global-view')}
        </Button>
      )}
      {/* TODO TECH-3233: Clean up */}
      {isCustomRegionEnabled ? (
        <Button
          className={cn({ [BUTTON_CLASSES]: true }, 'col-start-1 h-auto justify-start py-0')}
          type="button"
          variant="text-link"
          onClick={handleToggleCustomRegion}
        >
          <PlusCircle
            className={cn(
              {
                'rotate-45': isCustomRegionActive,
              },
              'ease-&lsqb;cubic-bezier(0.87,_0,_0.13,_1)&rsqb; mr-2 h-4 w-4 pb-px transition-transform duration-300'
            )}
          />
          {isCustomRegionActive ? t('close-custom-region') : t('create-custom-region')}
        </Button>
      ) : null}

      {isCustomRegionActive && !isTerrestrial && sharedMarineAreaCountries.length > 1 ? (
        <Popover>
          <PopoverTrigger asChild>
            <Button
              className={cn({ [BUTTON_CLASSES]: true }, 'h-auto justify-start py-0')}
              type="button"
              variant="text-link"
            >
              <AlertTriangle className="mr-2 h-4 w-4 pb-px" />
              {t('overlapping-eez')}
            </Button>
          </PopoverTrigger>

          <PopoverContent className="w-96 max-w-screen" align="start">
            <div>{t('overlapping-eez-explainer') + ' ' + sharedMarineAreaCountries.join(', ')}</div>
          </PopoverContent>
        </Popover>
      ) : null}
    </div>
  );
};

LocationSelector.messages = [
  'containers.map-sidebar-main-panel',
  ...LocationTypeToggle.messages,
  ...LocationDropdown.messages,
];

export default LocationSelector;
