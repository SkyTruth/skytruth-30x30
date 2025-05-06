import { PropsWithChildren, ReactNode } from 'react';

import { cn } from '@/lib/classnames';

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
    className={cn('flex max-h-[280px] w-full justify-center md:max-h-full md:w-[50%]', {
      'md:mt-16': isNumbered,
    })}
  >
    {children}
  </div>
);

export type TwoColSubSection = PropsWithChildren<{
  title: string;
  description?: string | ReactNode;
  itemNum?: number;
  itemTotal?: number;
}>;

const TwoColSubSection: React.FC<TwoColSubSection> = ({
  title,
  description,
  itemNum,
  itemTotal,
  children,
}) => {
  const minTwoDigits = (number: number) => {
    return (number < 10 ? '0' : '') + number;
  };

  const isNumbered = itemNum && itemTotal ? true : false;

  return (
    <div className="mt-0 flex flex-col gap-8 md:mt-20 md:flex-row">
      <div className="flex w-full flex-col pt-5 md:w-[50%]">
        {isNumbered && (
          <span className="mb-2 font-mono text-xl md:mb-6">
            <span className="text-black">{minTwoDigits(itemNum)}</span>
            <span className="opacity-60">-{minTwoDigits(itemTotal)}</span>
          </span>
        )}
        <div className="border-t border-black md:pt-3.5">
          <SubSectionTitle>{title}</SubSectionTitle>
          {description && <SubSectionDescription>{description}</SubSectionDescription>}
        </div>
      </div>
      <SubSectionContent isNumbered={isNumbered}>{children}</SubSectionContent>
    </div>
  );
};

export default TwoColSubSection;
export { SubSectionTitle, SubSectionDescription, SubSectionContent };
