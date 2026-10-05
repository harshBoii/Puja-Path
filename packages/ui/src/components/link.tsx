"use client";
// Locale-aware link slot: the app provides its Link through UiLinkContext; server components can render
// <UiLink> because it is a client component.
import { createContext, useContext, type AnchorHTMLAttributes, type ComponentType } from "react";

type LinkLike = ComponentType<AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }>;
const PlainLink: LinkLike = (props) => <a {...props} />;
export const UiLinkContext = createContext<LinkLike>(PlainLink);

export function UiLink(props: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) {
  const L = useContext(UiLinkContext);
  return <L {...props} />;
}
