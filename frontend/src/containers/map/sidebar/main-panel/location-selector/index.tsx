import { useCallback, useMemo, useRef, useState } from 'react';

import { useRouter } from 'next/router';

import { useSetAtom } from 'jotai';
import { PlusCircle } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import Icon from '@/components/ui/icon';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { NEW_LOCS } from '@/constants/territories'; // TODO TECH-3174: Clean up
import { CUSTOM_REGION_CODE } from '@/containers/map/constants';
import { popupAtom } from '@/containers/map/store';
import { useFeatureFlag } from '@/hooks/use-feature-flag'; // TODO TECH-3174: Clean up
import { cn } from '@/lib/classnames';
import GlobeIcon from '@/styles/icons/globe.svg';
import MagnifyingGlassIcon from '@/styles/icons/magnifying-glass.svg';
import { FCWithMessages } from '@/types';
import { useGetLocations } from '@/types/generated/location';
import { LocationGroupsDataItemAttributes } from '@/types/generated/strapi.schemas';

import LocationDropdown from './location-dropdown';
import LocationTypeToggle from './type-toggle';

export const FILTERS = {
  all: ['country', 'highseas', 'region', 'worldwide'],
  country: ['country'],
  regionsHighseas: ['region', 'highseas'],
};

const BUTTON_CLASSES =
  'font-mono text-xs font-semibold no-underline normal-case ring-offset-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2 transition-all px-0';

type LocationSelectorProps = {
  className?: HTMLDivElement['className'];
  theme: 'orange' | 'blue';
  size?: 'default' | 'small';
  isCustomRegionActive: boolean;
  onChange: (locationCode: string) => void;
};

const LocationSelector: FCWithMessages<LocationSelectorProps> = ({
  className,
  theme,
  size = 'default',
  isCustomRegionActive,
  onChange,
}) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();

  const {
    query: { locationCode = 'GLOB' },
  } = useRouter();

  const setPopup = useSetAtom(popupAtom);

  const [locationsFilter, setLocationsFilter] = useState<keyof typeof FILTERS>('all');
  const [locationPopoverOpen, setLocationPopoverOpen] = useState(false);

  const code = Array.isArray(locationCode) ? locationCode[0] : locationCode;
  const prevLocation = useRef(code);

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

  const filtersSearchLabels = useMemo(
    () => ({
      all: t('search-country-region'),
      country: t('search-country'),
      regionsHighseas: t('search-region-high-seas'),
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

  const handleToggleCustomRegion = useCallback(() => {
    if (!isCustomRegionActive) {
      const code = Array.isArray(locationCode) ? locationCode[0] : locationCode;
      prevLocation.current = code;
      handleLocationSelected(CUSTOM_REGION_CODE);
    } else {
      handleLocationSelected(prevLocation.current);
    }
  }, [isCustomRegionActive, prevLocation, handleLocationSelected, locationCode]);

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
    <div className={cn('flex gap-4 gap-y-0', className, 'grid grid-cols-2')}>
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
          className={cn({ [BUTTON_CLASSES]: true, 'h-auto py-0': true }, 'justify-end')}
          type="button"
          variant="text-link"
          onClick={() => handleLocationSelected('GLOB')}
        >
          <Icon icon={GlobeIcon} className="mr-2 h-4 w-4 pb-px" />
          {t('global-view')}
        </Button>
      )}
      <Button
        className={cn(
          { [BUTTON_CLASSES]: true, 'h-auto py-0': true },
          'col-start-1, col-span-2 col-end-2 justify-start pb-2'
        )}
        type="button"
        variant="text-link"
        onClick={handleToggleCustomRegion}
      >
        <PlusCircle
          className={cn(
            { 'rotate-45': isCustomRegionActive },
            'ease-&lsqb;cubic-bezier(0.87,_0,_0.13,_1)&rsqb; mr-2 h-4 w-4 pb-px transition-transform duration-300'
          )}
        />
        {isCustomRegionActive ? t('close-custom-region') : t('create-custom-region')}
      </Button>
    </div>
  );
};

LocationSelector.messages = [
  'containers.map-sidebar-main-panel',
  ...LocationTypeToggle.messages,
  ...LocationDropdown.messages,
];

export default LocationSelector;
