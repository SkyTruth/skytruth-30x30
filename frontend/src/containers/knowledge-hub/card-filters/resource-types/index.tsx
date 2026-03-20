import { useAtom } from 'jotai';
import { useLocale, useTranslations } from 'next-intl';

import FiltersButton from '@/components/filters-button';
import { cardFiltersAtom } from '@/containers/knowledge-hub/store';
import { FCWithMessages } from '@/types';
import { useGetDataToolResourceTypes } from '@/types/generated/data-tool-resource-type';

const CardFiltersResourceTypes: FCWithMessages = (): JSX.Element => {
  const t = useTranslations('containers.knowledge-hub-card-filters');
  const locale = useLocale();

  const [filters, setFilters] = useAtom(cardFiltersAtom);

  const resourceTypesQuery = useGetDataToolResourceTypes(
    {
      locale,
    },
    {
      query: {
        select: ({ data }) => data.map(( item ) => item.name),
      },
    }
  );

  const handleFiltersChange = (field, value) => {
    setFilters((prevFilters) => ({
      ...prevFilters,
      [field]: value,
    }));
  };

  const options =
    resourceTypesQuery?.data?.map((resourceType) => ({
      name: resourceType,
      value: resourceType,
    })) || [];

  return (
    <div className="flex items-center font-mono text-xs font-semibold">
      <FiltersButton
        field="resourceType"
        options={options}
        values={filters?.resourceType}
        onChange={handleFiltersChange}
      />
      <span>{t('filter-by-resource-type')}</span>
    </div>
  );
};

CardFiltersResourceTypes.messages = [
  'containers.knowledge-hub-card-filters',
  ...FiltersButton.messages,
];

export default CardFiltersResourceTypes;
