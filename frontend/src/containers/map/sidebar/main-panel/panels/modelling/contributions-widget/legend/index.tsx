import { useTranslations } from 'next-intl';

import { FCWithMessages } from '@/types';

import LegendItem from './item';

const ContributionLegend: FCWithMessages = () => {
  const t = useTranslations('containers.map-sidebar-main-panel');

  return (
    <ul aria-hidden className="flex gap-8 font-mono text-xs">
      <LegendItem className="bg-existing-area">{t('existing-area')}</LegendItem>
      <LegendItem className="bg-blue-700">{t('added-area')}</LegendItem>
    </ul>
  );
};

ContributionLegend.messages = ['containers.map-sidebar-main-panel'];

export default ContributionLegend;
