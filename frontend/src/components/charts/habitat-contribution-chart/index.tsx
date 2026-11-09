import { useLocale, useTranslations } from 'next-intl';

import {
  AddedPercentageBadge,
  ContributionBar,
  MAX_PERCENTAGE,
  ProtectedAreaText,
} from '@/components/charts/contribution-chart/parts';
import { formatPercentage } from '@/lib/utils/formats';
import { Contribution } from '@/lib/utils/modelling-contributions';
import { FCWithMessages } from '@/types';

type HabitatContributionChartProps = {
  className?: string;
  title: string;
  color: string;
  contribution: Contribution;
};

/**
 * One habitat row under "Habitat Protection" in the Conservation Builder panel: the habitat
 * name with its protected percentage and "+X%", a bar of the existing and added area, and
 * the protected km² of the habitat's extent
 */
const HabitatContributionChart: FCWithMessages<HabitatContributionChartProps> = ({
  className,
  title,
  color,
  contribution,
}) => {
  const t = useTranslations('components.chart-contribution');
  const locale = useLocale();

  const { added, addedPercentage, totalPercentage } = contribution;

  return (
    <div className={className}>
      <div className="flex items-center justify-between gap-4">
        <span className="text-base font-bold">{title}</span>
        <div className="flex items-center gap-2 font-mono">
          <span className="pt-[0.2em] text-base font-bold leading-none">
            {formatPercentage(locale, totalPercentage)}
          </span>
          {added > 0 && (
            <AddedPercentageBadge
              className="pb-0 pt-[0.2em] text-sm"
              percentage={addedPercentage}
            />
          )}
        </div>
      </div>
      <div className="flex items-center gap-1 pt-2 font-mono">
        <ContributionBar className="flex-1" contribution={contribution} existingColor={color} />
        <span className="text-xs">{t('percentage', { percentage: MAX_PERCENTAGE })}</span>
      </div>
      <ProtectedAreaText className="pt-2 font-mono" contribution={contribution} />
    </div>
  );
};

HabitatContributionChart.messages = ['components.chart-contribution'];

export default HabitatContributionChart;
