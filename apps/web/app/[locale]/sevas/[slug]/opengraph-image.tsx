import { ogSize, renderOg } from "@/components/detail/og";

export const size = ogSize;
export const contentType = "image/png";
export const alt = "";

export default async function Image({ params }: { params: Promise<{ locale: string; slug: string }> }) {
  const { locale, slug } = await params;
  return renderOg(locale, slug);
}
