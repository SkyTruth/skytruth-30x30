import { useTranslations } from 'next-intl';

import { FCWithMessages } from '@/types';

import { MAX_PERCENTAGE, toWidth } from '../helpers';

type ContributionAxisProps = {
  target?: number;
};

/** 0% and 100% at the ends, with the target label under the bar's target line */
const ContributionAxis: FCWithMessages<ContributionAxisProps> = ({ target }) => {
  const t = useTranslations('components.chart-contribution');

  return (
    <div className="relative flex justify-between text-xs">
      <span>{t('percentage', { percentage: 0 })}</span>
      {target != null && (
        <span
          className="absolute -translate-x-1/2 whitespace-nowrap font-bold text-orange-700"
          style={{ left: toWidth(target) }}
        >
          {t('target', { percentage: target })}
        </span>
      )}
      <span>{t('percentage', { percentage: MAX_PERCENTAGE })}</span>
    </div>
  );
};

ContributionAxis.messages = ['components.chart-contribution'];

export default ContributionAxis;
