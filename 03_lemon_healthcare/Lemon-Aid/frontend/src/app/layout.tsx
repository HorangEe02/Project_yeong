import type { Metadata, Viewport } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Lemon AID Web',
  description: 'Mobile web feature-test surface for Lemon AID OCR, YOLO, and recommendation flows.',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  themeColor: '#ffc400',
};

/**
 * Root layout for the Lemon AID web feature-test app.
 *
 * Args:
 *   children: Route content rendered by Next.js.
 *
 * Returns:
 *   The HTML document shell.
 */
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
