import { PropsWithChildren, forwardRef } from 'react';

import { cn } from '@/lib/classnames';

export type SubSectionProps = PropsWithChildren<{
  borderTop?: boolean;
}>;

const SubSection: React.FC<SubSectionProps> = ({ children, borderTop }) => (
  <div
    className={cn('border-black-65 w-full px-8 py-3 md:mx-auto md:mb-10 md:max-w-7xl md:px-0', {
      'border-t': borderTop,
    })}
  >
    {children}
  </div>
);

export type SubSectionTitleProps = PropsWithChildren;

const SubSectionTitle: React.FC<SubSectionTitleProps> = ({ children }) => (
  <h3 className="my-6 mb-8 mt-3 text-3xl font-extrabold md:mt-2">{children}</h3>
);

export type SubSectionDescriptionProps = PropsWithChildren;

const SubSectionDescription: React.FC<SubSectionDescriptionProps> = ({ children }) => (
  <div>{children}</div>
);

export type SubSectionContentProps = PropsWithChildren<{
  isNumbered?: boolean;
}>;

const SubSectionContent: React.FC<SubSectionContentProps> = ({ isNumbered = false, children }) => (
  <div
    className={cn('flex max-h-[280px] w-full justify-center md:max-h-full', {
      'md:mt-16': isNumbered,
    })}
  >
    {children}
  </div>
);

SubSection.displayName = 'SubSection';
export default SubSection;
export { SubSectionTitle, SubSectionDescription, SubSectionContent };
