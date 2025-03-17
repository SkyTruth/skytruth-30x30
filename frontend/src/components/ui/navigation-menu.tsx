import * as React from "react";

import * as NavigationMenuPrimitive from '@radix-ui/react-navigation-menu';
import { ChevronDown } from 'lucide-react';

import { cn } from "@/lib/classnames";

const NavigationMenu = NavigationMenuPrimitive.Root;
const NavigationMenuItem = NavigationMenuPrimitive.Item;
const NavigationMenuList = NavigationMenuPrimitive.List;

const NavigationMenuContent = React.forwardRef<
  React.ElementRef<typeof NavigationMenuPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof NavigationMenuPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <NavigationMenuPrimitive.Content
    ref={ref}
    onPointerLeave={(event) => event.preventDefault()}
    className={cn(
      'absolute z-50 max-h-96 min-w-[10rem] overflow-hidden border border-black bg-white text-slate-950 shadow-md',
      'data-[state=open]:animate-in data-[state=open]:slide-in-from-top-2 data-[state=closed]:animate-out',
      'data-[state=closed]:slide-out-to-top-2 data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
      'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 ',
    )}
    {...props}
  >
    {children}
  </NavigationMenuPrimitive.Content>
));

const NavigationMenuTrigger = React.forwardRef<
  React.ElementRef<typeof NavigationMenuPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof NavigationMenuPrimitive.Trigger>
>(({ className, children, ...props }, ref) => (
  <NavigationMenuPrimitive.Trigger
    ref={ref}
    onPointerMove={(event) => event.preventDefault()}
    onPointerLeave={(event) => event.preventDefault()}
    className={cn('dark:bg-slate-950 dark:ring-offset-slate-950 flex gap-x-1 w-full items-center px-3 py-2 ring-offset-white placeholder:text-slate-500 [&>span]:line-clamp-1',   // className={cn(selectTriggerVariants({ variant }), className)}
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[placeholder]:text-gray-300 dark:placeholder:text-slate-400 dark:focus-visible:ring-slate-300',
      className)}
    {...props}
  >
    {children}
    <ChevronDown aria-hidden className='h-4 w-4' />
  </NavigationMenuPrimitive.Trigger>
));

type NavigationMenuListItemProps = {
  className?: string;
  title?: string;
  href: string;
}

const NavigationMenuListItem = React.forwardRef<
  HTMLAnchorElement,
  NavigationMenuListItemProps
>(({ className = '', title, href, ...props }, ref) => (
  <li>
    <NavigationMenuPrimitive.Link
      asChild
      className={cn('relative flex w-full cursor-default select-none items-center py-1.5 px-2 font-mono text-xs outline-none hover:bg-slate-100 hover:text-slate-900 focus:bg-slate-100 focus:text-slate-900 data-[disabled]:pointer-events-none data-[disabled]:opacity-50 dark:hover:bg-slate-800 dark:hover:text-slate-50',
        className)}
    >
      <a
        href={href}
        target="_blank"
        referrerPolicy="no-referrer"
        ref={ref}
        {...props}
      >
        <div className="ListItemHeading">{title}</div>
      </a>
    </NavigationMenuPrimitive.Link>
  </li>
));

export { NavigationMenu, NavigationMenuItem, NavigationMenuTrigger, NavigationMenuContent, NavigationMenuList, NavigationMenuListItem };
