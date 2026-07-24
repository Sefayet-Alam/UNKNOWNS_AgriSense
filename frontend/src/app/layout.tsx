import type { Metadata } from "next";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "AgriSense · Plan the season before the soil pays for it",
    template: "%s · AgriSense",
  },
  description:
    "A Bangladesh-focused crop planning workspace for weather-aware, costed agricultural decisions.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
