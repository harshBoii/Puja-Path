import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: process.env.NEXT_PUBLIC_BRAND ?? "Puja Path",
    short_name: process.env.NEXT_PUBLIC_BRAND ?? "Puja Path",
    start_url: "/",
    display: "standalone",
    background_color: "#FBF9F5",
    theme_color: "#FBF9F5",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
    ],
  };
}
