import * as React from 'react';

import * as CollapsiblePrimitive from '@radix-ui/react-collapsible';

import { cn } from '@/lib/classnames';

const Collapsible = CollapsiblePrimitive.Root;

const CollapsibleTrigger = CollapsiblePrimitive.CollapsibleTrigger;

type CollapsibleContentProps = React.ComponentPropsWithoutRef<
  typeof CollapsiblePrimitive.CollapsibleContent
> & {
  onExpandEnd?: () => void;
  onCollapseEnd?: () => void;
};

const CollapsibleContent = React.forwardRef<
  React.ElementRef<typeof CollapsiblePrimitive.CollapsibleContent>,
  CollapsibleContentProps
>(({ className, children, onExpandEnd, onCollapseEnd, ...props }, ref) => {
  const handleAnimationEnd = (e: React.AnimationEvent<HTMLDivElement>) => {
    if (e.target !== e.currentTarget) return;
    const state = (e.currentTarget as HTMLElement).getAttribute('data-state');
    if (state === 'open' && onExpandEnd) {
      onExpandEnd();
    } else if (state === 'closed' && onCollapseEnd) {
      onCollapseEnd();
    }
  };

  return (
    <CollapsiblePrimitive.CollapsibleContent
      ref={ref}
      className={cn('overflow-y-hidden', className)}
      onAnimationEnd={handleAnimationEnd}
      {...props}
    >
      {children}
    </CollapsiblePrimitive.CollapsibleContent>
  );
});
CollapsibleContent.displayName = CollapsiblePrimitive.Content.displayName;

export { Collapsible, CollapsibleTrigger, CollapsibleContent };
