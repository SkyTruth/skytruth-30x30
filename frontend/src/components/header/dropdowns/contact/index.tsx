import { useTranslations } from 'use-intl';

import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuTrigger,
  NavigationMenuList,
  NavigationMenuListItem
} from '@/components/ui/navigation-menu';
import { FCWithMessages } from '@/types';

const ContactDropdown: FCWithMessages = () => {
  const t = useTranslations('components.header');

  const contactLinks = [
    {
      title: t('log-issue'),
      href: 'https://skytruth.atlassian.net/servicedesk/customer/portal/1/group/1/create/14'
    },
    {
      title: t('request-improvement'),
      href: 'https://skytruth.canny.io/feature-requests'
    }
  ]

  return (
    <NavigationMenu>
      <NavigationMenuList>
        <NavigationMenuItem>
          <NavigationMenuTrigger>Contacts</NavigationMenuTrigger>
          <NavigationMenuContent>
            <ul>
              {contactLinks.map((link, idx) => (
                <NavigationMenuListItem key={idx} title={link.title} href={link.href} />
              ))}
            </ul>
          </NavigationMenuContent>
        </NavigationMenuItem>
      </NavigationMenuList>
    </NavigationMenu>
  );
};

ContactDropdown.messages = ['components.header'];

export default ContactDropdown;
