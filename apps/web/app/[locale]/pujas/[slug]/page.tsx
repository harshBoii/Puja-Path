import { DetailPage, detailMetadata } from "@/components/detail/route";

export const revalidate = 300; // plus on-demand revalidation on publish and at booking cutoff
export const generateStaticParams = () => [];
export const generateMetadata = detailMetadata;

export default function Page(props: { params: Promise<{ locale: string; slug: string }> }) {
  return <DetailPage {...props} section="pujas" />;
}
