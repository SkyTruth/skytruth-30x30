import { useState } from 'react';

import { Check, XCircle } from 'lucide-react';
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
}) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();
  const [searchTerm, setSearchTerm] = useState<string>('');

  const handleFiltering = (value: string, search: string) => {
    if (value.toLocaleLowerCase().includes(search.toLocaleLowerCase())) return 1;
    return 0;
  };

  return (
    <Command label={searchPlaceholder} className={cn(className)} filter={handleFiltering}>
      <CommandInput
        value={searchTerm}
        onValueChange={setSearchTerm}
        placeholder={searchPlaceholder}
      />
      <CommandEmpty>{t('no-result')}</CommandEmpty>
      <CommandGroup className="mt-4 max-h-64 overflow-y-auto">
        {filteredLocations.map(({ attributes }, idx) => {
          const { name, name_es, name_fr, code, type } = attributes;

          let locationName = name;
          if (locale === 'es') {
            locationName = name_es;
          }
          if (locale === 'fr') {
            locationName = name_fr;
          }

          const locationType = LocationType[type] || LocationType.country;
          const Selected = isCustomRegionTab ? XCircle : Check;

          return (
            <>
              <CommandItem key={code} value={locationName} onSelect={() => onSelected(code)}>
                <div className="flex w-full cursor-pointer justify-between gap-x-4">
                  <div className="flex text-base font-bold">
                    {selectedLocation.has(code) && (
                      <Selected className="relative top-1 mr-1 inline-block h-4 w-4 flex-shrink-0" />
                    )}
                    {locationName}
                  </div>
                  <span className="flex flex-shrink-0 items-center font-mono text-xs capitalize text-gray-300">
                    {t(locationType)}
                  </span>
                </div>
              </CommandItem>
              {dividerIndex && searchTerm.length === 0 && idx === dividerIndex ? (
                <hr className="w-full" />
              ) : null}
            </>
          );
        })}
      </CommandGroup>
    </Command>
  );
};

LocationDropdown.messages = ['containers.map-sidebar-main-panel'];

export default LocationDropdown;
