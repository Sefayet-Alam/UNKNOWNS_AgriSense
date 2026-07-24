import Image from "next/image";
import { Logo } from "@/components/ui/Logo";

interface AuthShellProps {
  eyebrow: string;
  title: string;
  description: string;
  children: React.ReactNode;
  aside: React.ReactNode;
}

export function AuthShell({
  eyebrow,
  title,
  description,
  children,
  aside,
}: AuthShellProps) {
  return (
    <main className="atlas-grid min-h-screen bg-paper-50 px-4 py-4 sm:px-6 sm:py-6">
      <div className="mx-auto grid min-h-[calc(100vh-2rem)] max-w-[1380px] overflow-hidden border border-jute-300/55 bg-surface shadow-lift lg:grid-cols-[0.9fr_1.1fr]">
        <section className="flex flex-col px-5 py-6 sm:px-10 sm:py-9 lg:px-16">
          <Logo className="self-start" />
          <div className="my-auto w-full max-w-lg py-12">
            <p className="atlas-kicker">{eyebrow}</p>
            <h1 className="mt-4 font-display text-4xl leading-[1.02] tracking-[-0.045em] text-ink-900 sm:text-5xl">
              {title}
            </h1>
            <p className="mt-4 max-w-md leading-7 text-ink-500">{description}</p>
            <div className="mt-9">{children}</div>
          </div>
          <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500">
            AgriSense · Delta field station
          </p>
        </section>

        <aside className="relative hidden min-h-full overflow-hidden bg-field-900 lg:block">
          <Image
            src="/images/paddy-landscape-bangladesh.jpg"
            alt=""
            fill
            priority
            sizes="55vw"
            className="object-cover opacity-80"
          />
          <div className="absolute inset-0 bg-gradient-to-br from-field-900/25 via-field-900/15 to-field-900/80" />
          <div className="absolute inset-x-10 bottom-10 border border-paper-50/35 bg-field-900/75 p-8 text-paper-50 backdrop-blur-sm">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-jute-300">
              Field note · Bangladesh
            </p>
            <div className="mt-4 max-w-lg font-display text-3xl leading-tight tracking-[-0.035em]">
              {aside}
            </div>
          </div>
        </aside>
      </div>
    </main>
  );
}

