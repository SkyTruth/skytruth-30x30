import { MutableRefObject, PropsWithChildren, ReactNode } from 'react';

import Footer from '@/components/footer';
import Head from '@/components/head';
import Header, { HeaderProps } from '@/components/header';
import Icon from '@/components/ui/icon';
import { cn } from '@/lib/classnames';
import ArrowRight from '@/styles/icons/arrow-right.svg';
import { FCWithMessages } from '@/types';

type SidebarProps = {
  sections: {
    [key: string]: {
      id: string;
      name: string;
      ref: MutableRefObject<HTMLDivElement>;
    };
  };
  activeSection?: string;
  arrowColor?: 'black' | 'orange' | 'purple';
};

const Sidebar: React.FC<SidebarProps> = ({ sections, activeSection, arrowColor = 'black' }) => {
  if (!sections) return null;

  const handleClick = (key) => {
    const section = sections[key];
    if (!section) return;
    section.ref.current.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="-mb-6 min-w-[200px] px-8 md:mb-0 md:px-0">
      <nav className="sticky bottom-3 top-10 my-10 flex flex-col gap-3 font-mono text-sm">
        {Object.entries(sections).map(([key, { id, name }]) => {
          return (
            <button
              key={key}
              className="flex w-full items-center gap-3"
              type="button"
              onClick={() => handleClick(key)}
            >
              {id === activeSection && (
                <Icon
                  icon={ArrowRight}
                  className={cn('h-6', {
                    'text-black': arrowColor === 'black',
                    'text-orange': arrowColor === 'orange',
                    'text-purple-400': arrowColor === 'purple',
                  })}
                />
              )}
              <span className={cn('pt-1 hover:font-bold', { 'font-bold': id === activeSection })}>
                {name}
              </span>
            </button>
          );
        })}
      </nav>
    </div>
  );
};

type ContentProps = PropsWithChildren;

const Content: React.FC<ContentProps> = ({ children }) => {
  return <div className="flex-1">{children}</div>;
};

export interface StaticPageLayoutProps {
  title?: string;
  description?: string;
  hero?: ReactNode;
}

const StaticPageLayout: FCWithMessages<
  PropsWithChildren<StaticPageLayoutProps & Pick<HeaderProps, 'theme' | 'hideLogo'>>
> = ({ title, description, hero, children, theme, hideLogo }) => (
  <>
    <Head title={title} description={description} />
    <div className="flex h-screen w-full flex-col">
      <div className="flex-shrink-0">
        <Header theme={theme} hideLogo={hideLogo} />
      </div>
      <div className="border-x border-black">{hero && <>{hero}</>}</div>
      <div className={cn('border-black', { border: !!hero, 'border-x': !hero })}>
        <div className="flex w-full flex-col gap-6 py-6 md:mx-auto md:max-w-7xl md:flex-row md:py-24 md:pl-8">
          {children}
        </div>
      </div>
      <Footer />
    </div>
  </>
);

StaticPageLayout.messages = [...Header.messages, ...Footer.messages];

export default StaticPageLayout;
export { Content, Sidebar };
