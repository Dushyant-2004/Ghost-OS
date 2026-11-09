import "./globals.css";

export const metadata = { title: "GhostOS", description: "Autonomous AI computer operator" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
