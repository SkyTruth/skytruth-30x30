import { useTranslations } from 'next-intl';

import useLocationName from '@/hooks/use-location-name';
import { FCWithMessages } from '@/types';
import { useGetLocations } from '@/types/generated/location';
import { Location } from '@/types/generated/strapi.schemas';

type MissingCountriesListProps = {
  countries: string[];
};

const MissingCountriesList: FCWithMessages<MissingCountriesListProps> = ({ countries }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const getLocationName = useLocationName();

  const { data: locations, isFetching } = useGetLocations<Location[]>(
    {
      //@ts-ignore
      populate: {
        fields: ['code', 'type'],
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

  if (countries.length === 0 || isFetching) {
    return null;
  }
  return (
    <div className="mt-2 text-xs">
      {'* ' + t('no-data-for') + ' '}
      {locations.map(
        (loc, idx) => getLocationName(loc) + `${idx !== locations.length - 1 ? ', ' : ''}`
      )}
    </div>
  );
};

MissingCountriesList.messages = [
  'containers.map-sidebar-main-panel',
  // Required by the `useLocationName` hook
  'locations',
];

export default MissingCountriesList;
