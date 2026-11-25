import { cn } from '@/lib/classnames';
import { Contribution } from '@/lib/utils/modelling-contributions';

import { toWidth } from '../helpers';

type ContributionBarProps = {
  className?: string;
  contribution: Contribution;
  // Color of the existing area; gray when unset
  existingColor?: string;
  // Target line position in %; no line when unset
  target?: number;
};

/**
 * Bar of the existing area then the added area (blue), each with a black outline, and a
 * dashed line for the rest
 */
const ContributionBar: React.FC<ContributionBarProps> = ({
  className,
  contribution: { existingPercentage, addedPercentage },
  existingColor,
  target,
}) => (
  <div className={cn('relative h-3.5', className)} aria-hidden>
    <span className="absolute top-1/2 h-px w-full border-b border-dashed border-black" />
    <span
      className={cn('absolute bottom-0 left-0 top-0', {
        'bg-existing-area': !existingColor,
        'border border-black': existingPercentage > 0,
      })}
      style={{ width: toWidth(existingPercentage), backgroundColor: existingColor }}
    />
    <span
      className={cn('absolute bottom-0 top-0 bg-blue-700', {
        'border border-black': addedPercentage > 0,
        'border-l-0': existingPercentage > 0,
      })}
      style={{ left: toWidth(existingPercentage), width: toWidth(addedPercentage) }}
    />
    {target != null && (
      <span
        className="absolute -bottom-1 -top-1 w-0.5 -translate-x-1/2 bg-orange-700"
        style={{ left: toWidth(target) }}
      />
    )}
  </div>
);

export default ContributionBar;
