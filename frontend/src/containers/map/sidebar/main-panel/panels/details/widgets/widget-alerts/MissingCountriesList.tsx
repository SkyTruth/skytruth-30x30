import { useTranslations } from 'next-intl';

import useNameField from '@/hooks/use-name-field';
import { FCWithMessages } from '@/types';
import { useGetLocations } from '@/types/generated/location';
import { LocationListResponseDataItem } from '@/types/generated/strapi.schemas';

type MissingCountriesListProps = {
  countries: string[];
};

const MissingCountriesList: FCWithMessages<MissingCountriesListProps> = ({ countries }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const nameField = useNameField();

  const { data: locations, isFetching } = useGetLocations<LocationListResponseDataItem[]>(
    {
      //@ts-ignore
      populate: {
        fields: ['name', 'name_es', 'name_fr', 'name_pt'],
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
        (loc, idx) => loc.attributes[nameField] + `${idx !== locations.length - 1 ? ', ' : ''}`
      )}
    </div>
  );
};

MissingCountriesList.messages = ['containers.map-sidebar-main-panel'];

export default MissingCountriesList;
