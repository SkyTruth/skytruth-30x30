import { useCallback, useEffect, useMemo, useState } from 'react';

import { useRouter } from 'next/router';

import { useSetAtom } from 'jotai';
import { useLocale, useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import Icon from '@/components/ui/icon';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { NEW_LOCS } from '@/constants/territories'; // TODO TECH-3174: Clean up
import { locationsAtom, popupAtom } from '@/containers/map/store';
import { useFeatureFlag } from '@/hooks/use-feature-flag'; // TODO TECH-3174: Clean up
import { cn } from '@/lib/classnames';
import GlobeIcon from '@/styles/icons/globe.svg';
import MagnifyingGlassIcon from '@/styles/icons/magnifying-glass.svg';
import { FCWithMessages } from '@/types';
import { useGetLocations } from '@/types/generated/location';
import { Location, LocationGroupsDataItemAttributes } from '@/types/generated/strapi.schemas';

import LocationDropdown from './location-dropdown';
import LocationTypeToggle from './type-toggle';

export const FILTERS = {
  all: ['country', 'highseas', 'region', 'worldwide'],
  countryHighseas: ['country', 'highseas'],
  regions: ['region'],
};

const BUTTON_CLASSES =
  'font-mono text-xs px-0 font-semibold no-underline normal-case ring-offset-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2 transition-all';

type LocationSelectorProps = {
  className?: HTMLDivElement['className'];
  theme: 'orange' | 'blue';
  size?: 'default' | 'small';
  onChange: (locationCode: string) => void;
};

const LocationSelector: FCWithMessages<LocationSelectorProps> = ({
  className,
  theme,
  size = 'default',
  onChange,
}) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();

  const {
    query: { locationCode = 'GLOB' },
  } = useRouter();

  const setLocations = useSetAtom(locationsAtom);
  const setPopup = useSetAtom(popupAtom);

  const [locationsFilter, setLocationsFilter] = useState<keyof typeof FILTERS>('all');
  const [locationPopoverOpen, setLocationPopoverOpen] = useState(false);

  // TODO TECH-3174: Clean up
  const areTerritoriesActive = useFeatureFlag('are_territories_active');

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

  useEffect(() => {
    if (locationsData?.length) {
      const mappedLocs = locationsData.reduce(
        (acc, loc) => {
          acc[loc.attributes.code] = loc.attributes;
          return acc;
        },
        {} as { code: Location }
      );
      setLocations(mappedLocs);
    }
  }, [locationsData, setLocations]);

  const filtersSearchLabels = useMemo(
    () => ({
      all: t('search-country-region'),
      countryHighseas: t('search-country-high-seas'),
      regions: t('search-region'),
    }),
    [t]
  );

  const handleLocationsFilterChange = (value) => {
    setLocationsFilter(value);
  };

  const handleLocationSelected = useCallback(
    async (locationCode: LocationGroupsDataItemAttributes['code']) => {
      setLocationPopoverOpen(false);
      setPopup({});
      onChange(locationCode.toUpperCase());
    },
    [setPopup, onChange]
  );

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
    return reorderedLocations.filter(
      ({ attributes }) =>
        // TODO TECH-3174: Clean up NEW_LOCS filter
        FILTERS[locationsFilter].includes(attributes.type) &&
        (areTerritoriesActive || !NEW_LOCS.has(attributes.code))
    );
  }, [locationsFilter, reorderedLocations, areTerritoriesActive]);

  return (
    <div className={cn('flex gap-3.5', className)}>
      <Popover open={locationPopoverOpen} onOpenChange={setLocationPopoverOpen}>
        <PopoverTrigger asChild>
          <Button
            className={cn({ [BUTTON_CLASSES]: true, 'h-auto py-0': size === 'small' })}
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
          />
          <LocationDropdown
            searchPlaceholder={filtersSearchLabels[locationsFilter]}
            locations={filteredLocations}
            onSelected={handleLocationSelected}
          />
        </PopoverContent>
      </Popover>
      {locationCode !== 'GLOB' && (
        <Button
          className={cn({ [BUTTON_CLASSES]: true, 'h-auto py-0': size === 'small' })}
          type="button"
          variant="text-link"
          onClick={() => handleLocationSelected('GLOB')}
        >
          <Icon icon={GlobeIcon} className="mr-2 h-4 w-4 pb-px" />
          {t('global-view')}
        </Button>
      )}
    </div>
  );
};

LocationSelector.messages = [
  'containers.map-sidebar-main-panel',
  ...LocationTypeToggle.messages,
  ...LocationDropdown.messages,
];

export default LocationSelector;
