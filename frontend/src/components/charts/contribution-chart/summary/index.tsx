import { useLocale, useTranslations } from 'next-intl';

import { formatKM, formatPercentage } from '@/lib/utils/formats';
import { Contribution } from '@/lib/utils/modelling-contributions';
import { FCWithMessages } from '@/types';

type ContributionSummaryProps = {
  contribution: Contribution;
  target?: number;
};

const ContributionSummary: FCWithMessages<ContributionSummaryProps> = ({
  contribution: { existing, added, total, totalPercentage },
  target,
}) => {
  const t = useTranslations('components.chart-contribution');
  const locale = useLocale();

  return (
    <p className="sr-only">
      {t('summary', {
        addedArea: formatKM(locale, added),
        protectedArea: formatKM(locale, existing + added),
        totalArea: formatKM(locale, total),
        percentage: formatPercentage(locale, totalPercentage),
      })}
      {target != null && ` ${t('summary-target', { percentage: target })}`}
    </p>
  );
};

ContributionSummary.messages = ['components.chart-contribution'];

export default ContributionSummary;
