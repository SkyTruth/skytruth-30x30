import { useRouter } from 'next/router';

import { Check } from 'lucide-react';
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
import { useGetLocations } from '@/types/generated/location';
import { LocationListResponseDataItem } from '@/types/generated/strapi.schemas';

type LocationDropdownProps = {
  className?: HTMLDivElement['className'];
  searchPlaceholder?: string;
  locations: LocationListResponseDataItem[];
  onSelected: (code: string) => void;
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
  locations,
  onSelected,
}) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();

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
        queryKey: ['locations', locationCode],
        select: ({ data }) =>
          data?.find(({ attributes: { code } }) => code === (locationCode || 'GLOB'))?.attributes,
      },
    }
  );

  const handleFiltering = (value: string, search: string) => {
    if (value.toLocaleLowerCase().includes(search.toLocaleLowerCase())) return 1;
    return 0;
  };

  return (
    <Command label={t('search-country-region')} className={cn(className)} filter={handleFiltering}>
      <CommandInput placeholder={searchPlaceholder} />
      <CommandEmpty>{t('no-result')}</CommandEmpty>
      <CommandGroup className="mt-4 max-h-64 overflow-y-auto">
        {locations.map(({ attributes }) => {
          const { name, name_es, name_fr, code, type } = attributes;

          let locationName = name;
          if (locale === 'es') {
            locationName = name_es;
          }
          if (locale === 'fr') {
            locationName = name_fr;
          }

          const locationType = LocationType[type] || LocationType.country;

          return (
            <CommandItem key={code} value={locationName} onSelect={() => onSelected(code)}>
              <div className="flex w-full cursor-pointer justify-between gap-x-4">
                <div className="flex text-base font-bold">
                  {locationsQuery.data?.code === code && (
                    <Check className="relative top-1 mr-1 inline-block h-4 w-4 flex-shrink-0" />
                  )}
                  {locationName}
                </div>
                <span className="flex flex-shrink-0 items-center font-mono text-xs capitalize text-gray-300">
                  {t(locationType)}
                </span>
              </div>
            </CommandItem>
          );
        })}
      </CommandGroup>
    </Command>
  );
};

LocationDropdown.messages = ['containers.map-sidebar-main-panel'];

export default LocationDropdown;
