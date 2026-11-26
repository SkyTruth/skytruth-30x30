import { ComponentProps } from 'react';

import ContributionChart from '@/components/charts/contribution-chart';
import TooltipButton from '@/components/tooltip-button';
import { Contribution } from '@/lib/utils/modelling-contributions';
import { FCWithMessages } from '@/types';

import type { StatStatus } from '../helpers';
import StatStatusMessage from '../stat-status-message';

export type StatBlockProps = {
  className?: string;
  title: string;
  contribution?: Contribution;
  target?: number;
  status?: StatStatus;
  tooltip?: ComponentProps<typeof TooltipButton>;
};

const StatBlock: FCWithMessages<StatBlockProps> = ({
  className,
  title,
  contribution,
  target,
  status = 'success',
  tooltip,
}) => {
  if (status === 'success' && !contribution) return null;

  return (
    <div className={className}>
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-base font-bold">{title}</h4>
        {tooltip && <TooltipButton side="right" {...tooltip} />}
      </div>
      <StatStatusMessage status={status} />
      {status === 'success' && (
        <ContributionChart className="pt-3" contribution={contribution} target={target} />
      )}
    </div>
  );
};

StatBlock.messages = [
  ...StatStatusMessage.messages,
  ...ContributionChart.messages,
  ...TooltipButton.messages,
];

export default StatBlock;
