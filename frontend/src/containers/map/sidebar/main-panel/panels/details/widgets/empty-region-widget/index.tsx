import { PlusCircle } from 'lucide-react';
import { useTranslations } from 'next-intl';

import Icon from '@/components/ui/icon';
import Widget from '@/components/widget';
import MagnifyingGlassIcon from '@/styles/icons/magnifying-glass.svg';
import { FCWithMessages } from '@/types';

const EmptyRegionWidget: FCWithMessages = () => {
  const t = useTranslations('containers.map-sidebar-main-panel');

  const EmptyCustomRegion = (
    <span className="text-left text-sm">
      {t.rich('empty-custom-region', {
        addIcon: () => <PlusCircle className="inline h-4 w-4 pb-px" />,
        searchIcon: () => <Icon icon={MagnifyingGlassIcon} className="inline h-4 w-4 pb-px" />,
      })}
    </span>
  );

  return (
    <Widget
      title={t('add-country-custom-region')}
      className="text-left md:px-7"
      noData
      noDataMessage={EmptyCustomRegion}
      noDataClassName="text-left"
    />
  );
};

EmptyRegionWidget.messages = ['containers.map-sidebar-main-panel'];

export default EmptyRegionWidget;
