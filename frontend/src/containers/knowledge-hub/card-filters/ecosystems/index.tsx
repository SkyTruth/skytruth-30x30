import { useAtom } from 'jotai';
import { useLocale, useTranslations } from 'next-intl';

import FiltersButton from '@/components/filters-button';
import { cardFiltersAtom } from '@/containers/knowledge-hub/store';
import { FCWithMessages } from '@/types';
import { useGetDataToolEcosystems } from '@/types/generated/data-tool-ecosystem';

const CardFiltersEcosystems: FCWithMessages = (): JSX.Element => {
  const t = useTranslations('containers.knowledge-hub-card-filters');
  const locale = useLocale();

  const [filters, setFilters] = useAtom(cardFiltersAtom);

  const ecosystemsQuery = useGetDataToolEcosystems(
    {
      locale,
    },
    {
      query: {
        select: ({ data }) => data.map((item) => item.name),
      },
    }
  );

  const options =
    ecosystemsQuery?.data?.map((ecosystem) => ({ name: ecosystem, value: ecosystem })) || [];

  const handleFiltersChange = (field, value) => {
    setFilters((prevFilters) => ({
      ...prevFilters,
      [field]: value,
    }));
  };

  return (
    <div className="flex items-center font-mono text-xs font-semibold">
      <FiltersButton
        field="ecosystem"
        options={options}
        values={filters?.ecosystem}
        onChange={handleFiltersChange}
      />
      <span>{t('filter-by-ecosystem')}</span>
    </div>
  );
};

CardFiltersEcosystems.messages = [
  'containers.knowledge-hub-card-filters',
  ...FiltersButton.messages,
];

export default CardFiltersEcosystems;
