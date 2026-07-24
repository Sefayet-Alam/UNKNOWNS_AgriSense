import { ArrowLeft, MessageSquareText } from "lucide-react";
import Link from "next/link";
import { LogoMark } from "@/components/ui/Logo";

export default function NotFound() {
  return (
    <main className="atlas-grid grid min-h-screen place-items-center px-6 py-12">
      <section className="atlas-panel relative max-w-2xl overflow-hidden p-8 text-center sm:p-14">
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-field-600 via-river-500 to-clay-500" />
        <LogoMark size={54} className="mx-auto" />
        <p className="atlas-kicker mt-7">Field marker · 404</p>
        <h1 className="mt-4 font-display text-4xl leading-none tracking-[-0.045em] text-ink-900 sm:text-6xl">
          This path leaves the mapped field.
        </h1>
        <p className="mx-auto mt-5 max-w-md leading-7 text-ink-500">
          The page may have moved, but your crop plans and conversations are still where you left them.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/" className="atlas-button-secondary">
            <ArrowLeft size={16} /> Return home
          </Link>
          <Link href="/chat" className="atlas-button">
            <MessageSquareText size={16} /> Open workspace
          </Link>
        </div>
      </section>
    </main>
  );
}
