import { useLocale, useTranslations } from 'next-intl';

import { FCWithMessages } from '@/types';
import { useGetLocations } from '@/types/generated/location';
import { Location, LocationListResponseDataItem } from '@/types/generated/strapi.schemas';

type MissingCountriesListProps = {
  countries: string[];
};

const MissingCountriesList: FCWithMessages<MissingCountriesListProps> = ({ countries }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();

  const { data: locations, isFetching } = useGetLocations<LocationListResponseDataItem[]>(
    {
      //@ts-ignore
      populate: {
        fields: ['name', 'name_es', 'name_fr'],
      },
      filters: {
        code: {
          $in: countries,
        },
      },
    },
    {
      query: {
        select: ({ data }) => data,
      },
    }
  );

  const getName = (location: Location) => {
    if (locale === 'es' && location.name_es) return location.name_es;
    if (locale === 'fr' && location.name_fr) return location.name_fr;
    return location.name;
  };

  if (countries.length === 0 || isFetching) {
    return null;
  }
  return (
    <div className="mt-2 text-xs">
      {'* ' + t('no-data-for') + ' '}
      {locations.map(
        (loc, idx) => getName(loc.attributes) + `${idx !== locations.length - 1 ? ', ' : ''}`
      )}
    </div>
  );
};

MissingCountriesList.messages = ['containers.map-sidebar-main-panel'];

export default MissingCountriesList;
