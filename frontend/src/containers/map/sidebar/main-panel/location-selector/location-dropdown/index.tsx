import { useCallback, useMemo, useState } from 'react';

import { AlertTriangle, Check, XCircle } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';

import {
  Command,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandEmpty,
} from '@/components/ui/command';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';
import { LocationListResponseDataItem } from '@/types/generated/strapi.schemas';

type LocationDropdownProps = {
  className?: HTMLDivElement['className'];
  searchPlaceholder?: string;
  filteredLocations: LocationListResponseDataItem[];
  selectedLocation: Set<string>;
  isCustomRegionTab: boolean;
  onSelected: (code: string) => void;
  dividerIndex?: number;
  sharedMarineAreaCountries: {
    code: string;
    name: string;
  }[];
};

enum LocationType {
  country = 'country',
  region = 'region',
  highseas = 'highseas',
  worldwide = 'worldwide',
}

const LocationDropdown: FCWithMessages<LocationDropdownProps> = ({
  className,
  searchPlaceholder = 'Search',
  filteredLocations,
  selectedLocation,
  isCustomRegionTab,
  onSelected,
  dividerIndex,
  sharedMarineAreaCountries,
}) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();
  const [searchTerm, setSearchTerm] = useState<string>('');

  const normalize = (s: string) => s.normalize?.('NFKD').toLowerCase() || s.toLowerCase();

  const getName = useCallback(
    (location: LocationListResponseDataItem['attributes']) => {
      if (locale === 'es' && location.name_es) return location.name_es;
      if (locale === 'fr' && location.name_fr) return location.name_fr;
      return location.name;
    },
    [locale]
  );

  const visibleLocations = useMemo(() => {
    if (!searchTerm) return filteredLocations;

    const query = normalize(searchTerm);
    return filteredLocations.filter(({ attributes }) => {
      const name = getName(attributes);
      return normalize(name).includes(query);
    });
  }, [filteredLocations, searchTerm, getName]);

  return (
    <Command label={searchPlaceholder} className={cn(className)} shouldFilter={false}>
      <CommandInput
        value={searchTerm}
        onValueChange={setSearchTerm}
        placeholder={searchPlaceholder}
      />
      <CommandEmpty>{t('no-result')}</CommandEmpty>
      <CommandGroup className="mt-4 max-h-64 overflow-y-auto">
        {visibleLocations.map(({ attributes }, idx) => {
          const { code, type } = attributes;
          const locationName = getName(attributes);

          const locationType = LocationType[type] || LocationType.country;
          const Selected = isCustomRegionTab ? XCircle : Check;

          return (
            <div key={code}>
              <CommandItem value={locationName} onSelect={() => onSelected(code)}>
                <div className="flex w-full cursor-pointer justify-between gap-x-4">
                  <div className="flex text-base font-bold">
                    {selectedLocation.has(code) ? (
                      <Selected className="relative top-1 mr-1 inline-block h-4 w-4 flex-shrink-0" />
                    ) : !selectedLocation.has(code) &&
                      sharedMarineAreaCountries.length > 0 &&
                      attributes.has_shared_marine_area ? (
                      <AlertTriangle
                        color="#d60909"
                        className="relative top-1 mr-1 inline-block h-4 w-4 flex-shrink-0"
                      />
                    ) : null}
                    {locationName}
                  </div>
                  <span className="flex flex-shrink-0 items-center font-mono text-xs capitalize text-gray-300">
                    {t(locationType)}
                  </span>
                </div>
              </CommandItem>
              {dividerIndex !== null && searchTerm.length === 0 && idx === dividerIndex ? (
                <hr className="w-full" />
              ) : null}
            </div>
          );
        })}
      </CommandGroup>
    </Command>
  );
};

LocationDropdown.messages = ['containers.map-sidebar-main-panel'];

export default LocationDropdown;
