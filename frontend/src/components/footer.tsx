import Link from 'next/link';

import { Copyright } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';

import { EXTERNAL_LINKS } from '@/constants/external-links';
import { FCWithMessages } from '@/types';
import { useGetContactDetail } from '@/types/generated/contact-detail';

const Footer: FCWithMessages = () => {
  const t = useTranslations('components.footer');
  const locale = useLocale();

  const { data: contactDetails } = useGetContactDetail(
    { locale },
    {
      query: {
        select: ({ data }) => data?.attributes,
        placeholderData: { data: {} },
      },
    }
  );

  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-black text-white">
      <div className="px-8 md:mx-auto md:max-w-7xl">
        <div className="flex w-full flex-col">
          <div className="my-6">
            <address className="my-4 flex flex-col gap-0.5 pt-6 text-xs not-italic text-black-300 md:my-8">
              {contactDetails?.name && <span>{contactDetails?.name}</span>}
              {contactDetails?.address && <span>{contactDetails?.address}</span>}
              {contactDetails?.phone && (
                <a href={`tel:${contactDetails?.phone}`}>{contactDetails?.phone}</a>
              )}
              {contactDetails?.email && (
                <a href={`mailto:${contactDetails?.email}`}>{contactDetails?.email}</a>
              )}
              {contactDetails?.registration && <span>{contactDetails?.registration}</span>}
            </address>
          </div>
        </div>
        <div className="flex w-full justify-between gap-8 border-t border-black-400 py-6 text-xs font-extralight">
          <div className="flex py-2">
            <Copyright className="mr-2 h-3.5 w-3.5" aria-hidden="true" /> SkyTruth {currentYear}
          </div>
          <nav className="flex gap-6">
            <Link
              className="py-2"
              href={EXTERNAL_LINKS.privacyPolicy}
              target="_blank"
              rel="noopener noreferrer"
            >
              {t('privacy-policy')}
            </Link>
            <Link
              className="py-2"
              href={EXTERNAL_LINKS.termsOfUse}
              target="_blank"
              rel="noopener noreferrer"
            >
              {t('terms-of-use')}
            </Link>
          </nav>
        </div>
        <span
          className="block h-[12vw] w-full bg-contain bg-bottom bg-no-repeat opacity-10 sm:mt-2 md:mx-auto md:mt-4 md:max-w-7xl xl:-mt-8"
          style={{
            backgroundImage: `url(/images/static-pages/bg-images/footer.svg)`,
          }}
        />
      </div>
    </footer>
  );
};

Footer.messages = ['components.footer'];

export default Footer;
